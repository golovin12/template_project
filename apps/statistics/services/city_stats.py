from collections import defaultdict
from datetime import timedelta

from django.db.models import F, Avg, Count, Q, Sum, Value, DecimalField
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from apps.service_requests.models import ServiceRequest


class CityStatisticsService:
    def __init__(self, city_id: int):
        self.city_id = city_id

    def get_avg_check_by_month(self):
        return ServiceRequest.objects.filter(
            city_id=self.city_id, status=ServiceRequest.STATUS.COMPLETED, closing_time__isnull=False
        ).annotate(
            net_amount=F('closing_amount') - Coalesce(F('other_expenses'), Value(0, output_field=DecimalField())),
            month=TruncMonth('closing_time')
        ).values('month').annotate(
            avg_check=Avg('net_amount'), total=Count('id')
        ).order_by('month')

    def get_avg_check_by_device_by_month(self):
        return ServiceRequest.objects.filter(
            city_id=self.city_id, status=ServiceRequest.STATUS.COMPLETED, closing_time__isnull=False
        ).annotate(
            net_amount=F('closing_amount') - Coalesce(F('other_expenses'), Value(0, output_field=DecimalField())),
            month=TruncMonth('closing_time')
        ).values('month', 'device_type').annotate(
            avg_check=Avg('net_amount'), total=Count('id')
        ).order_by('month')

    def get_branch_requests_by_month(self):
        """
        Возвращает количество заявок по филиалам, сгруппированное по ценовым диапазонам дохода и месяцам.
        """
        qs = ServiceRequest.objects.filter(
            city_id=self.city_id,
            status=ServiceRequest.STATUS.COMPLETED,
            closing_time__isnull=False
        ).annotate(
            month=TruncMonth('closing_time'),
            net_amount=F('closing_amount') - Coalesce(F('other_expenses'), Value(0, output_field=DecimalField()))
        ).values('month', 'branch_id', 'branch__name').annotate(
            r1=Count('id', filter=Q(net_amount__lt=5000)),
            r2=Count('id', filter=Q(net_amount__gte=5000, net_amount__lt=10000)),
            r3=Count('id', filter=Q(net_amount__gte=10000, net_amount__lt=20000)),
            r4=Count('id', filter=Q(net_amount__gte=20000))
        ).order_by('branch_id', 'month')

        branch_map = defaultdict(list)
        for row in qs:
            branch_map[row['branch_id']].append(row)

        result = []

        for branch_id, rows in branch_map.items():
            month_data = []
            for row in rows:
                month_data.append({
                    'month': row['month'],
                    'r1': row['r1'],
                    'r2': row['r2'],
                    'r3': row['r3'],
                    'r4': row['r4'],
                })

            result.append({
                'branch_id': branch_id,
                'branch_name': rows[0]['branch__name'],
                'month_data': month_data
            })

        result.sort(key=lambda x: x['branch_name'])

        return result

    def get_branch_income_share_by_month(self):
        """Возвращает долю филиалов в доходе города по месяцам."""

        qs = ServiceRequest.objects.filter(
            city_id=self.city_id,
            status=ServiceRequest.STATUS.COMPLETED,
            closing_time__isnull=False,
        ).annotate(
            month=TruncMonth('closing_time'),
            net_amount=F('closing_amount') - Coalesce(F('other_expenses'), Value(0, output_field=DecimalField()))
        ).values('month', 'branch_id', 'branch__name').annotate(
            income=Coalesce(Sum('net_amount'), Value(0, output_field=DecimalField()))
        ).order_by('month', '-income')

        month_map = defaultdict(list)

        for row in qs:
            month_map[row['month']].append(row)

        result = []

        for month, rows in month_map.items():
            total_income = sum(r['income'] for r in rows)

            if not total_income:
                continue

            branches_data = []

            for r in rows:
                percent = (r['income'] / total_income) * 100

                branches_data.append({
                    'branch_id': r['branch_id'],
                    'branch_name': r['branch__name'],
                    'percent': round(percent, 2),
                })

            result.append({
                'month': month,
                'branches': branches_data
            })

        result.sort(key=lambda x: x['month'])
        return result

    def get_efficiency_stats(self):
        """
        Возвращает статистику эффективности для города и его филиалов.
        Оптимизированная версия с минимальным количеством запросов к БД.
        Учитываются как завершённые, так и отменённые заявки.
        """
        today = timezone.now()
        week_start = today - timedelta(days=today.weekday())
        prev_week_start = week_start - timedelta(days=7)

        zero_decimal = Value(0, output_field=DecimalField(max_digits=14, decimal_places=2))
        good_order_filter = Q(closing_amount__gte=Coalesce(F('other_expenses'), zero_decimal) + 1000)

        base_filter = dict(
            city_id=self.city_id,
            status__in=[ServiceRequest.STATUS.COMPLETED, ServiceRequest.STATUS.CANCELED],
            closing_time__isnull=False
        )

        city_weeks = ServiceRequest.objects.filter(**base_filter).aggregate(
            current_total=Count('id', filter=Q(closing_time__date__gte=week_start)),
            current_good=Count('id', filter=Q(status=ServiceRequest.STATUS.COMPLETED) & Q(
                closing_time__date__gte=week_start) & good_order_filter),
            previous_total=Count('id',
                                 filter=Q(closing_time__date__gte=prev_week_start, closing_time__date__lt=week_start)),
            previous_good=Count('id', filter=Q(status=ServiceRequest.STATUS.COMPLETED) & Q(
                closing_time__date__gte=prev_week_start, closing_time__date__lt=week_start) & good_order_filter)
        )

        city_months = ServiceRequest.objects.filter(**base_filter).annotate(
            month=TruncMonth('closing_time')
        ).values('month').annotate(
            total=Count('id'),
            good=Count('id', filter=Q(status=ServiceRequest.STATUS.COMPLETED) & good_order_filter)
        ).order_by('-month')

        branch_filter = Q(**base_filter) & Q(branch_id__isnull=False)

        branch_weeks = ServiceRequest.objects.filter(branch_filter).values('branch_id', 'branch__name').annotate(
            current_total=Count('id', filter=Q(closing_time__date__gte=week_start)),
            current_good=Count('id', filter=Q(status=ServiceRequest.STATUS.COMPLETED) & Q(
                closing_time__date__gte=week_start) & good_order_filter),
            previous_total=Count('id',
                                 filter=Q(closing_time__date__gte=prev_week_start, closing_time__date__lt=week_start)),
            previous_good=Count('id', filter=Q(status=ServiceRequest.STATUS.COMPLETED) & Q(
                closing_time__date__gte=prev_week_start, closing_time__date__lt=week_start) & good_order_filter)
        )

        branch_months = ServiceRequest.objects.filter(branch_filter).annotate(
            month=TruncMonth('closing_time')
        ).values('month', 'branch_id', 'branch__name').annotate(
            total=Count('id'),
            good=Count('id', filter=Q(status=ServiceRequest.STATUS.COMPLETED) & good_order_filter)
        ).order_by('-month', 'branch__name')

        branch_months_dict = {}
        for item in branch_months:
            branch_id = item['branch_id']
            if branch_id not in branch_months_dict:
                branch_months_dict[branch_id] = []
            branch_months_dict[branch_id].append({
                'month': item['month'],
                'efficiency': item['good'] * 100 / item['total'] if item['total'] else 0,
                'total': item['total'],
                'good': item['good'],
            })

        branches_data = []
        for item in branch_weeks:
            branch_id = item['branch_id']
            branches_data.append({
                'id': branch_id,
                'name': item['branch__name'],
                'current_week': item['current_good'] * 100 / item['current_total'] if item['current_total'] else 0,
                'current_week_total': item['current_total'],
                'current_week_good': item['current_good'],
                'previous_week': item['previous_good'] * 100 / item['previous_total'] if item['previous_total'] else 0,
                'previous_week_total': item['previous_total'],
                'previous_week_good': item['previous_good'],
                'months': branch_months_dict.get(branch_id, [])
            })

        branches_data.sort(key=lambda x: x['name'])

        return {
            'city': {
                'name': 'Весь город',
                'current_week': city_weeks['current_good'] * 100 / city_weeks['current_total']
                if city_weeks['current_total'] else 0,
                'current_week_total': city_weeks['current_total'],
                'current_week_good': city_weeks['current_good'],
                'previous_week': city_weeks['previous_good'] * 100 / city_weeks['previous_total']
                if city_weeks['previous_total'] else 0,
                'previous_week_total': city_weeks['previous_total'],
                'previous_week_good': city_weeks['previous_good'],
                'months': [
                    {
                        'month': item['month'],
                        'efficiency': item['good'] * 100 / item['total'] if item['total'] else 0,
                        'total': item['total'],
                        'good': item['good'],
                    }
                    for item in city_months
                ]
            },
            'branches': branches_data
        }
