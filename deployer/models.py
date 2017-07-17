import time
import datetime

from deployer import db
from deployer.clients import digital_ocean, github

class Droplet(db.Model):

    __tablename__ = 'droplets'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    status = db.Column(db.String, nullable=True)
    deployed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False)

    # Github-specific fields
    deploy_id = db.Column(db.Integer, nullable=True)
    repo_path = db.Column(db.String, nullable=True)

    def __init__(self, name):
        self.name = name.lower()
        self.created_at = datetime.datetime.now()

    def url(self):
        return 'http://{0}.nu-tab.com'.format(self.name)

    def droplet(self):
        return digital_ocean.get_droplet(self.droplet_name())

    def create_domain(self):
        return digital_ocean.create_domain_record(self.domain_name(), self.droplet().ip_address)

    def domain_record(self):
        return digital_ocean.get_domain_record(self.domain_name())

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

    def droplet_name(self):
        timestamp = time.mktime(self.created_at.timetuple())
        return 'mittab-{0}-{1}'.format(self.name, int(timestamp))

class GithubDeploy(Droplet):

    def __init__(self, repo_path, ref):
        self.repo_path = repo_path
        super(GithubDeploy, self).__init__(ref)

    def create_github_deploy(self):
        deployment = github.create_deployment(self.repo_path, self.name)
        print(deployment)
        self.deploy_id = int(deployment['id'])
        return self.set_status('pending')

    def domain_name(self):
        return 'staging-{}'.format(self.name)

    def reset(self):
        try:
            self.domain_record().destroy()
            self.droplet().destroy()
        except:
            pass

        return self.set_status('pending')

    def set_status(self, status):
        if self.deploy_id:
            github.create_deployment_status(self.repo_path, self.deploy_id, status, self.url())

        return super(GithubDeploy, self).set_status(status)


class Tournament(Droplet):

    def domain_name(self):
        return self.name
