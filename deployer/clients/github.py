import os

import requests

auth = (os.environ['GITHUB_USERNAME'], os.environ['GITHUB_TOKEN'])
base_url = 'https://api.github.com/'

def _post(path, **data):
    url = '{0}{1}'.format(base_url, path)
    response = requests.post(url, auth=auth, json=data)
    return response.json()

def create_deployment(user, repo, ref):
    path = 'repos/{0}/{1}/deployments'.format(user, repo)
    return _post(path, ref=ref, auto_merge=False, required_contexts=[])

def create_deployment_status(user, repo, deploy_id, state, deploy_url=''):
    path = 'repos/{0}/{1}/deployments/{2}/statuses'.format(user, repo, deploy_id)
    return _post(path, state=state, environment_url=deploy_url)
