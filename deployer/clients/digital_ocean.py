import os

import digitalocean

manager = digitalocean.Manager(token=os.environ['DIGITALOCEAN_TOKEN'])

class NoDropletError(Exception):
    def __init__(self, name, *args):
        message = "No droplet found with name '%s'" % name
        super(NoDropletError, self).__init__(message, args)


def get_droplet(droplet_name):
    droplets = manager.get_all_droplets()
    for droplet in droplets:
        if droplet.name == droplet_name:
            return droplet
    raise NoDropletError(droplet_name)
