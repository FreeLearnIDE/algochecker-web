from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404, redirect

from webapp.forms import TaskGroupSetForm
from webapp.models import TaskGroupSet
from webapp.utils.access import item_is_staff


@staff_member_required
def create(request, group_id):
    group, role = item_is_staff('group', request.user, group_id)

    rd = redirect('staff_group_tasks', group_id=group_id)

    if group.archived:
        messages.warning(request, 'Set cannot be created in archived group')
        return rd

    if request.POST:
        instance = TaskGroupSet(task_group_id=group_id)
        form = TaskGroupSetForm(request.POST, instance=instance)
        if form.is_valid:
            form.save()
            messages.success(request, 'Task set is created successfully')
            return rd
        else:
            messages.error(request, 'Form was filled incorrectly')

    context = {
        'title': 'Create task set in {}'.format(group.name),
        'group': group,
        'form': TaskGroupSetForm()
    }
    return render(request, 'webapp/admin/group/taskset/actions.html', context)


@staff_member_required
def edit(request, group_id, set_id):
    group, role = item_is_staff('group', request.user, group_id)

    rd = redirect('staff_group_tasks', group_id=group_id)

    if group.archived:
        messages.warning(request, 'Set in the archived group cannot be edited')
        return rd

    task_set = get_object_or_404(TaskGroupSet, task_group_id=group_id, pk=set_id)

    form = TaskGroupSetForm(instance=task_set)

    if request.POST:
        form = TaskGroupSetForm(request.POST, instance=task_set)
        if form.is_valid:
            form.save()
            messages.success(request, 'Changes saved')
            return rd
        else:
            messages.error(request, 'Form was filled incorrectly')

    context = {
        'group': group,
        'set': task_set,
        'title': 'Edit task set {}'.format(task_set.name),
        'form': form
    }
    return render(request, 'webapp/admin/group/taskset/actions.html', context)
    pass


@staff_member_required
def remove(request, group_id, set_id):
    item_is_staff('group', request.user, group_id)

    tg_set = get_object_or_404(TaskGroupSet, task_group_id=group_id, pk=set_id)

    if tg_set.task_set.exists():
        messages.error(request, 'Task set can be deleted only if empty')
    else:
        messages.success(request, 'Task set deleted successfully')
        tg_set.delete()

    return redirect('staff_group_tasks', group_id=group_id)


@staff_member_required
def publish_all(request, group_id, set_id):
    group, role = item_is_staff('group', request.user, group_id)

    rd = redirect('staff_group_tasks', group_id=group_id)

    if group.archived:
        messages.warning(request, 'Unable to publish tasks in archived group')
        return rd

    tg = get_object_or_404(TaskGroupSet, task_group_id=group_id, pk=set_id)
    tasks = tg.task_set.filter(published=False)

    if not tasks:
        messages.warning(request, 'There are no unpublished tasks in the set')
        return rd

    if request.POST:
        for task in tasks:
            task.published = True
            task.save()
        return rd

    context = {
        'title': 'Bulk publish',
        'bulk': True,
        'group': group,
        'tasks': tasks,
        'set_name': tg.name
    }

    return render(request, 'webapp/admin/task/publish.html', context)
