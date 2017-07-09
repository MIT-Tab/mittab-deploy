import datetime

from deployer import db


class Droplet(db.Model):

    __tablename__ = 'droplets'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)

    def __init__(self, name):
        self.name = name
        self.created_at = datetime.datetime.now()
