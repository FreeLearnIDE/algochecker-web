"use strict";

var sbmlist = {
    init: function() {
        $('.checkbox-handler').shiftSelectable();
        $('.select-trigger, .submit-trigger').click(sbmlist.handleClick);
        $('.tr-handler').click(sbmlist.toggle_me);
    },
    handleClick: function(e) {
        var data = $.parseJSON($(e.target).attr('data-action'));

        if(!data && !data.action && !data.args) return;

        switch (data.action) {
            case 'select': sbmlist.select.apply(this, data.args);  break;
            case 'select_all': sbmlist.select_all.apply(this, data.args); break;
            case 'submit': sbmlist.submit.apply(this, data.args); break;
        }
    },
    submit: function(act) {
        $('#action_input').val(act);
        $('#action_form').submit()
    },
    select: function(type, select) {
        $('tr[data-' + type + '="true"] input.checkbox-handler').prop('checked', (typeof select === 'undefined') ? true : select);
    },
    select_all: function(select) {
        $('.checkbox-handler').prop('checked', (typeof select === 'undefined') ? true : select);
    },
    toggle_me: function(ev) {
        if (!(
            $(ev.target).hasClass('checkbox-handler') ||
            $(ev.target).hasClass('view-report') ||
            $(ev.target).parent('a').hasClass('view-report')
        )) {
            $(this).find('input.checkbox-handler').prop('checked', function (i, sel) { return !sel });
        }
    }
};

$(sbmlist.init());
