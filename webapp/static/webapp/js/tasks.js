"use strict";

var tasks = {
    settings: {
        updateStatus: {
            toggleClass: ".pending",
            attrID:      "data-id",
            requestUrl:  "/task/submission/status/",
            reportUrl:   "/task/report/{}",
            updateRate:  300, // .3 s
            defaultExitMessage: "Unrecognized state... Terminating."
        },
        // triggers console logging
        dev: false
    },

    // list of ids of submissions to be updated
    checkList: [],
    // mapping uuid -> $row
    objects: {},

    // initializes status check for each row with special "trigger" class specified in settings
    init: function () {
        $(tasks.settings.updateStatus.toggleClass).each(function () {
            var id = $(this).attr(tasks.settings.updateStatus.attrID);
            if (!id) return true; // if data-id is undefined - skip to the next element
            tasks.checkList.push(id);
            tasks.objects[id.split(':', 1)[0]] = $(this);
        });

        if (tasks.checkList.length) {
            tasks.updateStatus();
        }
    },

    // updates the status of all submissions that are pending
    updateStatus: function () {
        $.ajax({
            url: tasks.settings.updateStatus.requestUrl,
            type: "POST",
            data: JSON.stringify({"ids": tasks.checkList}),
            dataType: 'json',
            contentType: 'application/json; charset=utf-8'
        }).done(function (response) {
            tasks.settings.dev ? console.log(response) : '';
            if (response && response.length) {
                var length = response.length;
                for (var i = 0; i < length; i++) {
                    tasks.parseResponse(response[i]);
                }
                // call itself until checkList becomes empty
                if (tasks.checkList.length) {
                    setTimeout(function () {
                        tasks.updateStatus();
                    }, tasks.settings.updateStatus.updateRate);
                }
            }
        }).fail(function (response)
        {
            tasks.settings.dev ? console.warn("request failed... terminating... response from server:") : '';
            tasks.settings.dev ? console.log(response) : '';
            return false;
        });
    },

    parseResponse: function (response) {
        var localSettings = tasks.settings.updateStatus,
            generateStatus = helpers.generateStatus;

        var $row = tasks.objects[response.id],
            $cell =
            {
                status:    $row.find('.status'),
                progress:  $row.find('.prog-bar'),
                message:   $row.find('.message'),
                reportUrl: $row.find('.report-link')
            },
            $progressBarWrap = $cell.progress.find('.progress'),
            $progressBar = $progressBarWrap.find('.progress-bar'),
            newStatus = '',
            newMessage = '';

        switch (response.state) {
            case -1: // not found
                newStatus = generateStatus('danger', 'exclamation-sign', lang.statusNotFound);
                newMessage = lang.messageNotFound;
                break;
            case 0: // pending (in queue)
                newStatus = generateStatus('info', 'hourglass gl-half-spin', lang.statusWaiting);
                newMessage = lang.messageWaiting.format(response.position);
                break;
            case 1: // in progress (worker is working)
                var messages = {
                    'preparing': lang.messagePreparing,
                    'compiling': lang.messageCompiling,
                    'testing':   lang.messageTesting,
                    'done':      lang.messageDone
                };
                // if JobState retrieved from server is unrecognized -> terminate
                if (!response.job_state || !messages[response.job_state]) {
                    tasks.settings.dev ? console.warn(localSettings.defaultExitMessage) : '';
                    tasks.checkList = [];
                    return false;
                }
                // set status and message according to JobState
                newStatus = generateStatus('info', 'refresh gl-spin', response.job_state);
                newMessage = '<span class="text-info">Worker</span> ' + messages[response.job_state];
                break;
            case 2: // checked (done)
                switch (response.status) {
                    case 'ok':
                        newStatus = generateStatus('success', 'ok', lang.resultStatusEvaluated);
                        break;
                    case 'compile_error':
                    case 'internal_error':
                        newStatus = generateStatus('danger', 'exclamation-sign', lang.resultStatusRejected);
                        break;
                    default: // status retrieved from server is unrecognized -> terminate
                        tasks.settings.dev ? console.warn(localSettings.defaultExitMessage) : '';
                        tasks.checkList = [];
                        return false;
                }
                newMessage = response.message;
                $row.removeAttr('class');
                break;
            default: // state retrieved from server is unrecognized -> terminate
                tasks.settings.dev ? console.warn(localSettings.defaultExitMessage) : '';
                tasks.checkList = [];
                return false;
        }

        // update progress bar only if task is not in queue
        if (response.state !== 0) {
            // if no progress bar yet, then create it
            if (!$progressBarWrap.length)
                $cell.progress.html('<div class="progress"><div class="progress-bar progress-bar-striped progress-bar-default active" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"></div></div>');

            // plug current values into the progress bar
            $progressBar.css('width', response.progress + '%');
            $progressBar.attr('aria-valuenow', response.progress);
        }
        // upd innerHTML only if it differs (using helper)
        helpers.replaceIfNew($cell.status, newStatus);
        helpers.replaceIfNew($cell.message, newMessage);

        // checking if we are done
        if (response.state == -1) {
            $cell.progress.html('');
        } else if (response.state == 2) {   // put score in place of progress bar
            $cell.progress.html((response.score !== null) ? '<span class="text-' + response.status_color + '">' + response.score + '%</span>' : '');
            // create button for accessing the report
            $cell.reportUrl.html('<a href="' + localSettings.reportUrl.format(response.id) + '" class="btn btn-xs btn-default"><span class="glyphicon glyphicon-list-alt"></span> ' + lang.viewReportButton + '</a>');
        }

        if (response.state == -1 || response.state == 2) {
            // removing IDs of finished submissions from the checklist
            var index = tasks.checkList.indexOf($row.attr(tasks.settings.updateStatus.attrID));
            index > -1 ? tasks.checkList.splice(index, 1) : null;
        }
    }
};
