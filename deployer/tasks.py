import shutil
import os
from time import time

from celery import Celery

from deployer import app, db
from deployer.clients import email, github
from deployer.models import Tournament, GithubDeploy

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

    tournament.set_status('Building (this will take around 5 minutes)')
    _deploy_droplet(tournament, password)

    tournament.set_status('Sending confirmation email')
    email.send_confirmation_email(email, tournament.name, password)
    email.send_tournament_notification(tournament.name)
    tournament.set_deployed()

@celery.task()
def deploy_ref(repo_path, ref):
    deployment = GithubDeploy(repo_path, ref)
    droplets_with_ref = GithubDeploy.query.filter_by(repo_path=repo_path, name=deployment.name)

    if droplets_with_ref.count() > 0:
        deployment = droplets_with_ref.first()
        deployment.reset()

    if not deployment.deploy_id:
        deployment.create_github_deploy()

    _deploy_droplet(deployment, 'password')
    deployment.set_deployed()

@celery.task()
def update_repo():
    os.system('./bin/update')

def _deploy_droplet(droplet, password, ref='master'):
    # uses a script rather than the DO api because we need Docker Machine to
    # spin up the server properly
    command = './bin/create_digitalocean_droplet {0} {1} {2}'.format(
            droplet.droplet_name(), password, ref)
    os.system(command)
    shutil.rmtree('mit-tab')
    droplet.create_domain()
