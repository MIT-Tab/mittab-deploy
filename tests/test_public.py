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
from deployer.extensions import db, mail
from deployer.models import App
from deployer.clients import email
from deployer.tasks import deploy_tournament


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


class AppTestCase(unittest.TestCase):

    def setUp(self):
        self.flask_app = create_app(AppConfig)
        self.context = self.flask_app.app_context()
        self.context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()


class TournamentDirectoryTest(AppTestCase):

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


class TournamentDeploymentTest(AppTestCase):
    temporary_url = "https://fall-open-example.ondigitalocean.app"

    def test_deployment_saves_url_before_sending_credentials(self):
        app = _app("fall-open", status="Initializing")
        app.temporary_url = "https://old-app.ondigitalocean.app"
        db.session.add(app)
        db.session.commit()

        def server_ready(app_id):
            self.assertEqual(app_id, "do-app-id")
            self.assertEqual(app.status, "Waiting for server to deploy")
            self.assertIsNone(app.temporary_url)
            return self.temporary_url

        def confirmation(tournament, password):
            db.session.refresh(tournament)
            self.assertEqual(tournament.status, "Deployed")
            self.assertEqual(tournament.temporary_url, self.temporary_url)
            self.assertEqual(password, "tab-password")

        with patch("deployer.tasks.time.sleep"), \
                patch("deployer.tasks.digital_ocean.create_database"), \
                patch("deployer.tasks.digital_ocean.create_app", return_value={
                    "app": {"id": "do-app-id"},
                }), \
                patch("deployer.tasks.digital_ocean.wait_for_app", side_effect=server_ready), \
                patch("deployer.tasks.email.send_confirmation", side_effect=confirmation) as send, \
                patch("deployer.tasks.email.send_notification"):
            deploy_tournament.run(app.id, "tab-password")
        send.assert_called_once()

    def test_status_poll_and_reloaded_page_include_temporary_url(self):
        app = _app("fall-open")
        app.temporary_url = self.temporary_url
        db.session.add(app)
        db.session.commit()

        client = self.flask_app.test_client()
        response = client.get("/tournaments/fall-open/status")
        self.assertEqual(response.get_json(), {
            "status": "Deployed", "temporary_url": self.temporary_url,
        })
        page = client.get("/tournaments/fall-open").get_data(as_text=True)
        self.assertIn(self.temporary_url, page)
        self.assertIn(app.url, page)
        self.assertIn("Your site has deployed!", page)

    def test_legacy_tournament_without_temporary_url_still_loads(self):
        db.session.add(_app("legacy"))
        db.session.commit()
        client = self.flask_app.test_client()
        self.assertEqual(client.get("/tournaments/legacy").status_code, 200)
        self.assertEqual(client.get("/tournaments/legacy/status").get_json(), {
            "status": "Deployed", "temporary_url": None,
        })
        self.assertEqual(client.get("/tournaments/missing/status").status_code, 404)

    def test_confirmation_email_includes_both_urls_and_credentials(self):
        app = _app("fall-open")
        app.temporary_url = self.temporary_url
        self.flask_app.config["MAIL_SUPPRESS_SEND"] = True
        with mail.record_messages() as messages:
            email.send_confirmation(app, "secret<&password")

        self.assertEqual(len(messages), 1)
        message = messages[0]
        self.assertEqual(message.recipients, [app.email])
        for body in (message.body, message.html):
            self.assertIn(app.url, body)
            self.assertIn(self.temporary_url, body)
            self.assertIn("Username:", body)
            self.assertIn("tab", body)
            self.assertIn("permanent URL will be available soon", body)
        self.assertIn("secret<&password", message.body)
        self.assertIn("secret&lt;&amp;password", message.html)
