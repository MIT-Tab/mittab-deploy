import os

import digitalocean

token = os.environ['DIGITALOCEAN_TOKEN']

class NoDropletError(Exception):
    def __init__(self, name, *args):
        message = "No droplet found with name '{}'".format(name)
        super(NoDropletError, self).__init__(message, args)

class NoRecordError(Exception):
    def __init__(self, name, *args):
        message = "No domain record found with name '{}'".format(name)
        super(NoRecordError, self).__init__(message, args)

# Droplet interactions

def get_droplet(droplet_name):
    manager = digitalocean.Manager(token=token)
    droplets = manager.get_all_droplets()
    for droplet in droplets:
        if droplet.name == droplet_name:
            return droplet
    raise NoDropletError(droplet_name)

# Domain record interactions

def get_domain_record(name, domain='nu-tab.com'):
    domain = digitalocean.Domain.get_object(token, domain)
    records = domain.get_records(params={ 'name': name })
    for record in records:
        if record.name == name:
            return record
    raise NoRecordError(name)
