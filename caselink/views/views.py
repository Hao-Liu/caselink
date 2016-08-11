import logging

from django.http import HttpResponse
from django.http import JsonResponse
from django.template import RequestContext, loader
from django.forms.models import model_to_dict
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from django.db import connection

from caselink.models import *
from caselink.serializers import *


def a2m(request):
    template = loader.get_template('caselink/a2m.html')
    context = RequestContext(request, {})
    return HttpResponse(template.render(context))


def m2a(request):
    template = loader.get_template('caselink/m2a.html')
    context = RequestContext(request, {})
    return HttpResponse(template.render(context))


def index(request):
    template = loader.get_template('caselink/index.html')
    context = RequestContext(request, {})
    return HttpResponse(template.render(context))


def data(request):
    request_type = request.GET.get('type', 'm2a')

    def workitem_to_json(workitem):
        if workitem.type == 'heading':
            return None
        json_case = model_to_dict(workitem)
        json_case['polarion'] = workitem.id
        json_case['documents'] = [doc.id for doc in workitem.documents.all()]
        json_case['errors'] = [error.message for error in workitem.errors.all()]
        return json_case

    json_list = []

    if request_type == 'a2m':
        cursor = connection.cursor()

        def dictfetchall(cursor):
            "Return all rows from a cursor as a dict"
            columns = [col[0] for col in cursor.description]
            return [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]

        cursor.execute(
            """
            select
            caselink_autocase.id AS "case",
            caselink_caselink.title as "title",
            caselink_caselink.workitem_id as "polarion",
            caselink_error.message as "errors",
            caselink_workitem_documents.document_id as "documents"
            from
            (((((
            caselink_autocase
            left join caselink_caselink_autocases on caselink_autocase.id = caselink_caselink_autocases.autocase_id)
            left join caselink_caselink on caselink_caselink_autocases.caselink_id = caselink_caselink.id)
            left join caselink_autocase_errors on caselink_autocase.id = caselink_autocase_errors.autocase_id)
            left join caselink_error on caselink_error.id = caselink_autocase_errors.error_id)
            left join caselink_workitem_documents on caselink_workitem_documents.workitem_id = caselink_caselink.workitem_id)
            order by "case";
            """
        )

        def add_or_update(entry):
            autocase_id = entry['case']
            if len(json_list) != 0 and json_list[-1]['case'] == autocase_id:
                pass
            else:
                json_list.append({'case': autocase_id})
            for key in ['title', 'polarion', 'errors', 'documents']:
                json_list[-1].setdefault(key, []).append(entry[key])

        for autocase in dictfetchall(cursor):
            add_or_update(autocase)

    elif request_type == 'm2a':
        for workitem in WorkItem.objects.all():
            json_case = workitem_to_json(workitem)
            if json_case is None:
                continue
            auto_cases = []
            json_case['patterns'] = []
            try:
                caselinks = workitem.caselinks.all()
                for case in caselinks:
                    json_case['errors'] += [err.message for err in case.errors.all()]
                    json_case['patterns'].append(case.autocase_pattern)
                    for auto_case in case.autocases.all():
                        auto_cases.append(auto_case)
            except ObjectDoesNotExist:
                pass
            json_case['cases'] = [case.id for case in auto_cases]
            json_list.append(json_case)

    return JsonResponse({'data': json_list})
