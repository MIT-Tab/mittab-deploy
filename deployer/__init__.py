import os

import celery
from flask import Flask, json
from flask.json.provider import JSONProvider
from raven.contrib.flask import Sentry

from deployer.config import BaseConfig
from deployer.extensions import db, migrate, mail, bootstrap, celery
from deployer.views.public import bp

class CustomJSONProvider(JSONProvider):
    def dumps(self, obj, **kwargs):
        return json.dumps(obj, **kwargs)

    def loads(self, s, **kwargs):
        return json.loads(s, **kwargs)



def create_app(config_object=None):
    app = Flask('deployer')
    app.json_encoder = CustomJSONProvider
    app.json = json

    # Load config
    if config_object is None:
        config_object = BaseConfig
    app.config.from_object(config_object)

    # Initialize Flask extensions
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)


    # Initialize Celery
    celery.config_from_object(app.config)
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask

    app.register_blueprint(bp)

    if not app.config.get('DEBUG'):
        sentry = Sentry(app, dsn=os.environ.get('SENTRY_DSN'))

    return app
