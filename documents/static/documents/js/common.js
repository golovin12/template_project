const NOTIFICATION_TYPES = {
    success: {className: 'alert-success', icon: '✅'},
    error: {className: 'alert-danger', icon: '❌'},
    warning: {className: 'alert-warning', icon: '⚠️'},
    info: {className: 'alert-info', icon: 'ℹ️'}
};

function showNotification(message, type = 'info', duration = 3000) {
    const $template = $('#notificationTemplate');
    if (!$template.length) return;

    const typeConfig = NOTIFICATION_TYPES[type] || NOTIFICATION_TYPES.info;
    const $element = $($template.html());

    $element.addClass(typeConfig.className);
    $element.find('.notification-icon').html(typeConfig.icon);
    $element.find('.notification-message').text(message);

    const notificationId = 'notification_' + Date.now();
    $element.attr('id', notificationId);

    $('#notificationContainer').append($element);

    setTimeout(function () {
        const $el = $('#' + notificationId);

        if ($el.length) {
            $el.alert('close');
        }
    }, duration);
}

$(function () {
    $('#upload-button').on('click', function () {
        $('#id_file').trigger('click');
    });

    $('#id_file').on('change', function () {
        if (this.files.length) {
            $('#upload-form').trigger('submit');
        }
    });

    $('#select-all').on('change', function () {
        $('.document-select').prop('checked', this.checked);
    });

    $('.document-select').on('change', function () {
        const total = $('.document-select').length;
        const selected = $('.document-select:checked').length;

        $('#select-all').prop('checked', total > 0 && total === selected);
    });

    $('#zip-form').on('submit', function (event) {
        if (!$('.document-select:checked').length) {
            event.preventDefault();
            showNotification('Выбери файлы или папки для скачивания.', 'warning');
        }
    });
});
