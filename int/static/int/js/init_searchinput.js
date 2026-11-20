$(function () {
    $('.SearchInput').each(function () {
        $(this).on('input', function () {
            const btn = $(this).siblings('.clear-btn');
            if ($(this).val()) {
                btn.show();
            } else {
                btn.hide();
            }
        });

        // клики по кнопке очистки
        $('.input-with-clear .clear-btn').on('click', function () {
            const input = $(this).siblings('input');
            input.val('').trigger('input');
            input.focus();
            $(this).hide();
        });
    });
});
