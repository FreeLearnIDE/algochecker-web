from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.db.models import F
from django.db.models.expressions import RawSQL
from django.forms import formset_factory
from django.shortcuts import redirect, render

from webapp.forms import TaskGroupForm, CopyTaskGroup, TaskGroupBulkDeadlines
from webapp.models import TaskGroupAccess, Task, TaskGroup, TaskGroupSet, SubmissionEvaluation, \
    CASUserMeta
from webapp.utils.access import item_is_staff
from webapp.views.staff.base import item_archive, item_edit


@staff_member_required
def create(request):
    if request.method == 'POST':
        form = TaskGroupForm(request.POST)
        if form.is_valid():
            new_group = form.save()
            try:
                provider_id = request.user.casusermeta.ext_id
            except CASUserMeta.DoesNotExist:
                provider_id = None

            access = TaskGroupAccess(
                user=request.user,
                role='owner',
                task_group=form.instance,
                provider_id=provider_id
            )
            access.save()
            return redirect('staff_group_tasks', group_id=new_group.pk)
        messages.error(request, 'Form was filled incorrectly')
    else:
        form = TaskGroupForm()

    return render(request, 'webapp/admin/group/actions.html', {'form': form, 'title': 'Create group'})


@staff_member_required
def edit(request, group_id):
    return item_edit(request, 'group', group_id)


@staff_member_required
def archive(request, group_id):
    return item_archive(request, 'group', group_id)


@staff_member_required
def task_list(request, group_id):
    group, role = item_is_staff('group', request.user, group_id)

    context = {
        'user_role': role,
        'group': group,
        'sets': [
            dict(
                id=tg_set.id,
                name=tg_set.name,
                description=tg_set.description,
                tasks=tg_set.task_set.filter(task_group=group),
                has_unpublished=tg_set.task_set.filter(task_group=group, published=False).exists()
            )
            for tg_set in TaskGroupSet.objects.filter(task_group=group)
        ],
        'title': group.name + ' task list'
    }
    return render(request, 'webapp/admin/group/index.html', context)


@staff_member_required
def copy(request, group_id):
    group, role = item_is_staff('group', request.user, group_id)

    if request.POST:
        form = CopyTaskGroup(request.POST)
        if form.is_valid():
            new_group = TaskGroup.objects.create(
                name=form.cleaned_data['name'],
                description=form.cleaned_data['description']
            )
            new_group.save()
            # creating access to the new group
            try:
                provider_id = request.user.casusermeta.ext_id
            except CASUserMeta.DoesNotExist:
                provider_id = None

            access = TaskGroupAccess(
                user=request.user,
                role='owner',
                task_group=new_group,
                provider_id=provider_id
            )
            access.save()

            for tg_set in TaskGroupSet.objects.filter(task_group=group):
                tasks = Task.objects.filter(task_group=group, tg_set=tg_set)
                tg_set.pk = None  # reset pk so that insert will be performed instead of update
                tg_set.task_group = new_group
                tg_set.save()
                for task in tasks:
                    task.pk = None  # reset pk
                    task.deadline = None
                    task.published = False
                    task.archived = False
                    task.task_group = new_group
                    task.tg_set = tg_set  # new TaskGroupSet
                    task.save()

            messages.success(request, 'Group was copied successfully')
            return redirect('staff_group_tasks', group_id=new_group.pk)
        else:
            messages.error(request, 'Please fill in the new group name')
            return redirect('staff_group_copy', group_id=group_id)

    context = {
        'group': group,
        'tasks': Task.objects.filter(task_group=group),
        'title': group.name + ' copy',
        'form': CopyTaskGroup(initial={'name': group.name, 'description': group.description})
    }

    return render(request, 'webapp/admin/group/copy.html', context)


@staff_member_required
def deadlines(request, group_id):
    group, role = item_is_staff('group', request.user, group_id)

    if group.archived:
        messages.warning(request, 'Group is archived, setting bulk deadlines is not possible.')
        return redirect('staff_group_tasks', group_id=group_id)

    formset = formset_factory(TaskGroupBulkDeadlines, extra=0)

    if request.POST:
        forms = formset(request.POST)
        if forms.is_valid():
            filled = False
            for data in forms.cleaned_data:
                if data['deadline']:
                    filled = True
                    for task in Task.objects.filter(tg_set=data['set_id']):
                        task.deadline = data['deadline']
                        task.save()
            if filled:
                messages.success(request, 'Changes applied')
                return redirect('staff_group_tasks', group_id=group_id)
            else:
                messages.warning(request, 'No changes were made')
                return redirect('staff_group_deadlines', group_id=group_id)
    else:
        initial_data = []

        for item in [st for st in TaskGroupSet.objects.filter(task_group=group) if st.task_set.exists()]:
            initial_data.append({'set_id': item.id, 'set_name': item.name[:20] + (item.name[20:] and '...')})

        forms = formset(initial=initial_data)

    context = {
        'group': group,
        'forms': forms,
        'title': 'Set bulk deadlines for {}'.format(group.name)
    }

    return render(request, 'webapp/admin/group/deadlines.html', context)


def user_reports(request, group_id, user_id):
    group, role = item_is_staff('group', request.user, group_id)

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        messages.warning(request, 'User with given ID does not exist')
        return redirect('staff_group_tasks', group_id=group_id)

    evaluations = SubmissionEvaluation.objects.filter(
        submission__user=user,
        submission__task__task_group_id=group_id
    ).select_related(
        'submission',
    ).annotate(
        task_name=F('submission__task__name'),
        set_name=F('submission__task__tg_set__name'),
        best=RawSQL('''dense_rank() over(partition by webapp_submission.task_id
        order by webapp_submissionevaluation.score desc, webapp_submission.submitted desc)''', []),
        latest=RawSQL('''dense_rank() over(partition by webapp_submission.task_id
        order by webapp_submission.submitted desc)''', [])
    ).order_by(
        '-submission__submitted'
    )

    context = {
        'title': 'Submissions from {} to group {}'.format(user.last_name, group.name),
        'group': group,
        'user': user,
        'evaluations': evaluations
    }

    return render(request, 'webapp/admin/submission/list_user_group.html', context)
