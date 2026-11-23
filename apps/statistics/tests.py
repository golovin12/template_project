import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase
from django.utils import timezone

from accounts.models import Branch, City
from common_tools.test import BaseTestCase
from apps.service_requests.models import ServiceRequest
from int.db_context import DatabaseContext
from .services import (
    CityStatisticsCacheService,
    CityStatisticsDataProvider,
    CityStatisticsService,
)
from .services.cache_keys import city_stats_cache_key


class CityStatisticsTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.city = City.objects.create(name='Москва')
        self.branch = Branch.objects.create(
            name='Центральный',
            city=self.city,
        )

        self.service = CityStatisticsService(self.city.pk)

    def create_request(self, **kwargs):
        defaults = {
            'request_number': 1,
            'request_type': ServiceRequest.REQUEST_TYPE_CHOICES.FIRST_TIME,
            'status': ServiceRequest.STATUS.COMPLETED,
            'branch': self.branch,
            'city': self.city,
            'client_name': 'Иван',
            'client_address': 'Москва',
            'problem_description': 'Ремонт',
            'time_to_service': timezone.now(),
            'closing_time': timezone.now(),
            'closing_amount': Decimal('5000.00'),
            'other_expenses': Decimal('1000.00'),
            'device_type': 'Телефон',
        }
        defaults.update(kwargs)
        return ServiceRequest.objects.create(**defaults)


class TestCityStatisticsService(CityStatisticsTestCase):
    def test_get_avg_check_by_month(self):
        now = timezone.now()

        self.create_request(
            closing_amount=Decimal('5000.00'),
            other_expenses=Decimal('1000.00'),
            closing_time=now.replace(day=5),
        )
        self.create_request(
            request_number=2,
            closing_amount=Decimal('7000.00'),
            other_expenses=Decimal('1000.00'),
            closing_time=now.replace(day=15),
        )
        self.create_request(
            request_number=3,
            status=ServiceRequest.STATUS.CANCELED,
        )
        self.create_request(
            request_number=4,
            closing_time=None,
        )

        result = list(self.service.get_avg_check_by_month())

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['avg_check'], Decimal('5000.00'))
        self.assertEqual(result[0]['total'], 2)
        self.assertEqual(result[0]['month'].month, now.month)

    def test_get_avg_check_by_device_by_month(self):
        now = timezone.now()

        self.create_request(
            closing_amount=Decimal('5000.00'),
            other_expenses=Decimal('1000.00'),
            device_type='Телефон',
        )
        self.create_request(
            request_number=2,
            closing_amount=Decimal('7000.00'),
            other_expenses=Decimal('1000.00'),
            device_type='Ноутбук',
        )

        result = list(self.service.get_avg_check_by_device_by_month())

        self.assertEqual(len(result), 2)

        self.assertEqual(
            {row['device_type']: row['avg_check'] for row in result},
            {
                'Телефон': Decimal('4000.00'),
                'Ноутбук': Decimal('6000.00'),
            },
        )

        self.assertTrue(all(row['month'].month == now.month for row in result))

    def test_get_branch_requests_by_month(self):
        now = timezone.now()

        amounts = [4999, 5000, 10000, 20000]

        for number, amount in enumerate(amounts, start=1):
            self.create_request(
                request_number=number,
                closing_amount=Decimal(amount),
                other_expenses=Decimal('0'),
            )

        result = self.service.get_branch_requests_by_month()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['branch_id'], self.branch.pk)
        self.assertEqual(result[0]['branch_name'], self.branch.name)
        self.assertEqual(
            result[0]['month_data'],
            [{
                'month': now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                'r1': 1,
                'r2': 1,
                'r3': 1,
                'r4': 1,
            }],
        )

    def test_get_branch_income_share_by_month(self):
        second_branch = Branch.objects.create(
            name='Северный',
            city=self.city,
        )

        now = timezone.now()

        self.create_request(
            closing_amount=Decimal('7500'),
            other_expenses=Decimal('0'),
        )
        self.create_request(
            request_number=2,
            branch=second_branch,
            closing_amount=Decimal('2500'),
            other_expenses=Decimal('0'),
        )

        result = self.service.get_branch_income_share_by_month()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['month'].month, now.month)
        self.assertEqual(
            {
                item['branch_name']: item['percent']
                for item in result[0]['branches']
            },
            {
                'Центральный': Decimal('75.00'),
                'Северный': Decimal('25.00'),
            },
        )

    def test_get_branch_income_share_by_month_skips_zero_income(self):
        self.create_request(
            closing_amount=Decimal('1000'),
            other_expenses=Decimal('1000'),
        )

        self.assertEqual(self.service.get_branch_income_share_by_month(), [])

    @patch('apps.statistics.services.city_stats.timezone.now')
    def test_get_efficiency_stats(self, now_mock):
        now = timezone.now()
        now_mock.return_value = now

        current_week = now.replace(hour=12, minute=0, second=0, microsecond=0)
        previous_week = current_week - timedelta(days=7)

        self.create_request(
            closing_time=current_week,
            closing_amount=Decimal('3000'),
            other_expenses=Decimal('1000'),
        )
        self.create_request(
            request_number=2,
            closing_time=current_week,
            closing_amount=Decimal('1500'),
            other_expenses=Decimal('1000'),
        )
        self.create_request(
            request_number=3,
            closing_time=current_week,
            status=ServiceRequest.STATUS.CANCELED,
            closing_amount=Decimal('3000'),
            other_expenses=Decimal('1000'),
        )
        self.create_request(
            request_number=4,
            closing_time=previous_week,
            closing_amount=Decimal('3000'),
            other_expenses=Decimal('1000'),
        )

        result = self.service.get_efficiency_stats()

        city = result['city']

        self.assertEqual(city['name'], 'Весь город')
        self.assertEqual(city['current_week_total'], 3)
        self.assertEqual(city['current_week_good'], 1)
        self.assertAlmostEqual(city['current_week'], 100 / 3)
        self.assertEqual(city['previous_week_total'], 1)
        self.assertEqual(city['previous_week_good'], 1)
        self.assertEqual(city['previous_week'], 100)

        self.assertEqual(len(result['branches']), 1)

        branch = result['branches'][0]

        self.assertEqual(branch['id'], self.branch.pk)
        self.assertEqual(branch['name'], self.branch.name)
        self.assertEqual(branch['current_week_total'], 3)
        self.assertEqual(branch['current_week_good'], 1)
        self.assertEqual(branch['previous_week_total'], 1)
        self.assertEqual(branch['previous_week_good'], 1)

    def test_get_efficiency_stats_without_requests(self):
        result = self.service.get_efficiency_stats()

        self.assertEqual(
            result,
            {
                'city': {
                    'name': 'Весь город',
                    'current_week': 0,
                    'current_week_total': 0,
                    'current_week_good': 0,
                    'previous_week': 0,
                    'previous_week_total': 0,
                    'previous_week_good': 0,
                    'months': [],
                },
                'branches': [],
            },
        )


class TestCityStatisticsDataProvider(SimpleTestCase):
    def setUp(self):
        self.service = Mock()

        self.service.get_avg_check_by_month.return_value = [
            {
                'month': datetime(2026, 1, 1),
                'avg_check': Decimal('5000.50'),
                'total': 2,
            },
            {
                'month': datetime(2026, 2, 1),
                'avg_check': None,
                'total': 0,
            },
        ]

        self.service.get_avg_check_by_device_by_month.return_value = [
            {
                'month': datetime(2026, 1, 1),
                'device_type': 'Телефон',
                'avg_check': Decimal('5000.50'),
                'total': 2,
            },
        ]

        self.service.get_branch_requests_by_month.return_value = []
        self.service.get_branch_income_share_by_month.return_value = []

        self.service.get_efficiency_stats.return_value = {
            'city': {
                'name': 'Весь город',
                'current_week': 75.0,
                'current_week_total': 4,
                'current_week_good': 3,
                'previous_week': 50.0,
                'previous_week_total': 2,
                'previous_week_good': 1,
                'months': [
                    {
                        'month': datetime(2026, 1, 1),
                        'efficiency': 75.0,
                        'total': 4,
                        'good': 3,
                    },
                ],
            },
            'branches': [
                {
                    'id': 1,
                    'name': 'Центральный',
                    'current_week': 75.0,
                    'current_week_total': 4,
                    'current_week_good': 3,
                    'previous_week': 50.0,
                    'previous_week_total': 2,
                    'previous_week_good': 1,
                    'months': [
                        {
                            'month': datetime(2026, 1, 1),
                            'efficiency': 75.0,
                            'total': 4,
                            'good': 3,
                        },
                    ],
                },
            ],
        }

        self.provider = CityStatisticsDataProvider(self.service)

    def test_json_handler(self):
        self.assertEqual(
            self.provider.json_handler(datetime(2026, 1, 15)),
            '01.2026',
        )
        self.assertEqual(
            self.provider.json_handler(Decimal('123.456')),
            '123.46',
        )

    def test_get_serialized_data(self):
        result = json.loads(self.provider.get_serialized_data())

        self.assertEqual(
            result['avg_check_by_month'],
            [
                {
                    'month': '01.2026',
                    'avg_check': '5000.50',
                    'total': 2,
                },
                {
                    'month': '02.2026',
                    'avg_check': '0.00',
                    'total': 0,
                },
            ],
        )

        self.assertEqual(
            result['avg_check_by_device'],
            {
                '01.2026': {
                    'Телефон': {
                        'avg_check': '5000.50',
                        'total': 2,
                    },
                },
            },
        )

        self.assertEqual(
            result['efficiency']['city']['months'],
            [{
                'month': '01.2026',
                'efficiency': 75.0,
                'total': 4,
                'good': 3,
            }],
        )

        self.assertEqual(
            result['efficiency']['branches'][0]['name'],
            'Центральный',
        )

        self.service.get_branch_requests_by_month.assert_called_once()
        self.service.get_branch_income_share_by_month.assert_called_once()
        self.service.get_efficiency_stats.assert_called_once()


class TestCityStatisticsCacheService(CityStatisticsTestCase):
    def test_get_returns_cached_data(self):
        key = city_stats_cache_key(self.city.pk)
        cache.set(key, '{"cached": true}')

        with patch.object(CityStatisticsCacheService, 'rebuild') as rebuild:
            result = CityStatisticsCacheService.get(self.city.pk)

        self.assertEqual(result, '{"cached": true}')
        rebuild.assert_not_called()

    def test_get_rebuilds_missing_data(self):
        with patch.object(
                CityStatisticsCacheService,
                'rebuild',
                return_value='{"rebuilt": true}',
        ) as rebuild:
            result = CityStatisticsCacheService.get(self.city.pk)

        self.assertEqual(result, '{"rebuilt": true}')
        rebuild.assert_called_once_with(self.city.pk)

    def test_rebuild_creates_and_caches_data(self):
        result = CityStatisticsCacheService.rebuild(self.city.pk)

        self.assertIsInstance(result, str)
        self.assertEqual(json.loads(result)['avg_check_by_month'], [])
        self.assertEqual(cache.get(city_stats_cache_key(self.city.pk)), result)

    def test_invalidate_deletes_cached_data(self):
        key = city_stats_cache_key(self.city.pk)
        cache.set(key, '{"cached": true}')

        CityStatisticsCacheService.invalidate(self.city.pk)

        self.assertIsNone(cache.get(key))


class TestCityStatisticsCacheKey(BaseTestCase):
    def test_cache_key_includes_database_alias(self):
        self.assertEqual(
            city_stats_cache_key(10),
            'organization_1:city_stats:10',
        )

    def test_cache_key_changes_with_database_context(self):
        with DatabaseContext.using('default'):
            self.assertEqual(
                city_stats_cache_key(10),
                'default:city_stats:10',
            )
