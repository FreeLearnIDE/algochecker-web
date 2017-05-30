"use strict";

var dashboard = {
    data: {
        archived_groups_wrap: '#dashboard-archived-groups-wrap',
        handler: '#archived-handler',
        hide_text: 'Hide',
        show_text: 'Show'
    },
    toggle_archived: function(e) {
        $(dashboard.data.archived_groups_wrap).toggleClass('hidden');
        $(dashboard.data.handler).text(
            $(dashboard.data.handler).text() == dashboard.data.show_text ? dashboard.data.hide_text : dashboard.data.show_text
        );
        helpers.prevent(e)
    },
    init: function() {
        $(dashboard.data.handler).click(dashboard.toggle_archived)
    }
};

$(dashboard.init);
