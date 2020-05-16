import os

from flask import Flask
from flask_bootstrap import Bootstrap
import flask_login
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_migrate import Migrate
from raven.contrib.flask import Sentry

from config.base import BaseConfig

app = Flask('deployer')
app.config.from_object(BaseConfig)

login_manager = flask_login.LoginManager()
login_manager.init_app(app)

Bootstrap(app)
db = SQLAlchemy(app)

# Lightweight user object for admin auth since we don't need persistent users
class User(flask_login.UserMixin):
    pass

@login_manager.user_loader
def user_loader(user_id):
    if user_id not in app.config.get('GOOGLE_AUTH_ALLOWED_EMAILS'):
        return

    user = User()
    user.id = user_id
    user.is_authenticated = True

    return user

if not app.config.get('DEBUG'):
    sentry = Sentry(app, dsn=os.environ.get('SENTRY_DSN'))

from deployer.models import *

migrate = Migrate(app, db)
mail = Mail(app)

import deployer.views
