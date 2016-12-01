import os
import requests
from django.conf import settings

from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest, HttpResponseServerError
from django.http import Http404
from django.db import IntegrityError, OperationalError, transaction
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render_to_response
from django.shortcuts import get_object_or_404
from django import forms

from caselink.models import *
from caselink.tasks.common import *
from caselink.tasks.polarion import sync_with_polarion

from celery.task.control import inspect
from celery.result import AsyncResult
from djcelery.models import TaskMeta

from caselink.form import MaitaiAutomationRequest

import xml.etree.ElementTree as ET

BASE_DIR = settings.BASE_DIR
BACKUP_DIR = BASE_DIR + "/caselink/backups"

def _get_tasks():
    workers = inspect(['celery@localhost']).active()
    if workers is None:
        return None
    return workers.items()


def _get_finished_tasks_results(number):
    ret = []
    task_metas = TaskMeta.objects.order_by('-date_done')[0:number-1]
    for i in task_metas:
        ret.append(i.to_dict())
        ret[-1]['result'] = "%s" % ret[-1]['result']
    return ret


def _get_running_tasks_status():
    task_status = []
    _tasks = _get_tasks()
    if not _tasks:
        return {}
    for worker, tasks in _tasks:
        for task in tasks:
            res = AsyncResult(task['id'])
            task_status.append({
                'name': task['name'],
                'id': task['id'],
                'state': res.state,
                'meta': res.info
            })
    return task_status


def _cancel_task():
    task_status = {}
    tasks = _get_tasks()
    if not tasks:
        return {}
    for worker, tasks in _get_tasks():
        for task in tasks:
            res = AsyncResult(task['id'])
            task_status[task['name']] = {
                'state': res.state,
                'meta': res.info
            }
            res.revoke(terminate=True)
            task_status[task['name']]['canceled'] = True
    return task_status


def _schedule_task(task_name, async_task=True):
    tasks_map = {
        'linkage_error_check': update_linkage_error,
        'autocase_error_check': update_autocase_error,
        'manualcase_error_check': update_manualcase_error,
        'dump_all_db': dump_all_db,
        'polarion_sync': sync_with_polarion,
    }
    if task_name in tasks_map:
        task = tasks_map[task_name]
    else:
        return {'message': 'Unknown task'}

    if not async_task:
        try:
            with transaction.atomic():
                task()
        except OperationalError:
            return {'message': 'DB Locked'}
        except IntegrityError:
            return {'message': 'Integrity Check Failed'}
        return {'message': 'done'}
    else:
        task.apply_async()
        return {'message': 'queued'}


def _get_backup_list():
    backup_list = []
    for file in os.listdir(BACKUP_DIR):
        if file.endswith(".yaml"):
            size = os.path.getsize(BACKUP_DIR + "/" + file)
            backup_list.append({
                'file': file,
                'size': size,
            })
    return backup_list


def overview(request):
    return JsonResponse({
        'tasks': _get_running_tasks_status(),
        'results': _get_finished_tasks_results(7),
        'backups': _get_backup_list(),
    })


def task(request):
    return JsonResponse(_get_running_tasks_status())


def trigger(request):
    results = {}

    cancel = True if request.GET.get('cancel', '') == 'true' else False
    async = True if request.GET.get('async', '') == 'true' else False
    tasks = request.GET.getlist('trigger', [])

    if cancel:
        result = _cancel_task()
    elif len(tasks) > 0:
        for task in tasks:
            results[task] = _schedule_task(task, async_task=async)

    return JsonResponse(results)


def backup(request):
    return JsonResponse({
        'message': 'Not implemented'}
    )


def backup_instance(request, filename=None):
    delete = True if request.GET.get('delete', '') == 'true' else False
    if delete:
        try:
            os.remove(BACKUP_DIR + "/" + filename)
        except OSError:
            raise HttpResponseServerError()
        else:
            return JsonResponse({'message': 'Done'})

    with open(BACKUP_DIR + "/" + filename) as file:
        data = file.read()
    response = HttpResponse(data, content_type='text/plain')
    response['Content-Length'] = os.path.getsize(BACKUP_DIR + "/" + filename)
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    return response


def restore(request, filename=None):
    clean_and_restore.apply_async((BACKUP_DIR + "/" + filename,))
    return JsonResponse({
        'filename': filename,
        'message': 'queued'}
    )


def upload(request):
    if request.method == 'POST' and request.FILES['file']:
        i = 0
        while os.path.exists(BACKUP_DIR + "/upload-%s.yaml" % i):
            i += 1
        with open(BACKUP_DIR + "/upload-%s.yaml" % i, "w+") as fl:
            for chunk in request.FILES['file'].chunks():
                fl.write(chunk)
        return render_to_response('caselink/popup.html', {'message': 'Upload successful'})
    else:
        return HttpResponseBadRequest()


def create_maitai_request(request):
    if not settings.CASELINK_MAITAI['ENABLE']:
        reason = (
            settings.CASELINK_MAITAI['REASON'] or 'Maitai disabled, please contact the admin.')
        return JsonResponse({'message': reason}, status=400)

    maitai_request = MaitaiAutomationRequest(request.POST)
    if not maitai_request.is_valid():
        return JsonResponse({'message': "Invalid parameters"}, status=400)

    workitem_ids = maitai_request.cleaned_data['manual_cases'].split()
    assignee = maitai_request.cleaned_data['assignee'].split()
    labels = maitai_request.cleaned_data['labels']

    maitai_pass = settings.CASELINK_MAITAI['PASSWORD']
    maitai_user = settings.CASELINK_MAITAI['USER']
    maitai_url = settings.CASELINK_MAITAI['ADD-URL']

    polarion_url = settings.CASELINK_POLARION['URL']
    project = settings.CASELINK_POLARION['PROJECT']

    ret = {}

    for workitem_id in workitem_ids:
        try:
            wi = WorkItem.objects.get(pk=workitem_id)
        except ObjectDoesNotExist:
            ret[workitem_id] = {"message": "Workitem doesn't exists."}
            continue

        #TODO: remove verify=False
        res = requests.post(maitai_url, params={
            "map_polarionId": workitem_id,
            #TODO: config file
            "map_polarionUrl": "%s/#/project/%s/workitem?id=%s" % (polarion_url, project, str(workitem_id)),
            "map_polarionTitle": wi.title,
            "map_issueAssignee": assignee[0],
            "map_issueLabels": labels
        },
            auth=(maitai_user, maitai_pass), verify=False)

        if res.status_code != 200:
            ret[workitem_id] = {'message': 'Maitai server internal error.'}
            continue

        root = ET.fromstring(res.content)

        process = root.find('process-id').text
        state = root.find('state').text
        id = root.find('id').text
        parentProcessInstanceId = root.find('parentProcessInstanceId').text
        status = root.find('status').text

        if status != 'SUCCESS':
            ret[workitem_id] = {'message': 'Maitai server returns error.'}
            continue

        wi.maitai_id = id
        wi.need_automation = True
        wi.save()

        ret[workitem_id] = {"maitai_id": id}

    return JsonResponse(ret, status=200)
