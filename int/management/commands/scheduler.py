import os
import time

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from django.core.management import BaseCommand

from int import scheduler_config


class Command(BaseCommand):
    help = """Запуск планировщика задач"""

    def handle(self, *args, **opts):
        jobstores = {
            'default': MemoryJobStore(),
        }
        executors = {
            'default': ThreadPoolExecutor(4),
        }
        job_default_args = {}
        scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_default_args
        )

        scheduler_config.add_tasks(scheduler)

        for job in scheduler.get_jobs():
            if not (job.name.endswith('.send') or job.name.endswith('.send_with_options')
                    or job.name.endswith('.send_with_db_alias')):
                raise ValueError('Задачи следует вызывать асинхронным методом .send или .send_with_options')

        scheduler.start()
        print('Press Ctrl+{0} to exit'.format('Break' if os.name == 'nt' else 'C'))
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()
