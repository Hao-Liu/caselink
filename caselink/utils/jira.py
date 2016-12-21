from __future__ import absolute_import

from jira import JIRA
from django.conf import settings

def add_jira_comment(jira_id, comment):
    if not settings.CASELINK_JIRA['ENABLE']:
        return False
    user = settings.CASELINK_JIRA['USER']
    password = settings.CASELINK_JIRA['PASSWORD']
    server = settings.CASELINK_JIRA['SERVER']
    basic_auth = (user, password)
    options = {
        'server': server,
        'verify': False,
    }
    jira = JIRA(options, basic_auth=basic_auth)
    jira.add_comment(jira.issue(id=jira_id), comment)
    return True
