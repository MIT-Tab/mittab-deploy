import os


class BaseConfig(object):
    WEB_CSRF_ENABLED = True
    SECRET_KEY = os.environ['SECRET_KEY']
    DEBUG = os.environ['DEBUG'] == 'True'

    DB_FILE = 'db.sqlite'
    DB_PATH = os.path.join(os.path.abspath(os.path.dirname(DB_FILE)), DB_FILE)
    SQLALCHEMY_DATABASE_URI = 'sqlite:///{}'.format(DB_PATH)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_POOL_RECYCLE = 120

    # configure celery to work with cloud amqp
    # AWS creds auto-loaded from AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY env
    # vars
    CELERY_RESULT_BACKEND = None
    CELERY_BROKER_URL = os.environ['CLOUD_AMQP_URL']
    AMQP_QUEUE_NAME = os.environ['AMQP_QUEUE']
    CELERY_DEFAULT_QUEUE = AMQP_QUEUE_NAME

    # for Flask-Mail
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 465
    MAIL_USE_TLS = False
    MAIL_USE_SSL = True
    MAIL_DEBUG = DEBUG
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    ADMINS = ['benmuschol@gmail.com']

    # DigitalOcean server config
    # https://developers.digitalocean.com/documentation/changelog/api-v2/new-size-slugs-for-droplet-plan-changes/
    DEFAULT_SIZE_SLUG = 's-1vcpu-3gb'
    TEST_SIZE_SLUG = 's-1vcpu-2gb'

    # Oauth login for admin app
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
    GOOGLE_DISCOVERY_URL = (
        "https://accounts.google.com/.well-known/openid-configuration"
    )
    GOOGLE_AUTH_ALLOWED_EMAILS = [
        "ben.muschol@airbnb.com",
        "benmuschol@gmail.com",
    ]
