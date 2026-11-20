import os
import re


def escape_filename(value: str) -> str:
    """Удалить управляющие символы из имени файла"""
    invalid_symbols = ['<', '>', '+', '=', '*', ':', ';', '|', '?', '!', '«', '»', r'\[', r'\]', '\\\\/', '\\\\', '"',
                       '%', '@']
    return re.sub(r'[{}]'.format(r''.join(invalid_symbols)), '', value).rstrip('. ')


def build_ascii_filename(file_name: str) -> str:
    """Преобразует имя файла в ASCII-совместимый вариант, сохраняя расширение."""

    name, ext = os.path.splitext(file_name)

    ascii_name = name.encode('ascii', 'ignore').decode().strip()

    if not ascii_name:
        ascii_name = 'file'

    return f'{ascii_name}{ext or ""}'
