import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_hookserver import Hooks
from flask_mail import Mail
from flask_migrate import Migrate
from raven.contrib.flask import Sentry

from config.base import BaseConfig

app = Flask('deployer')
app.config.from_object(BaseConfig)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///{}'.format(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), app.config['DB_FILE'])
)
print("DB_FILE: %s", app.config['SQLALCHEMY_DATABASE_URI'])
db = SQLAlchemy(app)
sentry = Sentry(app, dsn=os.environ.get('SENTRY_DSN'))

from deployer.models import *

migrate = Migrate(app, db)
hooks = Hooks(app, url='/payload')
mail = Mail(app)

import deployer.views
