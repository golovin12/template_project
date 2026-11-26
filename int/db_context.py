from contextlib import contextmanager
from contextvars import ContextVar

current_database = ContextVar('current_database', default='default')


def get_current_database():
    """Получить текущий алиас БД"""
    return current_database.get()


def set_current_database(db_alias):
    """Установить текущий алиас БД"""
    token = current_database.set(db_alias)
    return token


def reset_current_database(token):
    """Сбросить текущий алиас БД до предыдущего значения"""
    current_database.reset(token)


@contextmanager
def using_database(db_alias):
    """
    Контекстный менеджер для временного переключения БД.

    Использование:
        with using_database('organization_1'):
            # Все запросы здесь будут использовать organization_1
            user = User.objects.get(id=1)
    """
    token = current_database.set(db_alias)
    try:
        yield
    finally:
        current_database.reset(token)


class DatabaseContext:
    @staticmethod
    def get():
        return get_current_database()

    @staticmethod
    def set(db_alias):
        return set_current_database(db_alias)

    @staticmethod
    def reset(token):
        return reset_current_database(token)

    @staticmethod
    @contextmanager
    def using(db_alias):
        with using_database(db_alias):
            yield


def cache_key(key: str) -> str:
    return f'{DatabaseContext.get()}:{key}'
