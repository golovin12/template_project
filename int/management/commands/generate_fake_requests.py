import random
from datetime import timedelta

from faker import Faker

from django.core.management.base import BaseCommand

from apps.service_requests.models import ServiceRequest, Branch, Master
from accounts.models import User

fake = Faker("ru_RU")


class Command(BaseCommand):
    help = "Генерация фейковых заявок ServiceRequest"

    def add_arguments(self, parser):
        parser.add_argument("count", type=int, help="Количество заявок для генерации")

    def handle(self, *args, **options):
        count = options["count"]
        self.stdout.write(self.style.WARNING(f"Генерация {count} заявок..."))

        branches = list(Branch.objects.all())
        if not branches:
            self.stdout.write(self.style.ERROR("Нет филиалов (Branch) в базе!"))
            return

        users = list(User.objects.all())
        if not users:
            self.stdout.write(self.style.ERROR("Нет пользователей (User) в базе!"))
            return

        masters_by_branch = {
            branch.id: list(Master.objects.filter(branch=branch))
            for branch in branches
        }

        start_number = 200001

        batch_size = 5000
        objects = []

        for i in range(count):
            branch = random.choice(branches)
            request_number = start_number + i
            request_time = fake.date_time_between(start_date="-1y", end_date="now")
            time_to_service = request_time + timedelta(hours=random.randint(1, 72))

            status = random.choice([s[0] for s in ServiceRequest.STATUS.choices])
            created_by = random.choice(users)

            if status == ServiceRequest.STATUS.NEW:
                assigned_master = None
            else:
                masters = masters_by_branch.get(branch.id, [])
                assigned_master = random.choice(masters) if masters else None

            closing_time = None
            closing_amount = None
            if status == ServiceRequest.STATUS.COMPLETED:
                closing_time = time_to_service + timedelta(hours=random.randint(1, 48))
                closing_amount = round(random.uniform(500, 5000), 2)

            obj = ServiceRequest(
                request_number=request_number,
                parent=None,
                request_type=random.choice([c[0] for c in ServiceRequest.REQUEST_TYPE_CHOICES.choices]),
                request_time=request_time,
                created_by=created_by,
                status=status,
                branch=branch,
                assigned_master=assigned_master,
                client_name=fake.first_name(),
                client_address=fake.address(),
                client_apartment=str(random.randint(1, 300)),
                client_phone=fake.phone_number(),
                problem_description=fake.text(max_nb_chars=200),
                device_type=random.choice(["Кондиционеры", "Кофе машины", "Другое", "Стиральные машины"]),
                time_to_service=time_to_service,
                service_report="",
                other_expenses=None,
                closing_time=closing_time,
                closing_amount=closing_amount,
            )

            objects.append(obj)

            if len(objects) >= batch_size:
                ServiceRequest.objects.bulk_create(objects, batch_size)
                objects = []
                self.stdout.write(self.style.SUCCESS(f"{i + 1} заявок создано..."))

        if objects:
            ServiceRequest.objects.bulk_create(objects, batch_size)

        self.stdout.write(self.style.SUCCESS(f"Успешно создано {count} заявок"))
