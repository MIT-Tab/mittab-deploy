"""Owned database/user pairs on an explicitly enabled, existing MySQL cluster.

Only the deployer receives administrator credentials. App Platform binds the
restricted tenant user. No path in this module deletes a database cluster.
"""

import base64
from contextlib import contextmanager
import re
import tempfile
import uuid

from flask import current_app
import mysql.connector
import requests

from deployer.clients import digital_ocean as cloud

TENANT = re.compile(r"^nt[0-9a-f]{24}$")
PRIVILEGES = (
    "SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, INDEX, "
    "REFERENCES, CREATE TEMPORARY TABLES, SHOW VIEW, TRIGGER, LOCK TABLES"
)


def enabled():
    return bool(current_app.config.get("SHARED_MYSQL_ENABLED", False))


def cluster_id(value=None):
    value = value or current_app.config.get("SHARED_MYSQL_CLUSTER_ID", "")
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError("Configure a valid shared MySQL cluster ID") from exc


def new_tenant():
    # No '_' or '%' in SQL database names: database grants treat them as wildcards.
    return "nt" + uuid.uuid4().hex[:24]


def validate_tenant(value):
    if not isinstance(value, str) or not TENANT.fullmatch(value):
        raise ValueError("Refusing an unowned shared database/user name")
    return value


def _optional_get(path, key):
    try:
        return cloud.api_get(path)[key]
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return None
        raise


def _optional_delete(path):
    try:
        cloud.api_delete(path)
    except requests.HTTPError as exc:
        if exc.response is None or exc.response.status_code != 404:
            raise


def get_cluster(identifier):
    identifier = cluster_id(identifier)
    data = cloud.api_get("databases/" + identifier)["database"]
    if (
        data.get("id") != identifier
        or data.get("engine") != "mysql"
        or data.get("status") != "online"
    ):
        raise ValueError(
            "Shared MySQL cluster must be online and match its recorded ID"
        )
    return data


@contextmanager
def admin_connection(cluster):
    connection = cluster["connection"]
    if not connection.get("password") or connection.get("user") != "doadmin":
        raise ValueError("Shared MySQL administrator credentials are unavailable")
    encoded = cloud.api_get("databases/" + cluster["id"] + "/ca")["ca"]["certificate"]
    certificate = (
        encoded
        if encoded.startswith("-----BEGIN")
        else base64.b64decode(encoded).decode()
    )
    # The CA is public; credentials remain in memory, never in a command line/file.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pem") as ca:
        ca.write(certificate)
        ca.flush()
        client = mysql.connector.connect(
            host=connection["host"],
            port=connection["port"],
            user=connection["user"],
            password=connection["password"],
            database=connection.get("database", "defaultdb"),
            ssl_ca=ca.name,
            ssl_verify_cert=True,
            ssl_verify_identity=True,
            connection_timeout=10,
            autocommit=True,
        )
        try:
            yield client
        finally:
            client.close()


def reserved_tenants(identifier):
    from deployer.models import App

    return {
        row.shared_tenant
        for row in App.query.filter_by(
            database_mode="shared",
            shared_cluster_id=identifier,
            active=True,
        ).all()
        if row.shared_tenant
    }


def _capacity(cursor, slots, existing=None, reserved=()):
    maximum = int(current_app.config.get("SHARED_MYSQL_MAX_TENANTS", 8))
    if not 1 <= maximum <= 50:
        raise ValueError("Shared MySQL tenant limit must be between 1 and 50")
    connections = connection_budget()
    cursor.execute("SELECT @@max_connections")
    available = int(cursor.fetchone()[0]) - 1
    if maximum * connections + 10 > available:
        raise ValueError(
            "Shared MySQL connection budget leaves no administrator reserve"
        )
    cursor.execute(
        "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA "
        "WHERE SCHEMA_NAME REGEXP '^nt[0-9a-f]{24}$'"
    )
    names = {row[0] for row in cursor.fetchall()} | set(reserved)
    if existing in names:
        names.remove(existing)
    if len(names) + slots > maximum:
        raise ValueError(
            "Registration hosting is at capacity; please contact the operator"
        )


@contextmanager
def booking_capacity(slots=1):
    identifier = cluster_id()
    with admin_connection(get_cluster(identifier)) as client:
        cursor = client.cursor()
        try:
            cursor.execute("SELECT GET_LOCK('nutab_shared_provision', 10)")
            if cursor.fetchone()[0] != 1:
                raise RuntimeError("Shared provisioning is busy; retry later")
            try:
                _capacity(cursor, slots, reserved=reserved_tenants(identifier))
                # Keep admission serialized until both paid ownership records
                # are committed, including not-yet-provisioned reservations.
                yield
            finally:
                cursor.execute("SELECT RELEASE_LOCK('nutab_shared_provision')")
                cursor.fetchone()
        finally:
            cursor.close()


def _verify_grants(grants, name):
    expected = "`" + name + "`.*"
    own_grant = False
    for row in grants:
        grant = row[0]
        if " ON " not in grant or "WITH GRANT OPTION" in grant.upper():
            raise ValueError("Tenant still has a role or grant delegation")
        privilege, remainder = grant.split(" ON ", 1)
        scope = remainder.split(" TO ", 1)[0]
        if scope == "*.*" and privilege == "GRANT USAGE":
            continue
        if scope != expected:
            raise ValueError("Tenant still has privileges outside its own database")
        own_grant = True
    if not own_grant:
        raise ValueError("Tenant is missing its database privileges")


def connection_budget():
    connections = int(current_app.config.get("SHARED_MYSQL_MAX_CONNECTIONS", 8))
    if not 4 <= connections <= 8:
        raise ValueError("Shared MySQL connection budget must be between 4 and 8")
    return connections


def restrict_user(cursor, name):
    validate_tenant(name)
    # REVOKE ALL does not revoke role memberships. Remove them explicitly too.
    cursor.execute(
        "SELECT FROM_USER, FROM_HOST FROM mysql.role_edges "
        "WHERE TO_USER = %s AND TO_HOST = %s",
        (name, "%"),
    )
    for role, host in cursor.fetchall():
        cursor.execute("REVOKE %s@%s FROM %s@%s", (role, host, name, "%"))
    cursor.execute("SET DEFAULT ROLE NONE TO %s@%s", (name, "%"))
    cursor.execute("REVOKE ALL PRIVILEGES, GRANT OPTION FROM %s@%s", (name, "%"))
    cursor.execute("GRANT " + PRIVILEGES + " ON `" + name + "`.* TO %s@%s", (name, "%"))
    connections = connection_budget()
    cursor.execute(
        "ALTER USER %s@%s REQUIRE SSL WITH MAX_USER_CONNECTIONS %s",
        (name, "%", connections),
    )
    cursor.execute("SHOW GRANTS FOR %s@%s", (name, "%"))
    _verify_grants(cursor.fetchall(), name)


def ensure_database(app):
    name = validate_tenant(app.shared_tenant)
    cluster = get_cluster(app.shared_cluster_id)
    with admin_connection(cluster) as client:
        cursor = client.cursor()
        try:
            cursor.execute("SELECT GET_LOCK('nutab_shared_provision', 10)")
            if cursor.fetchone()[0] != 1:
                raise RuntimeError("Shared provisioning is busy; retry later")
            try:
                _capacity(
                    cursor, 1, existing=name, reserved=reserved_tenants(cluster["id"])
                )
                path = "databases/" + cluster["id"]
                if _optional_get(path + "/dbs/" + name, "db") is None:
                    cloud.api_post(path + "/dbs", {"name": name})
                if _optional_get(path + "/users/" + name, "user") is None:
                    cloud.api_post(path + "/users", {"name": name})
                restrict_user(cursor, name)
            finally:
                cursor.execute("SELECT RELEASE_LOCK('nutab_shared_provision')")
                cursor.fetchone()
        finally:
            cursor.close()
    # Bind explicitly to the restricted user/schema; never pass doadmin to apps.
    return {
        "name": cluster["name"],
        "id": cluster["id"],
        "shared": True,
        "connection": {"database": name, "user": name},
    }


def matches_app(resource, app):
    databases = resource.get("spec", {}).get("databases", [])
    if len(databases) != 1:
        return False
    binding = databases[0]
    cluster = get_cluster(app.shared_cluster_id)
    return (
        binding.get("cluster_name") == cluster["name"]
        and binding.get("db_name") == app.shared_tenant
        and binding.get("db_user") == app.shared_tenant
    )


def find_app(app):
    try:
        resource = cloud.get_app(app.name)
    except cloud.NoAppError:
        return None
    if app.cloud_app_id and resource["id"] != app.cloud_app_id:
        raise ValueError("Refusing to adopt/delete an app with a different recorded ID")
    if not matches_app(resource, app):
        raise ValueError("Refusing to adopt/delete an app owned by another deployment")
    return resource


def delete_tournament(app):
    name = validate_tenant(app.shared_tenant)
    identifier = cluster_id(app.shared_cluster_id)
    # Resolve and verify ownership before any destructive operation. A missing
    # app still permits cleanup of its persisted, uniquely owned schema/user.
    resource = find_app(app)
    if resource is not None:
        cloud.api_delete("apps/" + resource["id"])
    path = "databases/" + identifier
    _optional_delete(path + "/dbs/" + name)
    _optional_delete(path + "/users/" + name)
