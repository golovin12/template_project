$(function () {
    $('.PhoneInput').each(function () {
        // Устанавливаем маску
        Inputmask({
            mask: '8 (999) 999-99-99',
            showMaskOnHover: false,
            showMaskOnFocus: true,
            onBeforePaste: function (pastedValue) {
                let digits = pastedValue.replace(/\D/g, '');
                if (digits.startsWith('7') && digits.length === 11) digits = '8' + digits.slice(1);
                return digits;
            }
        }).mask(this);
    });
});
