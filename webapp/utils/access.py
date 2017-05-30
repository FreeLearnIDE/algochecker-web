import csv
import io

from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMessage
from django.shortcuts import get_object_or_404
from django.urls import reverse

from algoweb.settings import CSV_FIRST_NAME, CSV_LAST_NAME, CSV_EXTERNAL_ID, EMAIL_SENDER_INVITATION
from webapp.forms import TaskGroupAccessForm, TaskGroupInviteForm
from webapp.models import TaskGroup, Task, TaskGroupAccess, TaskGroupInviteToken
from webapp.utils.template import short_name


def get_item_with_role(item_name, user, item_id):
    """
    Returns desired item with role for a given user.
    :param item_name: Name of the item ('group' or 'task')
    :param user: User to be checked
    :param item_id: ID of the item
    :return: item object and given user's role in it
    :except: PermissionDenied, raises 404 error in case of item does not exist
    """
    if item_name == 'group':
        obj = TaskGroup
    elif item_name == 'task':
        obj = Task.objects.select_related('task_group')
    else:
        raise PermissionDenied

    item = get_object_or_404(obj, pk=item_id)

    role = item.check_membership(user)

    return item, role


def item_is_staff(item_name, user, item_id):
    """
    Checks if the `user` has an staff+ access to the item
    :param item_name:   group or task, strings
    :param user:        user, the access to be tested against
    :param item_id:     id of the item
    :return: tuple containing the item object and then the role itself
    :except: PermissionDenied, raises 404 error in case of item does not exist
    """
    item, role = get_item_with_role(item_name, user, item_id)

    if role == 'user':
        raise PermissionDenied

    return item, role


def load_csv_users(file_contents, group):
    """
    loads names and EReS ids of users from EReS CSV file
    """
    reader = csv.DictReader(filter(lambda r: r[0] != '#', io.StringIO(file_contents)), delimiter=';')
    id_list = group.taskgroupaccess_set.filter(provider_id__isnull=False).values_list('provider_id', flat=True)

    return map(lambda row: {
        'first_name': CSV_FIRST_NAME(row),
        'last_name': CSV_LAST_NAME(row),
        'provider_id': CSV_EXTERNAL_ID(row),
        'exists': CSV_EXTERNAL_ID(row) in id_list
    }, reader)


def grant_abstract_user_access(group_id, user):
    """
    grants an access for the user based on the provider_id thus "abstract"
    :param group_id: id of the TaskGroup
    :param user: dictionary with user data
    :return: newly created TaskGroupAccess object
    """
    try:
        access, created = TaskGroupAccess.objects.update_or_create(
            task_group_id=group_id,
            provider_id=user['provider_id']
        )

        if created:
            # role 'user' is set explicitly only to newly created access privileges
            # in order not to overwrite any possible "higher" permissions
            access.role = 'user'
            access.provider_first_name = short_name(user['first_name'])
            access.provider_last_name = user['last_name']
            access.save()
    except KeyError:
        return None

    return created


def grant_single_access(request, role, group):
    """
    grants single user access to group by username
    requires request to hold POST data from the TaskGroupAccessForm
    :return: tuple with message type and message contents
    """
    gc_form = TaskGroupAccessForm(request.POST)

    if not gc_form.is_valid():
        return messages.ERROR, 'Grant by username form was filled incorrectly.'

    username = gc_form.cleaned_data['username']
    extra_message = ''

    if role == 'user' and group.is_public:
        return messages.WARNING, 'user access cannot be granted because the task is public.'

    if role not in ['dev', 'staff', 'user']:
        return messages.WARNING, 'Role {} cannot be assigned to this user.'.format(role)

    try:
        user = User.objects.get(username=username)

        if not user.is_staff and role != 'user':
            return messages.WARNING, 'User with no staff permissions cannot be granted {} access.'.format(role)

        try:
            access = TaskGroupAccess.objects.get_user_access(user, group)

            if access.role == 'owner':
                return messages.ERROR, "Owner's role cannot be changed."

            if access.role == role:
                return messages.SUCCESS, 'Given user already has this role being set.'

            extra_message = 'Role was changed from {} to {}.'.format(access.role, role)
            access.role = role
            status = 'updated'
        except TaskGroupAccess.DoesNotExist:
            access = TaskGroupAccess(
                user=user,
                role=role,
                task_group=group
            )
            status = 'granted'

        access.save()

        return messages.SUCCESS, 'Access privileges for {} {} {} successfully. {}'.format(
            user.first_name,
            user.last_name,
            status,
            extra_message
        )

    except User.DoesNotExist:
        return messages.ERROR, 'User with given username is not registered in the system.'


def send_invitation(request, role, group):
    """
    sends an invitation email.
    requires request to hold POST data from the TaskGroupInviteForm
    :return: tuple with message type and message contents
    """
    i_form = TaskGroupInviteForm(request.POST)
    if not i_form.is_valid():
        return messages.ERROR, 'Invite form was filled incorrectly'

    email = i_form.cleaned_data['email']
    extra = ''

    try:
        token = TaskGroupInviteToken.objects.get(is_valid=True, sent_to=email)
        if token.check_valid():
            token.is_valid = False
            token.save()
            extra = 'Previous token sent to this email has been revoked.'
    except TaskGroupInviteToken.DoesNotExist:
        pass

    inv = TaskGroupInviteToken(
        created_by=request.user,
        sent_to=email,
        role=role,
        task_group=group
    )
    inv.save()

    html_content = '''
    <h2>Invitation to the Algochecker</h2>
    <p>You have been invited to the task group &laquo;{}&raquo; by {} {}.</p>
    <p>{} role has been assigned to you. In order to proceed, please click <a href="{}">this</a> link.</p>
    '''.format(
        group.name,
        request.user.first_name,
        request.user.last_name,
        role,
        request.build_absolute_uri(reverse('access_invite_link', args=[inv.access_token])))

    msg = EmailMessage(
        'Invitation to Algochecker',
        html_content,
        EMAIL_SENDER_INVITATION,
        [email]
    )
    msg.content_subtype = "html"  # main content is now text/html
    msg.send()

    return messages.SUCCESS, 'Invitation to this group with role {} sent successfully to {}. {}'.format(
        role, email, extra
    )

__all__ = [
    "get_item_with_role",
    "item_is_staff",
    "load_csv_users",
    "grant_abstract_user_access",
    "grant_single_access",
    "send_invitation"
]
