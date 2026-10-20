from datetime import date
import os
import unittest
from unittest.mock import patch

for key, value in {
    "SECRET_KEY": "test-secret",
    "DEBUG": "True",
    "PRODUCTION": "False",
    "DATABASE_NAME": "test",
    "DATABASE_PASSWORD": "test",
    "DATABASE_USER": "test",
    "DATABASE_HOST": "localhost",
    "DATABASE_PORT": "3306",
    "REDIS_URL": "redis://localhost:6379/0",
    "DIGITALOCEAN_ACCESS_KEY_ID": "test",
    "DIGITALOCEAN_ACCESS_KEY_SECRET": "test",
    "DIGITALOCEAN_TOKEN": "test",
    "STRIPE_PUBLISHABLE_KEY": "test",
    "STRIPE_SECRET_KEY": "test",
}.items():
    os.environ.setdefault(key, value)

from deployer import create_app
from deployer.extensions import db
from deployer.models import App


class AppConfig:
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False


def _app(name, *, active=True, status="Deployed"):
    app = App(name, "MIT-Tab/mit-tab", "master", date.today(), "tab@example.com")
    app.active = active
    app.status = status
    return app


class TournamentDirectoryTest(unittest.TestCase):

    def setUp(self):
        self.flask_app = create_app(AppConfig)
        self.context = self.flask_app.app_context()
        self.context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_lists_only_live_production_instances(self):
        db.session.add_all([
            _app("fall-open"),
            _app("fall-open-test"),
            _app("starting", status="Initializing"),
            _app("archived", active=False),
        ])
        db.session.commit()

        with patch.dict("os.environ", {"NU_TAB_DOMAIN": "tabs.example.test"}):
            response = self.flask_app.test_client().get("/api/tournaments")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "tournaments": [{
                "name": "fall-open",
                "url": "https://fall-open.tabs.example.test",
            }]
        })
