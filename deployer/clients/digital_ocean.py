import os

import digitalocean

token = os.environ['DIGITALOCEAN_TOKEN']

class NoDropletError(Exception):
    def __init__(self, name, *args):
        message = "No droplet found with name '%s'" % name
        super(NoDropletError, self).__init__(message, args)


def get_droplet(droplet_name):
    manager = digitalocean.Manager(token=token)
    droplets = manager.get_all_droplets()
    for droplet in droplets:
        if droplet.name == droplet_name:
            return droplet
    raise NoDropletError(droplet_name)

def create_domain_record(name, ip):
    record_type = 'A'
    domain = digitalocean.Domain(token=token, name='nu-tab.com')

    return domain.create_new_domain_record(type='A', name=name, data=ip)
