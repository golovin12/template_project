from django.core.exceptions import ValidationError


def validate_file_field(value):
    max_size_mb = 10
    size = getattr(value, 'size', None)

    if size and size > 1024 * 1024 * max_size_mb:
        raise ValidationError(f'Максимальный размер загружаемого файла - {max_size_mb} МБ')
