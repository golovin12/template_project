from functools import wraps

from django.conf import settings

from int import tasks as main_tasks
from django_dramatiq import tasks as django_dramatiq_tasks
from apps.notifications import tasks as notification_tasks
from apps.statistics import tasks as statistics_tasks
from promoter_app import tasks as promotreck_tasks

# ТИПЫ ЗАДАЧ (the alias name of the trigger (e.g. ``date``, ``interval`` or ``cron``))
DATE = 'date'
INTERVAL = 'interval'
CRON = 'cron'


def bind_zone(actor_send, zone):
    @wraps(actor_send)
    def wrapper(*args, **kwargs):
        return actor_send(zone, *args, **kwargs)

    return wrapper


def add_tasks(scheduler):
    """
    Добавление задач по расписанию в планировщик проекта
    Часовой пояс по умолчанию системный
    :param scheduler: наследник apscheduler.schedulers.base.BaseScheduler

    Параметры scheduler.add_job:
        func, trigger=None, args=None, kwargs=None, id=None, name=None, misfire_grace_time=undefined,
        coalesce=undefined, max_instances=undefined, next_run_time=undefined, jobstore='default',
        executor='default', replace_existing=False, **trigger_args)

    Параметры задач разных типов:
        DateTrigger.__init__ ('date') params:
            run_date=None, timezone=None
        IntervalTrigger.__init__ ('interval') params:
            weeks=0, days=0, hours=0, minutes=0, seconds=0, start_date=None, end_date=None, timezone=None, jitter=None
        CronTrigger.__init__ ('cron') params:
            year=None, month=None, day=None, week=None, day_of_week=None, hour=None, minute=None, second=None,
            start_date=None, end_date=None, timezone=None, jitter=None
            + можно так: CronTrigger.from_crontab("* * * * *")
            scheduler.add_job(tasks.count_words1.send, CronTrigger.from_crontab("* * * * *"))

    Задачу можно вызвать откуда угодно без ее кода, для этого нужно поставить ее в очередь вручную
        broker.send(Message(
          queue_name="default",
          actor_name="send_sms",
          args=("hello",),
          kwargs={},
          options={},
        ))

    Количество одновременно выполняемых экземпляров задания
        По умолчанию одновременно разрешается запускать только один экземпляр каждого задания.
        если задание готовится к запуску, но предыдущий запуск еще не завершен, то последний запуск считается осечкой.
        Можно задать максимальное число экземпляров для конкретного задания, которое планировщик позволит
        запускать одновременно, используя аргумент ключевого слова max_instances при добавлении задания.
        При запуске акторов dramatiq - задание выполняется моментально с точки зрения шедулера,
        поэтому необходимо выставить подходящий лимит на время выполнения актора

    Run the `job_function` every hour with an extra-delay picked randomly in a [-120,+120] seconds window.
        sched.add_job(job_function, 'interval', hours=1, jitter=120)
    """
    # default_zones
    # django_dramatiq
    scheduler.add_job(django_dramatiq_tasks.delete_old_tasks.send,
                      CRON, hour='23', minute='0')
    # notifications_queue
    scheduler.add_job(bind_zone(notification_tasks.send_notifications.send_with_zone, 'default'),
                      INTERVAL, minutes=1)
    # notifications
    scheduler.add_job(bind_zone(notification_tasks.cleanup_old_telegram_messages.send_with_zone, 'default'),
                      CRON, hour='3', minute='0')
    # Other zones
    all_databases = list(settings.DATABASES.keys())
    zones = [db for db in all_databases if db != 'old']
    for zone in zones:
        # backup
        scheduler.add_job(bind_zone(main_tasks.create_everyday_backup.send_with_zone, zone),
                          CRON, hour='1', minute='0', jitter=360)
        scheduler.add_job(bind_zone(main_tasks.create_every_week_backup.send_with_zone, zone),
                          CRON, day_of_week='0', hour='1', minute='30', jitter=360)
        scheduler.add_job(bind_zone(main_tasks.create_every_month_backup.send_with_zone, zone),
                          CRON, day='1', hour='2', minute='0', jitter=360)
    for zone in zones:
        if zone == 'default':
            continue
        # statistics
        scheduler.add_job(bind_zone(statistics_tasks.rebuild_cities_statistic.send_with_zone, zone),
                          CRON, hour='2', minute='12', jitter=300)
        # promotreck
        scheduler.add_job(bind_zone(promotreck_tasks.cleanup_old_promoter_assignment_photos.send_with_zone, zone),
                          CRON, hour='2', minute='30', jitter=300)
        scheduler.add_job(bind_zone(promotreck_tasks.cleanup_old_promoter_assignment_photos.send_with_zone, zone),
                          CRON, hour='14', jitter=180)
    # # примеры:
    # # scheduler.add_job(demo_tasks.operational_error_task.send, INTERVAL, minutes=1)
    # # scheduler.add_job(demo_tasks.send_email.send, INTERVAL, minutes=1, args=['golovin.dv@gmail.com'])
    # # scheduler.add_job(demo_tasks.send_email.send, DATE, run_date=dt.datetime(2019, 12, 19, 5, 00),
    # #                   args=['golovin.dv@gmail.com'])
    # scheduler.add_job(demo_tasks.imap_err.send, INTERVAL, minutes=2)
