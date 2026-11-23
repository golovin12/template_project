import os

from django.conf import settings
from django.core.management import call_command

from int.db_context import DatabaseContext
from int.management.storage_backends import BackupStorage


def create_backup(prefix: str) -> None:
    """Создаёт бэкап БД"""
    directory = settings.BASE_DIR
    database = DatabaseContext.get()
    file_name = f'backup_{database}_{prefix}.json'
    temp_file_name = f'{directory}/{file_name}'

    # Приложения для которых нужно делать дамп
    notification_labels = ('notifications.NotificationSettings', 'notifications.NotificationChannel',
                           'notifications.CityNotificationPreference')
    app_labels = ('identity', 'accounts', 'bookkeeping', 'service_requests', *notification_labels)

    with open(temp_file_name, 'w') as file:
        call_command(
            'dumpdata',
            *app_labels,  # Все приложения
            format='json',
            indent=2,
            stdout=file,
            database=database,
        )
    try:
        s3_storage = BackupStorage()
        with open(temp_file_name, 'rb') as file:
            s3_storage.save(file_name, file)
    except Exception as e:
        raise AssertionError(f'При выполнении загрузки дампа возникла ошибка: {e}')
    finally:
        os.remove(temp_file_name)
