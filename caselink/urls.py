from django.conf.urls import url

from caselink.views import views, restful, control

urlpatterns = [
    # Views for nagivation/look up
    url(r'^$', views.index, name='index'),
    url(r'^m2a$', views.m2a, name='m2a'),
    url(r'^a2m$', views.a2m, name='a2m'),
    url(r'^data$', views.data, name='data'),

    #RESTful APIs
    url(r'^manual/$', restful.WorkItemList.as_view(), name='workitem'),
    url(r'^manual/(?P<pk>[a-zA-Z0-9\-]+)/$', restful.WorkItemDetail.as_view(), name='workitem_detail'),
    url(r'^manual/(?P<workitem>[a-zA-Z0-9\-\._]+)/link/$', restful.WorkItemLinkageList.as_view(), name='workitem_link_list'),
    url(r'^manual/(?P<workitem>[a-zA-Z0-9\-\._]+)/link/(?P<pattern>[a-zA-Z0-9\-\.\ _]*)/$', restful.WorkItemLinkageDetail.as_view(), name='workitem_link_detail'),

    url(r'^auto/$', restful.AutoCaseList.as_view(), name='auto'),
    url(r'^auto/(?P<pk>[a-zA-Z0-9\-\._]+)/$', restful.AutoCaseDetail.as_view(), name='auto_detail'),

    url(r'^failure/$', restful.AutoCaseFailureList.as_view(), name='auto_failure_list'),
    url(r'^failure/(?P<pk>[a-zA-Z0-9\-\._]+)/$', restful.AutoCaseFailureDetail.as_view(), name='auto_failure_detail'),

    url(r'^link/$', restful.LinkageList.as_view(), name='link'),
    url(r'^link/(?P<pk>[a-zA-Z0-9\-\._]+)/$', restful.LinkageDetail.as_view(), name='link_detail'),

    url(r'^bug/$', restful.BugList.as_view(), name='bug'),
    url(r'^bug/(?P<pk>[a-zA-Z0-9\-\._]+)/$', restful.BugDetail.as_view(), name='bug_detail'),

    # API for get/start tasks, backup/restore
    url(r'^control/$', control.overview, name='task_overview'),
    url(r'^control/task$', control.task, name='task_list'),
    url(r'^control/trigger$', control.trigger, name='task_trigger'),
    url(r'^control/backup$', control.backup, name='backup_list'),
    url(r'^control/backup/(?P<filename>.+\.yaml)$', control.backup_instance, name='backup_download'),
    url(r'^control/restore/(?P<filename>.+\.yaml)$', control.restore, name='restore'),
    url(r'^control/upload$', control.upload, name='upload'),
]
