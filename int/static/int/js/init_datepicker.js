// air-datepicker
$(function () {
    $.current_lang = 'ru';
    let date_format = $.fn.datepicker.language[$.current_lang].dateFormat
    let time_format = $.fn.datepicker.language[$.current_lang].timeFormat
    let datetime_mask = Inputmask
    datetime_mask.extendDefinitions({
        'd': {
            validator: '[0-9]',
        },
        'm': {
            validator: '[0-9]',
        },
        'y': {
            validator: '[0-9]',
        },
        'h': {
            validator: '[0-9]',
        },
        'i': {
            validator: '[0-9]',
        },
    });

    $.init_datepickers = function (selector, params) {
        let datepickers_selector = selector || '.AirDateInput, .vDateField.hasDatepicker';
        let datepickers_params;
        if (params) {
            // always set lang
            datepickers_params = params;
        } else {
            // default params
            datepickers_params = {
                autoClose: true,
            }
        }
        datepickers_params['language'] = $.current_lang;
        $(datepickers_selector).each(function () {
            let params = {...datepickers_params};

            const year = parseInt($(this).attr('data-min-year'));
            const month = parseInt($(this).attr('data-min-month'));
            const day = parseInt($(this).attr('data-min-day'));

            if (year && month && day) {
                params.minDate = new Date(year, month - 1, day);
            }
            $(this).datepicker(params);
        });
    };

    $.add_mask_to_datepicker = function (selector, custom_mask) {
        let datepickers_selector = selector || '.AirDateInput, .vDateField.hasDatepicker';
        for (let datepicker_item of $(datepickers_selector)) {
            let datepicker_element = $(datepicker_item)
            if (!(datepicker_element.hasClass('noinputmask'))) {
                let input_mask = custom_mask || date_format
                datetime_mask({'mask': input_mask}).mask(datepicker_element)
            }
        }
    }

    $.init_datetimepickers = function () {
        $.init_datepickers('.AirDateTimeInput', {
            timepicker: true,
            minutesStep: 5,
        });
        $.add_mask_to_datepicker('.AirDateTimeInput', `${date_format} ${time_format}`);
    };

    $.init_range_datepickers = function () {
        $.init_datepickers('.AirDateRangeInput', {
            range: true,
            multipleDatesSeparator: ' - ',
            clearButton: true,
            toggleSelected: false,
            autoClose: true,
        })
        $.add_mask_to_datepicker('.AirDateRangeInput', `${date_format} - ${date_format}`)
    };

    // Usual date select
    $.init_datepickers();
    $.add_mask_to_datepicker();

    // Date time select
    $.init_datetimepickers()

    // Range date select
    $.init_range_datepickers()
});
