from datetime import date

import dramatiq

from accounts.base import actor
from int.management.create_backup import create_backup

BACKUP_QUEUE_NAME = 'backup'


@dramatiq.actor(queue_name='holding_connection', time_limit=1 * 1000, max_age=30 * 1000)
def holding_rmq_connection():
    """Заглушка, чтобы соединение с rabbitmq не прерывалось из-за heartbeat"""
    pass


@actor(queue_name=BACKUP_QUEUE_NAME, time_limit=10 * 60 * 1000, max_age=40 * 60 * 1000)
def create_everyday_backup() -> None:
    """Ежедневный бэкап (4 записи)"""
    today = date.today()
    prefix = (today.toordinal() % 4) + 1
    create_backup(f'day_{prefix}')


@actor(queue_name=BACKUP_QUEUE_NAME, time_limit=10 * 60 * 1000, max_age=40 * 60 * 1000)
def create_every_week_backup() -> None:
    """Еженедельный бэкап (2 записи)"""
    today = date.today()
    prefix = (today.isocalendar()[1] % 2) + 1
    create_backup(f'week_{prefix}')


@actor(queue_name=BACKUP_QUEUE_NAME, time_limit=10 * 60 * 1000, max_age=40 * 60 * 1000)
def create_every_month_backup() -> None:
    """Ежемесячный бэкап (2 записи)"""
    today = date.today()
    prefix = (today.month % 2) + 1
    create_backup(f'month_{prefix}')
