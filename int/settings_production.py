# настройки окружения PRODUCTION

from .settings import *

from pika import PlainCredentials

load_dotenv(BASE_DIR / 'int/management/envs/.env.production')

ENV = 'PROD'
DEBUG = False
TEMPLATES[0]['OPTIONS']['debug'] = False

SERVER_DOMAIN = 'int.template_project.space'

ALLOWED_HOSTS = ('web', 'localhost', '127.0.0.1', SERVER_DOMAIN)

# Хранить сессии в кеше джанго (редис)
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'

WSGI_APPLICATION = 'int.wsgi_production.application'
ASGI_APPLICATION = 'int.asgi_production.application'

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
                'min_size': 1,
                'max_size': 5,
                'timeout': 10,
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
                'min_size': 1,
                'max_size': 5,
                'timeout': 10,
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
                'min_size': 1,
                'max_size': 5,
                'timeout': 10,
            }
        }
    },
    'organization_3': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'template_project_organization_3',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': 'pgdb',
        'PORT': 5432,
        'OPTIONS': {
            'pool': {
                'min_size': 1,
                'max_size': 5,
                'timeout': 10,
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
    'connection_attempts': 3,  # Попытки переподключения
    'retry_delay': 5,  # Задержка между попытками
}
DRAMATIQ_BROKER['MIDDLEWARE'].append('int.management.dramatiq_middlewares.CloseConnectionAfterEnqueue')

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
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', 'access_key_id')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', 'secret_access_key')
AWS_S3_ENDPOINT_URL = 'https://s3.twcstorage.ru'
AWS_S3_URL_PROTOCOL = 'https:'
AWS_S3_CUSTOM_DOMAIN = SERVER_DOMAIN
AWS_S3_USE_SSL = True
AWS_S3_REGION_NAME = 'ru-1'
AWS_QUERYSTRING_AUTH = True

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
