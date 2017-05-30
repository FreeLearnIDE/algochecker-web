import bleach
import json
import re
import markdown

from algoweb.settings import BLEACH, MARKDOWN_EXT

from django.core import signing
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.utils import timezone

from os.path import basename

from webapp.models import SubmissionOperation


def apply_markdown(source):
    out = bleach.clean(
        markdown.markdown(source, extensions=MARKDOWN_EXT),
        tags=BLEACH['ALLOWED_TAGS'],
        attributes=BLEACH['ALLOWED_ATTRIBUTES']
    )
    # hack for tables extension as it is not configurable at all :(
    out = out.replace('<table>', '<table class="table table-striped">')
    return out


def check_files(files, count_limit, size_limit):
    """
    Check if uploaded files are conforming given requirements.
    """
    if len(files) == 0:
        return False, "No file was uploaded"
    elif len(files) > count_limit:
        return False, "Limit on amount of files exceeded"

    for file in files:
        if file.size > size_limit:
            return False, "Limit on file size exceeded"

        if re.search(r'[^a-zA-Z0-9_\-\.]', file.name):
            return False, "File name contains invalid characters"

    return True, None


def build_http_array(post, name):
    """
    builds a dictionary of dictionaries out of flat HTTP field data
    used for arrays like user[2][first_name] etc.

    by Herman Schaaf, ironzebra.com
    """
    dic = {}
    for k in post.keys():
        if k.startswith(name):
            rest = k[len(name):]

            # split the string into different components
            parts = [p[:-1] for p in rest.split('[')][1:]
            row_id = int(parts[0])

            # add a new dictionary if it doesn't exist yet
            if row_id not in dic:
                dic[row_id] = {}

            # add the information to the dictionary
            dic[row_id][parts[1]] = post.get(k)
    return dic


def get_package_link(task):
    pack_data = {
        "id": task.id,
        "ver": task.version,
    }

    url_kw = {
        "task_data": signing.dumps(pack_data),
        "package_name": basename(task.package.name)
    }

    return reverse("package_download", kwargs=url_kw)


def submission_operation_create(user, action, s_ids, task_id, redirect_to, bulk=True):
    op = SubmissionOperation.objects.create(
        invoker=user,
        action=action,
        submission_list=json.dumps(s_ids),
        task_id=task_id,
        is_bulk=bulk
    )
    rd = redirect('staff_task_operation_handle', sop_uuid=op.uuid, task_id=task_id)
    rd['Location'] += '?next={}'.format(redirect_to)
    return rd


def evaluation_set_validity(evaluations, valid, reason=None, invoker_id=None):
    if not valid and (reason is None or invoker_id is None):
        return False

    for evaluation in evaluations:
        if valid and evaluation.is_invalid:
            evaluation.is_invalid = False
            evaluation.invalidated_at = None
            evaluation.invalidated_by = None
            evaluation.invalidation_comment = None
            evaluation.save()
        elif not valid and not evaluation.is_invalid:
            evaluation.is_invalid = True
            evaluation.invalidated_at = timezone.now()
            evaluation.invalidated_by_id = invoker_id
            evaluation.invalidation_comment = reason
            evaluation.save()

    return True
