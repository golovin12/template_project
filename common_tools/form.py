import datetime
import re
from typing import Any

from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import ProhibitNullCharactersValidator
from django.db.models import QuerySet

from common_tools.widgets import SearchInputClear


class BaseFilterForm(forms.Form):
    """Базовый класс форм фильтрации"""
    filter_update_fields = tuple()  # Какие значения в форме следует обновить, для отображения на клиенте

    per_page_choices = ((10, '10'), (25, '25'), (50, '50'), (100, '100'))

    per_page = forms.TypedChoiceField(label='Отображать по', choices=per_page_choices, coerce=int, required=False)

    def __init__(self, request):
        super().__init__(data=request.GET)
        self.request = request

        # снять required сразу у всех полей
        for field in self.fields.values():
            field.required = False
            field.widget.is_required = False

        # возможность переопределить per_page_choices в наследнике
        if self.fields.get('per_page'):  # *поле могут убрать в наследнике
            self.fields['per_page'].choices = self.__class__.per_page_choices

    def filtrate(self, qs: QuerySet) -> tuple['BaseFilterForm', QuerySet]:
        """
        Фильтрует qs если форма валидна, иначе возвращает пустой qs
        :return: (form, qs)
        Пример: form, qs = filters.Form(request).filtrate(qs)
        """
        if self.is_valid():
            self._update_data()
            return self, self._filtration(qs)
        return self, qs.none()

    def _filtration(self, qs: QuerySet):
        """
        Логика фильтрации
        :return: qs
        """
        raise NotImplementedError

    def get_title(self) -> str:
        """Сборка текстового заголовка фильтрации"""

        if not (self.is_bound and self.is_valid()):
            return ''
        title_set = [
            self.format_value(name, self.cleaned_data[name]) for name in self.fields if self.cleaned_data.get(name)
        ]
        return ', '.join(title_set)

    def format_value(self, field_name: str, value: Any) -> str:
        field = self.fields[field_name]
        label = field.label.lower()

        if isinstance(value, datetime.date):
            fmt = '%d.%m.%Y' if not isinstance(value, datetime.datetime) else '%d.%m.%Y %H:%M'
            return f'{label}: {value.strftime(fmt)}'

        if isinstance(value, bool):
            return f'{label}'

        if hasattr(field, 'choices'):
            choices_dict = dict(field.choices)
            if isinstance(value, list):
                return f'{label}: {", ".join(str(choices_dict.get(v, v)) for v in value)}'
            return f'{label}: {choices_dict.get(value, value)}'

        return f'{label}: {value}'

    def get_per_page(self) -> int:
        """Количество записей на странице"""
        if self.is_bound and self.is_valid() and self.cleaned_data.get('per_page'):
            return self.cleaned_data['per_page']
        return self.per_page_choices[0][0]

    def _update_data(self):
        self.data = self.data.copy()

        for key in self.filter_update_fields:
            value = self.cleaned_data.get(key)

            if value is None or value == '':
                continue

            if isinstance(value, (list, tuple)):
                self.data.setlist(key, [str(v) for v in value])
            else:
                self.data[key] = str(value)


class WithoutPlaceholderMixin:
    """Класс без placeholder у полей формы модели"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['placeholder'] = ''
            field.widget.attrs['data-placeholder'] = ''


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True
    template_name = 'block/files_upload.html'

    def __init__(self, *args, **kwargs):
        self.accept = kwargs.pop('accept', '')
        super().__init__(*args, **kwargs)

    def get_context(self, name: str, value: Any, attrs: Any) -> dict:
        context = super().get_context(name, value, attrs)
        context['widget']['accept'] = self.accept
        return context


class MultipleImageField(forms.ImageField):
    """Поле для загрузки нескольких файлов изображений"""

    def __init__(self, *args, **kwargs):
        widget = MultipleFileInput(accept='image/*')

        kwargs.setdefault('widget', widget)

        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None) -> list[bool]:
        if not data:
            return []

        single_file_clean = super().clean

        files = [data] if isinstance(data, UploadedFile) else data

        return [single_file_clean(f, initial) for f in files]


class PhoneField(forms.CharField):
    default_error_messages = {
        'invalid': 'Введите корректный российский номер телефона.'
    }

    def __init__(self, *args, widget_style='', is_search=False, **kwargs):
        input_widget = SearchInputClear if is_search else forms.TextInput
        kwargs.setdefault('max_length', 19)
        kwargs.setdefault(
            'widget',
            input_widget(
                attrs={
                    'type': 'tel',
                    'class': 'PhoneInput',
                    'style': widget_style,
                    'placeholder': kwargs.get('label', ''),
                    'pattern': r'8 \(\d{3}\) \d{3}-\d{2}-\d{2}'
                }
            ),
        )
        super().__init__(*args, **kwargs)

    def clean(self, value) -> str:
        value = super().clean(value)

        if not value:
            return value

        # оставляем только цифры
        digits = re.sub(r'\D', '', value)

        # нормализация
        if digits.startswith('7') and len(digits) == 11:
            digits = '8' + digits[1:]
        elif digits.startswith('8') and len(digits) == 11:
            pass
        elif digits.startswith('9') and len(digits) == 10:  # если ввели без первой цифры
            digits = '8' + digits
        else:
            raise ValidationError(self.error_messages['invalid'])

        return digits


class CustomModelChoiceFieldInterface(forms.ChoiceField):
    """
    Базовый класс для кастомного ChoiceField, работающего через queryset.
    Поддерживает валидацию null-символов, преобразование значения в объект и сравнение изменений.
    """

    def __init__(self, *args, queryset=None, **kwargs):
        # Call Field instead of ChoiceField __init__() because we don't need ChoiceField.__init__().
        forms.Field.__init__(self, *args, **kwargs)
        if queryset is None:
            raise ValueError('CustomModelChoiceFieldInterface требует queryset')
        self.queryset = queryset
        # Пустая метка только если поле не required или нет initial
        self.empty_label = None if kwargs.get('required') and kwargs.get('initial') else '---------'
        self.choices = self.get_choices

    def __deepcopy__(self, memo):
        return super(forms.ChoiceField, self).__deepcopy__(memo)

    def validate_no_null_characters(self, value):
        return ProhibitNullCharactersValidator()(value)

    def validate(self, value):
        return forms.Field.validate(self, value)

    def prepare_value(self, value):
        if hasattr(value, '_meta'):
            return value.pk
        return super().prepare_value(value)

    def to_python(self, value):
        if value in self.empty_values:
            return None
        self.validate_no_null_characters(value)
        try:
            value = self.queryset.get(pk=value)
        except (ValueError, TypeError, self.queryset.model.DoesNotExist):
            raise ValidationError(
                self.error_messages['invalid_choice'],
                code='invalid_choice',
                params={'value': value},
            )
        return value

    def has_changed(self, initial, data) -> bool:
        if self.disabled:
            return False
        initial_value = '' if initial is None else self.prepare_value(initial)
        data_value = '' if data is None else data
        return str(initial_value) != str(data_value)

    def get_choices(self):
        """Должен быть реализован в подклассе."""
        raise NotImplementedError('Нужно реализовать get_choices() в подклассе')
