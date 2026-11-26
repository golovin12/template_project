from captcha.fields import CaptchaTextInput
from django_select2.forms import Select2Widget

from django.forms import widgets, ClearableFileInput, TextInput


class DescriptionSelect2Widget(Select2Widget):
    """
    Добавляет описание к options (описание должно быть разделено ": ")
    В шаблоне использовать вместе с:
    $('#id_field').select2({
        templateResult: formatOption
    })
    """

    def create_option(self, *args, **kwargs):
        option = super().create_option(*args, **kwargs)
        label = option['label'].split(': ', maxsplit=1)
        if len(label) == 2:
            option['label'] = label[0]
            option['attrs']['title'] = label[1]
        return option


class DateWidget(widgets.DateInput):
    """
    air-datepicker
    media подключается отдельно:
        int\\templates\\int\\base.html
    """

    default_attrs = {
        'style': 'width: auto;',
        'maxlength': '10',
        'class': 'AirDateInput',
        'autocomplete': 'off'
    }

    def __init__(self, attrs=None, format=None):
        if not attrs:
            attrs = {}
        for k, v in self.default_attrs.items():
            attrs.setdefault(k, v)
        if self.default_attrs['class'] not in attrs['class']:
            attrs['class'] += ' {}'.format(self.default_attrs['class'])
        super().__init__(attrs, format=format)


class DateTimeWidget(widgets.DateTimeInput):
    """
        air-datepicker
        media подключается отдельно:
            int\\templates\\int\\base.html
        """

    default_attrs = {
        'style': 'width: auto;',
        'maxlength': '16',
        'class': 'AirDateTimeInput',
        'autocomplete': 'off',
    }

    def __init__(self, attrs=None, format='%d.%m.%Y %H:%M'):
        if not attrs:
            attrs = {}
        for k, v in self.default_attrs.items():
            attrs.setdefault(k, v)
        if self.default_attrs['class'] not in attrs['class']:
            attrs['class'] += ' {}'.format(self.default_attrs['class'])
        super().__init__(attrs, format=format)


class DateRangeWidget(widgets.TextInput):
    """
    air-datepicker
    media подключается отдельно:
        int\\templates\\int\\base.html
    """

    default_attrs = {
        'style': 'width: auto;',
        'maxlength': '23',
        'class': 'AirDateRangeInput',
        'autocomplete': 'off',
    }

    def __init__(self, attrs=None):
        if not attrs:
            attrs = {}
        for k, v in self.default_attrs.items():
            attrs.setdefault(k, v)
        if self.default_attrs['class'] not in attrs['class']:
            attrs['class'] += ' {}'.format(self.default_attrs['class'])
        super().__init__(attrs)


class MultipleFileInput(ClearableFileInput):
    allow_multiple_selected = True  # Разрешаем выбор нескольких файлов


class SearchInputClear(TextInput):
    """
    Поисковое поле с очисткой
    media подключается отдельно:
        int\\templates\\int\\base.html
    """
    template_name = "int/widgets/search_clear.html"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs['class'] = (self.attrs.get('class', '') + ' SearchInput')


class CustomCaptchaTextInput(CaptchaTextInput):
    template_name = 'identity/captcha.html'
