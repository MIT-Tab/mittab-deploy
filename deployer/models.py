from time import time
import datetime

from deployer import db
from deployer.clients import digital_ocean, github

class Droplet(db.Model):

    __tablename__ = 'droplets'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    droplet_name = db.Column(db.String, nullable=True)
    status = db.Column(db.String, nullable=True)
    deployed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False)

    # Github-specific fields
    deploy_id = db.Column(db.Integer, nullable=True)
    repo_path = db.Column(db.String, nullable=True)

    def __init__(self, name, droplet_name):
        self.name = name.lower()
        self.droplet_name = droplet_name
        self.created_at = datetime.datetime.now()

    def url(self):
        return 'http://{0}.nu-tab.com'.format(self.name)

    def droplet(self):
        return digital_ocean.get_droplet(self.droplet_name)

    def create_domain(self):
        return digital_ocean.create_domain_record(self.name, self.droplet().ip_address)

    def domain_record(self):
        return digital_ocean.get_domain_record(self.name)

    def set_status(self, status):
        self.status = status
        db.session.add(self)
        return db.session.commit()

    def set_deployed(self):
        self.status = 'success'
        self.deployed = True
        db.session.add(self)
        return db.session.commit()

    def destroy(self):
        self.domain_record().destroy()
        self.droplet().destroy()

        db.session.delete(self)
        return db.session.commit()

class GithubDeploy(Droplet):

    def __init__(self, repo_path, ref):
        name = 'staging-{}'.format(ref)
        self.repo_path = repo_path
        super(GithubDeploy, self).__init__(name, name)

    def create_github_deploy(self):
        deployment = github.create_deployment(self.repo_path, self.name)
        self.deploy_id = deployment['id']
        return self.set_status('pending')

    def reset(self):
        self.domain_record().destroy()
        self.droplet.destroy()
        return self.set_status('pending')

    def set_status(self, status):
        github.create_deployment_status(self.repo_path, self.deploy_id, status, self.url())
        return super(GithubDeploy, self).set_status(status)


class Tournament(Droplet):

    def __init__(self, name):
        name = name.lower()
        droplet_name = 'mittab-{0}-{1}'.format(name, int(time()))
        super(Tournament, self).__init__(name, droplet_name)
