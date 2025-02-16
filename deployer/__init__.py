import os

import celery
from flask import Flask
from raven.contrib.flask import Sentry

from deployer.config import BaseConfig
from deployer.extensions import db, migrate, mail, bootstrap, celery
from deployer.views.public import bp
from deployer.logging import setup_logging


def create_app(config_object=None):
    setup_logging()
    app = Flask('deployer')

    # Load config
    if config_object is None:
        config_object = BaseConfig
    app.config.from_object(config_object)

    # Initialize Flask extensions
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)


    # Initialize Celery
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask

    app.register_blueprint(bp)

    if not app.config.get('DEBUG'):
        sentry = Sentry(app, dsn=os.environ.get('SENTRY_DSN'))

    return app
