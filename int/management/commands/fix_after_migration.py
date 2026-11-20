from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connections, transaction


class Command(BaseCommand):
    help = 'Исправление багов после миграции старой базы данных'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('🚀 Starting post-migration fixes...'))

        with transaction.atomic(using="zone_1"):
            with connections["zone_1"].cursor() as cursor:
                cursor.execute("SET session_replication_role = replica;")

            try:
                self.fix_dates()
                self.fix_accounting_entries()
                self.reset_sequences("zone_1")
            finally:
                with connections["zone_1"].cursor() as cursor:
                    cursor.execute("SET session_replication_role = DEFAULT;")

        self.stdout.write(self.style.SUCCESS('✅ All fixes completed!'))

    def fix_dates(self):
        """
        Исправление дат в моделях, где был убран auto_now_add
        """
        self.stdout.write('📅 Fixing dates...')

        # 1. PromoterAssignment - assigned_date
        self._fix_field_dates(
            app_label='promoter_app',
            model_name='PromoterAssignment',
            field_name='assigned_date'
        )

        # 2. ServiceRequest - request_time
        self._fix_field_dates(
            app_label='service_requests',
            model_name='ServiceRequest',
            field_name='request_time'
        )

        # 3. MasterIncome - created_date
        self._fix_field_dates(
            app_label='service_requests',
            model_name='MasterIncome',
            field_name='created_date'
        )

        # 4. Act - create_dt
        self._fix_field_dates(
            app_label='service_requests',
            model_name='Act',
            field_name='create_dt'
        )

        # 5. CashCollection - created_dt
        self._fix_field_dates(
            app_label='bookkeeping',
            model_name='CashCollection',
            field_name='created_dt'
        )

        self.stdout.write(self.style.SUCCESS('✅ Dates fixed!'))

    def _fix_field_dates(self, app_label, model_name, field_name):
        """
        Вспомогательный метод для исправления дат в конкретном поле
        Берет значения из старой БД и обновляет в новой
        """
        model = apps.get_model(app_label, model_name)
        self.stdout.write(f'  📅 Fixing {model._meta.label}.{field_name}...')

        for old in model.objects.using("old").iterator():
            model.objects.using("zone_1").filter(id=old.id).update(**{field_name: getattr(old, field_name)})

    def fix_accounting_entries(self):
        """
        Исправление AccountingEntry: добавляем недостающие записи с is_hidden=True
        """
        self.stdout.write('📊 Fixing AccountingEntry...')

        AccountingEntry = apps.get_model('bookkeeping', 'AccountingEntry')

        AccountingEntry.objects = AccountingEntry.all_objects

        for old in AccountingEntry.objects.using('old').filter(hidden=True).iterator():
            if AccountingEntry.objects.using('zone_1').filter(pk=old.pk).exists():
                continue
            values = {field.attname: getattr(old, field.attname) for field in AccountingEntry._meta.concrete_fields}
            new = AccountingEntry(**values)
            new.save(using='zone_1', force_insert=True)

    def reset_sequences(self, database):
        connection = connections[database]

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    c.relname AS table_name,
                    a.attname AS column_name,
                    pg_get_serial_sequence(
                        quote_ident(n.nspname)||'.'||quote_ident(c.relname),
                        a.attname
                    ) AS sequence_name
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_attribute a ON a.attrelid = c.oid
                WHERE c.relkind = 'r'
                  AND a.attname = 'id';
            """)

            for table, column, sequence in cursor.fetchall():
                if not sequence:
                    continue

                cursor.execute(f"""
                    SELECT setval(
                        '{sequence}',
                        COALESCE((SELECT MAX("{column}") FROM "{table}"), 1),
                        true
                    );
                """)

                self.stdout.write(f"✅ {table}")
