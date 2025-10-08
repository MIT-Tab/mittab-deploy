import os
import logging
import sys
from time import time, sleep

import requests

__access_key = os.environ['DIGITALOCEAN_ACCESS_KEY_ID']
__secret_key = os.environ['DIGITALOCEAN_ACCESS_KEY_SECRET']
__token = os.environ['DIGITALOCEAN_TOKEN']

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class NoDropletError(Exception):
    def __init__(self, name, *args):
        message = "No droplet found with name '{}'".format(name)
        super(NoDropletError, self).__init__(message, args)


class NoRecordError(Exception):
    def __init__(self, name, *args):
        message = "No domain record found with name '{}'".format(name)
        super(NoRecordError, self).__init__(message, args)

############################
# Apps
############################

def create_app(name, tab_password, database, repo_slug, branch):
    """
    Create the main App. DB must be created first.
    """
    return __post("apps",
            {"spec": __build_app_spec(name, tab_password, database, repo_slug, branch)})


def __build_app_spec(name, tab_password, database, repo_slug, branch):
    """
    Build the appspec object for digitalocean. Ideally we could use a yaml file on the
    branch of the deployment, but it gets a bit tricky with databases and secrets, which
    cannot be easily managed through that file.

    Reference: https://docs.digitalocean.com/products/app-platform/references/app-specification-reference/
    """
    def env_var(key, value, is_secret=False):
        return {
            "key": key,
            "value": value,
            "type": "SECRET" if is_secret else "GENERAL",
            "scope": "RUN_AND_BUILD_TIME",
        }

    github_config = {
        "repo": repo_slug,
        "branch": branch,
        "deploy_on_push": False,
    }

    base_config = {
        "name": f"mittab-{name}",
        "region": "nyc",
        "services": [{
            "name": "web",
            "instance_count": 1,
            "instance_size_slug": "professional-xs",
            "dockerfile_path": "Dockerfile",
            "http_port": 8000,
            "github": github_config,
            "routes": [{ "path": "/" }],
        }],
        "static_sites": [{
            "name": "django-static",
            "output_dir": "/var/www/tab/staticfiles",
            "dockerfile_path": "Dockerfile.static",
            "github": github_config,
            "routes": [{ "path": "/static" }]
        },
        {
            "name": "webpack-static",
            "output_dir": "/var/www/tab/assets/webpack_bundles",
            "dockerfile_path": "Dockerfile.static",
            "github": github_config,
            "routes": [{ "path": "/static/webpack_bundles" }]
        }
        ],
        "envs": [
            env_var("TAB_PASSWORD", tab_password, True),
            env_var("MYSQL_DATABASE", "${%s.DATABASE}" % database["name"]),
            env_var("MYSQL_PASSWORD", "${%s.PASSWORD}" % database["name"]),
            env_var("MYSQL_USER", "${%s.USERNAME}" % database["name"]),
            env_var("MYSQL_HOST", "${%s.HOSTNAME}" % database["name"]),
            env_var("MYSQL_PORT", "${%s.PORT}" % database["name"]),
            env_var("BACKUP_STORAGE", "S3"),
            env_var("BACKUP_BUCKET", "mittab-backups"),
            env_var("BACKUP_PREFIX", f"backups/{name}/{int(time())}"),
            env_var("BACKUP_S3_ENDPOINT", "https://nyc3.digitaloceanspaces.com"),
            env_var("AWS_ACCESS_KEY_ID", __access_key, True),
            env_var("AWS_SECRET_ACCESS_KEY", __secret_key, True),
            env_var("AWS_DEFAULT_REGION", "nyc3"),
            env_var("SENTRY_DSN", os.environ.get("MITTAB_SENTRY_DSN", ""), True),
            env_var("TOURNAMENT_NAME", name),
            env_var("DISCORD_BOT_TOKEN", os.environ.get("DISCORD_BOT_TOKEN", ""), True),
            env_var("MITTAB_ENV", "test-deployment" if name.endswith("-test") else "production"),
        ],
        "databases": [{
            "name": database["name"],
            "production": True,
            "engine": "MYSQL",
            "db_name": database["connection"]["database"],
            "db_user": database["connection"]["user"],
            "cluster_name": database["name"],
        }],
        "domains": []
    }

    if os.environ.get("NU_TAB_DOMAIN"):
        base_config["domains"].append(
            {
                "domain": f"{name}.{os.environ['NU_TAB_DOMAIN']}",
                "type": "PRIMARY",
                "zone": os.environ["NU_TAB_DOMAIN"],
                "wildcard": False,
            }
        )
    return base_config


def get_app(app_name):
    if not app_name.startswith("mittab-"):
        app_name = f"mittab-{app_name}"

    apps = __get("apps")["apps"]
    for app in apps:
        if app["spec"]["name"] != app_name:
            continue
        return app

    raise ValueError(f"App {app_name} not found")



def delete_app(app_name):
    try:
        app = get_app(app_name)
        __delete(f"apps/{app['id']}")
        delete_database(app["spec"]["databases"][0]["cluster_name"])
    except ValueError:
        logger.info(f"App {app_name} doesnt exist, no need to delete")
        try:
            delete_database(f"mittab-db-{app_name}")
        except ValueError:
            logger.info(f"DB {f'mittab-db-{app_name}'} doesnt exist, no need to delete")


############################
# Databases
############################

def create_database(name, timeout=600):
    data = __post("databases",
            {
                "name": f"mittab-db-{name}",
                "engine": "mysql",
                "version": "8",
                "size": "db-s-1vcpu-1gb",
                "region": "nyc3",
                "num_nodes": 1,
            })["database"]


    seconds_elapsed = 0
    while seconds_elapsed < timeout:
        if is_database_ready(data["id"]):
            break
        seconds_elapsed += 30
        sleep(30)

    if not is_database_ready(data["id"]):
        raise ValueError('Timeout exceeded')

    # necessary for python's mysql client
    path = f"databases/{data['id']}/users/{data['connection']['user']}/reset_auth"
    __post(path, {"mysql_settings": {"auth_plugin": "mysql_native_password"}})
    logger.info(f"sleeping after setting auth plugin for {data['id']}")

    seconds_elapsed = 0
    while seconds_elapsed < timeout:
        if is_database_ready(data["id"]):
            break
        seconds_elapsed += 30
        sleep(30)

    if not is_database_ready(data["id"]):
        raise ValueError('Timeout exceeded')

    return data


def delete_database(name):
    for db in __get("databases")["databases"]:
        if db["name"] != name:
            continue
        __delete(f"databases/{db['id']}")
        return
    raise ValueError(f"DB {name} not found")


def is_database_ready(db_id):
    status = __get(f"databases/{db_id}")["database"]["status"]
    if status != "online":
        logger.info(f"Got non-online status: {status} for {db_id}")
        return False
    return True


def __post(path, data):
    if not path.startswith("/"):
        path = f"/{path}"

    resp = requests.post(f"https://api.digitalocean.com/v2{path}",
            json=data,
            headers={"Authorization": f"Bearer {__token}"})
    try:
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Error posting {path}: {e}", exc_info=True)
        logger.info(resp.json())
        raise e


def __delete(path):
    if not path.startswith("/"):
        path = f"/{path}"

    resp = requests.delete(f"https://api.digitalocean.com/v2{path}",
            headers={"Authorization": f"Bearer {__token}"})
    try:
        resp.raise_for_status()
        return
    except Exception as e:
        logger.error(f"Error deleting {path}: {e}", exc_info=True)
        logger.debug(resp.json())
        raise e


def __get(path):
    if not path.startswith("/"):
        path = f"/{path}"

    resp = requests.get(f"https://api.digitalocean.com/v2{path}",
            headers={"Authorization": f"Bearer {__token}"})
    try:
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Error getting {path}: {e}", exc_info=True)
        logger.debug(resp.json())
        raise e
