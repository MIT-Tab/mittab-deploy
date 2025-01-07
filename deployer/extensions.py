from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
from flask_migrate import Migrate
from flask_bootstrap import Bootstrap
from celery import Celery

db = SQLAlchemy()
migrate = Migrate()
mail = Mail()
bootstrap = Bootstrap()
celery = Celery()
