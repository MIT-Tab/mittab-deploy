import os


class BaseConfig(object):
    WEB_CSRF_ENABLED = True
    SECRET_KEY = os.environ['SECRET_KEY']
    DEBUG = os.environ['DEBUG'] == 'True'
    PRODUCTION = os.environ['PRODUCTION'] == 'True'

    MYSQL_DATABASE = os.environ['DATABASE_NAME']
    MYSQL_PASSWORD = os.environ['DATABASE_PASSWORD']
    MYSQL_USER = os.environ['DATABASE_USER']
    MYSQL_HOST = os.environ['DATABASE_HOST']
    SQLALCHEMY_DATABASE_URI = f"mysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DATABASE}"
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
    ADMINS = ['benmuschol@gmail.com']

    # Oauth login for admin app
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
    GOOGLE_DISCOVERY_URL = (
        "https://accounts.google.com/.well-known/openid-configuration"
    )
    GOOGLE_AUTH_ALLOWED_EMAILS = [
        "benmuschol@gmail.com",
        "johnrod.john@gmail.com",
    ]
