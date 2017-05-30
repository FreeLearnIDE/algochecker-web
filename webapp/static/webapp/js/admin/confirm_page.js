"use strict";

var actions = {
    selectors: {
        dialog: '#action-dialog',
        form: '#action-form',
        cnf_button: '#btn-confirm',
        cnl_button: '#btn-cancel',
        send_callback: ['submission-operation', 'group-copy']
    },
    cancel_normal: function(e) {
        if ('referrer' in document) {
            location.replace(document.referrer);
        } else {
            window.history.back();
        }
        helpers.prevent(e);
    },
    cancel_callback: function(e) {
        $('#sbm-cancel').val(1);
        actions.submit();
        helpers.prevent(e);
    },
    submit: function(e) {
        $(actions.selectors.form).submit();
        helpers.prevent(e);
    },
    init: function() {
        $(actions.selectors.cnf_button).click(actions.submit);

        for (var i = 0; i < actions.selectors.send_callback.length; i++) {
            if ($(actions.selectors.dialog).hasClass(actions.selectors.send_callback[i])) {
                $(actions.selectors.cnl_button).click(actions.cancel_callback);
                return;
            }
        }
        $(actions.selectors.cnl_button).click(actions.cancel_normal);
    }
};

$(actions.init);
