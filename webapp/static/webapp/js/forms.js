"use strict";

var forms = {
    settings: {
        'textHideDelay':    4000, // timeout after which text is being hidden
        'classRemoveDelay': 7000, // timeout after which hasErrorSelector is removed from form-group
        'textHideSpeed':    100,  // speed of hiding text
        'hasErrorSelector': 'has-error', // selector of error class (with no dot!)
        'errorWrapSelector': '.help-block.error-timeout'
    },

    init: function () {
        /*
        var $errorTexts = $(forms.settings.errorWrapSelector),
            $errorClass =  $('.' + forms.settings.hasErrorSelector);

        // removing error text(s) if present
        if ($errorTexts.length) {
            $errorTexts
                .delay(forms.settings.textHideDelay)
                .slideUp(forms.settings.textHideSpeed);
        }

        // removing has-error selector(s) if present
        if ($errorClass.length) {
            setTimeout(function () {
                $errorClass
                    .removeClass(forms.settings.hasErrorSelector);
            }, forms.settings.classRemoveDelay);
        }*/

        var $deadlineField = $('*[data-dpk=1]');
        if ($deadlineField.length) {
            $deadlineField.datepicker({
                format: 'yyyy-mm-dd',
                weekStart: 1,
                todayHighlight: true
            });
        }
    },

    validation: {
        // to be introduced
    }
};

$(forms.init);
