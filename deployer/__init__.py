import os

from flask import Flask
from flask_bootstrap import Bootstrap
import flask_login
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_migrate import Migrate
from raven.contrib.flask import Sentry

from config.base import BaseConfig

import os


app = Flask('deployer')
app.config.from_object(BaseConfig)

login_manager = flask_login.LoginManager()
login_manager.init_app(app)

Bootstrap(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
db.init_app(app)

if not app.config.get('DEBUG'):
    sentry = Sentry(app, dsn=os.environ.get('SENTRY_DSN'))

from deployer.models import *
from deployer.helpers import *

mail = Mail(app)

import deployer.views
