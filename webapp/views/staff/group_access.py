from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect

from webapp.forms import TaskGroupCSVForm, TaskGroupAccessForm, TaskGroupInviteForm
from webapp.models import TaskGroupInviteToken, TaskGroupAccess
from webapp.utils.access import *
from webapp.utils.main import build_http_array


@staff_member_required
def index(request, group_id):
    group, role = item_is_staff('group', request.user, group_id)

    access_all = group.taskgroupaccess_set.filter(~Q(role='dev')).select_related('user').order_by(
        'provider_last_name',
        'provider_first_name',
        'user__last_name',
        'user__first_name'
    )
    access_user = []
    access_staff = []

    for access in access_all:
        if access.role == 'user':
            access_user.append(access)
        else:
            access_staff.append(access)

    context = {
        'user_role': role,
        'group': group,
        'access_user': access_user,
        'access_staff': access_staff,
        'invitations_count': group.taskgroupinvitetoken_set.count(),
        'title': 'Access control for ' + group.name
    }

    return render(request, 'webapp/admin/group/access/index.html', context)


@staff_member_required
def invitation_list(request, group_id):
    group, role = item_is_staff('group', request.user, group_id)

    invitations = group.taskgroupinvitetoken_set.all().select_related('created_by').order_by('creation_date')

    if not invitations:
        messages.warning(request, 'There are no invitations for this group.')
        return redirect('staff_group_access', group_id=group_id)

    context = {
        'group': group,
        'role': role,
        'title': 'Invitations to the {}'.format(group.name),
        'invitations': invitations
    }

    return render(request, 'webapp/admin/group/access/invitations.html', context)


@staff_member_required
def revoke_invitation(request, invitation_id, group_id):
    token = get_object_or_404(TaskGroupInviteToken, pk=invitation_id)
    if token.check_valid():
        token.is_valid = False
        token.save()
        messages.success(request, 'Invitation successfully revoked.')
    else:
        messages.error(request, 'Unable to revoke the invitation.')

    return redirect('staff_group_invitation_list', group_id=group_id)


@staff_member_required
def change(request, group_id):
    group, role = item_is_staff('group', request.user, group_id)

    if group.archived:
        messages.warning(request, 'This group is archived. No change of access type is allowed while archived.')

    elif request.method == 'POST':
        if not group.is_public:
            # if group is not public - we are about to make it public.
            # Hence all TaskGroupAccess'es for users should be revoked
            group.taskgroupaccess_set.filter(role='user').delete()

        group.is_public = not group.is_public
        group.save()
        messages.success(request, 'Access type successfully changed.')
    else:
        return render(request, 'webapp/admin/group/access/change_type.html', {
            'group': group,
            'title': 'Change access to ' + group.name
        })

    return redirect('staff_group_access', group_id=group.id)


@staff_member_required
def revoke_user_access(request, group_id, id_type, member_id):
    group, role = item_is_staff('group', request.user, group_id)

    rd = redirect('staff_group_access', group_id=group.id)

    try:
        if id_type == 'user':
            cond = Q(user_id=member_id)
        elif id_type == 'provider':
            cond = Q(provider_id=member_id)
        else:
            messages.error(request, 'Undefined id type')
            return rd

        member = group.taskgroupaccess_set.get(cond & ~Q(role='owner'))
    except TaskGroupAccess.DoesNotExist:
        messages.warning(request, 'User to revoke access cannot be found.')
        return rd

    own = member.user and member.user == request.user

    if request.method == 'POST':
        if own:
            # if revoking own access - redirect to the dashboard
            rd = redirect('staff_dashboard')

        member.delete()
        messages.success(request, 'Access successfully revoked')
        return rd

    context = {
        'member': member,
        'own': own,
        'id_type': id_type,
        'member_id': member_id,
        'group': group,
        'title': 'Revoke access'
    }

    return render(request, 'webapp/admin/group/access/revoke.html', context)


@staff_member_required
def csv_import(request, group_id):
    users = build_http_array(request.POST, 'user')
    counter = 0
    selected_counter = 0

    for key in users:
        if 'add' in users[key] and users[key]['add']:
            selected_counter += 1

            if grant_abstract_user_access(group_id, users[key]):
                counter += 1

    if counter:
        messages.success(request, 'Successfully imported {} user{}.'.format(
            str(counter),
            's' if counter > 1 else ''
        ))
    elif selected_counter:
        messages.warning(request, 'No new users were imported because selected ones are already on the list.')
    else:
        messages.warning(request, 'No new users were imported.')

    return redirect('staff_group_access', group_id=group_id)


@staff_member_required
def user(request, group_id):
    group, role = item_is_staff('group', request.user, group_id)

    if group.is_public:
        messages.warning(request, 'Unable to add users because this group is public. All users have an access.')
        return redirect('staff_group_access', group_id=group.id)

    if request.method == 'POST':
        if 'upload_csv' in request.POST:
            csv_form = TaskGroupCSVForm(request.POST, request.FILES)
            if csv_form.is_valid():
                file = request.FILES['file']
                if not file.name.endswith('.csv'):
                    messages.error(request, 'Wrong file type. Only .csv files are supported.')
                elif file.size > 64000:
                    messages.error(request, 'File size exceeds 64KB.')
                else:
                    try:
                        users = load_csv_users(file.read().decode('utf-8'), group)
                        return render(request, 'webapp/admin/group/access/csv_import.html', {
                            'users': users,
                            'group': group,
                            'title': 'Choose users to import'
                        })
                    except (UnicodeDecodeError, KeyError, IndexError):
                        messages.warning(request, 'File parsing failure. The file may be corrupted.')
            else:
                messages.error(request, 'No file was uploaded')
        elif 'grant_single' in request.POST or 'send_invitation' in request.POST:
            if 'grant_single' in request.POST:
                level, message = grant_single_access(request, 'user', group)
            else:
                level, message = send_invitation(request, 'user', group)

            messages.add_message(request, level, message)
            if level == messages.SUCCESS:
                return redirect('staff_group_access', group_id=group.id)

    context = {
        'type': 'user',
        'csv_form': TaskGroupCSVForm(),
        'grant_single_form': TaskGroupAccessForm(),
        'single_invitation_form': TaskGroupInviteForm(),
        'user_role': role,
        'group': group,
        'title': 'Add user access for ' + group.name
    }
    return render(request, 'webapp/admin/group/access/add.html', context)


@staff_member_required
def staff(request, group_id):
    group, role = item_is_staff('group', request.user, group_id)

    if request.method == 'POST':
        if 'grant_single' in request.POST:
            level, message = grant_single_access(request, 'staff', group)
        elif 'send_invitation' in request.POST:
            level, message = send_invitation(request, 'staff', group)
        else:
            return redirect('staff_group_access_staff', group_id=group.id)

        messages.add_message(request, level, message)
        if level == messages.SUCCESS:
            return redirect('staff_group_access', group_id=group.id)

    context = {
        'type': 'staff',
        'grant_single_form': TaskGroupAccessForm(),
        'single_invitation_form': TaskGroupInviteForm(),
        'user_role': role,
        'group': group,
        'title': 'Add staff access for ' + group.name
    }
    return render(request, 'webapp/admin/group/access/add.html', context)
