$(function () {
    // pagination: ctrl+right/left - next/prev page
    let prev_link = $('.paginator_previous_page_link');
    let next_link = $('.paginator_next_page_link');
    if (prev_link.length || next_link.length) {
        $(document).keydown(function (event) {
            if (event.ctrlKey && event.which === 37) {
                if (prev_link.is("[href]")) window.location = prev_link.attr('href');
            }
            if (event.ctrlKey && event.which === 39) {
                if (next_link.is("[href]")) window.location = next_link.attr('href');
            }
        });
    }

    // jQuery plugin to prevent double submission of forms
    jQuery.fn.preventDoubleSubmit = function () {
        return this.on('submit', function (e) {
            const $form = $(this);
            if ($form.data('submitted')) {
                e.preventDefault();
                // Показываем уведомление, если функция доступна
                if (typeof showNotification === 'function') {
                    showNotification('Пожалуйста, подождите, запрос уже обрабатывается...', 'warning');
                }
                return false;
            }
            $form.data('submitted', true);

            // Автоматическая разблокировка через 10 секунд (на случай ошибки)
            setTimeout(() => $form.data('submitted', false), 10000);
        });
    };

    $(function () {
        $('form.prevent-double-submit').preventDoubleSubmit();
    });
})

$(function () {
    $('.copy-btn').on('click', function () {
        let $button = $(this);
        let textToCopy = $button.attr('data-text');

        // Создаем временный элемент для копирования
        const $tempInput = $('<textarea>');
        $('body').append($tempInput);
        $tempInput.val(textToCopy)

        try {
            $tempInput.select();
            document.execCommand('copy');

            $button.find('i')
                .removeClass('text-secondary')
                .addClass('text-success');

            setTimeout(function () {
                $button.find('i')
                    .removeClass('text-success')
                    .addClass('text-secondary');
            }, 2000);

        } catch (err) {
            console.error('Ошибка при копировании:', err);
        } finally {
            $tempInput.remove();
        }
    });
});

function formatOption(option) {
    if (!option.id) {
        return option.text;
    }

    const description = $(option.element).data('description');

    return $(`
        <div>
            <div>${option.text}</div>
            <small class="text-muted">${description}</small>
        </div>
    `);
}

function formatMasterSelect(option) {
    if (!option.id) {
        return option.text;
    }

    let title = option.text || '';

    const openBracketIndex = title.indexOf('[');

    if (openBracketIndex !== -1) {
        title = title.substring(0, openBracketIndex).trim();
    }

    return title
}

function formatMasterResult(option) {
    if (!option.id) {
        return option.text + ' ';
    }

    const text = option.text || '';

    let title = text;
    let description = '';

    const openBracketIndex = text.indexOf('[');
    const closeBracketIndex = text.lastIndexOf(']');

    if (openBracketIndex !== -1 && closeBracketIndex !== -1 && closeBracketIndex > openBracketIndex) {
        title = text.substring(0, openBracketIndex).trim();
        description = text.substring(openBracketIndex + 1, closeBracketIndex).trim();
    }

    return $(`
        <div>
            <div>${title}</div>
            ${description ? `<small class="text-muted" style="white-space: pre-line;">${description}</small>` : ''}
        </div>
    `);
}

// Конфигурация типов уведомлений
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
    let citySelector = $('#city-select')

    citySelector.select2({
        width: '100%', placeholder: 'Выберите город', minimumResultsForSearch: 1
    }).data('select2')?.$container.attr("style", "min-width: 7.5em; max-width: 50em;");

    citySelector.on('change', function () {
        const form = $('#city-form');
        $.ajax({
            url: form.attr('action') || window.location.href,
            method: 'POST',
            data: form.serialize(),
            success: function () {
                location.reload();
            },
            error: function (xhr) {
                console.error('Ошибка при выборе города:', xhr.responseText);
                showNotification('Не удалось изменить город.', "error");
            }
        });
    });
});

$(function () {
    let organizationSelector = $('#organization-select');

    organizationSelector.select2({
        width: '100%', placeholder: 'Выберите организацию', minimumResultsForSearch: 1
    }).data('select2')?.$container.attr("style", "min-width: 7.5em; max-width: 50em;");

    organizationSelector.on('change', function () {
        const form = $('#organization-form');

        $.ajax({
            url: form.attr('action') || window.location.href,
            method: 'POST',
            data: form.serialize(),
            success: function () {
                location.reload();
            },
            error: function (xhr) {
                console.error('Ошибка при выборе организации:', xhr.responseText);
                showNotification('Не удалось сменить организацию.', 'error');
            }
        });
    });
});
