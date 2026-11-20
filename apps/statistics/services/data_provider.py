import json
from datetime import datetime, date
from decimal import Decimal


class CityStatisticsDataProvider:

    def __init__(self, statistics_service):
        self.service = statistics_service

    def get_serialized_data(self) -> str:
        return self.json_dumps({
            'avg_check_by_month': self._avg_check_by_month(),
            'avg_check_by_device': self._avg_check_by_device(),
            'branch_requests_by_month': self.service.get_branch_requests_by_month(),
            'branch_income_share_by_month': self.service.get_branch_income_share_by_month(),
            'efficiency': self._efficiency_stats(),
        })

    def json_dumps(self, value):
        return json.dumps(value, default=self.json_handler)

    @staticmethod
    def json_handler(x):
        if isinstance(x, (datetime, date)):
            return x.strftime('%m.%Y')
        if isinstance(x, Decimal):
            return f'{x:.2f}'
        return x

    def _avg_check_by_month(self) -> list[dict]:
        qs = self.service.get_avg_check_by_month()

        return [
            {
                'month': row['month'].strftime('%m.%Y') if row['month'] else None,
                'avg_check': Decimal(row['avg_check'] or 0),
                'total': row['total']
            }
            for row in qs
        ]

    def _avg_check_by_device(self) -> dict:
        qs = self.service.get_avg_check_by_device_by_month()

        result = {}

        for row in qs:
            month = row['month'].strftime('%m.%Y') if row['month'] else None
            device = row['device_type']

            result.setdefault(month, {})
            result[month][device] = {
                'avg_check': Decimal(row['avg_check'] or 0),
                'total': row['total']
            }

        return result

    def _efficiency_stats(self) -> dict:
        """Сериализует данные эффективности"""
        stats = self.service.get_efficiency_stats()

        return {
            'city': {
                'name': stats['city']['name'],
                'current_week': stats['city']['current_week'],
                'current_week_total': stats['city']['current_week_total'],
                'current_week_good': stats['city']['current_week_good'],
                'previous_week': stats['city']['previous_week'],
                'previous_week_total': stats['city']['previous_week_total'],
                'previous_week_good': stats['city']['previous_week_good'],
                'months': [
                    {
                        'month': item['month'].strftime('%m.%Y') if item['month'] else None,
                        'efficiency': item['efficiency'],
                        'total': item['total'],
                        'good': item['good'],
                    }
                    for item in stats['city']['months']
                ]
            },
            'branches': [
                {
                    'id': branch['id'],
                    'name': branch['name'],
                    'current_week': branch['current_week'],
                    'current_week_total': branch['current_week_total'],
                    'current_week_good': branch['current_week_good'],
                    'previous_week': branch['previous_week'],
                    'previous_week_total': branch['previous_week_total'],
                    'previous_week_good': branch['previous_week_good'],
                    'months': [
                        {
                            'month': item['month'].strftime('%m.%Y') if item['month'] else None,
                            'efficiency': item['efficiency'],
                            'total': item['total'],
                            'good': item['good'],
                        }
                        for item in branch['months']
                    ]
                }
                for branch in stats['branches']
            ]
        }
