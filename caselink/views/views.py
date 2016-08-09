import logging

from django.http import HttpResponse
from django.http import JsonResponse
from django.template import RequestContext, loader
from django.forms.models import model_to_dict
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404

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
        for auto_case in AutoCase.objects.all():
            workitems = []
            for caselink in auto_case.caselinks.all():
                workitems.append(caselink.workitem)

            json_case = {
                "errors": [],
                "polarion": [],
                "title": [],
                "automation": [],
                "project": [],
                "documents": [],
                "commit": [],
                "type": [],
                "id": [],
                "archs": []
            }

            for workitem in workitems:
                item_case = workitem_to_json(workitem)
                if item_case is None:
                    continue
                for key in item_case:
                    if key == 'errors':
                        continue
                    try:
                        json_case[key].append(item_case[key])
                    except KeyError:
                        json_case[key] = [item_case[key]];

            json_case['case'] = auto_case.id
            json_case['errors'].append([err.message for err in auto_case.errors.all()])
            json_list.append(json_case)

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
