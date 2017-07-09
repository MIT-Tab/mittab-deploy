import shutil
import os
from time import time

from celery import Celery

from deployer import app
from deployer.clients.digital_ocean import get_droplet, create_domain_record
from deployer.clients.email import send_confirmation_email, send_tournament_notification

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
def create_tournament(name, password, email):
    name = name.lower()
    namespaced_name = 'mittab-{0}-{1}'.format(name, int(time()))

    # uses a script rather than the DO api because we need Docker Machine to
    # spin up the server properly
    command = './bin/create_digitalocean_droplet {0} {1}'.format(namespaced_name, password)
    os.system(command)

    shutil.rmtree('mit-tab')

    droplet = get_droplet(namespaced_name)
    create_domain_record(name, droplet.ip_address)

    send_confirmation_email(email, name, password)
    send_tournament_notification(name)

@celery.task()
def update_repo():
    os.system('./bin/update')

