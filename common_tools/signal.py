from int.management.storage_backends import MediaStorage


def add_field_name_kwargs(field_name: str) -> callable:
    def decorator(func):

        def wrapper(*args, **kwargs):
            result = func(*args, field_name=field_name, **kwargs)
            return result

        return wrapper

    return decorator


def auto_delete_file_on_delete(sender, **kwargs):
    """Удаляет файл из S3 при удалении объекта модели."""
    instance = kwargs['instance']
    field_name = kwargs['field_name']
    file = getattr(instance, field_name)
    if file:
        storage = file.storage
        if isinstance(storage, MediaStorage):
            storage.delete(file.name)
