from django.apps import apps

from accounts.base import actor
from .services import CityStatisticsCacheService


@actor(queue_name='statistics', time_limit=2 * 60 * 60 * 1000, max_age=5 * 60 * 60 * 1000)
def rebuild_cities_statistic():
    City = apps.get_model('accounts', 'City')
    for city in City.objects.values_list('id', flat=True):
        CityStatisticsCacheService.rebuild(city)
