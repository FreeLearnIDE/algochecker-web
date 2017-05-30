from django.db import models
from django.db.models import Q


class TaskGroupAccessManager(models.Manager):

    def get_user_access(self, user, task_group):
        """
        Checks if user has any access defined for a particular task group,
        keeping in mind that he may have access granted either directly or by provider_id
        """
        from webapp.models import CASUserMeta
        try:
            provider_id = user.casusermeta.ext_id
        except CASUserMeta.DoesNotExist:
            provider_id = None

        cond = ((~Q(provider_id=None) & Q(provider_id=provider_id)) | Q(user=user)) & Q(task_group=task_group)
        access = self.get(cond)

        # ensure that user is bound both ways
        if access.user_id != user.id or access.provider_id != provider_id:
            access.user = user
            access.provider_id = provider_id
            access.save()

        return access
