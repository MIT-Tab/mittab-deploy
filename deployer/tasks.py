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
    _run_deploy_command(tournament, password)

    tournament.set_status('Sending confirmation email')
    email.send_confirmation_email(email, tournament.name, password)
    email.send_tournament_notification(tournament.name)
    tournament.set_deployed()

@celery.task()
def deploy_ref(repo_path, ref):
    droplets_with_ref = Droplet.query.filter_by(repo_path=repo_path, name=ref).all()

    if droplets_with_ref.count() > 0:
        deployment = droplets_with_ref.first()
        deployment.reset()
    else:
        deployment = GithubDeploy(ref)
        deployment.create_github_deploy()

    _run_deploy_command(deployment, 'password')
    deployment.set_deployed()

@celery.task()
def update_repo():
    os.system('./bin/update')

def _deploy_droplet(droplet, password):
    # uses a script rather than the DO api because we need Docker Machine to
    # spin up the server properly
    command = './bin/create_digitalocean_droplet {0} {1}'.format(droplet.droplet_name, password)
    os.system(command)
    shutil.rmtree('mit-tab')
    deploy.create_domain()
