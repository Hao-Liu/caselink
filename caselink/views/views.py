import logging

from django.http import JsonResponse
from django.shortcuts import render
from django.db import connection

from caselink.form import MaitaiAutomationRequest
from caselink.models import *
from caselink.serializers import *


def a2m(request):
    form = MaitaiAutomationRequest()
    return render(request, 'caselink/a2m.html')


def m2a(request):
    form = MaitaiAutomationRequest()
    return render(request, 'caselink/m2a.html', {'maitai_automation_form': form})


def index(request):
    return render(request, 'caselink/index.html')


def data(request):
    #TODO: sql too redundant
    request_type = request.GET.get('type', 'm2a')
    pk = request.GET.get('pk', None)

    def dictfetchall(cursor):
        "Return all rows from a cursor as a dict"
        columns = [col[0] for col in cursor.description]
        return [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]

    json_list = []

    if request_type == 'a2m':
        cursor = connection.cursor()
        sql = """
        select
        caselink_autocase.id AS "case",
        caselink_autocase.pr AS "pr",
        caselink_autocase.framework_id AS "framework",
        caselink_caselink.title as "title",
        caselink_caselink.workitem_id as "polarion"
        from
        ((
        caselink_autocase
        left join caselink_caselink_autocases on caselink_autocase.id = caselink_caselink_autocases.autocase_id)
        left join caselink_caselink on caselink_caselink_autocases.caselink_id = caselink_caselink.id)
        order by "case"
        """
        cursor.execute(sql)

        for autocase in dictfetchall(cursor):
            autocase_id = autocase['case']
            framework = autocase['framework']
            pr = autocase['pr']
            if len(json_list) == 0 or json_list[-1]['case'] != autocase_id:
                json_list.append({
                    'case': autocase_id,
                    'framework': framework,
                    'pr': pr,
                    'components': [],
                    'title': [],
                    'polarion': [],
                    'errors': [],
                    'documents': [],
                })
            for key in ['title', 'polarion', ]:
                if autocase[key]:
                    json_list[-1].get(key).append(autocase[key])

        cursor.execute(
            """
            select
            caselink_autocase.id AS "case",
            caselink_error.message AS "errors"
            from
            ((
            caselink_autocase
            inner join caselink_autocase_errors on caselink_autocase.id = caselink_autocase_errors.autocase_id)
            left join caselink_error on caselink_error.id = caselink_autocase_errors.error_id)
            order by "case";
            """
        )

        pos = 0;
        for autocase in dictfetchall(cursor):
            while json_list[pos]['case'] != autocase['case']:
                pos += 1
            json_list[pos].get('errors').append(autocase['errors'])

        cursor.execute(
            """
            select
            caselink_autocase.id AS "case",
            caselink_autocase_components.component_id AS "component"
            from
            (
            caselink_autocase
            inner join caselink_autocase_components on caselink_autocase.id = caselink_autocase_components.autocase_id)
            order by "case";
            """
        )

        pos = 0;
        for autocase in dictfetchall(cursor):
            while json_list[pos]['case'] != autocase['case']:
                pos += 1
            json_list[pos].get('components').append(autocase['component'])

        cursor.execute(
            """
            select
            caselink_autocase.id AS "case",
            caselink_workitem_documents.document_id as "documents"
            from
            (((
            caselink_autocase
            inner join caselink_caselink_autocases on caselink_autocase.id = caselink_caselink_autocases.autocase_id)
            left join caselink_caselink on caselink_caselink_autocases.caselink_id = caselink_caselink.id)
            inner join caselink_workitem_documents on caselink_workitem_documents.workitem_id = caselink_caselink.workitem_id)
            order by "case";
            """
        )

        pos = 0;
        for autocase in dictfetchall(cursor):
            while json_list[pos]['case'] != autocase['case']:
                pos += 1
            json_list[pos].get('documents').append(autocase['documents'])

    elif request_type == 'm2a':
        #TODO: M2m is not well handled here.
        cursor = connection.cursor()

        sql = """
        select
        caselink_workitem.id AS "polarion",
        caselink_workitem.title AS "title",
        caselink_workitem.automation AS "automation",
        caselink_workitem.need_automation AS "need_automation",
        caselink_workitem.maitai_id AS "maitai_id",
        caselink_caselink_autocases.autocase_id as "cases",
        caselink_caselink.autocase_pattern as "patterns",
        caselink_error.message as "errors"
        from
        ((((
        caselink_workitem
        left join caselink_caselink on caselink_caselink.workitem_id = caselink_workitem.id)
        left join caselink_caselink_errors on caselink_caselink_errors.caselink_id = caselink_caselink.id)
        left join caselink_error on caselink_error.id = caselink_caselink_errors.error_id)
        left join caselink_caselink_autocases on caselink_caselink_autocases.caselink_id = caselink_caselink.id)
        where caselink_workitem.type <> 'heading' %s
        order by "polarion"
        """
        if pk:
            sql = sql % "and caselink_workitem.id = %s"
            cursor.execute(sql, [pk])
        else:
            sql = sql % ""
            cursor.execute(sql)

        for workitem in dictfetchall(cursor):
            w_id = workitem['polarion']
            if len(json_list) != 0 and json_list[-1]['polarion'] == w_id:
                pass
            else:
                json_list.append({
                    'polarion': w_id,
                    'title': workitem['title'],
                    'automation': workitem['automation'],
                    'need_automation': workitem['need_automation'],
                    'maitai_id': workitem['maitai_id'],
                    'patterns': [],
                    'cases': [],

                    'errors': [],
                    'documents': [],
                })
            for key in ['cases', 'patterns', 'errors']:
                if workitem[key] and workitem[key] not in json_list[-1].get(key):
                    json_list[-1].get(key).append(workitem[key])

        sql = """
        select
        caselink_workitem.id AS "polarion",
        caselink_error.message as "errors"
        from
        ((
        caselink_workitem
        inner join caselink_workitem_errors on caselink_workitem.id = caselink_workitem_errors.workitem_id)
        left join caselink_error on caselink_error.id = caselink_workitem_errors.error_id)
        where caselink_workitem.type <> 'heading' %s
        order by "polarion";
        """

        if pk:
            sql = sql % "and caselink_workitem.id = %s"
            cursor.execute(sql, [pk])
        else:
            sql = sql % ""
            cursor.execute(sql)


        pos = 0;
        for workitem in dictfetchall(cursor):
            while json_list[pos]['polarion'] != workitem['polarion']:
                pos += 1
            json_list[pos].get('errors').append(workitem['errors'])

        sql = """
        select
        caselink_workitem.id AS "polarion",
        caselink_workitem_documents.document_id as "documents"
        from
        (
        caselink_workitem
        inner join caselink_workitem_documents on caselink_workitem.id = caselink_workitem_documents.workitem_id)
        where caselink_workitem.type <> 'heading' %s
        order by "polarion";
        """

        if pk:
            sql = sql % "and caselink_workitem.id = %s"
            cursor.execute(sql, [pk])
        else:
            sql = sql % ""
            cursor.execute(sql)

        pos = 0;
        for workitem in dictfetchall(cursor):
            while json_list[pos]['polarion'] != workitem['polarion']:
                pos += 1
            json_list[pos].get('documents').append(workitem['documents'])

    return JsonResponse({'data': json_list})
