import io
import mimetypes
from typing import Type
from urllib.parse import quote

from django.core.exceptions import ImproperlyConfigured
from django.core.handlers.wsgi import WSGIRequest
from django.db.models import QuerySet
from django_tables2 import SingleTableView

from django.http import HttpResponse

from common_tools.file_system import escape_filename, build_ascii_filename
from common_tools.form import BaseFilterForm


def attachment_response(request: WSGIRequest, file_path_or_mem_file: str | bytes | io.BytesIO,
                        file_name: str) -> HttpResponse:
    """
    Сформировать HTTP-ответ для скачивания файла (Content-Disposition: attachment).

    Учитывается используемый браузер для правильной кодировки имени файла

    Args:
        request: WSGIRequest
        file_path_or_mem_file: str | bytes | io.BytesIO - путь к файлу | объект BytesIO
        file_name: str - имя вложения

    Returns:
        HttpResponse:
            Ответ с корректными заголовками:
            - Content-Type
            - Content-Length
            - Content-Disposition (attachment)

    Raises:
        TypeError:
            Если передан неподдерживаемый тип file_path_or_mem_file.
    """

    file_name = escape_filename(file_name)

    if isinstance(file_path_or_mem_file, str):
        with open(file_path_or_mem_file, 'rb') as f:
            content = f.read()
    elif isinstance(file_path_or_mem_file, bytes):
        content = file_path_or_mem_file
    elif isinstance(file_path_or_mem_file, io.BytesIO):
        content = file_path_or_mem_file.getvalue()
    else:
        raise TypeError('file_path_or_mem_file must be str, bytes or io.BytesIO')

    content_length = len(content)

    mimetype, encoding = mimetypes.guess_type(file_name)
    if mimetype is None:
        mimetype = 'application/octet-stream'

    response = HttpResponse(content, content_type=mimetype)
    response['Content-Length'] = str(content_length)

    if encoding is not None:
        response['Content-Encoding'] = encoding

    if 'HTTP_USER_AGENT' in request.META and 'WebKit' in request.META['HTTP_USER_AGENT']:
        # Safari 3.0 and Chrome 2.0 accepts UTF-8 encoded string directly.
        filename_header = 'filename="{}"'.format(quote(file_name))

    elif 'HTTP_USER_AGENT' in request.META and 'MSIE' in request.META['HTTP_USER_AGENT']:
        # IE does not support internationalized filename at all.
        # It can only recognize internationalized URL, so we do the trick via routing rules.
        filename_header = 'filename="{}"'.format(build_ascii_filename(file_name))

    else:
        # For others like Firefox, we follow RFC2231 (encoding extension in HTTP headers).
        filename_header = 'filename*=UTF-8\'\'{}'.format(quote(file_name))

    response['Content-Disposition'] = 'attachment; ' + filename_header
    return response


class FilterSingleTableView(SingleTableView):
    """Таблица с возможностью фильтрации и разбивкой на страницы"""

    # класс формы фильтрации
    filter_form_class: Type[BaseFilterForm] = None

    # форма фильтрации
    filter_form = None
    # текстовое представление применённых фильтров
    filter_text = None
    # Количество записей на странице
    per_page = None

    def get_table(self, **kwargs):
        table = super().get_table(**kwargs)
        table.before_render(self.request)
        return table

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        context['filter_text'] = self.filter_text
        return context

    def get_queryset(self, **kwargs):
        qs = super().get_queryset()
        self.filter_form, filtered_qs = self.filter_form_class(self.request).filtrate(qs)
        self.filter_text = self.filter_form.get_title()
        self.per_page = self.filter_form.get_per_page()
        return filtered_qs

    def get_table_pagination(self, table):
        return {'per_page': self.per_page}


class PassRequestToFormMixin:
    """Передача request в форму для FilterSingleTableView"""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs


class QuerySetMixin:
    queryset = None
    model = None
    ordering = None

    def get_queryset(self):
        """
        Return the list of items for this view.

        The return value must be an iterable and may be an instance of
        `QuerySet` in which case `QuerySet` specific behavior will be enabled.
        """
        if self.queryset is not None:
            queryset = self.queryset
            if isinstance(queryset, QuerySet):
                queryset = queryset.all()
        elif self.model is not None:
            queryset = self.model._default_manager.all()
        else:
            raise ImproperlyConfigured(
                "%(cls)s is missing a QuerySet. Define "
                "%(cls)s.model, %(cls)s.queryset, or override "
                "%(cls)s.get_queryset()." % {"cls": self.__class__.__name__}
            )
        ordering = self.get_ordering()
        if ordering:
            if isinstance(ordering, str):
                ordering = (ordering,)
            queryset = queryset.order_by(*ordering)

        return queryset

    def get_ordering(self):
        """Return the field or fields to use for ordering the queryset."""
        return self.ordering
