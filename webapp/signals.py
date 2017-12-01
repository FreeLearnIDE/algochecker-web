from django.db.models.signals import pre_save
from django.dispatch import receiver
import django_cas_ng.signals

from webapp.models import TaskGroupAccess, Task, CASUserMeta
from webapp.utils.main import apply_markdown
from webapp.utils.template import short_name
from algoweb.settings import CAS_KEY_FIRST_NAME, CAS_KEY_LAST_NAME, CAS_KEY_EMAIL, \
    CAS_KEY_ADMIN_FLAG, CAS_KEY_ADMIN_FLAG_VALUES


# for static analysis this should exist
def load():
    pass


@receiver(django_cas_ng.signals.cas_user_authenticated)
def cas_user_authenticated(sender, user, created, attributes, ticket, service, **kwargs):
    # update the data in order to reflect what we had received from CAS
    # FIXME temporary hack for the case of too long first names/last names
    user.first_name = short_name(attributes[CAS_KEY_FIRST_NAME], max_subparts=2)[:30]
    user.last_name = short_name(attributes[CAS_KEY_LAST_NAME], max_subparts=2)[:30]
    user.email = attributes[CAS_KEY_EMAIL]

    try:
        cas_user_meta = CASUserMeta.objects.get(user=user)
    except CASUserMeta.DoesNotExist:
        cas_user_meta = CASUserMeta(user=user)

    cas_user_meta.attributes = attributes
    cas_user_meta.save()

    if attributes[CAS_KEY_ADMIN_FLAG] in CAS_KEY_ADMIN_FLAG_VALUES:
        user.is_staff = True

    user.save()


@receiver(pre_save, sender=TaskGroupAccess)
def pre_save_task_group_access(sender, instance, *args, **kwargs):
    if instance.user and instance.provider_id is None:
        try:
            instance.provider_id = instance.user.casusermeta.ext_id
        except CASUserMeta.DoesNotExist:
            pass


@receiver(pre_save, sender=Task)
def increment_version(instance, **kwargs):
    instance.version += 1


@receiver(pre_save, sender=Task)
def generate_markdown(instance, **kwargs):
    instance.description_cache = apply_markdown(instance.description)
