from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_hookserver import Hooks
from flask_mail import Mail
from flask_migrate import Migrate
from raven.contrib.flask import Sentry

from config.base import BaseConfig

app = Flask('deployer')
app.config.from_object(BaseConfig)
db = SQLAlchemy(app)
sentry = Sentry(app, dsn='https://d902814c71b2463a8c4ac7eef7c30481:8a09649a0cf844df9c77f2fcbb09a1f2@sentry.io/196701')

from deployer.models import *

migrate = Migrate(app, db)
hooks = Hooks(app, url='/payload')
mail = Mail(app)

import deployer.views
