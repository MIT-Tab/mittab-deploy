import time
import subprocess
from datetime import datetime

from celery import Celery
from celery.schedules import crontab
from tenacity import retry, stop_after_attempt, wait_fixed

from deployer import app, db
from deployer.clients import email, digital_ocean
from deployer.models import Tournament


class ServerNotReadyError(Exception):
    pass


class SetupFailedError(Exception):
    pass


class BackupFailedError(Exception):
    pass


def make_celery(app):
    celery = Celery(app.import_name,
                    backend=app.config['CELERY_RESULT_BACKEND'],
                    broker=app.config['CELERY_BROKER_URL'],
                    broker_pool_limit=1,
                    broker_heartbeat=None,
                    broker_connection_timeout=30,
                    result_backend=None,
                    event_queue_expires=60,
                    worker_prefetch_multiplier=1,
                    worker_concurrency=50)

    celery.conf.update(app.config)
    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    celery.Task = ContextTask
    return celery


celery = make_celery(app)

@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        contab(hour=10, minute=30),
        delete_droplets.s()
    )

@celery.task()
def deploy_tournament(tournament_id, password):
    tournament = Tournament.query.get(tournament_id)

    deploy_droplet(tournament, password, app.config['DEFAULT_SIZE_SLUG'])
    email.send_confirmation(tournament, password)
    email.send_notification(tournament.name)


@celery.task()
def deploy_test(name, clone_url, branch, deletion_date, email):
    name = '{}-test'.format(name)
    if Tournament.query.filter_by(name=name, active=True).count() > 0:
        raise SetupFailedError('Duplicate tournament {}'.format(name))

    tournament = Tournament(name, clone_url, branch, deletion_date, email)
    db.session.add(tournament)
    db.session.commit()

    deploy_droplet(tournament, 'password', app.config['TEST_SIZE_SLUG'])
    subprocess.check_call(['sh', './bin/setup_test', str(tournament.ip_address)])

@retry(stop=stop_after_attempt(5), wait=wait_fixed(30))
def deploy_droplet(droplet, password, size):
    try:
        droplet.set_status('Creating server')
        droplet.create_droplet(size)

        seconds_elapsed = 0
        while seconds_elapsed < 120:
            if droplet.is_ready():
                break
            seconds_elapsed += 5
            time.sleep(5)

        time.sleep(60)

        if not droplet.is_ready():
            raise ServerNotReadyError()

        droplet.set_status('Installing mit-tab on server')
        subprocess.check_call(['sh',
                './bin/setup_droplet',
                droplet.ip_address,
                droplet.clone_url,
                droplet.branch,
                password,
                droplet.droplet_name])

        droplet.set_status('Creating domain name')
        droplet.create_domain()
        droplet.set_status('Deployed')
    except Exception as e:
        import traceback; traceback.print_exc()
        droplet.set_status('An error occurred. Retrying up to 5 times')
        droplet.deactivate()
        raise e

def delete_droplets():
    tournaments = Tournament.query.filter_by(active=True)
    current_date = datetime.now().date()
    for tournment in tournaments:
        if tournament.deletion_date > current_date:
            print("Deleting {}...".format(tournament))
            try:
                if not tournament.is_test:
                    tournament.backup()
                tournament.deactivate()
                tournament.set_status('Deleted')
            except Exception as e:
                print("Error deleting {}".format(tournament))
                tournament.set_status('Error while deleting')
                import traceback; traceback.print_exc()
        elif (current_date - tournament.deletion_date).days <= 3 and \
                not tournament.warning_email_sent:
            email.send_warning(tournament)
            tournment.warning_email_sent = True
            db.session.add(tournament)
            db.session.commit()
