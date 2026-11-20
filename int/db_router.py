from int.db_context import DatabaseContext


class ZoneRouter:
    AUTH_APPS = {
        'identity',

        'admin',
        'auth',
        'contenttypes',
        'sessions',

        'captcha',

        'django_dramatiq',
    }
    DEFAULT_MODELS = {'notifications.notificationconnectcode', 'notifications.notificationmessage',
                      'promoter_app.promoterzone'}

    def db_for_read(self, model, **hints):
        app = model._meta.app_label
        model_name = model.__name__.lower()
        if app in self.AUTH_APPS or f'{app}.{model_name}' in self.DEFAULT_MODELS:
            return 'default'

        return DatabaseContext.get()

    def db_for_write(self, model, **hints):
        app = model._meta.app_label
        model_name = model.__name__.lower()
        if app in self.AUTH_APPS or f'{app}.{model_name}' in self.DEFAULT_MODELS:
            return 'default'

        return DatabaseContext.get()

    def allow_relation(self, obj1, obj2, **hints):
        if obj1._state.db == obj2._state.db:
            return True

        return False

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in self.AUTH_APPS or f'{app_label}.{model_name}' in self.DEFAULT_MODELS:
            return db == 'default'

        return db != 'default'
