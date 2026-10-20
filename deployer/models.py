from datetime import datetime
import os

from deployer.extensions import db
from deployer.clients.digital_ocean import *


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
        self.status = 'Initializing'

    @property
    def url(self):
        domain = os.environ.get("NU_TAB_DOMAIN", "nu-tab.com")
        return f"https://{self.name}.{domain}"

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
