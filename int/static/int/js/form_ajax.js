// Универсальная функция привязки AJAX-отправки
function loadFormToPage(response, bodySelector) {
    $(bodySelector).html(response).find('.django-select2').each(function () {
        $(this).select2({
            width: '100%', dropdownAutoWidth: true
        });
    });
    $.init_datetimepickers()
}

function bindAjaxFormSubmit(formSelector, bodySelector = null, afterReplaceCallback = null) {
    const form = $(formSelector);

    form.on('submit', function (event) {
        event.preventDefault();

        // Защита от двойного клика
        if (form.data('submitted') === true) {
            return;
        }
        form.data('submitted', true);

        let url = form.attr('action');
        let formData = new FormData(this);

        $.ajax({
            type: form.attr('method'),
            url: url,
            data: formData,
            processData: false,
            contentType: false,
            success: function (response, textStatus, xhr) {
                if (xhr.status === 204) {
                    window.location.reload();
                } else {
                    if (bodySelector) {
                        loadFormToPage(response, bodySelector);
                    }

                    // Колбэк, например инициализация загрузки файлов
                    if (afterReplaceCallback) {
                        afterReplaceCallback(response);
                    }

                    form.data('submitted', false);
                }
            },
            error: function (response) {
                if (response.status >= 400 && response.status < 500) {
                    showNotification("Нет доступа на выполнение данного действия!", "error");
                } else {
                    showNotification("На сервере произошла ошибка! \nПопробуйте отправить форму ещё раз", "error");
                }
                form.data('submitted', false);
            },
        });
    });
}

function ajaxLoadForm(url, modalSelector, formSelector, bodySelector) {
    // Запрашивает форму с сервера и показывает её. При ошибке - показывает ошибку
    let spinner = $(this).find('.spinner-border').removeClass('d-none')

    $.ajax({
        type: 'get',
        url: url,
        success: function (response, textStatus, xhr) {
            // Загрузка формы
            loadFormToPage(response, bodySelector)
            $(formSelector).attr('action', url)
            $(modalSelector).modal('show')
            spinner.addClass('d-none')
        },
        error: function (response) {
            console.log(response)
            showNotification("Не удалось загрузить форму! \nПопробуйте ещё раз", "error")
            spinner.addClass('d-none')
        },
    });
}
