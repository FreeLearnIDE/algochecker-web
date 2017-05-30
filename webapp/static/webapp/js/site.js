"use strict";

function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie != '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = $.trim(cookies[i]);
            if (cookie.substring(0, name.length + 1) == (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

$(function() {
    // global on load events
    $('[data-toggle="tooltip"]').tooltip();
});


var helpers = {
    // Lazy glyphicon generator (with space!)
    getGlyphicon: function (icon) {
        return '<span class="glyphicon glyphicon-' + icon + '"></span> ';
    },
    // Lazy label with icon generator
    generateStatus: function (color, icon, text) {
        return '<span class="label label-' + color + '">' + helpers.getGlyphicon(icon) + text + '</span>';
    },
    // Putting `content` into `$object` only if it differs from current
    replaceIfNew: function ($object, content) {
        if (content != $object.html()) {
            $object.html(content);
        }
    },
    // initializes hover line highlight (in pre) for the report
    initHoverHl: function() {
        $('.highlight .l-code, .highlight .l-num').hover(function(e) {
            var parent = $(e.target).parents('.hl-wrap').attr('id'); // in case of multiple files
            var n = $(this).attr('data-n');

            $('#' + parent + ' .l-num,' + '#' + parent + ' .l-code').removeClass('hover');
            $('#' + parent + ' .l-num[data-n="' + n + '"],' + '#' + parent + ' .l-code[data-n="' + n + '"]').addClass('hover');
        });
        $(window).hover(function(e) {
            if (!$(e.target).parents('.highlight').length) {
                $('.highlight .l-num, .highlight .l-code').removeClass('hover');
            }
        });
    },
    // prevents the default action and further propagation (by default)
    prevent: function(e, p) {
        var prop = (typeof p !== 'undefined') ? p : true;
        e.preventDefault();
        if (prop)
            e.stopPropagation();
    }
};

String.prototype.format = function() {
    // code from http://stackoverflow.com/a/13639670 with modifications due to "use strict";
    var args = arguments;
    var index = 0;
    return this.replace(/\{(\w*)\}/g, function(match, key) {
        if (key === '') {
            key = index;
            index++
        }
        if (key == +key) {
            return args[key] !== 'undefined'
                ? args[key]
                : match;
        } else {
            for (var i = 0; i < args.length; i++) {
                if (typeof args[i] === 'object' && typeof args[i][key] !== 'undefined') {
                    return args[i][key];
                }
            }
            return match;
        }
    });
};

$.fn.shiftSelectable = function() {
    // code from https://gist.github.com/DelvarWorld/3784055 with slight modifications
    var lastChecked,
        $boxes = this;

    $boxes.click(function(evt) {
        if(!lastChecked) {
            lastChecked = this;
            return;
        }

        if(evt.shiftKey) {
            var start = $boxes.index(this),
                end = $boxes.index(lastChecked);
            $boxes.slice(Math.min(start, end), Math.max(start, end) + 1)
                .prop('checked', lastChecked.checked)
                .trigger('change');
        }

        lastChecked = this;
    });
};
