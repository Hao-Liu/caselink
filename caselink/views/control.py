import os

from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.http import Http404
from django.db import IntegrityError, OperationalError, transaction
from django.shortcuts import render_to_response
from django import forms

from caselink.models import *
from caselink.tasks import *

from celery.task.control import inspect
from celery.result import AsyncResult

BASE_DIR = 'caselink/backups'

def _get_tasks():
    workers = inspect(['celery@localhost']).active()
    if workers is None:
        return None
    return workers.items()


def _get_tasks_status():
    task_status = {}
    _tasks = _get_tasks()
    if not _tasks:
        return {}
    for worker, tasks in _tasks:
        for task in tasks:
            res = AsyncResult(task['id'])
            task_status[task['name']] = {
                'state': res.state,
                'meta': res.info
            }
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

    if 'linkage_error_check' == task_name:
        operations = update_linkage_error
    elif 'autocase_error_check' == task_name:
        operations = update_autocase_error
    elif 'manualcase_error_check' == task_name:
        operations = update_manualcase_error
    elif 'dump_all_db' == task_name:
        operations = dump_all_db
    else:
        return {'message': 'Unknown task'}

    if not async_task:
        try:
            with transaction.atomic():
                operations()
        except OperationalError:
            return {'message': 'DB Locked'}
        except IntegrityError:
            return {'message': 'Integrity Check Failed'}
        return {'message': 'done'}
    else:
        operations.apply_async()
        return {'message': 'queued'}


def _get_backup_list():
    backup_list = []
    for file in os.listdir(BASE_DIR):
        if file.endswith(".yaml"):
            size = os.path.getsize(BASE_DIR + "/" + file)
            backup_list.append({
                'file': file,
                'size': size,
            })
    return backup_list


def overview(request):
    return JsonResponse({
        'task': _get_tasks_status(),
        'backup': _get_backup_list(),
    })


def task(request):
    return JsonResponse(_get_tasks_status())


def trigger(request):
    results = {}

    cancel = True if request.GET.get('cancel', '') == 'true' else False
    async = True if request.GET.get('async', '') == 'true' else False
    operations = request.GET.getlist('trigger', [])

    if cancel:
        result = _cancel_task()
    elif len(operations) > 0:
        for op in operations:
            results[op] = _schedule_task(op, async_task=async)

    return JsonResponse(results)


def backup(request):
    return JsonResponse({
        'message': 'Not implemented'}
    )


def backup_instance(request, filename=None):
    delete = True if request.GET.get('delete', '') == 'true' else False
    if delete:
        try:
            os.remove(BASE_DIR + "/" + filename)
        except OSError:
            raise HttpResponseServerError()
        else:
            return JsonResponse({'message': 'Done'})

    with open(BASE_DIR + "/" + filename) as file:
        data = file.read()
    response = HttpResponse(data, content_type='text/plain')
    response['Content-Length'] = os.path.getsize(BASE_DIR + "/" + filename)
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    return response


def restore(request, filename=None):
    clean_and_restore.apply_async((BASE_DIR + "/" + filename,))
    return JsonResponse({
        'filename': filename,
        'message': 'queued'}
    )


def upload(request):
    if request.method == 'POST' and request.FILES['file']:
        i = 0
        while os.path.exists(BASE_DIR + "/upload-%s.yaml" % i):
            i += 1
        with open(BASE_DIR + "/upload-%s.yaml" % i, "w+") as fl:
            for chunk in request.FILES['file'].chunks():
                fl.write(chunk)
        return render_to_response('caselink/popup.html', {'message': 'Upload successful'})
    else:
        return HttpResponseBadRequest()
