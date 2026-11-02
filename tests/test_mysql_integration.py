"""Real MySQL regression checks; CI supplies a private MySQL8 service.

TEST_MYSQL_PORT must be explicit. No DigitalOcean/Stripe/production connections.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

import mysql.connector
import requests
import sqlalchemy as sa
from flask_migrate import upgrade, downgrade

from test_public import AppConfig
from deployer import create_app
from deployer.clients import shared_mysql
from deployer.extensions import db

CLUSTER = "b7f112b1-26f1-46d8-a0dd-cc151c6d208f"
MIGRATIONS = str(Path(__file__).resolve().parents[1] / "migrations")


@unittest.skipUnless(
    os.environ.get("TEST_MYSQL_PORT"), "requires explicit private TEST_MYSQL_PORT"
)
class MysqlIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.params = {
            "host": "127.0.0.1",
            "port": int(os.environ["TEST_MYSQL_PORT"]),
            "user": "root",
            "password": os.environ.get("TEST_MYSQL_PASSWORD", ""),
            "autocommit": True,
        }
        cls.control = "verify" + uuid.uuid4().hex[:16]
        client = mysql.connector.connect(**cls.params)
        q = client.cursor()
        q.execute("CREATE DATABASE `" + cls.control + "`")
        q.close()
        client.close()

    @classmethod
    def tearDownClass(cls):
        client = mysql.connector.connect(**cls.params)
        q = client.cursor()
        q.execute("DROP DATABASE `" + cls.control + "`")
        q.close()
        client.close()

    def setUp(self):
        class Config(AppConfig):
            SHARED_MYSQL_ENABLED = True
            SHARED_MYSQL_CLUSTER_ID = CLUSTER
            SHARED_MYSQL_MAX_TENANTS = 2
            SHARED_MYSQL_MAX_CONNECTIONS = 4

        Config.SQLALCHEMY_DATABASE_URI = sa.engine.URL.create(
            "mysql+mysqlconnector",
            username="root",
            password=self.params["password"],
            host="127.0.0.1",
            port=self.params["port"],
            database=self.control,
        )
        self.flask_app = create_app(Config)
        self.context = self.flask_app.app_context()
        self.context.push()
        self.environment = patch.dict(
            os.environ,
            {
                "DATABASE_NAME": self.control,
                "DATABASE_HOST": "127.0.0.1",
                "DATABASE_PORT": str(self.params["port"]),
                "DATABASE_USER": "root",
                "DATABASE_PASSWORD": self.params["password"],
            },
        )
        self.environment.start()
        upgrade(directory=MIGRATIONS)
        self.names = []
        self.deletes = []
        self.cluster = {
            "id": CLUSTER,
            "name": "verification-pool",
            "engine": "mysql",
            "status": "online",
        }
        self.api_patches = [
            patch(
                "deployer.clients.shared_mysql.cloud.api_get", side_effect=self.api_get
            ),
            patch(
                "deployer.clients.shared_mysql.cloud.api_post",
                side_effect=self.api_post,
            ),
            patch(
                "deployer.clients.shared_mysql.cloud.api_delete",
                side_effect=self.api_delete,
            ),
            patch(
                "deployer.clients.shared_mysql.admin_connection", side_effect=self.admin
            ),
        ]
        for item in self.api_patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.api_patches):
            item.stop()
        client = mysql.connector.connect(**self.params)
        q = client.cursor()
        for name in self.names:
            q.execute("DROP DATABASE IF EXISTS `" + name + "`")
            q.execute("DROP USER IF EXISTS %s@%s", (name, "%"))
        q.close()
        client.close()
        db.session.remove()
        if sa.inspect(db.engine).has_table("apps"):
            db.session.execute(sa.text("DELETE FROM apps"))
            db.session.commit()
        downgrade(directory=MIGRATIONS, revision="base")
        db.engine.dispose()
        self.context.pop()
        self.environment.stop()

    @contextmanager
    def admin(self, _cluster):
        client = mysql.connector.connect(**self.params)
        try:
            yield client
        finally:
            client.close()

    def not_found(self):
        response = requests.Response()
        response.status_code = 404
        raise requests.HTTPError("Not found", response=response)

    def api_get(self, path):
        if path == "databases/" + CLUSTER:
            return {"database": self.cluster}
        parts = path.split("/")
        client = mysql.connector.connect(**self.params)
        q = client.cursor()
        try:
            if parts[2] == "dbs":
                q.execute(
                    "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s",
                    (parts[3],),
                )
                if q.fetchone():
                    return {"db": {"name": parts[3]}}
            elif parts[2] == "users":
                q.execute(
                    "SELECT User FROM mysql.user WHERE User=%s AND Host=%s",
                    (parts[3], "%"),
                )
                if q.fetchone():
                    return {"user": {"name": parts[3]}}
            return self.not_found()
        finally:
            q.close()
            client.close()

    def api_post(self, path, data):
        name = data["name"]
        shared_mysql.validate_tenant(name)
        client = mysql.connector.connect(**self.params)
        q = client.cursor()
        try:
            if path.endswith("/dbs"):
                q.execute("CREATE DATABASE `" + name + "` CHARACTER SET utf8mb4")
            elif path.endswith("/users"):
                q.execute(
                    "CREATE USER %s@%s IDENTIFIED BY %s",
                    (name, "%", "SyntheticVerificationOnly12"),
                )
                # Model DigitalOcean's dangerous broad default grants. The
                # production restrict_user must strip these and role grants.
                q.execute(
                    "GRANT ALL PRIVILEGES ON *.* TO %s@%s WITH GRANT OPTION",
                    (name, "%"),
                )
                q.execute("CREATE ROLE IF NOT EXISTS 'verify_role'@'%'")
                q.execute("GRANT SELECT ON *.* TO 'verify_role'@'%'")
                q.execute("GRANT %s@%s TO %s@%s", ("verify_role", "%", name, "%"))
                q.execute(
                    "SET DEFAULT ROLE %s@%s TO %s@%s", ("verify_role", "%", name, "%")
                )
            else:
                raise AssertionError(path)
            return {}
        finally:
            q.close()
            client.close()

    def api_delete(self, path):
        self.deletes.append(path)
        if path.startswith("apps/"):
            return
        parts = path.split("/")
        self.assertEqual(
            len(parts), 4, "Cluster deletion is forbidden in shared cleanup"
        )
        name = shared_mysql.validate_tenant(parts[3])
        client = mysql.connector.connect(**self.params)
        q = client.cursor()
        try:
            if parts[2] == "dbs":
                q.execute("DROP DATABASE IF EXISTS `" + name + "`")
            elif parts[2] == "users":
                q.execute("DROP USER IF EXISTS %s@%s", (name, "%"))
            else:
                raise AssertionError(path)
        finally:
            q.close()
            client.close()

    def tenant(self):
        name = shared_mysql.new_tenant()
        self.names.append(name)
        app = SimpleNamespace(
            shared_tenant=name,
            shared_cluster_id=CLUSTER,
            cloud_app_id=None,
            name="verification-open",
        )
        binding = shared_mysql.ensure_database(app)
        self.assertEqual(binding["connection"], {"database": name, "user": name})
        return app

    def connect_tenant(self, app):
        # MySQL's local generated cert is accepted only in this private test.
        # Production admin_connection separately verifies the provider CA/DNS.
        return mysql.connector.connect(
            host="127.0.0.1",
            port=self.params["port"],
            user=app.shared_tenant,
            password="SyntheticVerificationOnly12",
            database=app.shared_tenant,
            autocommit=True,
            ssl_disabled=False,
        )

    def test_actual_grants_isolate_tenants_and_support_schema_migrations(self):
        first = self.tenant()
        second = self.tenant()
        client = self.connect_tenant(first)
        q = client.cursor()
        q.execute(
            "CREATE TABLE roster(id INT PRIMARY KEY, name VARCHAR(30)) ENGINE=InnoDB"
        )
        q.execute("ALTER TABLE roster ADD COLUMN active BOOLEAN DEFAULT TRUE")
        q.execute("INSERT INTO roster(id,name) VALUES(1,'Synthetic Team')")
        q.execute("SELECT name FROM roster")
        self.assertEqual(q.fetchone()[0], "Synthetic Team")
        for query in [
            "SELECT * FROM `" + self.control + "`.apps",
            "CREATE TABLE `" + second.shared_tenant + "`.intruder(id INT)",
            "DROP DATABASE `" + second.shared_tenant + "`",
            "CREATE USER 'forbidden'@'localhost'",
            "FLUSH TABLES WITH READ LOCK",
        ]:
            with self.assertRaises(mysql.connector.Error):
                q.execute(query)
        q.close()
        client.close()

    def test_idempotent_retry_and_tenant_capacity_leave_other_data_intact(self):
        first = self.tenant()
        second = self.tenant()
        shared_mysql.ensure_database(first)
        with self.assertRaisesRegex(ValueError, "capacity"):
            self.tenant()
        client = self.connect_tenant(second)
        q = client.cursor()
        q.execute("CREATE TABLE survivors(id INT PRIMARY KEY) ENGINE=InnoDB")
        q.execute("INSERT INTO survivors VALUES(42)")
        with patch(
            "deployer.clients.shared_mysql.cloud.get_app",
            side_effect=shared_mysql.cloud.NoAppError,
        ):
            shared_mysql.delete_tournament(first)
            shared_mysql.delete_tournament(first)
        q.execute("SELECT id FROM survivors")
        self.assertEqual(q.fetchone()[0], 42)
        q.close()
        client.close()
        self.assertFalse(any(p == "databases/" + CLUSTER for p in self.deletes))

    def test_migration_preserves_old_rows_without_reassigning_resources(self):
        downgrade(directory=MIGRATIONS, revision="base")

        upgrade(directory=MIGRATIONS, revision="2bf32bd5be0c")
        with db.engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO apps(name,status,active,confirmed,created_at,repo_slug,branch,deletion_date,email,warning_email_sent) VALUES('old-live','Deployed',1,1,:created,'MIT-Tab/mit-tab','master',:end,'old@example.com',0)"
                ),
                {
                    "created": datetime.utcnow(),
                    "end": datetime.utcnow().date() + timedelta(days=5),
                },
            )
        upgrade(directory=MIGRATIONS)
        row = db.session.execute(
            sa.text(
                "SELECT name,status,active,database_mode,shared_cluster_id,shared_tenant,pricing_version FROM apps WHERE name='old-live'"
            )
        ).one()
        self.assertEqual(
            tuple(row), ("old-live", "Deployed", 1, None, None, None, None)
        )
        db.session.execute(
            sa.text("UPDATE apps SET database_mode='shared' WHERE name='old-live'")
        )
        db.session.commit()
        # Flask-Migrate turns the migration's explicit RuntimeError into CLI
        # exit1. The important invariant is that ownership columns survive.
        with self.assertRaises(SystemExit):
            downgrade(directory=MIGRATIONS, revision="2bf32bd5be0c")
        self.assertIn(
            "shared_tenant",
            {c["name"] for c in sa.inspect(db.engine).get_columns("apps")},
        )
        # Clean up metadata for the other tests' independent shared schemas.
        db.session.execute(
            sa.text("UPDATE apps SET database_mode=NULL WHERE name='old-live'")
        )
        db.session.commit()
        downgrade(directory=MIGRATIONS, revision="base")

    def test_checkout_counts_paid_records_waiting_for_provisioning(self):
        from deployer.models import App

        pending = App(
            "waiting",
            "MIT-Tab/mit-tab",
            "master",
            datetime.utcnow().date() + timedelta(days=5),
            "tab@example.com",
        )
        pending.database_mode = "shared"
        pending.shared_cluster_id = CLUSTER
        pending.shared_tenant = shared_mysql.new_tenant()
        pending.active = True
        db.session.add(pending)
        db.session.commit()
        with self.assertRaisesRegex(ValueError, "capacity"):
            with shared_mysql.booking_capacity(2):
                self.fail("Insufficient slots must be rejected before payment")

    def test_mysql_enforces_per_tenant_connection_cap(self):
        tenant = self.tenant()
        connections = []
        try:
            for _ in range(4):
                connections.append(self.connect_tenant(tenant))
            with self.assertRaises(mysql.connector.Error):
                self.connect_tenant(tenant)
        finally:
            for client in connections:
                client.close()
