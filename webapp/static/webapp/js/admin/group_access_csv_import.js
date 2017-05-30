"use strict";

var csv_import = {
    data: {
        checkbox: '.user-adder',
        toggle: '.select-toggle'
    },

    toggle_select: function(act) {
        $('input[disabled!="disabled"]' + csv_import.data.checkbox).prop('checked', act);
    },

    init: function() {
        $(csv_import.data.toggle).click(function() {
            csv_import.toggle_select($.parseJSON($(this).attr('data-select')))
        });
    }
};

$(csv_import.init);
