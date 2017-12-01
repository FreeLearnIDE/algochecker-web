from django.contrib.auth.models import User
from redis.exceptions import ConnectionError as RConnectionError
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect

from webapp.forms import TaskGroupForm, TaskForm
from webapp.models import TaskGroup, Submission, CASUserMeta
from webapp.utils.access import item_is_staff
from webapp.utils.redis_facade import get_worker_list, get_queue_contents


@staff_member_required
def dashboard(request):
    items = []
    archived_items = []

    for task_group in TaskGroup.objects.all():
        try:
            role = task_group.check_membership(request.user)
        except PermissionDenied:
            continue

        if role == 'user':
            continue

        item = {
            'group': task_group,
            'role': role
        }

        if task_group.archived:
            archived_items.append(item)
        else:
            items.append(item)

    context = {
        'items': items,
        'archived_items': archived_items,
        'title': 'Staff Dashboard'
    }
    return render(request, 'webapp/admin/dashboard.html', context)


@staff_member_required
def user_list(request):
    metas = sorted(CASUserMeta.objects.all(), key=lambda um: um.user.date_joined, reverse=True)
    users = User.objects.all()

    cas_users = [u.user for u in metas if u.has_ext_id()]
    int_users = sorted([u for u in users if u not in cas_users], key=lambda u: u.date_joined, reverse=True)

    context = {
        'cas_users': metas,
        'int_users': int_users
    }

    return render(request, 'webapp/admin/user_list.html', context)


@staff_member_required
def worker_status(request):
    if not request.user.is_superuser:
        return redirect('staff_dashboard')
    try:
        # list of active workers, their states and currently processed UUIDs
        worker_list = get_worker_list()
    except RConnectionError:
        messages.error(request, 'Unable to show worker status because there is connection problem with Redis')
        return redirect('staff_dashboard')

    # UUIDs which are being checked at the moment
    active_uuids = [item['current_uuid'] for instance, item in worker_list if item['current_uuid'] is not None]

    not_checked_list = Submission.objects.filter(submissionevaluation__isnull=True)\
        .select_related('user').order_by('submitted')

    # lookup of our database rows: uuid => row
    subm_lookup = {str(item.uuid): item for item in not_checked_list}

    # list of queue items with preserved priority
    queue_list = list(get_queue_contents())

    # list of UUIDs present in Redis queue
    queue_uuids = [item['uuid'] for item in queue_list]

    # list of tuples: (queue_item, our_db_item)
    queue_total = [(item, dict.get(subm_lookup, item['uuid'])) for item in queue_list]

    # list of tuples: (None, our_db_item) with rows which are not present in Redis
    not_mapped = [(None, item) for item in not_checked_list
                  if str(item.uuid) not in queue_uuids and str(item.uuid) not in active_uuids]

    # so we have two lists:
    # not_mapped (records not present in Redis)
    # queue_total (mapped records + records not present in our DB)
    total_list = not_mapped + queue_total

    context = {
        'worker_list': worker_list,
        'queues': total_list,
        'title': 'Worker status'
    }

    return render(request, 'webapp/admin/pages/worker_status.html', context)


def item_edit(request, item_name, item_id):
    item, role = item_is_staff(item_name, request.user, item_id)

    context = {
        'title': 'Edit ' + item.name
    }

    if item_name == 'group':
        form_object = TaskGroupForm
        context['group'] = item
        rd = redirect('staff_group_tasks', group_id=item_id)
    else:
        form_object = TaskForm
        context['group'] = item.task_group
        context['task'] = item
        rd = redirect('staff_task_details', task_id=item_id)

    if item.archived or (item.task_group.archived if hasattr(item, 'task_group') else False):
        messages.warning(request, 'Archived {} cannot be edited'.format(item_name))
        return rd

    if request.method == 'POST':
        if item_name == 'group':
            form = form_object(request.POST, instance=item)
        else:
            form = form_object(request.POST, request.FILES, edit=1, instance=item)

        if form.is_valid():
            form.save()
            messages.success(request, 'Changes saved successfully')
            return rd
        else:
            messages.error(request, 'Form was filled incorrectly')
    else:
        form = form_object(instance=item, edit=1)

    context['form'] = form

    return render(request, 'webapp/admin/{}/actions.html'.format(item_name), context)


def item_archive(request, item_name, item_id):
    item, role = item_is_staff(item_name, request.user, item_id)

    if request.method == 'POST':
        item.archived = not item.archived
        item.save()
        return redirect('staff_task_details', task_id=item_id) \
            if item_name == 'task' else redirect('staff_group_tasks', group_id=item_id)

    return render(request, 'webapp/admin/item_archive.html', {
        'item_name': item_name,
        'item': item,
        'title': 'Unarchive ' if item.archived else 'Archive ' + item.name
    })
