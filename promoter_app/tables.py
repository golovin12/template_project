from django_tables2 import tables, columns

from django.utils.safestring import mark_safe

from .models import PromoterAssignment, PromoterProfile


class PromoterAssignmentTable(tables.Table):
    """Таблица назначений промоутеров"""
    promoter = tables.Column(verbose_name='Промоутер', accessor='promoter.nickname', order_by=('promoter__nickname',))
    assigned_date = columns.DateTimeColumn(verbose_name='Дата назначения', format='d.m.Y H:i', accessor='assigned_date')
    route_zone = tables.Column(verbose_name='Маршрут', accessor='route_zone.name', order_by=('route_zone__name',))
    photos_progress = tables.Column(verbose_name='Фото с GPS / Всего', empty_values=(), orderable=False)
    open_detail = columns.TemplateColumn(verbose_name='Фото', orderable=False,
                                         template_name='promoter_app/table_includes/assignment_open_detail.html')

    class Meta:
        model = PromoterAssignment
        fields = (
            'promoter', 'status', 'assigned_date', 'route_zone', 'photos_progress', 'full_data_loaded', 'open_detail'
        )
        attrs = {
            'class': 'table table-hover table-responsive-lg',
            'thead': {'class': 'thead-light'}
        }

    def render_photos_progress(self, value, record):
        """Отображение прогресса загрузки фото"""
        total_photos = record.total_photos
        photos_with_gps = total_photos - record.photos_no_gps

        if total_photos == 0:
            return mark_safe('<span class="text-muted">Нет фото</span>')

        return f'{photos_with_gps} / {total_photos}'

    def render_status(self, value, record):
        """Отображение статуса с цветом и иконкой"""
        status_map = {
            'new': {
                'icon': '⏳',
                'badge_class': 'badge-info',
                'text': 'Назначен'
            },
            'process': {
                'icon': '🔄',
                'badge_class': 'badge-warning',
                'text': 'В работе'
            },
            'ended': {
                'icon': '✅',
                'badge_class': 'badge-success',
                'text': 'Завершён'
            },
        }

        status = record.status
        status_info = status_map.get(status, {
            'icon': '❓',
            'badge_class': 'badge-secondary',
            'text': value or 'Неизвестно'
        })

        status_badge = (
            f'<span class="badge {status_info["badge_class"]}" style="font-size: 0.85rem; padding: 5px 10px;">'
            f'{status_info["icon"]} {status_info["text"]}'
            '</span>'
        )

        if record.is_confirmed and record.confirmed_dt:
            status_badge += f'<div class="text-muted">Подтверждён: {record.confirmed_dt.strftime("%d.%m.%Y")}</div>'

        return mark_safe(status_badge)


class PromotersTable(tables.Table):
    assignments_stat = tables.Column(verbose_name='Маршруты', accessor='total_assignments',
                                     order_by=('total_assignments',))
    last_assignment_date = columns.DateTimeColumn(verbose_name='Последнее назначение', format='d.m.Y H:i')
    actions = columns.TemplateColumn(verbose_name='Действия', orderable=False,
                                     template_name='promoter_app/table_includes/promoter_actions.html')

    class Meta:
        model = PromoterProfile
        fields = ('nickname', 'assignments_stat', 'last_assignment_date', 'actions')
        attrs = {'class': 'table table-hover table-responsive-md'}

    def render_assignments_stat(self, record):
        return f'Завершено: {record.completed_assignments}/{record.total_assignments}'
