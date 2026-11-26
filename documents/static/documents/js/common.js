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
