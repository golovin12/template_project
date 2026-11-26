from django.core.cache import cache

from .city_stats import CityStatisticsService
from .data_provider import CityStatisticsDataProvider
from .cache_keys import city_stats_cache_key


class CityStatisticsCacheService:
    CACHE_TIMEOUT = 60 * 60 * 25  # 25 часов

    @classmethod
    def get(cls, city_id: int) -> str:
        key = city_stats_cache_key(city_id)
        data = cache.get(key)

        if data is None:
            data = cls.rebuild(city_id)

        return data

    @classmethod
    def rebuild(cls, city_id: int) -> str:
        service = CityStatisticsService(city_id)
        provider = CityStatisticsDataProvider(service)

        data = provider.get_serialized_data()

        cache.set(
            city_stats_cache_key(city_id),
            data,
            timeout=cls.CACHE_TIMEOUT
        )

        return data

    @classmethod
    def invalidate(cls, city_id: int):
        cache.delete(city_stats_cache_key(city_id))
