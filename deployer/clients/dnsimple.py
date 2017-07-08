import os
import json

import requests

class DNSimple(object):
    base_url = 'https://api.dnsimple.com/v1/'

    def __init__(self, email, token):
        self.email = email
        self.token = token
        token_header = '{0}:{1}'.format(email, token)
        self.headers = { 'X-DNSimple-Token': token_header, 'Content-Type': 'application/json' }

    def create_record(self, **kwargs):
        try:
            domain, name, record_type, content = kwargs['domain'], kwargs['name'], kwargs['record_type'], kwargs['content']
        except:
            raise Exception('Missing required argument (domain, name, record_type or content)')

        url = '{0}domains/{1}/records'.format(self.base_url, domain)
        record = {
            'name': name,
            'record_type': record_type,
            'content': content,
        }
        data = json.dumps({ 'record': record })

        return requests.post(url, headers=self.headers, data=data).json()

def create_record(name, ip):
    record_type = 'A'
    domain='nu-tab.com'

    client = DNSimple(os.environ['DNSIMPLE_EMAIL'], os.environ['DNSIMPLE_TOKEN'])

    return client.create_record(name=name, domain=domain,
            record_type=record_type, content=ip)

