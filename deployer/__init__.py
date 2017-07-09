from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_hookserver import Hooks
from flask_mail import Mail

from config.base import BaseConfig

app = Flask('deployer')
app.config.from_object(BaseConfig)
db = SQLAlchemy(app)

hooks = Hooks(app, url='/payload')
mail = Mail(app)

import deployer.views
