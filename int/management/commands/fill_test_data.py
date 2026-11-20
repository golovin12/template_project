import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import City
from apps.promoters.models import PromoterProfile, RouteZone, PromoterAssignment, PromoterPhoto

User = get_user_model()


class Command(BaseCommand):
    help = 'Заполнение базы данных тестовыми данными'

    def handle(self, *args, **options):
        self.stdout.write('Начинаем заполнение базы данных...')

        # Создаем города
        cities = self.create_cities()

        # Создаем пользователя для назначений
        user = self.create_user()

        # Создаем промоутеров
        promoters = self.create_promoters(cities)

        # Создаем маршруты
        routes = self.create_routes(cities)

        # Создаем назначения
        assignments = self.create_assignments(promoters, routes, user)

        # Создаем фотографии
        self.create_photos(assignments)

        self.stdout.write(self.style.SUCCESS('База данных успешно заполнена!'))

    def create_cities(self):
        """Создание городов"""
        cities_data = [
            {'name': 'Москва'},
            {'name': 'Санкт-Петербург'},
            {'name': 'Казань'},
            {'name': 'Новосибирск'},
            {'name': 'Екатеринбург'},
        ]

        cities = []
        for city_data in cities_data:
            city, created = City.objects.get_or_create(
                name=city_data['name'],
            )
            cities.append(city)
            if created:
                self.stdout.write(f'Создан город: {city.name}')

        return cities

    def create_user(self):
        """Создание пользователя для назначений"""
        user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@example.com',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            user.set_password('admin123')
            user.save()
            self.stdout.write('Создан пользователь: admin (пароль: admin123)')

        return user

    def create_promoters(self, cities):
        """Создание промоутеров"""
        promoters_names = [
            'Анна', 'Борис', 'Виктория', 'Григорий', 'Дарья',
            'Евгений', 'Жанна', 'Захар', 'Ирина', 'Константин',
            'Людмила', 'Михаил', 'Наталья', 'Олег', 'Полина'
        ]

        promoters = []
        for i, name in enumerate(promoters_names):
            city = random.choice(cities)
            promoter, created = PromoterProfile.objects.get_or_create(
                nickname=name,
                defaults={'city': city}
            )
            promoters.append(promoter)
            if created:
                self.stdout.write(f'Создан промоутер: {name} ({city.name})')

        return promoters

    def create_routes(self, cities):
        """Создание маршрутов с полигонами"""
        routes_data = {
            'Москва': [
                {
                    'name': 'Центральный парк',
                    'polygon': {
                        "type": "Polygon",
                        "coordinates": [[[37.518495, 47.107408], [37.509633, 47.108023],
                                         [37.508239, 47.099599], [37.517165, 47.098969],
                                         [37.518495, 47.107408]]]
                    }
                },
                {
                    'name': 'Тверской район',
                    'polygon': {
                        "type": "Polygon",
                        "coordinates": [[[37.526576, 47.116422], [37.527359, 47.121175],
                                         [37.542701, 47.116985], [37.543667, 47.11689],
                                         [37.526576, 47.116422]]]
                    }
                },
                {
                    'name': 'Арбат',
                    'polygon': {
                        "type": "Polygon",
                        "coordinates": [[[37.524851, 47.106892], [37.523564, 47.098504],
                                         [37.517198, 47.098979], [37.518518, 47.107374],
                                         [37.524851, 47.106892]]]
                    }
                }
            ],
            'Санкт-Петербург': [
                {
                    'name': 'Невский проспект',
                    'polygon': {
                        "type": "Polygon",
                        "coordinates": [[[30.315868, 59.936391], [30.318497, 59.935783],
                                         [30.317283, 59.932146], [30.314201, 59.933079],
                                         [30.315868, 59.936391]]]
                    }
                },
                {
                    'name': 'Васильевский остров',
                    'polygon': {
                        "type": "Polygon",
                        "coordinates": [[[30.276215, 59.943864], [30.279188, 59.942166],
                                         [30.277752, 59.939664], [30.274264, 59.940528],
                                         [30.276215, 59.943864]]]
                    }
                }
            ]
        }

        routes = []
        for city in cities:
            city_routes = routes_data.get(city.name, [])
            if not city_routes:
                # Создаем стандартный маршрут для городов без данных
                city_routes = [{
                    'name': 'Центральный район',
                    'polygon': {
                        "type": "Polygon",
                        "coordinates": [[[37.518495, 47.107408], [37.509633, 47.108023],
                                         [37.508239, 47.099599], [37.517165, 47.098969],
                                         [37.518495, 47.107408]]]
                    }
                }]

            for route_data in city_routes:
                route, created = RouteZone.objects.get_or_create(
                    city=city,
                    name=route_data['name'],
                    defaults={
                        'polygon': route_data['polygon'],
                        'is_active': random.choice([True, False])
                    }
                )
                routes.append(route)
                if created:
                    self.stdout.write(f'Создан маршрут: {route.name} ({city.name})')

        return routes

    def create_assignments(self, promoters, routes, user):
        """Создание назначений"""
        assignments = []

        # Даты за последние 30 дней
        dates = [timezone.now() - timedelta(days=i) for i in range(30)]

        for promoter in promoters:
            # Каждому промоутеру 2-5 назначений
            num_assignments = random.randint(2, 5)
            assigned_routes = random.sample(routes, min(num_assignments, len(routes)))

            for route in assigned_routes:
                assigned_date = random.choice(dates)

                # Обновляем дату последнего назначения маршрута
                if not route.last_assigned_date or assigned_date > route.last_assigned_date:
                    route.last_assigned_date = assigned_date
                    route.save()

                assignment, created = PromoterAssignment.objects.get_or_create(
                    promoter=promoter,
                    route_zone=route,
                    defaults={
                        'assigned_date': assigned_date,
                        'assigned_by': user,
                        'status': random.choice(['new', 'process', 'ended']),
                        'full_data_loaded': random.choice([True, False])
                    }
                )

                # Если назначение уже существует, но не обновляем дату
                if not created:
                    continue

                assignments.append(assignment)
                self.stdout.write(f'Создано назначение: {promoter.nickname} -> {route.name} ({assigned_date.date()})')

        return assignments

    def create_photos(self, assignments):
        """Создание фотографий для назначений"""
        total_photos = 0

        for assignment in assignments:
            # Количество фото от 0 до 20
            num_photos = random.randint(0, 20)

            photos_no_gps = 0

            for i in range(num_photos):
                # 80% фото с GPS, 20% без GPS
                has_location = random.random() > 0.2

                if has_location:
                    # Генерируем координаты вокруг центра полигона
                    # Для простоты используем случайные координаты
                    lat = 47.10 + random.uniform(-0.05, 0.05)
                    lng = 37.52 + random.uniform(-0.05, 0.05)
                else:
                    lat = None
                    lng = None
                    photos_no_gps += 1

                # Создаем фиктивный путь к изображению
                # В реальности нужно иметь реальные файлы
                PromoterPhoto.objects.create(
                    assignment=assignment,
                    image=f'promoter_photos/test_photo_{assignment.id}_{i}.jpg',
                    created_at=assignment.assigned_date + timedelta(hours=random.randint(1, 72)),
                    lat=lat,
                    lng=lng,
                    has_location=has_location
                )
                total_photos += 1

            # Обновляем статистику назначения
            assignment.total_photos = num_photos
            assignment.photos_no_gps = photos_no_gps
            assignment.full_data_loaded = num_photos > 0

            # Если есть фото с GPS и статус NEW, меняем на PROCESS
            if num_photos > 0 and assignment.status == 'new':
                assignment.status = 'process'

            assignment.save()

            if num_photos > 0:
                self.stdout.write(f'Для назначения {assignment.id} создано {num_photos} фото')

        self.stdout.write(f'Всего создано {total_photos} фотографий')
