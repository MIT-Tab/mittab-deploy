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
    created_at = db.Column(db.DateTime, nullable=False)

    def __init__(self, name, droplet_name):
        self.name = name.lower()
        self.droplet_name = droplet_name
        self.created_at = datetime.datetime.now()

    def url(self):
        return 'http://{0}.nu-tab.com'.format(self.name)

    def droplet(self):
        return get_droplet(self.droplet_name)

    def create_domain(self):
        return create_domain_record(self.name, self.droplet().ip_address)


class Tournament(Droplet):

    def __init__(self, name):
        name = name.lower()
        droplet_name = 'mittab-{0}-{1}'.format(name, int(time()))
        super(Tournament, self).__init__(name, droplet_name)
