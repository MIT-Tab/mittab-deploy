from datetime import datetime, timedelta
from unittest import TestCase
from unittest.mock import patch

from test_shared_checkout import SharedConfig, CLUSTER
from deployer import create_app, pricing
from deployer.extensions import db
from deployer.models import App
from deployer.tasks import deploy_shared_app
from deployer.clients import digital_ocean


class SharedDeploymentTest(TestCase):
    def setUp(self):
        self.context = create_app(SharedConfig).app_context()
        self.context.push()
        db.create_all()
        self.app = App(
            "new-open",
            "MIT-Tab/mit-tab",
            "master",
            pricing.today() + timedelta(days=5),
            "tab@example.com",
        )
        self.app.active = True
        self.app.database_mode = "shared"
        self.app.shared_cluster_id = CLUSTER
        self.app.shared_tenant = "nt" + "a" * 24
        db.session.add(self.app)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    @patch("deployer.clients.shared_mysql.find_app", return_value=None)
    @patch("deployer.clients.shared_mysql.ensure_database")
    @patch(
        "deployer.clients.digital_ocean.create_app",
        return_value={"app": {"id": "created-app"}},
    )
    @patch(
        "deployer.clients.digital_ocean.wait_for_app",
        return_value="https://synthetic.ondigitalocean.app",
    )
    def test_commits_ownership_and_waits_for_readiness(
        self, wait, create, ensure, _find
    ):
        ensure.return_value = {"shared": True}
        self.assertTrue(deploy_shared_app(self.app, "Synthetic12"))
        wait.assert_called_once_with("created-app", timeout=900)
        self.assertEqual(self.app.temporary_url, "https://synthetic.ondigitalocean.app")
        self.assertEqual(self.app.cloud_app_id, "created-app")
        self.assertEqual(self.app.status, "Deployed")
        self.assertIsNone(self.app.provisioning_until)
        self.assertEqual(create.call_args.args[2], {"shared": True})

    @patch("deployer.clients.shared_mysql.find_app")
    @patch("deployer.clients.shared_mysql.ensure_database")
    def test_duplicate_delivery_with_live_lease_does_nothing(self, ensure, find):
        self.app.provisioning_until = datetime.utcnow() + timedelta(minutes=10)
        db.session.commit()
        self.assertFalse(deploy_shared_app(self.app, "Synthetic12"))
        ensure.assert_not_called()
        find.assert_not_called()

    @patch(
        "deployer.clients.shared_mysql.find_app", return_value={"id": "retained-app"}
    )
    @patch("deployer.clients.shared_mysql.ensure_database")
    @patch(
        "deployer.clients.digital_ocean.wait_for_app",
        side_effect=RuntimeError("timeout"),
    )
    @patch("deployer.clients.shared_mysql.delete_tournament")
    def test_uncertain_readiness_retains_app_and_data_for_retry(
        self, delete, _wait, ensure, _find
    ):
        with self.assertRaises(RuntimeError):
            deploy_shared_app(self.app, "Synthetic12")
        self.assertEqual(self.app.cloud_app_id, "retained-app")
        self.assertTrue(self.app.active)
        self.assertIsNone(self.app.provisioning_until)
        ensure.assert_not_called()
        delete.assert_not_called()

    def test_shared_spec_binds_tenant_and_limits_connections_without_downsizing(self):
        spec = getattr(digital_ocean, "__build_app_spec")(
            "open",
            "Synthetic12",
            {
                "name": "tournament-pool",
                "shared": True,
                "connection": {
                    "database": self.app.shared_tenant,
                    "user": self.app.shared_tenant,
                },
            },
            "MIT-Tab/mit-tab",
            "master",
        )
        binding = spec["databases"][0]
        self.assertEqual(binding["db_user"], self.app.shared_tenant)
        self.assertEqual(binding["db_name"], self.app.shared_tenant)
        self.assertEqual(spec["services"][0]["instance_size_slug"], "professional-xs")
        env = {x["key"]: x["value"] for x in spec["envs"]}
        self.assertEqual(env["MYSQL_SHARED_CLUSTER"], "true")
        self.assertEqual(env["GUNICORN_WORKERS"], "2")
        self.assertEqual(env["GUNICORN_CONNECTIONS"], "3")
        self.assertNotIn("doadmin", str(spec))
