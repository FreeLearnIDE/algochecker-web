from django.contrib import admin

from .models import *


admin.site.register(Task)
admin.site.register(Submission)
admin.site.register(SubmissionEvaluation)
admin.site.register(SubmissionFile)
admin.site.register(SubmissionTest)
admin.site.register(SubmissionOperation)
admin.site.register(CASUserMeta)
admin.site.register(TaskGroup)
admin.site.register(TaskGroupSet)
admin.site.register(TaskGroupAccess)
admin.site.register(TaskGroupInviteToken)
