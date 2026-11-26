# настройки окружения STAGE

from .settings import *

from pika import PlainCredentials

ENV = 'STAGE'

SERVER_DOMAIN = 'repairservice.flyawaymaking.ru'

ALLOWED_HOSTS = ('web', 'localhost', '127.0.0.1', '192.168.0.120', SERVER_DOMAIN)

if DEBUG:
    CSRF_TRUSTED_ORIGINS = [
        "https://repairservice.flyawaymaking.ru",
        "https://repairservice.flyawaymaking.ru:8443",
        "https://192.168.0.120",
        "https://192.168.0.120:8443",
    ]
    # INSTALLED_APPS += [
    #     'debug_toolbar',
    # ]
    #
    # MIDDLEWARE = [
    #                  'debug_toolbar.middleware.DebugToolbarMiddleware',
    #              ] + MIDDLEWARE
    #
    # import socket
    #
    # hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    #
    # INTERNAL_IPS = ['127.0.0.1'] + [ip.rsplit('.', 1)[0] + '.1' for ip in ips]
    #
    # DEBUG_TOOLBAR_CONFIG = {
    #     "SHOW_TOOLBAR_CALLBACK": lambda request: True,
    # }

# Хранить сессии в кеше джанго (редис)
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'

WSGI_APPLICATION = 'int.wsgi_stage.application'
ASGI_APPLICATION = 'int.asgi_stage.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'template_project_default',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': 'pgdb',
        'PORT': 5432,
        'OPTIONS': {
            'pool': {
                'min_size': 2,
                'max_size': 20,
                'timeout': 30,
            }
        }
    },
    'organization_1': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'template_project_organization_1',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': 'pgdb',
        'PORT': 5432,
        'OPTIONS': {
            'pool': {
                'min_size': 2,
                'max_size': 20,
                'timeout': 30,
            }
        }
    },
    'organization_2': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'template_project_organization_2',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': 'pgdb',
        'PORT': 5432,
        'OPTIONS': {
            'pool': {
                'min_size': 2,
                'max_size': 20,
                'timeout': 30,
            }
        }
    },
}

STORAGES = {
    'default': {
        'BACKEND': 'int.management.storage_backends.MediaStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage',
    },
}

DRAMATIQ_BROKER['BROKER'] = 'dramatiq.brokers.rabbitmq.RabbitmqBroker'
DRAMATIQ_BROKER['OPTIONS'] = {
    'host': 'rabbitmq',
    'port': 5672,
    'credentials': PlainCredentials('rmq_admin', 'rmq_admin'),
    'heartbeat': 10 * 60,  # sec
    'virtual_host': '/',
}

DRAMATIQ_RESULT_BACKEND['BACKEND'] = 'dramatiq.results.backends.RedisBackend'
DRAMATIQ_RESULT_BACKEND['BACKEND_OPTIONS'] = {'url': 'redis://redis:6379/15'}

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://redis:6379/14',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 1000
            }
        },
    },
}

# Настройки S3
AWS_ACCESS_KEY_ID = 'minioadmin'
AWS_SECRET_ACCESS_KEY = 'minioadmin'
AWS_S3_ENDPOINT_URL = 'http://minio:9000/'
AWS_S3_URL_PROTOCOL = 'http:'
AWS_S3_CUSTOM_DOMAIN = SERVER_DOMAIN
AWS_S3_USE_SSL = False  # Для MinIO без SSL
AWS_QUERYSTRING_AUTH = True

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
