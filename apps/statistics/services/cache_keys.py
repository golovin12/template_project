from int.db_context import cache_key


def city_stats_cache_key(city_id: int) -> str:
    return cache_key(f'city_stats:{city_id}')
