import os
from flask import Flask
from flask_bootstrap import Bootstrap
import flask_login
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_migrate import Migrate
from raven.contrib.flask import Sentry

db = SQLAlchemy()
migrate = Migrate()
login_manager = flask_login.LoginManager()
mail = Mail()
bootstrap = Bootstrap()

def create_app(config_object=None):
    app = Flask('deployer')

    # Load config
    if config_object is None:
        from config.base import BaseConfig
        config_object = BaseConfig
    app.config.from_object(config_object)

    # Initialize Flask extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bootstrap.init_app(app)
    mail.init_app(app)

    if not app.config.get('DEBUG'):
        sentry = Sentry(app, dsn=os.environ.get('SENTRY_DSN'))

    with app.app_context():
        # Import parts of our application
        from deployer import models, views

        return app
