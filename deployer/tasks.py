import shutil
import os
import time

from celery import Celery

from deployer import app, db
from deployer.clients.digital_ocean import get_droplet, create_domain_record
from deployer.clients.email import send_confirmation_email, send_tournament_notification
from deployer.models import Tournament

class ServerNotReadyError(Exception):
    pass

class SetupFailedError(Exception):
    pass

def make_celery(app):
    celery = Celery(app.import_name, backend=app.config['CELERY_RESULT_BACKEND'],
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
def deploy_tournament(tournament_id, password, email):
    tournament = Tournament.query.get(tournament_id)

    # uses a script rather than the DO api because we need Docker Machine to
    # spin up the server properly
    try:
        tournament.set_status('Creating server')
        tournament.create_droplet()

        seconds_elapsed = 0
        while seconds_elapsed < 120:
            if tournament.is_ready():
                break
            else:
                time.sleep(5)

        time.sleep(60)
        if not tournament.is_ready():
            raise ServerNotReadyError()

        tournament.set_status('Installing mit-tab on server')
        command = './bin/setup_droplet {} {} {} {}'.format(
                tournament.droplet().ip_address,
                'https://github.com/jolynch/mit-tab.git',
                'master',
                password
        )
        return_code = os.system(command)
        if return_code != 0:
            raise SetupFailedError()

        tournament.set_status('Creating domain name')
        tournament.create_domain()

        tournament.set_status('Sending confirmation email')
        send_confirmation_email(email, tournament.name, password)
        send_tournament_notification(tournament.name)
        tournament.set_deployed()
    except Exception as e:
        tournament.set_status('An error occurred')
        raise e

@celery.task()
def update_repo():
    os.system('./bin/update')

