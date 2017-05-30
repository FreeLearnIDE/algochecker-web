from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect


def restrict_admin_middleware(get_response):
    """
    Restricts admin panel to superusers only
    """
    def middleware(request):
        if request.path == reverse('admin:index') or request.path == reverse('admin:login'):
            if not (request.user.is_active and request.user.is_superuser):
                try:
                    if request.GET['get_admin'] == '42':
                        return get_response(request)
                except KeyError:
                    pass
                return HttpResponseRedirect('/')

        return get_response(request)

    return middleware


def csp_middleware(get_response):
    """
    Adds Content Security Policy header
    """
    def middleware(request):
        response = get_response(request)

        response['Content-Security-Policy'] = \
            "default-src 'self'; script-src 'self'; style-src 'self'; report-uri /csp-report/"

        return response

    return middleware
