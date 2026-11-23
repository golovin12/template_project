from django.apps import apps
from django.contrib.auth.models import AbstractUser
from django.core.management.base import BaseCommand
from django.db import connections, transaction, models

from accounts.consts import USER_ROLES
from apps.notifications.enums import NotificationProvider
from identity.models import AuthUser, Organization
from accounts.models import OrganizationUser
from int.db_context import DatabaseContext
from int.db_router import OrganizationRouter


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        with transaction.atomic(using="default"), transaction.atomic(using="zone_1"):
            with connections["zone_1"].cursor() as cursor:
                cursor.execute("SET session_replication_role = replica;")

            try:
                self.copy_auth_users()
                self.create_zones()
                self.copy_zone_users()
                self.copy_models()
                self.copy_notif_connect_code()
                self.copy_user_m2m_relations()
                self.copy_promoter_data()
                self.reset_sequences("default")
                self.reset_sequences("zone_1")
            finally:
                with connections["zone_1"].cursor() as cursor:
                    cursor.execute("SET session_replication_role = DEFAULT;")

    def copy_auth_users(self):
        for old in LegacyUser.objects.using("old").all():
            if AuthUser.objects.using("default").filter(pk=old.pk).exists():
                continue

            AuthUser.objects.using("default").create(
                id=old.id,
                password=old.password,
                last_login=old.last_login,
                is_superuser=old.is_superuser,
                username=old.username,
                first_name=old.first_name,
                last_name=old.last_name,
                second_name=old.second_name,
                is_staff=old.is_staff,
                is_active=old.is_active,
                date_joined=old.date_joined,
            )

    def create_zones(self):
        zone1, _ = Organization.objects.using("default").get_or_create(database_alias="zone_1",
                                                               defaults={"name": "Основная зона"})
        zone2, _ = Organization.objects.using("default").get_or_create(database_alias="zone_2",
                                                               defaults={"name": "Вторая зона"})
        zone3, _ = Organization.objects.using("default").get_or_create(database_alias="zone_3",
                                                               defaults={"name": "Третья зона"})

        zone1.users.set(AuthUser.objects.using("default").all())

    def copy_zone_users(self):
        for old in LegacyUser.objects.using("old").all():
            if OrganizationUser.objects.using("zone_1").filter(pk=old.pk).exists():
                continue

            new = OrganizationUser(
                id=old.id,
                user_id=old.id,
                username=old.username,
                first_name=old.first_name,
                last_name=old.last_name,
                second_name=old.second_name,
                is_global_superuser=old.is_superuser,
                is_superuser=old.is_superuser,
                role=old.role,
                all_cities_access=old.all_cities_access,
            )

            new.save(using="zone_1", force_insert=True)

    def copy_notif_connect_code(self):
        NotificationConnectCode = apps.get_model("notifications", "NotificationConnectCode")

        for old in LegacyNotificationConnectCode.objects.using("old").all():
            if NotificationConnectCode.objects.using("default").filter(pk=old.pk).exists():
                continue

            new = NotificationConnectCode(
                id=old.id,
                user_id=old.user_id,
                code=old.code,
                provider=old.provider,
                database_alias='zone_1',
                created_dt=old.created_dt,
                expires_at=old.expires_at,
                is_used=old.is_used,
            )

            new.save(using="default", force_insert=True)

    def copy_promoter_data(self):
        """
        Копирование данных промоутеров с сохранением связи API ключей
        """
        self.stdout.write("📦 Copying Promoter data...")

        # Используем Legacy модели для чтения из старой БД
        for old in LegacyPromoterProfile.objects.using("old").all():
            # Копируем PromoterProfile в organization_1
            PromoterProfile = apps.get_model("promoter_app", "PromoterProfile")

            if not PromoterProfile.objects.using("zone_1").filter(pk=old.pk).exists():
                new = PromoterProfile(
                    id=old.id,
                    city_id=old.city_id,
                    nickname=old.nickname,
                )
                new.save(using="zone_1", force_insert=True)
                self.stdout.write(f"  ✅ Copied PromoterProfile id={old.id}")

            # Копируем PromoterZone в default (сохраняем API ключ)
            PromoterZone = apps.get_model("promoter_app", "PromoterZone")

            # Проверяем существование записи с таким api_key
            if not PromoterZone.objects.using("default").filter(api_key=old.api_key).exists():
                # Проверяем существование записи с такой парой (database_alias, promoter_id)
                if not PromoterZone.objects.using("default").filter(
                        database_alias="zone_1",
                        promoter_id=old.id
                ).exists():
                    new_zone = PromoterZone(
                        api_key=old.api_key,  # Сохраняем существующий ключ!
                        database_alias="zone_1",
                        promoter_id=old.id,
                    )
                    new_zone.save(using="default", force_insert=True)
                    self.stdout.write(f"  ✅ Copied PromoterZone id={new_zone.id} (key={old.api_key[:8]}...)")
                else:
                    self.stdout.write(f"  ⚠️ PromoterZone for promoter {old.id} already exists in zone_1")
            else:
                self.stdout.write(f"  ⚠️ API key {old.api_key[:8]}... already exists in default")

        self.stdout.write(self.style.SUCCESS("✅ Promoter data copied successfully"))

    def copy_models(self):
        excluded_models = [
            ('accounts', 'User'),
            ('identity', 'AuthUser'),
            ('identity', 'Zone'),
            ('notifications', 'NotificationConnectCode'),
            ('accounts', 'AppSettings'),
            ('promoter_app', 'PromoterZone'),
            ('promoter_app', 'PromoterProfile'),
            # LegacyModels
            ('int', 'LegacyUser'),
            ('int', 'LegacyPromoterProfile'),
            ('int', 'LegacyNotificationConnectCode'),
            # Системные модели Django - их не копируем
            ('admin', 'LogEntry'),
            ('auth', 'Permission'),
            ('auth', 'Group'),
            ('contenttypes', 'ContentType'),
            ('sessions', 'Session'),
        ]

        # Копирование основных данных
        for model in apps.get_models():
            app = model._meta.app_label
            model_name = model.__name__

            if (app, model_name) in excluded_models:
                continue

            if f'{app}.{model_name}' == 'bookkeeping.AccountingEntry':
                model.objects = model.all_objects

            if model_name == 'Task':
                continue

            if app in OrganizationRouter.AUTH_APPS or f'{app}.{model_name}'.lower() in OrganizationRouter.DEFAULT_MODELS:
                target_db = "default"
            else:
                target_db = "zone_1"

            self.stdout.write(f"📦 Copying {model._meta.label}")

            for obj in model.objects.using("old").iterator():
                if model.objects.using(target_db).filter(pk=obj.pk).exists():
                    continue

                values = {field.attname: getattr(obj, field.attname) for field in model._meta.concrete_fields}
                new = model(**values)
                new.save(using=target_db, force_insert=True)

        self.stdout.write('📦 Copying ManyToMany relations:')

        for model in apps.get_models():
            app = model._meta.app_label
            model_name = model.__name__

            if (app, model_name) in excluded_models:
                continue

            if f'{app}.{model_name}' == 'bookkeeping.AccountingEntry':
                model.objects = model.all_objects

            if model_name == 'Task':
                continue

            if app in ZoneRouter.AUTH_APPS or f'{app}.{model_name}'.lower() in OrganizationRouter.DEFAULT_MODELS:
                target_db = "default"
            else:
                target_db = "zone_1"

            self.stdout.write(f"📦 M2M {model._meta.label}")

            with DatabaseContext.using(target_db):
                for obj in model.objects.using("old").iterator():
                    if not model.objects.using(target_db).filter(pk=obj.pk).exists():
                        continue

                    new = model.objects.using(target_db).get(pk=obj.pk)

                    for field in model._meta.many_to_many:
                        ids = list(getattr(obj, field.name).using("old").values_list("pk", flat=True))

                        if ids:
                            getattr(new, field.name).set(ids)

    def copy_user_m2m_relations(self):
        self.stdout.write("📦 Copying User M2M relations (cities)")

        User = apps.get_model("accounts", "User")

        with connections["old"].cursor() as cursor:
            cursor.execute("""SELECT user_id, city_id FROM accounts_user_cities ORDER BY user_id""")

            user_cities = {}

            for user_id, city_id in cursor.fetchall():
                user_cities.setdefault(user_id, []).append(city_id)

        through = User.cities.through

        rows = []

        for user_id, city_ids in user_cities.items():
            zone_user = User.objects.using("zone_1").get(user_id=user_id)

            for city_id in city_ids:
                rows.append(
                    through(
                        user_id=zone_user.pk,
                        city_id=city_id,
                    )
                )

        through.objects.using("zone_1").bulk_create(rows, ignore_conflicts=True)

        self.stdout.write(f"✅ Copied {len(rows)} User-City relations")

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


class LegacyUser(AbstractUser):
    """Временная таблица для переноса данных"""
    username = models.CharField(max_length=150, unique=True)

    role = models.CharField(max_length=20, choices=USER_ROLES.choices)

    current_city = models.ForeignKey(
        'accounts.City',
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        db_column="current_city_id",
        related_name="+",
    )

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='legacy_users',
        blank=True,
        verbose_name='groups'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='legacy_users',
        blank=True,
        verbose_name='user permissions'
    )

    all_cities_access = models.BooleanField(default=False)
    is_history_access = models.BooleanField(default=False)
    is_cash_collection_access = models.BooleanField(default=False)
    is_act_creation_access = models.BooleanField(default=False)

    second_name = models.CharField(max_length=150, blank=True)

    class Meta:
        managed = False
        db_table = "accounts_user"


class LegacyPromoterProfile(models.Model):
    """Временная таблица для переноса данных промоутеров (со старым api_key)"""
    id = models.BigIntegerField(primary_key=True)
    city_id = models.BigIntegerField()
    nickname = models.CharField(max_length=100)
    api_key = models.CharField(max_length=64, unique=True, db_index=True)

    class Meta:
        managed = False
        db_table = "promoter_app_promoterprofile"


class LegacyNotificationConnectCode(models.Model):
    """Код для подключения к бд, хранится в default"""
    user = models.ForeignKey('accounts.OrganizationUser', on_delete=models.CASCADE, related_name="+", )
    code = models.CharField(max_length=32, unique=True)

    provider = models.CharField(max_length=20, choices=NotificationProvider.choices)
    created_dt = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    is_used = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = "notifications_notificationconnectcode"
