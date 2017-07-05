from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db import IntegrityError

import algoweb.settings
import json
import redis
import uuid

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMessage
from django.core.signing import TimestampSigner
from django.core.urlresolvers import reverse
from django.db.models import F
from django.db.models.expressions import RawSQL
from django.http import HttpResponseRedirect, Http404, HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.static import serve

from os.path import basename, join as path_join

from webapp.forms import FeedbackFrom, InternalLoginForm, InternalRegisterForm
from webapp.models import Task, Submission, SubmissionFile, SubmissionEvaluation, SubmissionTest, TaskGroup, \
    TaskGroupAccess, TaskGroupInviteToken, TaskGroupSet
from webapp.utils.highlight import highlight_submission_files
from webapp.utils.redis_facade import upload_submission, get_submission_status
from webapp.utils.main import check_files
from algoweb.settings import EMAIL_SENDER_NOTIFIER, EMAIL_RECIPIENT_NOTIFIER, INTERNAL_USERNAME_FORMAT


def index(request):
    return render(request, 'webapp/index.html', {'title': 'Home', 'revision': get_git_revision()})


def feedback(request):
    if request.method == 'POST':
        form = FeedbackFrom(request.POST)
        if form.is_valid():
            html_content = '<p>Message: {}</p><p>Contact e-mail: {}</p>'.format(
                form.cleaned_data['content'],
                form.cleaned_data['email']
            )

            msg = EmailMessage(
                'Algo feedback: {}'.format(form.cleaned_data['theme']),
                html_content,
                EMAIL_SENDER_NOTIFIER,
                EMAIL_RECIPIENT_NOTIFIER
            )
            msg.content_subtype = "html"  # main content is now text/html
            msg.send()

            # cleaning the form after sending
            form = FeedbackFrom()
            messages.success(request, 'Your message has been sent. Thanks for the feedback!')
        else:
            messages.error(request, 'Please fill fields highlighted in red properly')
    else:
        form = FeedbackFrom()

    return render(request, 'webapp/pages/feedback.html', {'title': 'Feedback', 'form': form})


@login_required
def tasks(request):

    items = []

    for task_group in TaskGroup.objects.filter(archived=False):
        try:
            task_group.check_membership(request.user)
        except PermissionDenied:
            continue

        # here we define minimum submission score when the task is considered as "accepted" to be any score
        # greater than zero. theoretically we could provide a possibility for the tutor to set this value manually.
        # * in line score__gt
        has_ok_eval = SubmissionEvaluation.objects.filter(
            submission__task__in=task_group.task_set.filter(archived=False, published=True),
            submission__user=request.user,
            status='ok',
            score__gt=0
        ).values_list('submission__task_id', flat=True).distinct('submission__task_id')

        items.append({
            'group': task_group,
            'sets': [
                dict(set=tg_set, tasks=tg_set.task_set.filter(task_group=task_group, archived=False, published=True))
                for tg_set in TaskGroupSet.objects.filter(task_group=task_group)
            ],
            'has_ok_eval': has_ok_eval
        })

    context = {
        'title': 'Tasks',
        'items': items
    }
    return render(request, 'webapp/tasks.html', context)


@login_required
def task(request, task_id):
    task = get_object_or_404(Task.objects.select_related('task_group', 'tg_set'), id=task_id)
    role = task.task_group.check_membership(request.user)

    if role == 'user' and not task.published:
        raise Http404('Task not found')

    submissions = Submission.objects.filter(user=request.user, task_id=task_id)

    context = {
        'title': task.name,
        'task': task,
        'group': task.task_group,
        'submissions': submissions,
        'evaluations': {},
        'tokens': {},
        'limits': task.get_user_limits(request.user.id),
        'deadline': task.get_deadline_data()
    }

    evaluations = SubmissionEvaluation.objects.filter(submission__uuid__in=[sbm.uuid for sbm in submissions])

    signer = TimestampSigner()

    for submission in submissions:
        context['tokens'][submission.uuid] = signer.sign(submission.uuid)

    for evaluation in evaluations:
        context['evaluations'][evaluation.submission_id] = evaluation

    return render(request, 'webapp/task.html', context)


@login_required
def task_submit(request, task_id):
    redirect_url = '{}#{}'.format(reverse('task', kwargs={'task_id': task_id}), 'submissions_anchor')

    try:
        task = Task.objects.select_related('task_group').get(id=task_id, archived=False)
        role = task.task_group.check_membership(request.user)
        if role == 'user' and not task.published:
            raise Task.DoesNotExist
    except Task.DoesNotExist:
        messages.error(request, 'Task with given ID does not exist')
        return redirect('tasks')

    if task.task_group.archived:
        messages.error(request, 'The task group is archived. No submissions are accepted')
        return HttpResponseRedirect(redirect_url)
    if not task.get_user_limits(request.user.id).can_submit:
        messages.error(request, 'You have exceeded limit on amount of submissions')
        return HttpResponseRedirect(redirect_url)
    if task.get_deadline_data() is not None and task.get_deadline_data().missed:
        messages.error(request, 'The deadline has already missed. Submission rejected.')
        return HttpResponseRedirect(redirect_url)

    files = request.FILES.getlist('file')

    file_check_res, message = check_files(
        files=files,
        count_limit=task.files_count_limit,
        size_limit=task.file_size_limit
    )

    if not file_check_res:
        messages.warning(request, message)
        return HttpResponseRedirect(redirect_url)

    count_pending = Submission.objects.filter(submissionevaluation__isnull=True, user=request.user).count()

    qp = "medium"

    # if user has already two or more not evaluated submissions then the next ones will go with
    # low priority, so it would not be possible for a single user to create a total disaster
    if count_pending >= 2:
        qp = "low"

    submission = Submission.objects.create(uuid=str(uuid.uuid4()), user=request.user, task=task, queue_priority=qp)

    for file in files:
        SubmissionFile.objects.create(submission=submission, name=file.name, contents=file)

    try:
        upload_submission(submission)
    except redis.exceptions.RedisError:
        # delete this submission, if we failed to upload it
        # then it doesn't really exist at all
        submission.delete()
        return render(request, 'webapp/submit_fail.html', {'task': task})

    return HttpResponseRedirect(redirect_url)


@login_required
def submission_report(request, submission_id):
    # here no check on membership is done since user should always have access to his submissions (by link)
    try:
        # submission = Submission.objects.get(user=request.user, uuid=submission_id)
        evaluation = SubmissionEvaluation.objects.select_related(
            'submission',
            'submission__task',
            'submission__task__task_group'
        ).get(
            submission__user_id=request.user.id,
            submission_id=submission_id
        )
        submission = evaluation.submission
    except (ValueError, Submission.DoesNotExist, SubmissionEvaluation.DoesNotExist):
        raise Http404("Report does not exist")

    context = {
        'title': 'Report on ' + submission.task.name,
        'submission': submission,
        'evaluation': evaluation,
        'tests': SubmissionTest.objects.filter(evaluation=evaluation),
        'files': SubmissionFile.objects.filter(submission=submission),
        'code': {},
    }

    context['code'] = highlight_submission_files(context['files'])

    return render(request, 'webapp/report.html', context)


@require_POST
@login_required
@csrf_exempt
def submission_status(request):
    try:
        rq = json.loads(request.body.decode('utf-8'))
    except UnicodeDecodeError:
        return JsonResponse([])

    response = []
    try:
        signer = TimestampSigner()
        submissions = Submission.objects.filter(
            uuid__in=[signer.unsign(i, max_age=timedelta(hours=24)) for i in rq['ids']]
        )
        evaluations = SubmissionEvaluation.objects.filter(submission__in=submissions)
    except (KeyError, ValueError, signing.BadSignature, signing.SignatureExpired):
        return JsonResponse([])

    submission_list = ((str(sbm.uuid), sbm.queue_priority) for sbm in submissions)
    evaluation_list = {str(evl.submission_id): evl for evl in evaluations}

    for sid, queued_priority in submission_list:
        if sid not in evaluation_list:
            # we don't have evaluation result in DB
            try:
                status_kind, data = get_submission_status(sid, queued_priority)
            except redis.exceptions.RedisError:
                # maybe add some error indication here?
                continue

            if status_kind == "processing":
                # is in progress or finished (progress may be 100, but evaluation is not ready yet)
                response.append({
                    'id': sid,
                    'state': 1,
                    'job_state': data['status'],
                    'progress': data['progress']
                })
            elif status_kind == "queued":
                # is in queue
                response.append({
                    'id': sid,
                    'state': 0,
                    'position': data['position']
                })
            else:
                response.append({
                    'id': sid,
                    'state': -1
                })
        else:
            # evaluation is in DB and submission is ready
            evaluation = evaluation_list[sid]
            response.append({
                'id': sid,
                'state': 2,
                'score': evaluation.score,
                'status': evaluation.status,
                'message': evaluation.view_info['message'],
                'status_color': evaluation.view_info['color']
            })

    return JsonResponse(response, safe=False)


@login_required
def user_profile(request):
    return render(request, 'webapp/user_profile.html', {'title': 'My profile'})


@login_required
def user_reports(request):
    # this is conforming with an assumption that user always has an access to own reports [not necessarily task]

    evaluations = SubmissionEvaluation.objects.filter(
        submission__user=request.user
    ).select_related(
        'submission',
    ).annotate(
        task_name=F('submission__task__name'),
        set_name=F('submission__task__tg_set__name'),
        group_name=F('submission__task__task_group__name'),
        best=RawSQL('''dense_rank() over(partition by webapp_submission.task_id
        order by webapp_submissionevaluation.score desc, webapp_submission.submitted desc)''', []),
        latest=RawSQL('''dense_rank() over(partition by webapp_submission.task_id
        order by webapp_submission.submitted desc)''', [])
    ).order_by(
        '-submission__submitted'
    )

    context = {
        'title': 'My reports',
        'evaluations': evaluations
    }

    return render(request, 'webapp/user_reports.html', context)


def download_package(request, task_data, package_name):
    try:
        task_data_obj = signing.loads(task_data)
    except signing.BadSignature:
        raise PermissionDenied

    try:
        task_obj = Task.objects.get(id=task_data_obj['id'], version=task_data_obj['ver'], archived=False)
    except (ValueError, Task.DoesNotExist):
        raise Http404('Task cannot be found')

    root_path = path_join(algoweb.settings.MEDIA_ROOT, 'task', 'package')
    return serve(request, path=basename(task_obj.package.name), document_root=root_path)


def get_git_revision():
    import subprocess
    from algoweb.settings import BASE_DIR

    try:
        pr = subprocess.Popen(
            'git rev-parse HEAD',
            shell=True,
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except subprocess.SubprocessError:
        return None

    (out, error) = pr.communicate()

    if error:
        return None

    out = out.decode('utf-8')
    return {
        'short': out[0:8],
        'full': out
    }


@login_required
def access_invite_link(request, access_token):
    invitation = get_object_or_404(TaskGroupInviteToken.objects.select_related('task_group'), access_token=access_token)

    if not invitation.check_valid():
        messages.error(request, 'Failed to grant permissions. Your token is invalid or has expired.')
        return redirect('index')

    invitation.is_valid = False
    invitation.save()

    try:
        access = TaskGroupAccess.objects.get_user_access(request.user, invitation.task_group)
    except TaskGroupAccess.DoesNotExist:
        access = TaskGroupAccess(user=request.user, task_group=invitation.task_group)

    if (invitation.role == 'user' and access.role == '') or \
            (invitation.role == 'staff' and access.role not in ['', 'user']):
        messages.error(request, 'Failed to grant permissions. Your access is already the same or greater.')
        return redirect('index')

    if invitation.role == 'staff' and not request.user.is_staff:
        request.user.is_staff = True
        request.user.save()

    access.role = invitation.role
    access.save()

    messages.info(request, 'You were granted {} access to "{}".'.format(access.role, invitation.task_group.name))
    return redirect('index')


@csrf_exempt
def handle_csp_violation(request):
    # TODO handle it in a different way (maybe file?)
    rq = json.loads(request.body.decode('utf-8'))

    import logging
    logging.warning('CSP VIOLATION: {}'.format(rq))

    return HttpResponse('accepted')


def choose_login_method(request):
    return render(request, 'webapp/choose_login.html')


def internal_login(request):
    if request.method == 'POST':
        form = InternalLoginForm(request.POST)
        username = INTERNAL_USERNAME_FORMAT.format(form.data['username'])

        user = authenticate(username=username, password=form.data['password'])

        if user is not None:
            login(request, user)
            messages.info(request, 'Login successful. Welcome {}.'.format(username))
            return redirect('index')
        else:
            form.add_error('username', 'Invalid login or password was provided.')
    else:
        form = InternalLoginForm()

    context = {"form": form}
    return render(request, 'webapp/internal_login.html', context)


def internal_logout(request):
    logout(request)
    return redirect('index')


def internal_register(request):
    if request.method == 'POST':
        form = InternalRegisterForm(request.POST)

        if form.data['password'] != form.data['repeat_password']:
            form.add_error('repeat_password', 'Provided passwords doesn\'t match each other.')

        if User.objects.filter(username=form.data['username']).count() != 0:
            form.add_error('username', 'User with such username already exists.')

        if form.is_valid():
            username = INTERNAL_USERNAME_FORMAT.format(form.data['username'])

            try:
                user = User.objects.create_user(username, form.data['email'], form.data['password'])
                user.first_name = form.data['first_name']
                user.last_name = form.data['last_name']
                user.save()

                messages.info(request, 'Your account was succesfully created. Now please log in.')
                return redirect('internal_login')
            except IntegrityError:
                form.add_error('username', 'User with such username already exists.')
    else:
        form = InternalRegisterForm()

    context = {"form": form}
    return render(request, 'webapp/internal_register.html', context)
