from django.http import JsonResponse
from django.http import Http404
from django.db import IntegrityError, OperationalError, transaction

from caselink.models import *
from caselink.tasks import *

from celery.task.control import inspect
from celery.result import AsyncResult


def task(request):
    cancel = True if request.GET.get('cancel', '') == 'true' else False

    workers = inspect()
    task_status = {}
    if workers.active() is None:
        return JsonResponse(task_status)
    for worker, tasks in workers.active().items():
        for task in tasks:
            res = AsyncResult(task['id'])
            task_status[task['name']] = {
                'state': res.state,
                'meta': res.info
            }
            if cancel:
                res.revoke(terminate=True)
                task_status[task['name']]['canceled'] = True
    return JsonResponse(task_status)


def trigger(request):

    operations = []

    async = True if request.GET.get('async', '') == 'true' else False

    task_to_trigger = request.GET.getlist('trigger', [])
    if 'linkage_error_check' in task_to_trigger:
        operations.append(update_linkage_error)
    if 'autocase_error_check' in task_to_trigger:
        operations.append(update_autocase_error)
    if 'manualcase_error_check' in task_to_trigger:
        operations.append(update_manualcase_error)
    if 'dump_all_db' in task_to_trigger:
        operations.append(dump_all_db)

    if len(operations) > 0:
        if not async:
            try:
                for op in operations:
                    with transaction.atomic():
                        op()
            except OperationalError:
                return JsonResponse({'message': 'DB Locked'})
            except IntegrityError:
                return JsonResponse({'message': 'Integrity Check Failed'})
            return JsonResponse({'message': 'done'})
        else:
            for op in operations:
                op.apply_async()
            return JsonResponse({'message': 'queued'})



def backup(request):
    return JsonResponse({
        'message': 'Not implemented'}
    )


def backup_download(request, filename=None):
    return JsonResponse({
        'filename': filename,
        'message': 'Not implemented'}
    )


def restore(request, filename=None):
    return JsonResponse({
        'filename': filename,
        'message': 'Not implemented'}
    )


def upload(request):
    return JsonResponse({
        'message': 'Not implemented'}
    )


