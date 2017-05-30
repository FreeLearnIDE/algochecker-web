"use strict";

var settings = {
    descriptionSelector: '#id_description',
    requestURL: '/staff/preview_markdown/',
    modalSelector: '#md_dsc_preview',
    toggleButtonSelector: '#md_dsc_toggle'
};

var preview_markdown = function() {
    var content = $(settings.descriptionSelector).val();
    if (!content.length) return;
    $.ajax({
        url: settings.requestURL,
        type: "POST",
        data: JSON.stringify({"content": content}),
        dataType: 'json',
        contentType: 'application/json; charset=utf-8',
        beforeSend: function (xhr) {
            xhr.setRequestHeader("X-CSRFToken", getCookie('csrftoken'));
        }
    }).done(function(response) {
        $(settings.modalSelector + ' .modal-body').html(response.data);
    }).fail(function(response) {
        $(settings.modalSelector + ' .modal-body').html('Unable to show preview. Request failed.');
        console.log(response);
    }).always(function() {
        if (MathJax !== undefined) { // if MathJax exists -> reinitialize
            MathJax.Hub.Queue(["Typeset", MathJax.Hub]);
        }
        $(settings.modalSelector).modal('show');
    });
};

$($(settings.toggleButtonSelector).click(preview_markdown)); // button click event init on load
