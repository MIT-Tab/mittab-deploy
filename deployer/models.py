from time import time
import datetime

from deployer import db

class Droplet(db.Model):

    __tablename__ = 'droplets'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    dropet_name = db.Column(db.String, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False)

    def __init__(self, name):
        self.name = name.lower()
        self.droplet_name = 'mittab-{0}-{1}'.format(self.name, int(time()))
        self.created_at = datetime.datetime.now()
