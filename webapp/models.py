import datetime
import uuid

from collections import namedtuple
from json import dumps

from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Q
from django.utils.timezone import utc
from django.utils.safestring import mark_safe

from os.path import join as path_join

from algoweb.settings import CAS_KEY_EXTERNAL_ID


class TaskGroup(models.Model):
    name = models.CharField(max_length=64)
    is_public = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)
    archived = models.BooleanField(default=False, editable=False)

    class Meta:
        ordering = ['name']

    def check_membership(self, user):
        """
        get string describing membership.
        updates TaskGroupAccess object in case of missing app-given user_id
        :return: string with membership
        :except: raises PermissionDenied in case of no membership
        """

        try:
            access = self.taskgroupaccess_set.get_user_access(user, self)
        except TaskGroupAccess.DoesNotExist:
            if user.is_superuser:
                access = TaskGroupAccess(
                    user=user,
                    role='dev',
                    task_group=self
                )
                access.save()
                return 'dev'
            else:
                if self.is_public:
                    return 'user'
                else:
                    raise PermissionDenied

        return access.role

    def __str__(self):
        return 'Task group {} '.format(self.name)


class TaskGroupSet(models.Model):
    name = models.CharField(max_length=64)
    description = models.TextField(blank=True, null=True)
    task_group = models.ForeignKey(TaskGroup, on_delete=models.CASCADE)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return 'Task set "{}"'.format(self.name)


class BaseAccessData(models.Model):
    ROLES = (
        # regular permissions - user role
        ('user', 'user'),
        # view results, edit permissions, archive/publish - staff, owner, dev
        ('staff', 'staff'),
        ('owner', 'owner'),
        ('dev', 'dev')
    )

    role = models.CharField(max_length=12, choices=ROLES)
    task_group = models.ForeignKey(TaskGroup, on_delete=models.CASCADE)

    class Meta:
        abstract = True


class TaskGroupInviteToken(BaseAccessData):
    access_token = models.UUIDField(default=uuid.uuid4)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    sent_to = models.CharField(max_length=64)
    creation_date = models.DateTimeField(auto_now_add=True)
    is_valid = models.BooleanField(default=True)

    def check_valid(self):
        now = datetime.datetime.utcnow().replace(tzinfo=utc)
        if self.is_valid and (now - self.creation_date) > datetime.timedelta(hours=72):
            self.is_valid = False
            self.save()

        return self.is_valid

    def __str__(self):
        return 'invite token {} sent to {}, role {}'.format(self.access_token, self.sent_to, self.role)


class TaskGroupAccess(BaseAccessData):
    from webapp.managers import TaskGroupAccessManager
    objects = TaskGroupAccessManager()
    user = models.ForeignKey(User, models.SET_NULL, blank=True, null=True)
    provider_id = models.CharField(null=True, blank=True, max_length=32)
    provider_first_name = models.CharField(max_length=64, null=True, blank=True)
    provider_last_name = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        unique_together = (('user', 'task_group'), ('provider_id', 'task_group'))

    def __str__(self):
        return '{}: {} with uid={}, pid={}'.format(
            self.task_group.name,
            self.role,
            self.user_id,
            self.provider_id
        )


class Task(models.Model):
    # IN STAFF (task results view):
    RESULT_TYPE = (
        # best -> best result is shown
        ('best', 'best'),
        # latest -> last submitted result is shown
        ('latest', 'latest')
    )

    USER_LIMITS = namedtuple('USER_LIMITS', ['total', 'used', 'remaining', 'can_submit'])
    DEADLINE_DATA = namedtuple('DEADLINE_DATA', ['left', 'soon', 'missed'])

    name = models.CharField(max_length=64)
    description = models.TextField(blank=False)
    description_brief = models.CharField(blank=True, max_length=255)
    description_cache = models.TextField(default="", editable=False)
    package = models.FileField(upload_to='task/package/')
    version = models.IntegerField(default=1, editable=False)
    archived = models.BooleanField(default=False, editable=False)
    published = models.BooleanField(default=False, editable=False)

    # deleting owner will cause the task to be deleted
    owner = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'is_staff': True}, editable=False)
    # relationship with the group. task cannot exist outside the group
    task_group = models.ForeignKey(TaskGroup, on_delete=models.CASCADE)
    # relationship with the set. task cannot exist outside of the set
    tg_set = models.ForeignKey(TaskGroupSet, on_delete=models.CASCADE)

    # decides whether to show best or latest result in staff panel
    result_type = models.CharField(default='best', max_length=12, choices=RESULT_TYPE)

    # -- LIMITS --
    # limit of submissions for a single user
    submission_limit = models.IntegerField(default=0)
    # limit number of files submitted
    files_count_limit = models.PositiveIntegerField(default=15)
    # limit on file size
    file_size_limit = models.PositiveIntegerField(default=64000)
    # if blank then task has no deadline
    deadline = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['name']

    def get_deadline_data(self):
        """
        get dictionary describing deadline data
        :return: tuple with args 'left', 'soon', 'missed' if deadline exists, else - None
        """

        if self.deadline:
            seconds_left = (self.deadline - datetime.datetime.utcnow().replace(tzinfo=utc)).total_seconds()
            return self.DEADLINE_DATA(
                left=seconds_left,
                soon=seconds_left < 604800,  # one week
                missed=seconds_left < 0
            )
        else:
            return None

    def get_user_limits(self, user_id):
        """
        get dictionary describing limit usage for particular user

        :return: dict with keys 'total', 'used' and 'remaining'
        :Note: 'remaining' and 'total' may be None - this means no limit
        """
        condition = Q(task_id=self.id) & Q(user_id=user_id) & \
            ~Q(submissionevaluation__status='internal_error') & Q(reevaluated=False)

        limit = Task.objects.get(pk=self.id).submission_limit
        used = Submission.objects.filter(condition).count()

        if limit > 0:
            return self.USER_LIMITS(total=limit, used=used, remaining=limit-used, can_submit=limit-used > 0)
        else:
            return self.USER_LIMITS(total=None, used=used, remaining=None, can_submit=True)

    def check_membership(self, user):
        """
        an alias for checking membership through TaskGroup
        """
        return self.task_group.check_membership(user)

    @property
    def get_deadline_label(self):
        """
        get html label regarding the deadline
        :return: html string
        """

        deadline = self.get_deadline_data()
        html = ''

        if deadline:
            template = '<span class="label label-{} task-label pull-right">{}</span>'
            if deadline.missed:
                html = template.format('danger', 'after deadline')
            else:
                if deadline.soon:
                    html = template.format('warning', 'soon deadline')
                else:
                    html = template.format('success', 'before deadline')

        return mark_safe(html)

    def __str__(self):
        return self.name


class Submission(models.Model):
    uuid = models.UUIDField(primary_key=True)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owner')
    submitted = models.DateTimeField(auto_now_add=True, blank=True)
    queue_seq_number = models.BigIntegerField(default=0)
    queue_priority = models.CharField(max_length=16, default='medium')

    # re-evaluation related fields
    reevaluated = models.BooleanField(default=False)
    copy_of = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True)
    invoked_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='invoker')

    class Meta:
        ordering = ['submitted']

    def __str__(self):
        return '{} by {} ({:%d/%m/%Y %H:%M:%S})'.format(self.task.name, self.user.username, self.submitted)


def get_submission_filename(self, filename):
    return path_join('submission', str(self.submission.uuid), filename)


class SubmissionFile(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE)
    name = models.CharField(max_length=64)
    contents = models.FileField(upload_to=get_submission_filename)

    def __str__(self):
        return self.name


class SubmissionEvaluation(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE)
    received = models.DateTimeField(auto_now_add=True)
    message = models.TextField(null=True)
    status = models.CharField(max_length=32)
    score = models.IntegerField(null=True)
    # worker time-related data
    worker_start_time = models.BigIntegerField(null=True)
    worker_end_time = models.BigIntegerField(null=True)
    worker_took_time = models.IntegerField(null=True)
    # invalidation related fields
    is_invalid = models.BooleanField(default=False, blank=False)
    invalidated_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    invalidated_at = models.DateTimeField(blank=True, null=True)
    invalidation_comment = models.TextField(blank=True, null=True)

    def __str__(self):
        return '{} ({}%), solution for {}'.format(self.status, self.score, self.submission)

    @property
    def view_info(self):
        result = {
            'color': 'danger',
            'message': 'Unknown status ({})'.format(self.status),
            'status': 'unknown'
        }
        if self.status == 'ok':
            if self.score > 80:
                result = {
                    'color': 'success',
                    'message': 'Perfect Work! Well done'
                }
            elif self.score > 59:
                result = {
                    'color': 'success',
                    'message': 'Your result is okay'
                }
            elif self.score < 39:
                result = {
                    'color': 'danger',
                    'message': 'Your result is unsatisfactory'
                }
            else:
                result = {
                    'color': 'warning',
                    'message': 'Your result is satisfactory'
                }

        elif self.status == 'internal_error':
            result = {
                'color': 'warning',
                'message': 'Error on our side occurred during evaluation of your work.',
                'status': 'worker fail'
            }
        elif self.status == 'compile_error':
            result = {
                'color': 'danger',
                'message': 'Compilation failed. Check the report for more info',
                'status': 'compilation failed'
            }

        if self.is_invalid:
            result['color'] = 'danger'
            result['message'] = 'This submission was invalidated by the staff member'

        return result


class SubmissionTest(models.Model):
    evaluation = models.ForeignKey(SubmissionEvaluation, on_delete=models.CASCADE)
    name = models.CharField(max_length=32)
    status = models.CharField(max_length=32)
    time = models.IntegerField(null=True)
    memory = models.IntegerField(null=True)
    points = models.FloatField(null=False)
    max_points = models.FloatField(null=False)
    output = models.TextField(null=True)
    # options are: Null, "private" - (staff only), "public" - (staff & user)
    output_visibility = models.CharField(null=True, max_length=10)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return '{}: {} ({} ms)'.format(self.name, self.status, self.time)

    @property
    def tpl_data(self):
        if self.status == 'ok':
            return {
                'status_info': 'execution succeeded',
                'status_color': 'success'
            }
        if self.status == 'soft_timeout' or self.status == 'hard_timeout':
            return {
                'status_info': 'program failed to execute within given time limit',
                'status_color': 'warning',
                'time_color': 'danger'
            }
        if self.status == 'bad_exit_code':
            return {
                'status_info': 'execution failed with non-zero exit code',
                'status_color': 'danger'
            }
        if self.status == 'bad_answer':
            return {
                'status_info': 'execution succeeded, but the answer is improper',
                'status_color': 'danger'
            }
        if self.status == 'exceeded_memory':
            return {
                'status_info': 'execution succeeded, the answer is correct, but the memory limit was exceeded',
                'status_color': 'danger',
                'memory_color': 'warning'
            }
        if self.status == 'bad_unicode':
            return {
                'status_info': 'execution succeeded, but your program outputted a character which is considered '
                               'as invalid and could not be decoded, most probably there is an improper memory '
                               'reference (problem with some pointer) somewhere',
                'status_color': 'danger'
            }
        if self.status == 'no_output_file':
            return {
                'status_info': 'execution succeeded, this test requires an output file, but it was not produced',
                'status_color': 'warning'
            }

        return {
            'status_info': 'non-standard status was returned by the evaluator',
            'status_color': 'warning'
        }

    @property
    def tpl_time(self):
        if self.status == 'hard_timeout' and self.time:
            return mark_safe('&ge; {}'.format(self.time))

        if not self.time:
            return 'n/a'

        return self.time


class Operation(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    invoker = models.ForeignKey(User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    has_started = models.BooleanField(default=False)

    class Meta:
        abstract = True


class SubmissionOperation(Operation):
    ACTIONS = (
        ('reevaluate', 'reevaluate'),
        ('invalidate', 'invalidate'),
        ('validate', 'validate')
    )
    action = models.CharField(max_length=32, blank=False, choices=ACTIONS)
    submission_list = JSONField(blank=False, null=False)
    is_bulk = models.BooleanField(default=True)
    extra = JSONField(blank=True, null=True)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)


class CASExtIDNotAvailable(RuntimeError):
    pass


class CASUserMeta(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    attributes = JSONField()

    def __str__(self):
        return 'CASUserMeta for user #{}: {}'\
            .format(self.user.id, dumps(self.attributes))

    def has_ext_id(self):
        try:
            return not not self.ext_id
        except CASExtIDNotAvailable:
            return False

    @property
    def ext_id(self):
        try:
            return self.attributes[CAS_KEY_EXTERNAL_ID]
        except KeyError as e:
            raise CASExtIDNotAvailable('User CAS meta doesn\'t contain the property: {}.'
                                       .format(CAS_KEY_EXTERNAL_ID)) from e
