import os

from celery import Celery

from deployer.app import app
from deployer.clients.digital_ocean import get_droplet, create_domain_record

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
def create_tournament(name, password):
    name = name.lower()
    namespaced_name = 'mittab-' + name

    # uses a script rather than the DO api because we need Docker Machine to
    # spin up the server properly
    command = './bin/create_digitalocean_droplet {0} {1}'.format(namespaced_name, password)
    os.system(command)

    droplet = get_droplet(namespaced_name)
    create_domain_record(name, droplet.ip_address)
