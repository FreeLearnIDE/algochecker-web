"use strict";

if (tasks && lang) {
    tasks.settings.updateStatus.reportUrl = '/staff/submission/{}/report/';
    lang.viewReportButton = 'View new report';
    tasks.init();

    var total = tasks.checkList.length;

    if (total > 1) {
        $('#confirm-message').hide();
        var int = setInterval(function () {
            var current = tasks.checkList.length,
                progress = (1 - (current / total)) * 100,
                $barWrap = $('#total-progress-bar'),
                $bar = $barWrap.find('.progress-bar'),
                $progbars = $('.prog-bar').find('.progress-bar'),
                intermediate_sum = 0;

            $progbars.each(function (i, k) {
                intermediate_sum += $(k).attr('aria-valuenow') / total;
            });

            progress = Math.round(progress + intermediate_sum);

            $bar.css('width', progress + '%').text((total - current) + ' / ' + total + ' (' + progress + '%)');

            if (progress >= 100) {
                $barWrap.fadeOut(100, function () {
                    $('#confirm-message').html('<p class="text-center">The re-evaluation is completed</p>').fadeIn(100);
                });
                clearInterval(int);
            }
        }, 200);
    }
}
