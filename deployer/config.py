import os

REPO_OPTIONS = {
    "default": {
        "repo_slug": "MIT-Tab/mit-tab",
        "branch": "master",
        "name": "Default"
    },
    "discord": {
        "repo_slug": "MIT-Tab/mit-tab",
        "branch": "discord",
        "name": "Discord - BETA, only use with explicit approval"
    },
}

class BaseConfig(object):
    WEB_CSRF_ENABLED = True
    SECRET_KEY = os.environ['SECRET_KEY']
    DEBUG = os.environ['DEBUG'] == 'True'
    PRODUCTION = os.environ['PRODUCTION'] == 'True'

    MYSQL_DATABASE = os.environ['DATABASE_NAME']
    MYSQL_PASSWORD = os.environ['DATABASE_PASSWORD']
    MYSQL_USER = os.environ['DATABASE_USER']
    MYSQL_HOST = os.environ['DATABASE_HOST']
    MYSQL_PORT = os.environ['DATABASE_PORT']
    SQLALCHEMY_DATABASE_URI =  f"mysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_POOL_RECYCLE = 120

    CELERY_RESULT_BACKEND = None
    CELERY_BROKER_URL = os.environ['REDIS_URL']

    # for Flask-Mail
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 465
    MAIL_USE_TLS = False
    MAIL_USE_SSL = True
    MAIL_DEBUG = DEBUG
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
