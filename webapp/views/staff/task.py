import json

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Avg, Count
from django.db.models.expressions import RawSQL, F, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from webapp.forms import TaskForm
from webapp.models import Task, SubmissionEvaluation, TaskGroupSet
from webapp.views.staff.base import item_archive, item_edit
from webapp.utils.access import item_is_staff
from webapp.utils.main import get_package_link, apply_markdown
from webapp.utils.time import format_int


@staff_member_required
def create(request, group_id, set_id):
    group, role = item_is_staff('group', request.user, group_id)

    rd = redirect('staff_group_tasks', group_id=group_id)

    if group.archived:
        messages.warning(request, 'Task cannot be added to archived group.')
        return rd

    try:
        task_set = TaskGroupSet.objects.get(pk=set_id)
    except TaskGroupSet.DoesNotExist:
        messages.warning(request, 'Task cannot be added to nonexistent task set.')
        return rd

    if request.method == 'POST':
        instance = Task(owner=request.user, task_group=group, tg_set=task_set)
        form = TaskForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            return rd
        messages.error(request, 'Form was filled incorrectly')
    else:
        form = TaskForm()

    context = {
        'form': form,
        'group': group,
        'set': task_set,
        'title': 'Create task'
    }
    return render(request, 'webapp/admin/task/actions.html', context)


@staff_member_required
def edit(request, task_id):
    return item_edit(request, 'task', task_id)


@staff_member_required
def archive(request, task_id):
    return item_archive(request, 'task', task_id)


@require_POST
@staff_member_required
def preview_markdown(request):
    try:
        rq = json.loads(request.body.decode('utf-8'))
    except UnicodeDecodeError:
        return JsonResponse({'success': False, 'data': 'Unable to decode content. [utf-8 decode error]'})

    try:
        md_html = apply_markdown(rq['content'])
    except KeyError:
        return JsonResponse({'success': False, 'data': 'Required data was not received.'})

    return JsonResponse({'success': True, 'data': md_html})


@staff_member_required
def details(request, task_id):
    task, role = item_is_staff('task', request.user, task_id)

    ids = SubmissionEvaluation.objects.annotate(
        rank=RawSQL('''dense_rank() over(partition by webapp_submission.user_id
        order by {}webapp_submission.submitted desc)'''.format(
            'webapp_submissionevaluation.score desc, ' if task.result_type == 'best' else ''
        ), [])
    ).values(
        'id',
        'rank',
        'status',
        'received',
        'worker_took_time',
        'submission__submitted'
    ).filter(submission__task_id=task_id, is_invalid=False)

    results = SubmissionEvaluation.objects.select_related(
        'submission',
        'submission__user'
    ).filter(pk__in=(pk['id'] for pk in ids if pk['rank'] == 1)).order_by('-score', 'submission__submitted')

    # separating staff and user submissions
    staff_members = task.task_group.taskgroupaccess_set.filter(~Q(role='user')).values_list('user_id', flat=True)
    d_results = []
    s_results = []

    for r in results:
        if r.submission.user_id in staff_members:
            d_results.append(r)
        else:
            s_results.append(r)

    # gathering stats
    stats = {
        'avg_check_time': 'n/a',
        'avg_wait_time': 'n/a',
        'avg_score': '0.0',
        'sbm_count': 0
    }

    total_check = 0
    total_wait = 0
    index = 0
    for i in ids:
        try:
            if i['status'] == 'ok' and i['worker_took_time'] is not None:
                worker_took = i['worker_took_time'] / 1000  # ms to seconds without loosing precision
                total_check += worker_took
                # wait time is calculated by subtracting submit unix time and worker_took_time assuming remaining
                # time gap to be the time spent in queue
                total_wait += (i['received'] - i['submission__submitted']).total_seconds() - worker_took
                index += 1
        except KeyError:
            pass

    if index > 0:
        stats['avg_check_time'] = format_int(round(total_check / index))
        stats['avg_wait_time'] = format_int(round(total_wait / index))

    if s_results:
        stats.update(SubmissionEvaluation.objects.filter(
            pk__in=(pk.id for pk in s_results)
        ).aggregate(
            avg_score=Avg(F('score')),
            sbm_count=Count(F('score'))
        ))

    context = {
        'title': 'Task: ' + task.name,
        'task': task,
        'group': task.task_group,
        'pack_url': get_package_link(task),
        'are_results': len(ids) > 0,
        's_results': s_results,
        'd_results': d_results,
        'stats': stats,
    }
    return render(request, 'webapp/admin/task/index.html', context)


@staff_member_required
def publish(request, task_id):
    task, role = item_is_staff('task', request.user, task_id)

    if task.published:
        messages.warning(request, 'This task is already published')

    elif task.task_group.archived:
        messages.warning(request, 'The group, to which this task belongs is archived. Task cannot be published')

    elif request.method == 'POST':
        task.published = True
        task.save()
        messages.success(request, 'Task was published successfully.')

    else:
        return render(request, 'webapp/admin/task/publish.html', {
            'task': task,
            'group': task.task_group,
            'title': 'Publish ' + task.name
        })

    return redirect('staff_task_details', task_id=task.id)
