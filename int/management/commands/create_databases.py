from psycopg import connect

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Создаёт отсутствующие базы данных'

    def handle(self, *args, **options):
        first_db = next(iter(settings.DATABASES.values()))

        with connect(
                dbname='postgres',
                user=first_db['USER'],
                password=first_db['PASSWORD'],
                host=first_db['HOST'],
                port=first_db['PORT'],
                autocommit=True,
        ) as conn:

            with conn.cursor() as cursor:
                for db in settings.DATABASES.values():
                    db_name = db['NAME']

                    cursor.execute(
                        'SELECT 1 FROM pg_database WHERE datname = %s',
                        (db_name,),
                    )

                    if cursor.fetchone():
                        continue

                    cursor.execute(f'CREATE DATABASE "{db_name}"')
                    self.stdout.write(
                        self.style.SUCCESS(f'Создана БД {db_name}')
                    )
