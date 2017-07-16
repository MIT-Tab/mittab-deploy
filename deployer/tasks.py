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

    # uses a script rather than the DO api because we need Docker Machine to
    # spin up the server properly
    tournament.set_status('Building (this will take around 5 minutes)')
    _run_deploy_command(tournament, password)

    tournament.set_status('Creating domain name')
    shutil.rmtree('mit-tab')
    tournament.create_domain()

    tournament.set_status('Sending confirmation email')
    email.send_confirmation_email(email, tournament.name, password)
    email.send_tournament_notification(tournament.name)
    tournament.set_deployed()

@celery.task()
def deploy_ref(repo_path, ref):
    deploy = GithubDeploy(ref)

    dup_droplets = Droplet.query.filter_by(name=deploy.name).all()
    for dup in dup_droplets():
        dup.destroy()

    db.session.add(deploy)
    db.session.commit()

    gh_deploy_data = create_deployment()
    _run_deploy_command(deploy, 'password')
    deploy.create_domain()
    deploy.set_deployed()
    create_deployment_status(repo_path, gh_deploy_data['id'], 'success', deploy.url())

@celery.task()
def update_repo():
    os.system('./bin/update')

def _run_deploy_command(droplet, password):
    command = './bin/create_digitalocean_droplet {0} {1}'.format(droplet.droplet_name, password)
    os.system(command)
