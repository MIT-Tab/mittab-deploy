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
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, nullable=False)
    deletion_date = db.Column(db.DateTime, nullable=True)
    clone_url = db.Column(db.String, nullable=True)
    branch = db.Column(db.String, nullable=True)

    def __init__(self, name, droplet_name):
        self.name = name.lower()
        self.droplet_name = droplet_name
        self.created_at = datetime.datetime.now()
        self.deletion_date = self._calculate_deletion_date()

    @property
    def url(self):
        return 'http://{0}.nu-tab.com'.format(self.name)

    @property
    def droplet(self):
        try:
            return get_droplet(self.droplet_name)
        except NoDropletError:
            return None

    def create_droplet(self, size):
        return create_droplet(self.droplet_name, size)

    def create_domain(self):
        return create_domain_record(self.name, self.ip_address)

    @property
    def ip_address(self):
        return self.droplet and self.droplet.ip_address

    def is_ready(self):
        if not self.droplet:
            return False

        self.droplet.load()
        return self.droplet.status == 'active'

    @property
    def domain_record(self):
        try:
            return get_domain_record(self.name)
        except NoRecordError:
            return None

    def set_status(self, status):
        self.status = status
        db.session.add(self)
        return db.session.commit()

    def should_be_deleted(self):
        return self.active and datetime.datetime.now() > self.deletion_date

    def deactivate(self):
        self.domain_record and self.domain_record.destroy()
        self.droplet and self.droplet.destroy()
        self.active = False

        db.session.add(self)
        return db.session.commit()

    def _calculate_deletion_date(self):
        if self.name.endswith("-test"):
            return self.created_at + datetime.timedelta(days=7)
        else:
            return self.created_at + datetime.timedelta(days=31)

    def __repr__(self):
        return "<Droplet name={} ip={} status={}>".format(self.name,
                                                          self.ip_address,
                                                          self.status)


class Tournament(Droplet):

    def __init__(self, name, clone_url, branch):
        name = name.lower()
        droplet_name = '{0}-{1}'.format(name, int(time()))
        self.clone_url = clone_url
        self.branch = branch
        super(Tournament, self).__init__(name, droplet_name)
