import shutil
import os
from time import time

from celery import Celery

from deployer import app, db
from deployer.clients.digital_ocean import get_droplet, create_domain_record
from deployer.clients.email import send_confirmation_email, send_tournament_notification
from deployer.models import Tournament

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
    return
    tournament = Tournament.query.get(tournament_id)

    # uses a script rather than the DO api because we need Docker Machine to
    # spin up the server properly
    tournament.set_status('building (this will take around 5 minutes)')
    command = './bin/create_digitalocean_droplet {0} {1}'.format(tournament.droplet_name, password)
    os.system(command)

    tournament.set_status('creating domain name')
    shutil.rmtree('mit-tab')
    tournament.create_domain()

    tournament.set_status('sending confirmation email')
    send_confirmation_email(email, tournament.name, password)
    send_tournament_notification(tournament.name)
    tournament.set_deployed()

@celery.task()
def update_repo():
    os.system('./bin/update')

