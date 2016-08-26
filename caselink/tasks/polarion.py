from __future__ import print_function

from collections import OrderedDict
from pylarion.document import Document
from pylarion.enum_option_id import EnumOptionId
from pylarion.work_item import _WorkItem
from pylarion.wiki_page import WikiPage

from caselink import models
from celery import shared_task, current_task


PROJECT = 'RedHatEnterpriseLinux7'
AUTO_SPACE = 'Virt-LibvirtAuto'
MANUAL_SPACE = 'Virt-LibvirtQE'
DEFAULT_COMPONENT = 'libvirt'


class literal(unicode):
    pass


def load_polarion(project, space, load_automation=False):
    """
    Load all Manual cases with given project and spave, return a dictionary,
    keys are workitem id, values are dicts presenting workitem attributes.
    """
    workitem_fields_to_load = ['work_item_id', 'type', 'title', 'updated']
    direct_call = current_task.request.id is None

    def flatten_cases(cases):
        all_cases = {}
        for doc_id, doc in cases['documents'].items():
            for wi_id, wi in doc['work_items'].items():
                wi_entry = all_cases.setdefault(wi_id, wi)
                wi_entry.setdefault('documents', []).append(doc_id)
        return all_cases

    obj = OrderedDict([
        ('project', literal(project)),
        ('space', literal(space)),
        ('documents', OrderedDict()),
    ])
    docs = Document.get_documents(
        project, space, fields=['document_id', 'title', 'type', 'updated', 'project_id'])
    for doc_idx, doc in enumerate(docs):
        if not direct_call:
            current_task.update_state(state='PROGRESS',
                                      meta={'current': doc_idx, 'total': len(docs)})
        obj_doc = OrderedDict([
            ('title', literal(doc.title)),
            ('type', literal(doc.type)),
            ('project', project),
            ('work_items', OrderedDict()),
            ('updated', doc.updated),
        ])
        wis = doc.get_work_items(None, True, fields=workitem_fields_to_load)
        for wi_idx, wi in enumerate(wis):
            obj_wi = OrderedDict([
                ('title', literal(wi.title)),
                ('type', literal(wi.type)),
                ('project', project),
                ('updated', wi.updated),
            ])
            obj_doc['work_items'][literal(wi.work_item_id)] = obj_wi
        obj['documents'][literal(doc.document_id)] = obj_doc
    cases = flatten_cases(obj)
    if load_automation:
        sync_automation(cases, mode="poll")
    return cases


def sync_automation(workitem_dict, mode="poll"):
    """
    Automation attribute is a custom column and we fetch it sperately.
    :param workitem_dict: A dictionary contains all workitems need to sync.
        eg. {'RHEL-1234': {'automation': False}}
    :param mode: "poll" or "push", poll will override attributes in given dict,
        push will override polarion
    """
    # TODO: Find a way to fetch all needed attributes all in once,
    direct_call = current_task.request.id is None
    current, total = 0, len(workitem_dict.keys())
    for wi_id, wi in workitem_dict.items():
        current += 1
        if not direct_call:
            current_task.update_state(state='PROGRESS',
                                      meta={'current': current, 'total': total})
        polarion_wi = _WorkItem(project_id=PROJECT, work_item_id=wi_id)
        if mode == "poll":
            try:
                for custom in polarion_wi._suds_object.customFields.Custom:
                    if custom.key == 'caseautomation':
                        wi['automation'] = custom.value.id
            except AttributeError:
                # Skip heading / case with no automation attribute
                pass

        elif mode == "push":
            raise RuntimeError('push disabled')
            session = _WorkItem.session
            session.tx_begin()
            if wi['automation'] in ['notautomated', None]: #TODO: What?
                value = EnumOptionId(enum_id='automated')
                wi._set_custom_field('caseautomation', value._suds_object)
            session.tx_commit()


@shared_task
def sync_with_polarion():
    direct_call = current_task.request.id is None
    if not direct_call:
        current_task.update_state(state='PROGRESS')
    current_polarion_workitems = load_polarion(PROJECT, MANUAL_SPACE)
    current_caselink_workitems = models.WorkItem.objects.all()

    polarion_set = set(current_polarion_workitems.keys())
    caselink_set = set(current_caselink_workitems.values_list('id', flat=True))

    new_wi = polarion_set - caselink_set
    deleted_wi = caselink_set - polarion_set

    for wi_id in new_wi:
        wi = current_polarion_workitems[wi_id]
        workitem = models.WorkItem(
            id=wi_id,
            title=wi['title'],
            type=wi['type'],
        )

        workitem.project, created = models.Project.objects.get_or_create(name=wi['project'])

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

        if 'automation' in wi:
            workitem.automation = 'automated' if wi['automation'] == 'automated' else 'notautomated'

        if 'errors' in wi:
            for error_message in wi['errors']:
                error, created = models.Error.objects.get_or_create(message=error_message)
                if created:
                    error.id = error_message
                    error.workitems.add(workitem)
                    error.save()

        workitem.save()

    for wi_id in deleted_wi:
        models.WorkItem.objects.get(id=wi_id).delete()

    return "Created: " + ', '.join(new_wi) + "\nDeleted: " + ', '.join(deleted_wi)
