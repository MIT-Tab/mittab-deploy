import os

from github import Github

__hub = Github(os.environ['GITHUB_BOT_TOKEN'])
__mittab = __hub.get_repo('mit-tab/mit-tab')
__create_deploy_comment = """
Would you like to deploy this pull request? If so, comment `@mittab-bot deploy`

The deploy will include the commit at the time of the comment. Any new commits
will be automatically deployed.

By default, the server will be deactivated in 7 days or when this PR is closed.
If you want to deactivate it earlier, you can comment `@mittab-bot delete`
"""


def post_deploy_option(pr_number):
    return __post_comment(pr_number, __create_deploy_comment)


def __post_comment(pr_number, body):
    __mittab.get_pull(pr_number).create_issue_comment(body)
