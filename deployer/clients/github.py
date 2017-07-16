import os

import requests

auth = (os.environ['GITHUB_USERNAME'], os.environ['GITHUB_TOKEN'])
base_url = 'https://api.github.com/'

def _post(path, **data):
    url = '{0}{1}'.format(base_url, path)
    response = requests.post(url, auth=auth, json=data)
    return response.json()

def create_deployment(repo_path, ref):
    path = 'repos/{0}/deployments'.format(repo_path)
    return _post(path, ref=ref, auto_merge=False, required_contexts=[])

def create_deployment_status(repo_path, deploy_id, state, deploy_url=''):
    path = 'repos/{0}/deployments/{1}/statuses'.format(repo_path, deploy_id)
    return _post(path, state=state, environment_url=deploy_url)
