from datetime import datetime, timedelta
import os

from deployer.extensions import db
from deployer.clients.digital_ocean import *


class App(db.Model):
    __tablename__ = 'apps'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    status = db.Column(db.String, nullable=True)
    temporary_url = db.Column(db.String(512), nullable=True)
    active = db.Column(db.Boolean, default=False)
    confirmed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False)
    repo_slug = db.Column(db.String, nullable=True)
    branch = db.Column(db.String, nullable=True)
    deletion_date = db.Column(db.Date, nullable=False)
    email = db.Column(db.String, nullable=False)
    warning_email_sent = db.Column(db.Boolean, default=False)
    # NULL means legacy/dedicated. Migration never reassigns existing resources.
    database_mode = db.Column(db.String(16), nullable=True)
    shared_cluster_id = db.Column(db.String(36), nullable=True)
    shared_tenant = db.Column(db.String(26), nullable=True, unique=True)
    cloud_app_id = db.Column(db.String(36), nullable=True)
    tournament_start_date = db.Column(db.Date, nullable=True)
    pricing_version = db.Column(db.String(32), nullable=True)
    amount_paid_cents = db.Column(db.Integer, nullable=True)
    checkout_key = db.Column(db.String(32), nullable=True, unique=True)
    stripe_charge_id = db.Column(db.String(64), nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('apps.id'), nullable=True)
    provisioning_until = db.Column(db.DateTime, nullable=True)

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
        if self.database_mode == 'shared':
            from deployer.clients import shared_mysql
            # Use the same lease as provisioning, so daily cleanup cannot drop
            # the database while a worker is still migrating/starting the app.
            now = datetime.utcnow()
            acquired = App.query.filter(
                App.id == self.id,
                db.or_(App.provisioning_until.is_(None), App.provisioning_until < now),
            ).update({'provisioning_until': now + timedelta(minutes=20)}, synchronize_session=False)
            db.session.commit()
            if not acquired:
                raise RuntimeError('Tournament provisioning/cleanup is already in progress')
            try:
                shared_mysql.delete_tournament(self)
                self.active = False
                db.session.commit()
            finally:
                self.provisioning_until = None
                db.session.add(self)
                db.session.commit()
            return
        else:
            delete_app(self.name)
        self.active = False

        db.session.add(self)
        return db.session.commit()
