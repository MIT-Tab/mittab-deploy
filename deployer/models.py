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

class Droplet(db.Model):
    """
    DEPRECATED! Replaced with the App-based deployment
    """

    __tablename__ = 'droplets'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    droplet_name = db.Column(db.String, nullable=True)
    status = db.Column(db.String, nullable=True)
    active = db.Column(db.Boolean, default=True)
    confirmed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False)
    clone_url = db.Column(db.String, nullable=True)
    branch = db.Column(db.String, nullable=True)
    deletion_date = db.Column(db.Date, nullable=False)
    email = db.Column(db.String, nullable=False)
    warning_email_sent = db.Column(db.Boolean, default=False)

    def __init__(self, name, droplet_name, deletion_date, email):
        self.name = name.lower()
        self.droplet_name = droplet_name
        self.created_at = datetime.now()
        self.deletion_date = deletion_date
        self.email = email

    @property
    def url(self):
        return 'http://{0}.nu-tab.com'.format(self.name)

    @property
    def is_test(self):
        return self.name.endswith('-test')

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

    def deactivate(self):
        self.domain_record and self.domain_record.destroy()
        self.droplet and self.droplet.destroy()
        self.active = False

        db.session.add(self)
        return db.session.commit()

    def backup(self):
        if not self.droplet: raise NoDropletError('No droplet found!')

        src_csv = "/usr/src/mit-tab/exports/"
        src_db = "/usr/src/mit-tab/mittab/final-backup.json"
        base_path = os.path.join(flask_app.root_path, 'backups', self.ip_address)
        dst_db = os.path.join(base_path, 'final-backup.json')
        dst_csv = os.path.join(base_path)
        os.makedirs(dst_csv, exist_ok=True)

        try:
            dumpdata_cmd = "docker-compose run --rm web python manage.py dumpdata " \
                    "--exclude tab.Scratch --exclude auth.permission " \
                    "--exclude contenttypes --exclude admin.logentry " \
                    "--natural-foreign > %s" % (src_db)
            export_cmd = "docker-compose run --rm web python manage.py " \
                    "export_stats --root exports"

            remote_server.exec_commands(
                    self.ip_address,
                    "cd /usr/src/mit-tab; mkdir -p %s" % src_csv,
                    "cd /usr/src/mit-tab; %s" % dumpdata_cmd,
                    "cd /usr/src/mit-tab; %s" % export_cmd
            )
            remote_server.get_file(self.ip_address, src_csv, dst_csv)
            remote_server.get_file(self.ip_address, src_db, dst_db)

            folder = "%s-%s" % (self.name, datetime.now().strftime("%Y-%m-%s"))
            csv_folder = os.path.join(base_path, 'exports')
            upload_file(dst_db, os.path.join(folder, "final-backup.json"))
            for basename in os.listdir(csv_folder):
                upload_file(os.path.join(csv_folder, basename),
                        os.path.join(folder, basename))
        finally:
            shutil.rmtree(base_path)

    def __repr__(self):
        return "<Droplet name={} ip={} status={}>".format(self.name,
                                                          self.ip_address,
                                                          self.status)


class Tournament(Droplet):

    def __init__(self, name, clone_url, branch, deletion_date, email):
        name = name.lower()
        droplet_name = '{0}-{1}'.format(name, int(time()))
        self.clone_url = clone_url
        self.branch = branch
        super(Tournament, self).__init__(name, droplet_name, deletion_date, email)
