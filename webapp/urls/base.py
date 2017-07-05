from django.conf.urls import url
from django.views.generic import TemplateView as Tv
import django_cas_ng.views
import webapp.views.base as v


urlpatterns = [
    # index

    url(r'^$', v.index, name='index'),

    # static pages

    url(r'^help/$', Tv.as_view(template_name='webapp/pages/help.html'), name='help'),
    url(r'^feedback/$', v.feedback, name='feedback'),

    # tasks

    url(r'^tasks/$', v.tasks, name='tasks'),
    url(r'^task/(?P<task_id>[0-9]+)/$', v.task, name='task'),
    url(r'^task/(?P<task_id>[0-9]+)/submit/$', v.task_submit, name='submit_task'),
    url(r'^task/submission/status/$', v.submission_status, name='check_submission_status'),
    url(r'^task/report/(?P<submission_id>[^/]+)/$', v.submission_report, name='view_report'),

    # accounts
    url(r'^accounts/login/$', v.choose_login_method, name='base_login'),

    url(r'^accounts/internal/$', v.choose_internal_login, name='internal_choose'),
    url(r'^accounts/internal/login/$', v.internal_login, name='internal_login'),
    url(r'^accounts/internal/logout/$', v.internal_logout, name='internal_logout'),
    url(r'^accounts/internal/forget/$', v.internal_forget, name='internal_forget'),
    url(r'^accounts/internal/forget/(?P<signed_data>[^/]+)/$', v.internal_forget_link, name='internal_forget_link'),
    url(r'^accounts/internal/register/$', v.internal_register, name='internal_register'),

    url(r'^accounts/cas/login/$', django_cas_ng.views.login, name='cas_ng_login'),
    url(r'^accounts/cas/logout/$', django_cas_ng.views.logout, name='cas_ng_logout'),
    url(r'^accounts/cas/callback/$', django_cas_ng.views.callback, name='cas_ng_proxy_callback'),

    # user

    url(r'^user/profile/$', v.user_profile, name='user_profile'),
    url(r'^user/reports/$', v.user_reports, name='user_reports'),

    # other

    url(r'^invitation/(?P<access_token>[^/]+)/$', v.access_invite_link, name='access_invite_link'),

    url(r'^package/(?P<task_data>[^/]+)/(?P<package_name>[^/]+)$',
        v.download_package, name='package_download'),

    url(r'^csp-report/$', v.handle_csp_violation, name='handle_csp_violation')
]
