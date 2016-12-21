import re
import difflib
import datetime
import suds
import requests

import sys

if sys.version_info >= (3, 0):
    from html.parser import HTMLParser
else:
    import HTMLParser

import pytz
from jira import JIRA

from collections import OrderedDict
from django.conf import settings
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from caselink import models
from caselink.utils.maitai import CaseUpdateWorkflow, WorkflowDisabledException

from celery import shared_task, current_task

try:
    from pylarion.document import Document
    from pylarion.enum_option_id import EnumOptionId
    from pylarion.work_item import _WorkItem
    from pylarion.wiki_page import WikiPage
    PYLARION_INSTALLED = True
except ImportError:
    PYLARION_INSTALLED = False
    pass


PROJECT = settings.CASELINK_POLARION['PROJECT']
SPACES = settings.CASELINK_POLARION['SPACES']
DEFAULT_COMPONENT = 'n/a'


try:
    class literal(unicode):
        pass
except NameError:
    class literal(str):
        pass


def load_polarion(project, spaces):
    """
    Load all Manual cases with given project and spave, return a dictionary,
    keys are workitem id, values are dicts presenting workitem attributes.
    """
    # If called as a celery task...
    direct_call = current_task.request.id is None

    utc = pytz.UTC

    def flatten_cases(docs):
        all_cases = {}
        for doc_id, doc in docs.items():
            for wi_id, wi in doc['work_items'].items():
                wi_entry = all_cases.setdefault(wi_id, wi)
                wi_entry.setdefault('documents', []).append(doc_id)
        return all_cases

    doc_dict = {}
    for space in spaces:
        docs = Document.get_documents(
            project, space, fields=['document_id', 'title', 'type', 'updated', 'project_id'])
        for doc_idx, doc in enumerate(docs):
            if not direct_call:
                current_task.update_state(state='Fetching documents',
                                          meta={'current': doc_idx, 'total': len(docs)})
            obj_doc = OrderedDict([
                ('title', literal(doc.title)),
                ('type', literal(doc.type)),
                ('project', project),
                ('work_items', OrderedDict()),
                ('updated', utc.localize(doc.updated)),
            ])
            wis = doc.get_work_items(None, True, fields=['work_item_id', 'type', 'title', 'updated'])
            for wi_idx, wi in enumerate(wis):
                obj_wi = OrderedDict([
                    ('title', literal(wi.title)),
                    ('type', literal(wi.type)),
                    ('project', project),
                    ('updated', utc.localize(wi.updated)),
                ])
                obj_doc['work_items'][literal(wi.work_item_id)] = obj_wi
            doc_dict[literal(doc.document_id)] = obj_doc
    cases = flatten_cases(doc_dict)
    return cases


def get_history_of_wi(wi_id, project, service=None, start=None):
    uri = 'subterra:data-service:objects:/default/%s${WorkItem}%s' % (
        PROJECT, wi_id)
    if service is None:
        service = _WorkItem.session.tracker_client.service
    changes = service.generateHistory(uri)
    if start:
        latest_changes = []
        for change in changes:
            if change.date > start:
                latest_changes.append(change)
        return latest_changes
    else:
        return changes


def get_automation_of_wi(wi_id):
    """
    Get the automation status of a workitem.
    """
    ret = 'notautomated'
    polarion_wi = _WorkItem(project_id=PROJECT, work_item_id=wi_id)
    try:
        for custom in polarion_wi._suds_object.customFields.Custom:
            if custom.key == 'caseautomation':
                ret = custom.value.id
    except AttributeError:
        # Skip heading / case with no automation attribute
        pass
    return ret


def get_recent_changes(wi_id, service=None, start_time=None):
    """
    Get changes after start_time, return a list of suds objects.
    """
    def suds_2_object(suds_obj):
        obj = OrderedDict()
        for key, value in suds_obj.__dict__.items():
            if key.startswith('_'):
                continue

            if isinstance(value, suds.sax.text.Text):
                value = literal(value.strip())
            elif isinstance(value, (bool, int, datetime.date, datetime.datetime)):
                pass
            elif value is None:
                pass
            elif isinstance(value, list):
                value_list = []
                for elem in value:
                    value_list.append(suds_2_object(elem))
                value = value_list
            elif hasattr(value, '__dict__'):
                value = suds_2_object(value)
            else:
                print('Unhandled value type: %s' % type(value))

            obj[key] = value
        return obj

    utc = pytz.UTC

    uri = 'subterra:data-service:objects:/default/%s${WorkItem}%s' % (
        PROJECT, wi_id)
    if service is None:
        service = _WorkItem.session.tracker_client.service
    changes = service.generateHistory(uri)
    latest_changes = []
    for change in changes:
        if not start_time or utc.localize(change.date) > start_time:
            latest_changes.append(suds_2_object(change))
    return latest_changes


def filter_changes(changes):
    """
    Filter out irrelevant changes, return a list of dict.
    """

    def _convert_text(text):
        lines = re.split(r'\<[bB][rR]/\>', text)
        new_lines = []
        for line in lines:
            line = " ".join(line.split())
            if line:
                line = HTMLParser.HTMLParser().unescape(line)
                new_lines.append(line)
        return '\n'.join(new_lines)

    def diff_test_steps(before, after):
        """Will break if steps are not in a two columns table (Step, Result)"""
        def _get_steps_for_diff(data):
            ret = []
            if not data:
                return ret
            else:
                steps = data.get('steps', {}).get('TestStep', [])
                if not isinstance(steps, list):
                    steps = [steps]
                for idx, raw_step in enumerate(steps):
                    step, result = [
                        _convert_text(text['content'])
                        for text in raw_step['values']['Text']]
                    ret.extend([
                        "Step:",
                        step or ",<empty>",
                        "Expected result:",
                        result or "<empty>",
                    ])
            return ret

        steps_before, steps_after = _get_steps_for_diff(before), _get_steps_for_diff(after)

        diff_txt = '\n'.join(difflib.unified_diff(steps_before, steps_after))

        return diff_txt

    summary = ""
    for change in changes:
        creation = change['creation']
        empty = change['empty']
        invalid = change['invalid']
        date = change['date']
        diffs = change['diffs']
        revision = change['revision']
        user = change['user']

        if creation:
            summary += "User %s create this workitem at %s\n" % (user, date)
            if empty:
                continue

        if diffs:
            for diff in diffs['item']:
                before = diff.get('before', None)
                after = diff.get('after', None)
                field = diff['fieldName']

                # Ignore irrelevant properties changing
                if field not in ['testSteps', 'teardown', 'setup', 'environment', 'description']:
                    continue

                if field == 'testSteps':
                    summary += "User %s changed test steps at %s:\n%s\n" % (user, date, diff_test_steps(before, after))
                    continue

                else:
                    def _get_text_content(data):
                        if not data:
                            return ''
                        elif not isinstance(data, (str, unicode)):
                            if 'id' in data: # It'a Enum?
                                data = data['id']
                            elif 'content' in data: # It's a something else...
                                data = _convert_text(data['content'])
                        return data

                    before, after = _get_text_content(before), _get_text_content(after)

                    if not before or not after:
                        summary += "User %s changed %s at %s, details not avaliable\n" % (user, field, date)
                        continue

                    else:
                        detail_diff = ''.join(
                            difflib.unified_diff(before.splitlines(True), after.splitlines(True)))
                        summary += "User %s changed %s at %s:\n%s\n" % (user, field, date, detail_diff)
    return summary


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


def info_maitai_workitem_changed(workitem, assignee=None, labels=None):
    workflow = CaseUpdateWorkflow(workitem.id, workitem.title,
                                  assignee=assignee, label=labels)
    try:
        res = workflow.start()
    except WorkflowDisabledException as error:
        return False

    workitem.maitai_id = res['id']
    workitem.need_automation = True
    return True


@shared_task
def sync_with_polarion():
    """
    Main task, fetch workitems from polarion.
    """
    if not PYLARION_INSTALLED:
        return "Pylarion not installed"
    if not settings.CASELINK_POLARION['ENABLE']:
        return settings.CASELINK_POLARION['REASON']

    current_polarion_workitems = load_polarion(PROJECT, SPACES)
    current_caselink_workitems = models.WorkItem.objects.all()
    polarion_set = set(current_polarion_workitems.keys())
    caselink_set = set(current_caselink_workitems.values_list('id', flat=True))

    updating_set = polarion_set & caselink_set
    deleting_set = caselink_set - polarion_set
    creating_set = polarion_set - caselink_set
    mark_deleting_set = set()

    direct_call = current_task.request.id is None
    if not direct_call:
        current_task.update_state(state='Updating database.')

    # Ignore workitems with an up-to-dated timestamp
    for wi_id in updating_set.copy():
        workitem = models.WorkItem.objects.get(id=wi_id)
        if workitem.updated == current_polarion_workitems[wi_id]['updated']:
            updating_set.discard(wi_id)

    # Fetch automation info information
    length = len(creating_set | updating_set)
    for idx, wi_id in enumerate(creating_set | updating_set):
        if not direct_call:
            current_task.update_state(state='Fetching detail',
                                      meta={'current': idx, 'total': length})
        current_polarion_workitems[wi_id]['automation'] = get_automation_of_wi(wi_id)

    for wi_id in creating_set:
        with transaction.atomic():
            wi = current_polarion_workitems[wi_id]
            workitem = models.WorkItem(
                id=wi_id,
                title=wi['title'],
                type=wi['type'],
                updated=wi['updated'],
                automation=wi.get('automation', 'notautomated')
            )

            workitem.project, created = models.Project.objects.get_or_create(name=wi['project'])

            # Commit db changes, or there could be a Integrity error.
            workitem.save()

            for doc_id in wi['documents']:
                doc, created = models.Document.objects.get_or_create(id=doc_id)
                if created:
                    doc.title = doc_id
                    doc.component = models.Component.objects.get_or_create(name=DEFAULT_COMPONENT)
                doc.workitems.add(workitem)
                doc.save()

            if 'arch' in wi:
                for arch_name in wi['arch']:
                    arch, _ = models.Arch.objects.get_or_create(name=arch_name)
                    arch.workitems.add(workitem)
                    arch.save()

            if 'errors' in wi:
                for error_message in wi['errors']:
                    error, created = models.Error.objects.get_or_create(message=error_message)
                    if created:
                        error.id = error_message
                        error.workitems.add(workitem)
                        error.save()

            workitem.error_check()
            workitem.save()

    for wi_id in deleting_set.copy():
        wi = models.WorkItem.objects.get(id=wi_id)
        related_wis = wi.error_related.all()
        if not any([getattr(wi, data) for data in wi._user_data]):
            if not wi.caselinks.exists():
                wi.delete()
                for wi_r in related_wis:
                    wi_r.error_check()
                continue
        wi.mark_deleted()
        mark_deleting_set.add(wi_id)
        deleting_set.discard(wi_id)

    for wi_id in updating_set:
        with transaction.atomic():
            wi = current_polarion_workitems[wi_id]
            workitem = models.WorkItem.objects.get(id=wi_id)

            # In case a old deleted case show up again in polarion.
            workitem.mark_notdeleted()

            workitem.documents.clear()
            for doc_id in wi['documents']:
                doc, created = models.Document.objects.get_or_create(id=doc_id)
                if created:
                    doc.title = doc_id
                    doc.component = models.Component.objects.get_or_create(name=DEFAULT_COMPONENT)
                doc.workitems.add(workitem)
                doc.save()

            #TODO: Create JIRA comment
            workitem_changes = get_recent_changes(wi_id, start_time=workitem.updated)
            workitem_changes = filter_changes(workitem_changes)

            workitem.title = wi['title']
            workitem.automation = wi.get('automation', workitem.automation)

            if workitem_changes:
                if workitem.automation == 'automated':
                    if workitem.jira_id:
                        add_jira_comment(workitem.jira_id,
                                         comment="Caselink Changed: %s" % workitem_changes
                                         )
                    if not workitem.maitai_id:
                        info_maitai_workitem_changed(workitem)
                        # Mark as changed on caselink
                        workitem.changes = workitem_changes
                    else:
                        pass
                        #raise RuntimeError("Automated Workitem have a pending maitai progress")
                elif workitem.automation != 'manualonly':
                    if workitem.maitai_id:
                        if workitem.jira_id:
                            add_jira_comment(workitem.jira_id,
                                             comment="Caselink Changed: %s" % workitem_changes
                                             )
                        else:
                            # Mark as changed on caselink
                            workitem.changes = workitem_changes
                            #raise RuntimeError("Not automated Workitem with a pending maitai progress don't have a JIRA task")
                    else:
                        if workitem.jira_id:
                            add_jira_comment(workitem.jira_id,
                                             comment="Caselink Changed: %s" % workitem_changes
                                             )
                        else:
                            # Just a normal, not automated test case, do nothing
                            pass

            #TODO: use comfirmed as a standlone attribute
            workitem.comfirmed = workitem.updated

            workitem.updated = wi['updated']

            #TODO: Trigger a maitai job by checking automation and history.
            workitem.save()
            workitem.error_check()

    return (
        "Created: " + ', '.join(creating_set) + "\n" +
        "Deleted: " + ', '.join(deleting_set) + "\n" +
        "Mark Deleted: " + ', '.join(mark_deleting_set) + "\n" +
        "Updated: " + ', '.join(updating_set)
    )
