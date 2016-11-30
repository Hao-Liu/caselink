import re
import difflib
import datetime
import HTMLParser
import suds
from jira import JIRA

from django.core.exceptions import ObjectDoesNotExist
import pytz

from collections import OrderedDict
try:
    from pylarion.document import Document
    from pylarion.enum_option_id import EnumOptionId
    from pylarion.work_item import _WorkItem
    from pylarion.wiki_page import WikiPage
    PYLARION_INSTALLED = True
except ImportError:
    PYLARION_INSTALLED = False
    pass

from django.conf import settings
from caselink import models
from celery import shared_task, current_task
from django.db import transaction

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

    def convert_text(text):
        lines = re.split(r'\<[bB][rR]/\>', text)
        new_lines = []
        for line in lines:
            line = " ".join(line.split())
            line = line.strip()
            if not line:
                continue
            line = HTMLParser.HTMLParser().unescape(line)
            new_lines.append(line)
        return '\n'.join(new_lines)

    def diff_test_steps(before, after):
        if before:
            steps_before = before['steps']['TestStep']
            if not isinstance(steps_before, list):
                steps_before = [steps_before]
        else:
            steps_before = []
        if after:
            steps_after = after['steps']['TestStep']
            if not isinstance(steps_after, list):
                steps_after = [steps_after]
        else:
            steps_after = []

        diff_txt = ''
        if len(steps_before) == len(steps_after):
            for idx in range(len(steps_before)):
                if steps_before:
                    step_before, result_before = [
                        convert_text(text['content'])
                        for text in steps_before[idx].get('values', {}).get('Text', '')]
                else:
                    step_before = result_before = ''
                if steps_after:
                    step_after, result_after = [
                        convert_text(text['content'])
                        for text in steps_after[idx].get('values', {}).get('Text', '')]
                else:
                    step_after = result_after = ''
                if step_before != step_after:
                    diff_txt += 'Step %s changed:\n' % (idx + 1)
                    for line in difflib.unified_diff(step_before.splitlines(1),
                                                     step_after.splitlines(1)):
                        diff_txt += line
                    diff_txt += '\n'
                if result_before != result_after:
                    diff_txt += 'Result %s changed:\n' % (idx + 1)
                    for line in difflib.unified_diff(result_before.splitlines(1),
                                                     result_after.splitlines(1)):
                        diff_txt += line
                    diff_txt += '\n'
        else:
            diff_txt = ('Steps count changed %s --> %s' %
                        (len(steps_before), len(steps_after)))
        return diff_txt

    diffs = []
    for change in changes:
        for diff in change['diffs']['item']:
            field = diff['fieldName']
            # Ignore irrelevant properties changing
            if field in [
                    'updated', 'outlineNumber', 'caseautomation', 'status',
                    'previousStatus', 'approvals', 'tcmscaseid', 'caseimportance']:
                continue

            # Ignore parent item changing
            if (field == 'linkedWorkItems' and
                    diff['added'] and diff['removed'] and
                    len(diff['added']['item']) == 1 and
                    len(diff['removed']['item']) == 1 and
                    diff['added']['item'][0]['role']['id'] == 'parent' and
                    diff['removed']['item'][0]['role']['id'] == 'parent'):
                continue

            result_diff = {'field': field, 'added': [], 'removed': [],
                           'changed': ''}

            if diff['added']:
                adds = diff['added']['item']
                for add in adds:
                    result_diff['added'].append(add)

            if diff['removed']:
                removes = diff['removed']['item']
                for remove in removes:
                    result_diff['removed'].append(remove)

            if 'before' in diff or 'after' in diff:
                before = diff.get('before', '')
                after = diff.get('after', '')

                if field == 'testSteps':
                    step_change = diff_test_steps(before, after)
                    if step_change:
                        result_diff['changed'] = diff_test_steps(before, after)
                        diffs.append(result_diff)
                    continue

                if 'id' in before:
                    before = before['id']
                if 'id' in after:
                    after = after['id']
                if 'content' in before:
                    before = convert_text(before['content'])
                if 'content' in after:
                    after = convert_text(after['content'])
                before += '\n'
                after += '\n'

                diff_txt = ''
                for line in difflib.unified_diff(
                        before.splitlines(1),
                        after.splitlines(1)):
                    diff_txt += line
                result_diff['changed'] = diff_txt
                diffs.append(result_diff)
    return diffs


def add_jira_comment(jira_id, comment):
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


def info_maitai_workitem_changed(wi_instance):
    pass


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
                workitem.changes = workitem_changes
                if workitem.automation == 'automated':
                    if workitem.jira_id:
                        add_jira_comment(workitem.jira_id,
                                         comment="Caselink Changed: %s" % workitem_changes
                                         )
                    else:
                        info_maitai_workitem_changed(workitem)
                else:
                    if workitem.jira_id:
                        add_jira_comment(workitem.jira_id,
                                         comment="Caselink Changed: %s" % workitem_changes
                                         )

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
