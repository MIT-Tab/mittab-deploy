import os
import time
from datetime import datetime

from celery import Celery

from deployer import app, db
from deployer.clients import email, paypal, digital_ocean
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
                    broker=app.config['CELERY_BROKER_URL'])

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


@celery.task()
def deploy_tournament(tournament_id, password, email_addr, with_invoice=True):
    tournament = Tournament.query.get(tournament_id)

    deploy_droplet(tournament, password, app.config['DEFAULT_SIZE_SLUG'])
    email.send_confirmation(email_addr, tournament, password)
    email.send_notification(tournament.name)

    with_invoice and paypal.send_invoice(email_addr)


@celery.task()
def deploy_pr(pr_number, clone_url, branch):
    tournament = Tournament('{}-pr-{}'.format(branch, pr_number), clone_url, branch)
    db.session.add(tournament)
    db.session.commit()

    deploy_deploy(tournament, 'password', app.config['TEST_SIZE_SLUG'])
    command = './bin/setup_test {}'.format(tournament.ip_address)
    os.system(command)


@celery.task()
def update_pr(tournament_id):
    tournament = Tournament.query.get(tournament_id)


@celery.task()
def deploy_test(name, clone_url, branch):
    tournament = Tournament('{}-test'.format(name), clone_url, branch)
    db.session.add(tournament)
    db.session.commit()

    deploy_droplet(tournament, 'password', app.config['TEST_SIZE_SLUG'])
    command = './bin/setup_test {}'.format(tournament.ip_address)
    os.system(command)

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
        command = './bin/setup_droplet {} {} {} {} {}'.format(
                droplet.ip_address,
                droplet.clone_url,
                droplet.branch,
                password,
                droplet.droplet_name
        )
        return_code = os.system(command)
        if return_code != 0:
            raise SetupFailedError()

        droplet.set_status('Creating domain name')
        droplet.create_domain()
        droplet.set_status('Deployed')
    except Exception as e:
        droplet.set_status('An error occurred')
        droplet.deactivate()
        raise e


@celery.task()
def update_repo():
    os.system('./bin/update')


@celery.task()
def backup_tournament(tournament_id):
    tournament = Tournament.query.get(tournament_id)
    backup_file = os.path.join(
            '%s_%s_%s.db' % (tournament.name, int(time.time()), datetime.now().year)
    )
    command = './bin/clone_db {} {}'.format(
            tournament.droplet.ip_address,
            backup_file
    )
    return_code = os.system(command)

    if return_code != 1:
        raise BackupFailedError()

    try:
        digital_ocean.upload_file(backup_file, os.path.join(tournament.name, backup_file))
    except Exception as e:
        raise BackupFailedError(e)

    os.remove(backup_file)
