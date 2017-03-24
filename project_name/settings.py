# Django settings for central project.
from os import path
import os

PROJECT_ROOT = path.dirname(path.abspath(path.dirname(__file__)))

# This will mainly change the behaviour from debug or not, debug = true should be local dev only
# since it will use SQLite
env_debug = os.environ.get("DEBUG", None)
# Need to know if deployed behind a balancer so proxy settings can be configured
env_load_balancer = os.environ.get("LOAD_BALANCER", None)
env_production = os.environ.get("PRODUCTION", None)

if env_debug is not None:
    DEBUG = env_debug == "True"
else:
    DEBUG = True

LOAD_BALANCER = env_load_balancer == "True"
PRODUCTION = env_production == "True"

if not PRODUCTION:

    ALLOWED_HOSTS = ['*']
    CORS_ORIGIN_ALLOW_ALL = True

else:

    ALLOWED_HOSTS = ['localhost']
    CORS_ORIGIN_ALLOW_ALL = False
    CORS_ORIGIN_WHITELIST = ()
    SESSION_COOKIE_SECURE = True

CORS_URLS_REGEX = r'^/api/.*$'

if LOAD_BALANCER:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Note: View critical settings at the bottom of the file. More env vars are used there.

# ------------------------------------------ Standard django settings -------------------------------------------------

DATA_UPLOAD_MAX_NUMBER_FIELDS = 15000
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

# Password validators.
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
        'OPTIONS': {
            'user_attributes': {'email'}

        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 6,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)
MANAGERS = ADMINS

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en'

SITE_ID = 1

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        # 'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'cache',
        'TIMEOUT': 60
    }
}

# Set any special view you want for CSRF, some times it is useful to create a new one to handle ajax requests
# CSRF_FAILURE_VIEW = "app.controllers.mycsrfview"

# This needs to be the administrator model in order for the admin site to work
# Unless we want to skip django authentication completely and implement our own.
# Should not be an issue with the rest API
AUTH_USER_MODEL = 'administration.Administrator'  # to use custom user model.

# Maximo largo de un file upload en memoria hasta que se pase a disco en bytes
# FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760

# Default controller to call on login redirect
LOGIN_URL = 'administration.controllers.home.index'

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
TIME_ZONE = "UTC"

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = ''

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = path.join(PROJECT_ROOT, 'static').replace('\\', '/')

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    #    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Use cached loader if not debuging.
if DEBUG:
    _loaders = [
        # ('django.template.loaders.cached.Loader', (
        #    'django.template.loaders.filesystem.Loader',
        #    'django.template.loaders.app_directories.Loader',
        # ))
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    ]
else:
    _loaders = [
        ('django.template.loaders.cached.Loader', (
            'django.template.loaders.filesystem.Loader',
            'django.template.loaders.app_directories.Loader',
        ))
    ]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'OPTIONS': {
            'debug': DEBUG,
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
            'loaders': _loaders
        }
    },
]

_middlewares = (
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # Needed for cors requests to the api
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'administration.middlewares.exception_handler.ExceptionMiddleware',
    'core.middlewares.locale_middleware.LocaleMiddleware',
)

MIDDLEWARE = _middlewares

# Importante, debe apuntar al archivo maestro de urls.
ROOT_URLCONF = 'project_name.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'project_name.wsgi.application'

# All apps can be installed regardless of deploy. Base urls.py file will handle the rest.
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'rest_framework',
    'clients',
    'logs_app',
    'administration',
    'corsheaders',
    'jsoneditor'
]

if not PRODUCTION:
    INSTALLED_APPS.append('rest_framework_swagger')

PASSWORD_HASHERS = (
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.SHA1PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptPasswordHasher',
    'django.contrib.auth.hashers.MD5PasswordHasher',
    'django.contrib.auth.hashers.CryptPasswordHasher',
)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {

        'verbose': {
            'format': "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
            'datefmt': "%Y-%m-%d %H:%M:%S"
        },
        'onlyMessage': {
            'format': "%(message)s",
            'datefmt': "%Y-%m-%d %H:%M:%S"
        },

    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'core.loggers.ConsoleLogger',
            'formatter': 'verbose',

        },
        'centralErrors': {
            'level': 'DEBUG',
            'class': 'core.loggers.CentralErrorLogger',
            'formatter': 'onlyMessage',

        }
    },
    'loggers': {

        # Base root loggers
        'django': {
            'handlers': ['console', 'centralErrors'],
            'propagate': True,
            'level': 'ERROR',  # Django debug is way too verbose
        },
        'django.server': {
            'handlers': ['console'],
            'level': 'INFO' if DEBUG else 'ERROR',  # Django server debugger, do not log to DB
            'propagate': False,
        },
        'administration': {
            'handlers': ['console', 'centralErrors'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'clients': {
            'handlers': ['console', 'centralErrors'],
            'propagate': True,
            'level': 'DEBUG',
        },

        # administration logging

        'administration.site.auth': {
            'handlers': ['console', 'centralErrors'],
            'propagate': False,
            'level': 'DEBUG',
        },

        'administration.site.others': {
            'handlers': ['console', 'centralErrors'],
            'propagate': False,
            'level': 'DEBUG',
        },

        # storages logging
        'storages.s3': {
            'handlers': ['console', 'centralErrors'],
            'propagate': False,
            'level': 'DEBUG',
        },

        # Email
        'email.sending': {
            'handlers': ['console', 'centralErrors'],
            'propagate': False,
            'level': 'DEBUG',
        },

        # api logging
        'clients.api.auth': {
            'handlers': ['console', 'centralErrors'],
            'propagate': False,
            'level': 'DEBUG',
        },

        'clients.api.validation': {
            'handlers': ['console', 'centralErrors'],
            'propagate': False,
            'level': 'DEBUG',
        },

        'clients.api.data': {
            'handlers': ['console', 'centralErrors'],
            'propagate': False,
            'level': 'DEBUG',
        },

        'clients.api.throttled': {
            'handlers': ['console', 'centralErrors'],
            'propagate': False,
            'level': 'DEBUG',
        },

        'clients.api.others': {
            'handlers': ['console', 'centralErrors'],
            'propagate': False,
            'level': 'DEBUG',
        },

    }
}

LOCALE_PATHS = (
    "./locale/",
)

REST_FRAMEWORK = {

    'UNICODE_JSON': False,  # This greatly improves json serialization performance in python 2.7.x

    # With value of 1 always get the latest IP in the X-Forwarded-For header as that's the one added by the load
    # balancer. When not behind a load balancer, this value should be 0
    # RIGHT NOW: No load balancer, IT IS CRITICAL TO SET IT TO 1 when using a load balancer.
    'NUM_PROXIES': 0 if not LOAD_BALANCER else 1,

    'DEFAULT_PARSER_CLASSES': (
        'clients.custom_parsers.LimitedJSONParser',
        'clients.custom_parsers.LimitedFormParser',
        'rest_framework.parsers.MultiPartParser',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'clients.custom_renderers.FasterJSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',  # browsable api

    ),

    # No authentication required by default, will be set depending on service
    'DEFAULT_AUTHENTICATION_CLASSES': (
        # 'rest_framework.authentication.BasicAuthentication', #for testing purposes
        # 'clients.auth.token.JWTAuthentication',


    ),
    'NON_FIELD_ERRORS_KEY': '__all__',
    # Error key to be used for non field validation errors, make it match django's one.

    'EXCEPTION_HANDLER': 'clients.api.exception_handler.custom_exception_handler'
}

# ------------------------ Keys and external settings ----------------------------

# This will handle how many threads are used for each system thread pool
# Keep a low value otherwise the database will start to fail due to a huge amount of connections
# This is only a factor/multipler and not the real value
THREAD_POOL_SIZE_FACTOR = int(os.environ.get("THREAD_POOL_SIZE_FACTOR", 1))

# Make this unique, and don't share it with anybody.
# This secret key is very important and used by django framework in many places.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", 'n(bd1f1c%e8=_xad02x5qtfn%wgwpi492e$8_erx+d)!tpeoim')

# Secret key usen for password recovery
RESET_TOKEN_SECRET_KEY = os.environ.get("RESET_TOKEN_SECRET_KEY", '=6hzo8&4zued@bj11=k4n^&22d^r^l^nko05=z6+@ar5fx5(-q')

# Database settings
if not DEBUG:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
            'NAME': os.environ.get("CENTRAL_DB_NAME", ''),
            'USER': os.environ.get("CENTRAL_DB_USER", ''),
            'PASSWORD': os.environ.get("CENTRAL_DB_PW", ''),
            'HOST': os.environ.get("CENTRAL_DB_HOST", ''),
            'PORT': os.environ.get("CENTRAL_DB_PORT", '5432'),
            'CONN_MAX_AGE': 60 * 2
        }
    }

else:
    DATABASES = {

        'default': {
            'ENGINE': 'django.db.backends.sqlite3',  # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
            'NAME': path.join(PROJECT_ROOT, 'db.sqlite3'),  # Or path to database file if using sqlite3.
            'USER': '',  # Not used with sqlite3.
            'PASSWORD': '',  # Not used with sqlite3.
            'HOST': '',  # Set to empty string for localhost. Not used with sqlite3.
            'PORT': '',  # Set to empty string for default. Not used with sqlite3.
            'CONN_MAX_AGE': 60 * 2  # Database connection age in seconds, to allow connection pooling
        }
    }

# Email settings
EMAIL_HOST = os.environ.get("EMAIL_HOST", 'email-smtp.us-west-2.amazonaws.com')
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", 'xx')
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", 'xx')
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", 'xx')
SERVER_EMAIL = DEFAULT_FROM_EMAIL
EMAIL_USE_TLS = True

# AWS settings
AWS_KEY = os.environ.get("AWS_KEY", "")
AWS_SECRET = os.environ.get("AWS_SECRET", "")
S3_UPLOAD_BUCKET = os.environ.get("S3_UPLOAD_BUCKET", "")
S3_UPLOAD_PREFIX = os.environ.get("S3_UPLOAD_PREFIX", "")
SES_REGION = os.environ.get("SES_REGION", 'us-west-2')
