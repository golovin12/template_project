import random
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from faker import Faker

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.consts import USER_ROLES
from accounts.models import Branch, City, OrganizationUser
from apps.bookkeeping.models import AccountingEntry
from apps.service_requests.models import DeviceType, ServiceRequest
from documents.models import DocumentsUser, DocumentFile, DocumentFolder
from identity.models import AuthUser, Organization
from int.db_context import using_database

fake = Faker('ru_RU')


class Command(BaseCommand):
    help = 'Генерация тестовых данных для всех моделей проекта'

    def add_arguments(self, parser):
        parser.add_argument(
            'count',
            type=int,
            help='Количество заявок для генерации в каждой организации',
        )

    def handle(self, *args, **options):
        count = options['count']

        if count < 1:
            raise CommandError('Количество заявок должно быть больше нуля.')

        databases = [alias for alias in settings.DATABASES if alias != 'default']

        if not databases:
            raise CommandError('Не найдены базы данных организаций.')

        self.stdout.write(self.style.WARNING('Генерация тестовых данных...'))

        users = self._create_default_data(databases)

        for alias in databases:
            self.stdout.write(f'Обработка базы данных {alias}...')

            with using_database(alias):
                with transaction.atomic(using=alias):
                    self._create_organization_data(alias, users, count)

            self.stdout.write(
                self.style.SUCCESS(f'Данные для {alias} созданы.')
            )

        self.stdout.write(
            self.style.SUCCESS('Генерация тестовых данных завершена.')
        )

    def _create_default_data(self, databases):
        with transaction.atomic(using='default'):
            users = []

            for _ in range(5):
                user = AuthUser(
                    username=f'fake_{uuid4().hex[:12]}',
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    second_name=fake.middle_name(),
                    email=fake.email(),
                )
                user.set_password('test-password')
                user.save(using='default')
                users.append(user)

            for alias in databases:
                organization, _ = Organization.objects.using('default').get_or_create(
                    database_alias=alias,
                    defaults={
                        'name': f'Тестовая организация {alias}',
                    },
                )
                organization.users.add(*users)

            self._create_documents()

        return users

    def _create_documents(self):
        for _ in range(3):
            user = DocumentsUser(
                username=f'documents_{uuid4().hex[:12]}',
            )
            user.set_password('test-password')
            user.save(using='default')

            folders = [
                DocumentFolder.objects.using('default').create(
                    user=user,
                    name=name,
                )
                for name in ('Документы', 'Изображения')
            ]

            for folder in folders:
                for _ in range(2):
                    filename = f'{uuid4().hex}.txt'
                    content = fake.text(max_nb_chars=500).encode()

                    document = DocumentFile(
                        user=user,
                        folder=folder,
                        original_name=filename,
                        size=len(content),
                    )
                    document.file.save(
                        filename,
                        ContentFile(content),
                        save=True,
                    )

    def _create_organization_data(self, alias, auth_users, count):
        cities = [
            City.objects.create(
                name=f'{fake.city()} {uuid4().hex[:5]}',
                is_active=True,
            )
            for _ in range(3)
        ]

        branches = [
            Branch.objects.create(
                name=f'Филиал {index + 1} {uuid4().hex[:5]}',
                city=city,
                is_active=True,
            )
            for city in cities
            for index in range(2)
        ]

        users = self._create_organization_users(auth_users, cities)
        device_types = self._create_device_types(branches)

        requests = self._create_requests(
            users,
            branches,
            device_types,
            count,
        )

        self._create_accounting_entries(requests, users)

    def _create_organization_users(self, auth_users, cities):
        roles = [
            USER_ROLES.MANAGER,
            USER_ROLES.CHIEF,
            USER_ROLES.CITY_ADMIN,
        ]

        users = []

        for index, auth_user in enumerate(auth_users):
            user = OrganizationUser.objects.create(
                user_id=auth_user.pk,
                username=auth_user.username,
                first_name=auth_user.first_name,
                last_name=auth_user.last_name,
                second_name=auth_user.second_name,
                role=roles[index % len(roles)],
                is_superuser=index == 0,
                all_cities_access=index == 0,
            )

            user.cities.set(
                cities if index == 0 else random.sample(
                    cities,
                    random.randint(1, len(cities)),
                )
            )

            users.append(user)

        return users

    def _create_device_types(self, branches):
        names = [
            'Кондиционеры',
            'Стиральные машины',
            'Холодильники',
            'Кофемашины',
        ]

        device_types = []

        for name in names:
            available_for_all = random.choice([True, False])

            device_type = DeviceType.objects.create(
                name=f'{name} {uuid4().hex[:5]}',
                is_available_for_all=available_for_all,
            )

            if not available_for_all:
                device_type.branches.set(
                    random.sample(
                        branches,
                        random.randint(1, len(branches)),
                    )
                )

            device_types.append(device_type)

        return device_types

    def _create_requests(self, users, branches, device_types, count):
        last_number = ServiceRequest.objects.order_by('-request_number').values_list(
            'request_number', flat=True).first() or 200000

        statuses = ServiceRequest.STATUS.values
        request_types = ServiceRequest.REQUEST_TYPE_CHOICES.values

        objects = []

        for index in range(count):
            branch = random.choice(branches)
            request_time = fake.date_time_between(
                start_date='-1y',
                end_date='now',
            )
            status = random.choice(statuses)
            completed = status == ServiceRequest.STATUS.COMPLETED
            has_diagnostics = status in (ServiceRequest.STATUS.SERVICE_DIAGNOSTICS, ServiceRequest.STATUS.COMPLETED)

            time_to_service = (
                request_time + timedelta(hours=random.randint(1, 168)) if has_diagnostics else None
            )

            closing_time = (
                request_time + timedelta(days=random.randint(1, 40)) if completed else None
            )

            device_type = random.choice(device_types)

            objects.append(
                ServiceRequest(
                    request_number=last_number + index + 1,
                    request_type=random.choice(request_types),
                    request_time=request_time,
                    created_by=random.choice(users),
                    status=status,
                    branch=branch,
                    city=branch.city,
                    client_name=fake.name()[:100],
                    client_address=fake.address()[:255],
                    client_phone=f'+7{random.randint(9000000000, 9999999999)}',
                    problem_description=fake.text(max_nb_chars=200),
                    device_type=device_type.name,
                    time_to_service=time_to_service,
                    service_report=fake.text(max_nb_chars=300) if completed else '',
                    sd_closing_date=(
                        time_to_service.date()
                        if status == ServiceRequest.STATUS.SERVICE_DIAGNOSTICS
                        else None
                    ),
                    other_expenses=(
                        Decimal(str(round(random.uniform(100, 2000), 2)))
                        if completed else None
                    ),
                    closing_time=closing_time,
                    closing_amount=(
                        Decimal(str(round(random.uniform(500, 5000), 2)))
                        if completed else None
                    ),
                )
            )

        ServiceRequest.objects.bulk_create(objects, batch_size=500)

        created = list(
            ServiceRequest.objects
            .order_by('-pk')[:count]
        )

        if len(created) > 1:
            parent = created[-1]
            children = created[::5]

            for child in children:
                if child.pk != parent.pk:
                    child.parent = parent

            ServiceRequest.objects.bulk_update(
                children,
                ['parent'],
                batch_size=500,
            )

        return created

    def _create_accounting_entries(self, requests, users):
        if not requests:
            return

        entries = []

        count = max(1, len(requests) // 5)

        for _ in range(count):
            request = random.choice(requests)
            entry_type = random.choice(
                AccountingEntry.ENTRY_TYPE.CHOICES
            )[0]

            expense_subtype = (
                random.choice(AccountingEntry.EXPENSE_SUBTYPE.CHOICES)[0]
                if entry_type == AccountingEntry.ENTRY_TYPE.EXPENSE
                else ''
            )

            entries.append(
                AccountingEntry(
                    entry_type=entry_type,
                    expense_subtype=expense_subtype,
                    amount=Decimal(str(round(random.uniform(100, 15000), 2))),
                    description=fake.sentence(),
                    branch=request.branch,
                    city=request.city,
                    service_request=request,
                    created_by=random.choice(users),
                )
            )

        AccountingEntry.objects.bulk_create(
            entries,
            batch_size=500,
        )
