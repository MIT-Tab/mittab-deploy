import os


class BaseConfig(object):
    WEB_CSRF_ENABLED = True
    SECRET_KEY = os.environ['SECRET_KEY']
    DEBUG = os.environ['DEBUG'] == 'True'

    DB_NAME = os.environ['DB_NAME']
    DB_USER = os.environ['DB_USER']
    DB_PASS = os.environ['DB_PASS']
    DB_SERVICE = os.environ['DB_SERVICE']
    DB_PORT = os.environ['DB_PORT']
    SQLALCHEMY_DATABASE_URI = 'postgresql://{0}:{1}@{2}:{3}/{4}'.format(
        DB_USER, DB_PASS, DB_SERVICE, DB_PORT, DB_NAME
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # configure celery to work with redis
    CELERY_RESULT_BACKEND = 'redis://{0}:{1}'.format(
        os.environ['REDIS_PORT_6379_TCP_ADDR'],
        os.environ['REDIS_PORT_6379_TCP_PORT']
    )
    CELERY_BROKER_URL = CELERY_RESULT_BACKEND

    # for Flask-Webhooks extension
    GITHUB_WEBHOOKS_KEY = os.environ['GITHUB_SECRET']
    VALIDATE_IP = False
    VALIDATE_SIGNATURE = True

    # for Flask-Mail
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 465
    MAIL_USE_TLS = False
    MAIL_USE_SSL = True
    MAIL_DEBUG = DEBUG
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    ADMINS = ['benmuschol@gmail.com']
