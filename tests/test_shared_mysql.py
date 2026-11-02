from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import os

from test_public import AppConfig
from deployer import create_app
from deployer.clients import shared_mysql, digital_ocean as cloud

CLUSTER = "b7f112b1-26f1-46d8-a0dd-cc151c6d208f"
TENANT = "nt" + "a" * 24


class OwnershipTest(TestCase):
    def setUp(self):
        self.context = create_app(AppConfig).app_context()
        self.context.push()
        self.app = SimpleNamespace(
            name="open",
            shared_cluster_id=CLUSTER,
            shared_tenant=TENANT,
            cloud_app_id="app-1",
        )
        self.cluster = {
            "id": CLUSTER,
            "name": "tournament-pool",
            "engine": "mysql",
            "status": "online",
        }

    def tearDown(self):
        self.context.pop()

    def resource(self, tenant=TENANT):
        return {
            "id": "app-1",
            "spec": {
                "databases": [
                    {
                        "cluster_name": "tournament-pool",
                        "db_name": tenant,
                        "db_user": tenant,
                    }
                ]
            },
        }

    @patch("deployer.clients.shared_mysql.cloud.api_delete")
    @patch("deployer.clients.shared_mysql.get_cluster")
    @patch("deployer.clients.shared_mysql.cloud.get_app")
    def test_cleanup_deletes_only_owned_app_schema_and_user(
        self, get_app, cluster, delete
    ):
        get_app.return_value = self.resource()
        cluster.return_value = self.cluster
        shared_mysql.delete_tournament(self.app)
        paths = [c.args[0] for c in delete.call_args_list]
        self.assertEqual(
            paths,
            [
                "apps/app-1",
                "databases/" + CLUSTER + "/dbs/" + TENANT,
                "databases/" + CLUSTER + "/users/" + TENANT,
            ],
        )
        self.assertNotIn("databases/" + CLUSTER, paths)

    @patch("deployer.clients.shared_mysql.cloud.api_delete")
    @patch("deployer.clients.shared_mysql.get_cluster")
    @patch("deployer.clients.shared_mysql.cloud.get_app")
    def test_mismatched_app_binding_prevents_every_delete(
        self, get_app, cluster, delete
    ):
        get_app.return_value = self.resource("nt" + "b" * 24)
        cluster.return_value = self.cluster
        with self.assertRaises(ValueError):
            shared_mysql.delete_tournament(self.app)
        delete.assert_not_called()

    @patch("deployer.clients.shared_mysql.cloud.api_delete")
    def test_unsafe_names_fail_before_cloud_calls(self, delete):
        for name in ["defaultdb", "doadmin", "nt_abc", "nt%", "tenant;DROP DATABASE x"]:
            self.app.shared_tenant = name
            with self.assertRaises(ValueError):
                shared_mysql.delete_tournament(self.app)
        delete.assert_not_called()

    def test_grant_audit_rejects_global_privileges_roles_and_other_schemas(self):
        valid = [
            ("GRANT USAGE ON *.* TO `u`@`%`",),
            ("GRANT SELECT, INSERT ON `" + TENANT + "`.* TO `u`@`%`",),
        ]
        shared_mysql._verify_grants(valid, TENANT)
        for grant in [
            "GRANT SELECT ON *.* TO `u`@`%`",
            "GRANT `doadmin`@`%` TO `u`@`%`",
            "GRANT SELECT ON `defaultdb`.* TO `u`@`%`",
            "GRANT SELECT ON `" + TENANT + "`.* TO `u`@`%` WITH GRANT OPTION",
        ]:
            with self.assertRaises(ValueError):
                shared_mysql._verify_grants(valid + [(grant,)], TENANT)

    @patch(
        "deployer.clients.shared_mysql.cloud.api_get",
        return_value={
            "ca": {
                "certificate": "-----BEGIN CERTIFICATE-----\nsynthetic\n-----END CERTIFICATE-----"
            }
        },
    )
    @patch("deployer.clients.shared_mysql.mysql.connector.connect")
    def test_admin_connection_verifies_tls_and_removes_temporary_ca(
        self, connect, _get
    ):
        cluster = {
            "id": CLUSTER,
            "connection": {
                "host": "db.example.test",
                "port": 25060,
                "user": "doadmin",
                "password": "synthetic-admin-only",
            },
        }
        with shared_mysql.admin_connection(cluster):
            options = connect.call_args.kwargs
            self.assertTrue(options["ssl_verify_cert"])
            self.assertTrue(options["ssl_verify_identity"])
            self.assertTrue(os.path.exists(options["ssl_ca"]))
        self.assertFalse(os.path.exists(options["ssl_ca"]))
        connect.return_value.close.assert_called_once()

    @patch("deployer.clients.digital_ocean.__delete")
    @patch("deployer.clients.digital_ocean.get_app")
    def test_legacy_cleanup_cannot_delete_a_shared_bound_app(self, get_app, delete):
        get_app.return_value = self.resource()
        with self.assertRaises(ValueError):
            cloud.delete_app("open")
        delete.assert_not_called()

    @patch("deployer.clients.digital_ocean.__delete")
    @patch("deployer.clients.digital_ocean.__get")
    @patch("deployer.clients.digital_ocean.get_app")
    def test_legacy_cleanup_protects_pool_id_even_if_pool_has_legacy_style_name(
        self, get_app, get, delete
    ):
        get_app.return_value = {
            "id": "legacy-app",
            "spec": {
                "databases": [
                    {"cluster_name": "mittab-db-open", "db_name": "defaultdb"}
                ]
            },
        }
        get.return_value = {"databases": [{"name": "mittab-db-open", "id": CLUSTER}]}
        with patch.dict("os.environ", {"SHARED_MYSQL_CLUSTER_ID": CLUSTER}):
            with self.assertRaises(ValueError):
                cloud.delete_app("open")
        delete.assert_not_called()
