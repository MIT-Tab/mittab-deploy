import os
from time import time, sleep

import boto3
import digitalocean
import requests

__access_key = os.environ['DIGITALOCEAN_ACCESS_KEY_ID']
__secret_key = os.environ['DIGITALOCEAN_ACCESS_KEY_SECRET']
__token = os.environ['DIGITALOCEAN_TOKEN']
__manager = digitalocean.Manager(token=__token)
__boto_client = boto3.client(
        's3',
        aws_access_key_id=__access_key,
        aws_secret_access_key=__secret_key,
        region_name='nyc3',
        endpoint_url='https://nyc3.digitaloceanspaces.com'
)


class NoDropletError(Exception):
    def __init__(self, name, *args):
        message = "No droplet found with name '{}'".format(name)
        super(NoDropletError, self).__init__(message, args)


class NoRecordError(Exception):
    def __init__(self, name, *args):
        message = "No domain record found with name '{}'".format(name)
        super(NoRecordError, self).__init__(message, args)

######################
# Droplet interactions
######################


def create_droplet(droplet_name, size):
    user_ssh_key = open(os.path.join(os.environ['HOME'], '.ssh/id_rsa.pub')).read()
    keys = __manager.get_all_sshkeys()

    if user_ssh_key.strip() not in [key.public_key for key in keys]:
        key = digitalocean.SSHKey(
                token=__token,
                name='deployer-{}'.format(int(time())),
                public_key=user_ssh_key
                )

        key.create()
        keys = __manager.get_all_sshkeys()

    droplet = digitalocean.Droplet(token=__token,
                                   name=droplet_name,
                                   region='nyc3',
                                   image=__get_image_slug(),
                                   size_slug=size,
                                   ssh_keys=keys)
    droplet.create()
    return droplet


def get_droplet(droplet_name):
    droplets = __manager.get_all_droplets()
    for droplet in droplets:
        if droplet.name == droplet_name:
            return droplet
    raise NoDropletError(droplet_name)

def __get_image_slug():
    """
    TODO: Un-comment after fixing API pagination error
    images = __manager.get_images()
    return sorted(filter(lambda i: i.slug and ('docker' in i.slug), images), key=lambda i: i.created_at)[0].slug
    """
    return 'docker-20-04'


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
        }

    github_config = {
        "repo": repo_slug,
        "branch": branch,
        "deploy_on_push": False,
    }

    return {
        "name": f"mittab-{name}",
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
            "name": "static",
            "output_dir": "/var/www/tab/assets",
            "dockerfile_path": "Dockerfile.static",
            "github": github_config,
            "routes": [{ "path": "/static" }]
        }],
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
            env_var("SENTRY_DSN", os.environ.get("MITTAB_SENTRY_DSN"), True),
            env_var("TOURNAMENT_NAME", name),
            env_var("DISCORD_BOT_TOKEN", os.environ.get("DISCORD_BOT_TOKEN", True)),
        ],
        "databases": [{
            "name": database["name"],
            "production": True,
            "engine": "MYSQL",
            "db_name": database["connection"]["database"],
            "db_user": database["connection"]["user"],
            "cluster_name": database["name"],
        }],
        "domains": [{
            "domain": f"{name}.nu-tab.com",
            "type": "PRIMARY",
            "zone": "nu-tab.com",
            "wildcard": False,
        }]
    }


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
        print("App doesnt exist, no need to delete")
        try:
            delete_database(f"mittab-db-{app_name}")
        except ValueError:
            print("DB doesnt exist, no need to delete")


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
    print("sleeping after setting auth plugin")

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
        print(f"Got non-online status: {status}")
        return False
    return True


############################
# Domain record interactions
############################


def create_domain_record(name, ip, domain='nu-tab.com'):
    domain = digitalocean.Domain(token=__token, name=domain)

    return domain.create_new_domain_record(type='A',
                                           name=name,
                                           data=ip,
                                           ttl=3600)


def get_domain_record(name, domain='nu-tab.com'):
    domain = digitalocean.Domain.get_object(__token, domain)
    records = domain.get_records(params={'name': name})
    for record in records:
        if record.name == name:
            return record
    raise NoRecordError(name)


########
# Spaces
########


def upload_file(src_path, dst_path):
    __boto_client.upload_file(src_path, 'mittab-backups', dst_path)


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
        print(resp.json())
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
        print(resp.json())
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
        print(resp.json())
        raise e
