from django.db.models import QuerySet

from common_tools.excel import XlsDocument
from .models import AccountingEntry


def accounting_entry_list(accounting_entries: QuerySet[AccountingEntry]) -> XlsDocument:
    def data_generator():
        for accounting_entry in accounting_entries.iterator(chunk_size=5000):
            yield [
                (accounting_entry.created_dt, 'DateTime'),
                str(accounting_entry.branch),
                accounting_entry.get_entry_type_display(),
                (accounting_entry.amount, 'Money'),
                accounting_entry.description,
                str(accounting_entry.service_request or '—'),
            ]

    return XlsDocument(
        sheet_title='Бухгалтерия',
        title=None,
        headers=('Время добавления', 'Филиал', 'Тип', 'Сумма', 'Описание', 'Заявка'),
        data_generator=data_generator(),
    )
