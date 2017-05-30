from django import forms
from django.forms import Form, ModelForm
from django.utils import timezone

from webapp.models import Task, TaskGroup, TaskGroupSet
from webapp.validators import validate_package
from webapp.widgets import CustomSplitDateTimeWidget


class TaskGroupForm(ModelForm):
    class Meta:
        model = TaskGroup
        fields = '__all__'
        exclude = ['raw_csv', 'is_public']
        labels = {
            'name': 'Group name',
            'description': 'Description',
            'is_public': 'Public'
        }

        help_texts = {
            'is_public': 'determines whether group is public or not'
        }

    def __init__(self, *args, **kwargs):
        kwargs.pop('edit', None)
        super(TaskGroupForm, self).__init__(*args, **kwargs)


class TaskGroupCSVForm(Form):
    file = forms.FileField()
    upload_csv = forms.IntegerField(initial=1, widget=forms.HiddenInput)


class TaskGroupAccessForm(Form):
    grant_single = forms.IntegerField(initial=1, widget=forms.HiddenInput)
    username = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'placeholder': 'username', 'class': 'form-control'})
    )


class TaskGroupInviteForm(Form):
    send_invitation = forms.CharField(initial=1, widget=forms.HiddenInput)
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'E-mail', 'class': 'form-control'}))


class TaskForm(ModelForm):
    deadline = forms.SplitDateTimeField(
        input_date_formats=['%Y-%m-%d'],
        input_time_formats=['%H:%M:%S'],
        widget=CustomSplitDateTimeWidget(
            date_attrs={'placeholder': 'Date: yyyy-mm-dd', 'data-dpk': '1'},
            time_attrs={'placeholder': 'Time: hh:mm:ss'},
            date_format='%Y-%m-%d',
            time_format='%H:%M:%S'
        ),
        help_text='Set blank if no deadline',
        required=False
    )
    package = forms.FileField(
        label='Package',
        help_text='.zip package created according to guidelines',
        widget=forms.FileInput,
        validators=[validate_package]
    )

    class Meta:
        model = Task
        fields = '__all__'
        exclude = ['task_group']
        labels = {
            'name': 'Task name',
            'description_brief': 'Short description',
            'tg_set': 'Task set',
            'submission_limit': 'Submissions limit',
            'result_type': 'Result priority',
            'files_count_limit': 'Max. files amount',
            'file_size_limit': 'Max. file size'
        }

        help_texts = {
            'description': 'Markdown can be used here',
            'description_brief': 'Short description will be shown on the tasks list page',
            'tg_set': 'Task set to which this task belongs',
            'result_type': 'Pattern, according to which results list will appear.',
            'submission_limit': 'Limit of submissions per user. Put 0 if unlimited',
            'files_count_limit': 'Maximal amount of files in one submission',
            'file_size_limit': 'Maximal size of single file (in bytes)'
        }
        widgets = {
            'package': forms.FileInput
        }

    def __init__(self, *args, **kwargs):
        edit = kwargs.pop('edit', None)
        super(TaskForm, self).__init__(*args, **kwargs)

        if edit:
            self.fields['package'].label = 'New package'
            self.fields['package'].required = False
            self.fields['tg_set'].queryset = TaskGroupSet.objects.filter(task_group_id=self.instance.task_group_id)
        else:
            self.fields['deadline'].initial = timezone.now() + timezone.timedelta(days=14)
            del self.fields['tg_set']


class InvalidateSubmissionForm(Form):
    comment = forms.CharField(
        label='Your comment',
        widget=forms.Textarea(attrs={'placeholder': 'Type in the reason here'}),
        required=True
    )


class CopyTaskGroup(Form):
    name = forms.CharField(
        label='New name',
        widget=forms.TextInput(attrs={'placeholder': 'New name'}),
        required=True
    )
    description = forms.CharField(
        label='Description',
        widget=forms.Textarea(attrs={'placeholder': 'Type in new description (optional)'}),
        required=False
    )


class TaskGroupSetForm(ModelForm):
    class Meta:
        model = TaskGroupSet
        fields = '__all__'
        exclude = ['task_group']
        labels = {
            'name': 'Name',
            'description': 'Description'
        }


class TaskGroupBulkDeadlines(Form):
    set_id = forms.IntegerField(
        required=True,
        widget=forms.HiddenInput()
    )
    deadline = forms.SplitDateTimeField(
        input_date_formats=['%Y-%m-%d'],
        input_time_formats=['%H:%M:%S'],
        widget=CustomSplitDateTimeWidget(
            date_attrs={'placeholder': 'Date: yyyy-mm-dd', 'data-dpk': '1'},
            time_attrs={'placeholder': 'Time: hh:mm:ss'},
            date_format='%Y-%m-%d',
            time_format='%H:%M:%S'
        ),
        required=False,
        label='name of the set'
    )

    def __init__(self, *args, **kwargs):
        super(TaskGroupBulkDeadlines, self).__init__(*args, **kwargs)
        self.fields['deadline'].label = self.initial.get('set_name')


class FeedbackFrom(Form):
    TOPIC = (
        ('', '- Please select -'),
        ('proposal', 'I have a proposal'),
        ('report', 'I want to report a problem'),
        ('question', 'I have a question'),
        ('other', 'Other')
    )
    theme = forms.ChoiceField(label='What happened?', choices=TOPIC)
    email = forms.EmailField(
        label='',
        widget=forms.EmailInput(attrs={'placeholder': 'Contact e-mail'})
    )
    content = forms.CharField(
        label='Write your message here:',
        widget=forms.Textarea
    )
