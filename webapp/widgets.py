from django import forms
from django.forms.utils import to_current_timezone


class CustomSplitDateTimeWidget(forms.MultiWidget):
    """
    Custom SplitDateTimeWidget which allows to pass separate attributes for both DateInput and TimeInput
    """
    def __init__(self, date_attrs=None, time_attrs=None, date_format=None, time_format=None):
        widgets = (
            forms.DateInput(attrs=date_attrs, format=date_format),
            forms.TimeInput(attrs=time_attrs, format=time_format),
        )
        super(CustomSplitDateTimeWidget, self).__init__(widgets)

    def format_output(self, rendered_widgets):
        output = ''

        for w in rendered_widgets:
            output += '<div class="col-md-6">{}</div>'.format(w)

        return '<div class="row">{}</div>'.format(output)

    def decompress(self, value):
        if value:
            value = to_current_timezone(value)
            return [value.date(), value.time().replace(microsecond=0)]
        return [None, None]
