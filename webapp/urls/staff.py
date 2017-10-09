from django.conf.urls import url
from django.views.generic import TemplateView as Tv
from django.contrib.admin.views.decorators import staff_member_required as staff_required
from webapp.views.staff import base, group_access, group_taskset, group, submission, task

urlpatterns = [

    url(r'^$', base.dashboard, name='staff_dashboard'),
    url(r'^user_list$', base.user_list, name='staff_user_list'),

    # | - groups

    url(r'^group/create/$', group.create, name='staff_group_create'),
    url(r'^group/(?P<group_id>[0-9]+)/$', group.task_list, name='staff_group_tasks'),
    url(r'^group/(?P<group_id>[0-9]+)/edit/$', group.edit, name='staff_group_edit'),
    url(r'^group/(?P<group_id>[0-9]+)/copy/$', group.copy, name='staff_group_copy'),
    url(r'^group/(?P<group_id>[0-9]+)/archive/$', group.archive, name='staff_group_archive'),
    url(r'^group/(?P<group_id>[0-9]+)/deadlines/$', group.deadlines, name='staff_group_deadlines'),
    url(r'^group/(?P<group_id>[0-9]+)/reports/(?P<user_id>[0-9]+)/$', group.user_reports,
        name='staff_group_user_reports'),

    # | - groups / access

    url(r'^group/(?P<group_id>[0-9]+)/access/$', group_access.index, name='staff_group_access'),
    url(r'^group/(?P<group_id>[0-9]+)/access/change_type/$', group_access.change, name='staff_group_change_access'),
    url(r'^group/(?P<group_id>[0-9]+)/access/user/$', group_access.user, name='staff_group_access_user'),
    url(r'^group/(?P<group_id>[0-9]+)/access/staff/$', group_access.staff, name='staff_group_access_staff'),
    url(r'^group/(?P<group_id>[0-9]+)/access/csv_import/$', group_access.csv_import, name='staff_access_csv_import'),
    url(r'^group/(?P<group_id>[0-9]+)/access/revoke/(?P<id_type>[^/]+):(?P<member_id>[0-9]+)/$',
        group_access.revoke_user_access, name='staff_group_revoke_user_access'),
    url(r'^group/(?P<group_id>[0-9]+)/access/invitation_list/$',
        group_access.invitation_list, name='staff_group_invitation_list'),
    url(r'^group/(?P<group_id>[0-9]+)/access/invitation/(?P<invitation_id>[0-9]+)/revoke/$',
        group_access.revoke_invitation, name='staff_group_revoke_invitation'),

    # | - groups / set

    url(r'^group/(?P<group_id>[0-9]+)/set/create/$', group_taskset.create, name='staff_group_set_create'),
    url(r'^group/(?P<group_id>[0-9]+)/set/(?P<set_id>[0-9]+)/edit/$', group_taskset.edit,
        name='staff_group_set_edit'),
    url(r'^group/(?P<group_id>[0-9]+)/set/(?P<set_id>[0-9]+)/remove/$', group_taskset.remove,
        name='staff_group_set_remove'),
    url(r'^group/(?P<group_id>[0-9]+)/set/(?P<set_id>[0-9]+)/publish/$', group_taskset.publish_all,
        name='staff_group_set_publish'),

    # | - tasks

    url(r'^task/create/group:(?P<group_id>[0-9]+)/set:(?P<set_id>[0-9]+)/$', task.create, name='staff_task_create'),
    url(r'^task/(?P<task_id>[0-9]+)/archive/$', task.archive, name='staff_task_archive'),
    url(r'^task/(?P<task_id>[0-9]+)/$', task.details, name='staff_task_details'),
    url(r'^task/(?P<task_id>[0-9]+)/edit/$', task.edit, name='staff_task_edit'),
    url(r'^task/(?P<task_id>[0-9]+)/publish/$', task.publish, name='staff_task_publish'),

    # | - tasks / submissions

    url(r'^task/(?P<task_id>[0-9]+)/operation/(?P<sop_uuid>[^/]+)/$',
        submission.operation_handle, name='staff_task_operation_handle'),
    url(r'^task/(?P<task_id>[0-9]+)/submissions/user:(?P<user_id>[0-9]+)/$',
        submission.list_user, name='staff_task_submissions_user'),
    url(r'^task/(?P<task_id>[0-9]+)/submissions/$', submission.list_all, name='staff_task_submissions_all'),

    # | - submissions

    url(r'^submission/(?P<submission_id>[^/]+)/report/$', submission.report, name='staff_submission_report'),
    url(r'^submission/(?P<s_uuid>[^/]+)/reevaluate/$',
        submission.perform_action, {'action': 'reevaluate'}, name='staff_submission_reevaluate'),
    url(r'^submission/(?P<s_uuid>[^/]+)/invalidate/$',
        submission.perform_action, {'action': 'invalidate'}, name='staff_submission_invalidate'),
    url(r'^submission/(?P<s_uuid>[^/]+)/validate/$',
        submission.perform_action, {'action': 'validate'}, name='staff_submission_validate'),

    # other
    url(r'^worker_status/$', base.worker_status, name='staff_worker_status'),
    url(r'^guidelines/$',
        staff_required(Tv.as_view(template_name='webapp/admin/pages/guidelines.html')), name='staff_guidelines'),
    url(r'^preview_markdown/$', task.preview_markdown, name='staff_preview_markdown')
]
