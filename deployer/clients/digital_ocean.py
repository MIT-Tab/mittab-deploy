import os
from time import time

import digitalocean

token = os.environ['DIGITALOCEAN_TOKEN']
manager = digitalocean.Manager(token=token)

class NoDropletError(Exception):
    def __init__(self, name, *args):
        message = "No droplet found with name '{}'".format(name)
        super(NoDropletError, self).__init__(message, args)

class NoRecordError(Exception):
    def __init__(self, name, *args):
        message = "No domain record found with name '{}'".format(name)
        super(NoRecordError, self).__init__(message, args)

# Droplet interactions

def create_droplet(droplet_name):
    user_ssh_key = open('/root/.ssh/id_rsa.pub').read()
    keys = manager.get_all_sshkeys()

    if user_ssh_key.strip() not in [ key.public_key for key in keys ]:
        key = digitalocean.SSHKey(token=token,
                                name='deployer-{}'.format(int(time())),
                                public_key=user_ssh_key)
        key.create()
        keys = manager.get_all_sshkeys()

    droplet = digitalocean.Droplet(token=token,
                                   name=droplet_name,
                                   region='nyc3',
                                   image='docker',
                                   size_slug='512mb',
                                   ssh_keys=keys)
    droplet.create()
    return droplet


def get_droplet(droplet_name):
    droplets = manager.get_all_droplets()
    for droplet in droplets:
        if droplet.name == droplet_name:
            return droplet
    raise NoDropletError(droplet_name)

# Domain record interactions

def create_domain_record(name, ip, domain='nu-tab.com'):
    record_type = 'A'
    domain = digitalocean.Domain(token=token, name=domain)

    return domain.create_new_domain_record(type='A', name=name, data=ip)

def get_domain_record(name, domain='nu-tab.com'):
    domain = digitalocean.Domain.get_object(token, domain)
    records = domain.get_records(params={ 'name': name })
    for record in records:
        if record.name == name:
            return record
    raise NoRecordError(name)
