from __future__ import print_function
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

PROJECT = 'RedHatEnterpriseLinux7'
AUTO_SPACE = 'Virt-LibvirtAuto'
MANUAL_SPACE = 'Virt-LibvirtQE'
DEFAULT_COMPONENT = 'libvirt'


try:
    class literal(unicode):
        pass
except NameError:
    class literal(str):
        pass


def load_polarion(project, space):
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


@shared_task
def sync_with_polarion():
    """
    Main task, fetch workitems from polarion.
    """
    if not PYLARION_INSTALLED:
        return "Pylarion not installed"
    if not settings.CASELINK_POLARION['ENABLE']:
        return settings.CASELINK_POLARION['REASON']

    current_polarion_workitems = load_polarion(PROJECT, MANUAL_SPACE)
    current_caselink_workitems = models.WorkItem.objects.all()
    polarion_set = set(current_polarion_workitems.keys())
    caselink_set = set(current_caselink_workitems.values_list('id', flat=True))

    updating_set = polarion_set & caselink_set
    deleting_set = caselink_set - polarion_set
    creating_set = polarion_set - caselink_set

    direct_call = current_task.request.id is None
    if not direct_call:
        current_task.update_state(state='Updating database.')

    # Ignore workitems with an up-to-dated timestamp
    for wi_id in updating_set.copy():
        workitem = models.WorkItem.objects.get(id=wi_id)
        if workitem.updated == current_polarion_workitems[wi_id]['updated']:
            updating_set.discard(wi_id)

    # Fetch automation info information
    for wi_id in creating_set | updating_set:
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

            workitem.save()

    for wi_id in deleting_set:
        models.WorkItem.objects.get(id=wi_id).mark_deleted()

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

            workitem.title = wi['title']
            workitem.automation = wi.get('automation', workitem.automation)
            workitem.updated = wi['updated']

            #TODO: Trigger a maitai job by checking automation and history.

            workitem.save()

    return (
        "Created: " + ', '.join(creating_set) + "\n" +
        "Deleted: " + ', '.join(deleting_set) + "\n" +
        "Updated: " + ', '.join(updating_set)
    )
