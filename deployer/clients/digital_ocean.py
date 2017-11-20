import os
from time import time

import boto3
from botocore.client import Config
import digitalocean

__token = os.environ['DIGITALOCEAN_TOKEN']
__manager = digitalocean.Manager(token=__token)


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
    user_ssh_key = open('/root/.ssh/id_rsa.pub').read()
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
                                   image='docker',
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

############################
# Domain record interactions
############################


def create_domain_record(name, ip, domain='nu-tab.com'):
    record_type = 'A'
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


####################
# Spaces interations
####################

__session = boto3.session.Session()
__client = __session.client('s3',
        region_name='nyc3',
        endpoint_url='https://nyc3.digitaloceanspaces.com',
        aws_access_key_id=os.environ['DIGITALOCEAN_ACCESS_KEY'],
        aws_secret_access_key=__token)

def upload_file(filename, bucket_name, key_name):
    __client.upload_file(filename, bucket_name, key_name)
