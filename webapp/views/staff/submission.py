import json
import uuid

import redis
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.signing import TimestampSigner
from django.db.models.expressions import RawSQL
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse

from webapp.forms import InvalidateSubmissionForm
from webapp.models import SubmissionEvaluation, SubmissionOperation, Submission, SubmissionTest, SubmissionFile
from webapp.utils.access import item_is_staff
from webapp.utils.main import build_http_array, submission_operation_create, evaluation_set_validity
from webapp.utils.highlight import highlight_submission_files
from webapp.utils.redis_facade import upload_submission
from webapp.utils.template import short_name


@staff_member_required
def list_all(request, task_id):
    task, role = item_is_staff('task', request.user, task_id)

    evaluations = SubmissionEvaluation.objects.select_related(
        'submission',
        'submission__user'
    ).filter(
        submission__task_id=task_id
    ).annotate(
        best=RawSQL('''dense_rank() over(partition by webapp_submission.user_id
        order by webapp_submissionevaluation.score desc, webapp_submission.submitted desc)''', []),
        latest=RawSQL('''dense_rank() over(partition by webapp_submission.user_id
        order by webapp_submission.submitted desc)''', [])
    ).order_by('-submission__submitted')

    context = {
        'title': 'Submissions to {}'.format(task.name),
        'task': task,
        'group': task.task_group,
        'evaluations': evaluations
    }

    if request.POST:
        s_ids = []
        action = request.POST.get('action')
        if action and action in ['reevaluate', 'invalidate', 'validate']:
            objects = build_http_array(request.POST, 'submission')
            for index in objects:
                s_ids.append(objects[index]['uuid'])

            redirect_to = reverse('staff_task_submissions_all', args=[task_id])
            return submission_operation_create(request.user, action, s_ids, task_id, redirect_to)
        else:
            messages.warning(request, 'Action parameter was not received or is invalid')

    return render(request, 'webapp/admin/submission/list_all.html', context)


@staff_member_required
def list_user(request, task_id, user_id):
    task, role = item_is_staff('task', request.user, task_id)
    user = get_object_or_404(User, pk=user_id)

    evaluations = SubmissionEvaluation.objects.select_related(
        'submission'
    ).filter(
        submission__user_id=user_id,
        submission__task_id=task_id
    ).order_by('submission__submitted')

    context = {
        'title': 'Submissions of {} {} on {}'.format(short_name(user.first_name), user.last_name, task.name),
        'task': task,
        'group': task.task_group,
        'user': user,
        'evaluations': evaluations
    }

    return render(request, 'webapp/admin/submission/list_user_task.html', context)


@staff_member_required
def report(request, submission_id):
    try:
        submission = Submission.objects.get(uuid=submission_id)
        role = submission.task.task_group.check_membership(request.user)
        if role == 'user':
            raise PermissionDenied
        user = submission.user
    except (ValueError, Submission.DoesNotExist):
        raise Http404("Submission with given ID cannot be found.")

    try:
        evaluation = SubmissionEvaluation.objects.get(submission=submission)
    except SubmissionEvaluation.DoesNotExist:
        evaluation = None

    context = {
        # title is long but will look good in history
        'title': 'Report on {} by {} {}'.format(
            submission.task.name, short_name(user.first_name), user.last_name),
        'submission': submission,
        'evaluation': evaluation,
        'tests': SubmissionTest.objects.filter(evaluation=evaluation) if evaluation else None,
        'files': SubmissionFile.objects.filter(submission=submission),
        'user': user,
        'from_staff': True
    }

    context['code'] = highlight_submission_files(context['files'])

    return render(request, 'webapp/admin/submission/report.html', context)


@staff_member_required
def operation_handle(request, task_id, sop_uuid):
    task, role = item_is_staff('task', request.user, task_id)

    # set redirect targets
    redirect_to = request.GET.get('next')
    self_rd = redirect('staff_task_operation_handle', sop_uuid=sop_uuid, task_id=task_id)

    if redirect_to:
        rd = HttpResponseRedirect(redirect_to)
        self_rd['Location'] += '?next={}'.format(redirect_to)
    else:
        rd = redirect('staff_task_submissions_all', task_id=task_id)

    # SubmissionOperation's task_id must correspond to the given task_id
    try:
        op = SubmissionOperation.objects.get(pk=sop_uuid, task_id=task_id)
    except (SubmissionOperation.DoesNotExist, ValueError):
        messages.error(request, 'The operation cannot be found')
        return rd

    # here we also select only submissions with evaluations and those which belong to the task
    try:
        evaluations = SubmissionEvaluation.objects.filter(
            submission__pk__in=json.loads(op.submission_list),
            submission__task_id=task_id
        ).select_related('submission', 'submission__user')
    except ValueError:
        messages.error(request, 'The operation is invalid')
        op.delete()
        return rd

    if not evaluations:
        if op.is_bulk:
            message = 'You have to select at least one submission in order to perform any action.'
        else:
            message = 'The operation cannot be performed. (no submission received)'

        messages.warning(request, message)
        op.delete()
        return rd

    if op.has_started:
        if op.action == 'reevaluate':
            extra = json.loads(op.extra)
            if not len(extra):
                messages.error(request, 'The operation cannot be performed. (no pending submissions received)')
                op.delete()
                return rd

            try:
                pending_submissions = Submission.objects.select_related('user').filter(pk__in=extra)
            except ValueError:
                messages.error(request, 'The operation cannot be performed. (no valid pending submissions received)')
                op.delete()
                return rd

            context = {
                'task': task,
                'group': task.task_group,
                'role': role,
                'submissions': pending_submissions,
                'title': 'Re-evaluating submission{}'.format('s' if op.is_bulk else ''),
                'tokens': {},
                'old_scores': {},
                'bulk': op.is_bulk
            }

            for e in evaluations:
                context['old_scores'][e.submission_id] = e.score

            signer = TimestampSigner()

            for ps in pending_submissions:
                context['tokens'][ps.uuid] = signer.sign(ps.uuid)

            return render(request, 'webapp/admin/submission/reevaluation.html', context)

        elif op.action == 'invalidate' or op.action == 'validate':
            messages.warning(request, 'This operation has already been invoked.')
            return rd
        else:
            messages.error(request, 'The operation cannot be performed. (invalid action)')
            op.delete()
            return rd
    else:
        if request.POST:
            if request.POST.get('cancel-action') == '1':  # action cancelled
                op.delete()
                return rd
            # confirmation received:
            if op.action == 'reevaluate':
                pending = []
                for evaluation in evaluations:
                    old_submission = evaluation.submission
                    files = SubmissionFile.objects.filter(submission=old_submission)

                    new_s = Submission.objects.create(
                        uuid=str(uuid.uuid4()),
                        user=evaluation.submission.user,
                        task=task,
                        reevaluated=True,
                        copy_of=old_submission,
                        invoked_by=request.user,
                        queue_priority="low"
                    )

                    pending.append(str(new_s.uuid))

                    for file in files:
                        SubmissionFile.objects.create(submission=new_s, name=file.name, contents=file.contents)

                    try:
                        upload_submission(new_s)
                    except redis.exceptions.RedisError:
                        new_s.delete()
                        op.delete()
                        return render(request, 'webapp/submit_fail.html', {'task': task})

                op.has_started = True
                op.extra = json.dumps(pending)
                op.save()

                return self_rd

            elif op.action == 'invalidate':
                form = InvalidateSubmissionForm(request.POST)
                if form.is_valid():
                    evaluation_set_validity(evaluations, False, form.cleaned_data['comment'], request.user.id)
                else:
                    messages.error(request, 'Please fill in the reason of invalidation.')
                    return self_rd

            elif op.action == 'validate':
                evaluation_set_validity(evaluations, True)
            else:
                messages.error(request, 'The operation cannot be performed. (invalid action)')
                op.delete()
                return rd

            op.has_started = True
            op.save()
            return rd
        else:  # ask for a confirmation
            if op.action == 'invalidate' or op.action == 'validate':
                evaluations = evaluations.filter(is_invalid=False if op.action == 'invalidate' else True)
                if not evaluations:
                    messages.warning(request, '{} submission{} already {}'.format(
                        'Selected' if op.is_bulk else 'This',
                        's are' if op.is_bulk else ' is',
                        'invalid' if op.action == 'invalidate' else 'valid'
                    ))
                    op.delete()
                    return rd

            context = {
                'title': 'Confirm operation',
                'evaluations': evaluations,
                'task': task,
                'group': task.task_group,
                'op': op,
                'form': InvalidateSubmissionForm()
            }

            return render(request, 'webapp/admin/task/confirm_operation.html', context)


@staff_member_required
def perform_action(request, s_uuid, action):
    try:
        submission = Submission.objects.get(uuid=s_uuid)
        task, role = item_is_staff('task', request.user, submission.task_id)
    except (Submission.DoesNotExist, ValueError):
        messages.warning(request, 'Unable to find submission with given uuid.')
        return redirect('staff_dashboard')

    # pass redirect argument if existent
    redirect_to = request.GET.get('next') if request.GET.get('next') else \
        reverse('staff_submission_report', args=[submission.uuid])

    if action not in ['reevaluate', 'validate', 'invalidate']:
        messages.warning(request, 'Invalid action')
        return redirect(redirect_to)

    return submission_operation_create(request.user, action, [s_uuid], task.id, redirect_to, False)
