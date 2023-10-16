import os
import shutil
from time import time
from datetime import datetime, date

from deployer import app as flask_app
from deployer import db
from deployer.clients.digital_ocean import *
from deployer.clients import remote_server


class App(db.Model):
    __tablename__ = 'apps'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    status = db.Column(db.String, nullable=True)
    active = db.Column(db.Boolean, default=False)
    confirmed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False)
    repo_slug = db.Column(db.String, nullable=True)
    branch = db.Column(db.String, nullable=True)
    deletion_date = db.Column(db.Date, nullable=False)
    email = db.Column(db.String, nullable=False)
    warning_email_sent = db.Column(db.Boolean, default=False)

    def __init__(self, name, repo_slug, branch, deletion_date, email):
        self.name = name.lower()
        self.created_at = datetime.now()
        self.repo_slug = repo_slug
        self.branch = branch
        self.deletion_date = deletion_date
        self.email = email

    @property
    def url(self):
        return 'http://{0}.nu-tab.com'.format(self.name)

    @property
    def is_test(self):
        return self.name.endswith('-test')

    def is_ready(self):
        try:
            app = get_app(self.name)
        except ValueError:
            return False

        return app.get('active_deployment', {}).get('phase') == 'ACTIVE'

    def set_status(self, status):
        self.status = status
        db.session.add(self)
        return db.session.commit()

    def deactivate(self):
        delete_app(self.name)
        self.active = False

        db.session.add(self)
        return db.session.commit()
