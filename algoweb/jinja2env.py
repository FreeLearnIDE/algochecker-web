from django.contrib.messages import get_messages
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.urlresolvers import reverse
from django.utils.timezone import template_localtime
from jinja2 import Environment
from markdown import markdown
from webapp.utils.template import short_name, global_alert
from webapp.utils.time import format_int
from django.template import defaultfilters as df


def environment(**options):
    env = Environment(**options)
    env.globals.update({
        'static': staticfiles_storage.url,
        'url': reverse,
        'get_messages': get_messages,
        'global_alert': global_alert
    })
    env.filters.update({
        'markdown': lambda text: markdown(text),
        'short_name': lambda name: short_name(name),
        'f_setattr': lambda field, attributes: field.as_widget(attrs=attributes),
        'localtime': template_localtime,
        'fltime': lambda time: template_localtime(time).strftime('%d.%m.%Y, %H:%M:%S'),
        'linebreaks': df.linebreaks,
        'linebreaksbr': df.linebreaksbr,
        'format_int_time': format_int
    })
    return env
