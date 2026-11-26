from io import BytesIO

import openpyxl
from openpyxl.styles import PatternFill, Alignment, NamedStyle
from openpyxl.utils import get_column_letter


class XlsDocument:
    """
    Класс для создания excel отчётов
    *Для большого количества данных работает медленно
    http://openpyxl.readthedocs.org
    """
    DEFAULT_TAB_COLOR = "2E8B57"
    MAX_COLUMN_WIDTH = 30

    def __init__(self, sheet_title: str, headers=None, data_generator=None, title=None,
                 workbook: openpyxl.Workbook = None, start_data_row: int = None):
        """
        :param sheet_title: Имя страницы в файле excel
        :param title: str|(str,)|[str,]|None - Заголовок таблицы на всю ширину таблицы (количество headers)
        :param headers: Заголовки колонок: [head: str] | [(head: str, width: int)] | None
        :param data_generator: generator | iterable object - Элементы объекта должны содержать структуры вида:
            [<value>] | [(<value>, <style: Style>)]
        :param workbook: openpyxl.Workbook | None - Использовать готовый workbook, *openpyxl.load_workbook
        :param start_data_row: int | None - Строка начала записи данных, нужна если используется workbook
        """
        # workbook
        self.workbook = workbook or openpyxl.Workbook()

        # worksheet
        self.worksheet = self.workbook.active
        self.worksheet.title = sheet_title
        self.worksheet.sheet_properties.tabColor = self.DEFAULT_TAB_COLOR  # seagreen

        self._register_styles()

        # заголовок таблицы
        head_size = self._write_title(title, len(headers) if headers else 10)

        # заголовки колонок
        if headers:
            header_row = []
            header_styles = []
            for h in headers:
                if isinstance(h, (tuple, list)):
                    header_row.append(h[0])
                else:
                    header_row.append(h)
                header_styles.append('Header')  # один стиль для всех заголовков
            self._write_row(header_row, row=head_size, styles=header_styles)

        row_index = start_data_row or head_size + 1
        self.worksheet.freeze_panes = self.worksheet.cell(row=row_index, column=1)

        for data_row in data_generator or []:
            row_values = []
            row_styles = []
            for item in data_row:
                if isinstance(item, (tuple, list)):
                    row_values.append(item[0])
                    row_styles.append(item[1])
                else:
                    row_values.append(item)
                    row_styles.append(None)
            self._write_row(row_values, row=row_index, styles=row_styles)
            row_index += 1

        self._autofit_columns()

    def _register_styles(self):
        """Добавляет стандартные стили в workbook"""
        styles = (
            NamedStyle(name='Header', fill=PatternFill(start_color='D9D9D9', end_color='D9D9D9', fill_type='solid')),
            NamedStyle(name='VertTop', alignment=Alignment(vertical='center')),
            NamedStyle(name='VertCenter', alignment=Alignment(vertical='center')),
            NamedStyle(name='GreenSolid',
                       fill=PatternFill(start_color='D8E4BC', end_color='D8E4BC', fill_type='solid')),
            NamedStyle(name='Money', number_format='0.00'),
            NamedStyle(name='Percent', number_format='0.00%'),
            NamedStyle(name='DateTime', number_format='dd.mm.yyyy hh:mm'),
            NamedStyle(name='Date', number_format='dd.mm.yyyy'),
            NamedStyle(name='Wrapped', alignment=Alignment(wrapText=True)),
        )
        for s in styles:
            self.workbook.add_named_style(s)

    def _write_title(self, title, merge_x: int) -> int:
        """Записывает title и возвращает номер строки для заголовков"""
        if not title:
            return 1
        if isinstance(title, str):
            title = [title]
        for i, t in enumerate(title, start=1):
            self.cell(col=1, row=i, val=t, merge_x=merge_x)
        return len(title) + 2

    def _write_row(self, values, row, styles=None):
        """Записывает одну строку с опциональными стилями"""
        styles = styles or [None] * len(values)
        for i, (val, style) in enumerate(zip(values, styles), start=1):
            width = max(len(str(val)) + 3, 20)
            self.cell(col=i, row=row, val=val, style=style, width=width)

    def _autofit_columns(self):
        """Автоподбор ширины колонок"""
        for col in self.worksheet.columns:
            max_length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in col)
            max_length = min(max_length, self.MAX_COLUMN_WIDTH)
            self.worksheet.column_dimensions[get_column_letter(col[0].column)].width = max_length + 2

    def cell(self, col: int, row: int, val,
             width: int = None, style: str = None, merge_x: int = None, merge_y: int = None):
        """
        Записать данные в ячейку
        :param col: int - Колонка
        :param row: int - Строка
        :param val: Значение ячейки
        :param width: int - ширина ячейки, измеряется в количестве символов ツ
        :param style: имя стандартного стиля или
                      имя openpyxl.styles.NamedStyle, добавленное в workbook: wb.add_named_style(highlight)
                          по умолчанию в книгу добавлено несколько своих стилей
                          https://openpyxl.readthedocs.io/en/stable/styles.html#creating-a-named-style
                          есть стандартные стили
                          https://openpyxl.readthedocs.io/en/stable/styles.html#using-builtin-styles
        :param merge_x: int - объединить с указанным количеством ячеек справа от этой ячейки
        :param merge_y: int - объединить с указанным количеством ячеек снизу от этой ячейки
        """
        cell_obj = self.worksheet.cell(column=col, row=row, value=val)
        if width:
            self.worksheet.column_dimensions[get_column_letter(col)].width = width if width > 1 else 20
        if merge_x:
            self.worksheet.merge_cells(start_row=row, start_column=col, end_row=row, end_column=col + merge_x)
        if merge_y:
            self.worksheet.merge_cells(start_row=row, start_column=col, end_row=row + merge_y, end_column=col)
        if style:
            self.worksheet[cell_obj.coordinate].style = style

    def save_to(self, filename_or_stream):
        """Save the current workbook under the given filename_or_stream"""
        self.workbook.save(filename_or_stream)

    def get_bytes_buffer(self) -> BytesIO:
        mem_file = BytesIO()
        self.save_to(mem_file)
        return mem_file  # BytesIO(mem_file.getvalue()) был баг

    def get_bytes(self) -> bytes:
        return self.get_bytes_buffer().getvalue()
