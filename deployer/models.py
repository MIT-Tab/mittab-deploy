from time import time
import datetime

from deployer import db
from deployer.clients.digital_ocean import *

class Droplet(db.Model):

    __tablename__ = 'droplets'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    droplet_name = db.Column(db.String, nullable=True)
    status = db.Column(db.String, nullable=True)
    deployed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False)

    def __init__(self, name, droplet_name):
        self.name = name.lower()
        self.droplet_name = droplet_name
        self.created_at = datetime.datetime.now()

    def url(self):
        return 'http://{0}.nu-tab.com'.format(self.name)

    def droplet(self):
        return get_droplet(self.droplet_name)

    def create_droplet(self):
        return create_droplet(self.droplet_name)

    def create_domain(self):
        return create_domain_record(self.name, self.droplet().ip_address)

    def is_ready(self):
        self.droplet().load()
        return self.droplet().status == 'active'

    def domain_record(self):
        return get_domain_record(self.name)

    def set_status(self, status):
        self.status = status
        db.session.add(self)
        return db.session.commit()

    def set_deployed(self):
        self.status = 'deployed'
        self.deployed = True
        db.session.add(self)
        return db.session.commit()

    def destroy(self):
        self.domain_record().destroy()
        self.droplet().destroy()

        db.session.delete(self)
        return db.session.commit()


class Tournament(Droplet):

    def __init__(self, name):
        name = name.lower()
        droplet_name = 'mittab-{0}-{1}'.format(name, int(time()))
        super(Tournament, self).__init__(name, droplet_name)
