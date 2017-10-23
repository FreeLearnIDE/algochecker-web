from django.utils.safestring import mark_safe


def short_name(name, max_subparts=1):
    """
    Take only first subpart of string if it contains more than one part.
    Used to extract only first part of first name.
    """
    return ' '.join(name.split(' ')[:max_subparts])


def global_alert():
    try:
        from algoweb.settings import MAINTENANCE_WARN as M
    except ImportError:
        return ''

    try:
        if M['active']:
            return mark_safe('''
<div class="alert alert-{}">
    <span class="glyphicon glyphicon-{}" aria-hidden="true"></span>&nbsp;{}
</div>'''.format(M['color'], M['icon'], M['message']))
    except KeyError:
        pass

    return ''
