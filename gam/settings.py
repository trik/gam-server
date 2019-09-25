import os
import sys

from datetime import timedelta

DEBUG = True

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

APP_NAME = 'gam'
DATABASE_URL = 'postgresql://gam:gam@localhost/gam'
SECRET_KEY = 'yj9)%373b%ckd-_ytzv8tp=+%-c-2a9++50rzcz2swb=f1@r)2'
JWT_EXPIRATION_DELTA = 24 * 60 * 60

ALLOWED_ORIGINS = [
    'http://localhost:4200',
    
    ## swagger on docker
    'http://localhost:999',

    ## ionic dev server
    'http://localhost:8100',
]

I18N_ASSETS_PATH = os.path.join(BASE_DIR, 'assets', 'i18n')

CELERY_BROKER = 'pyamqp://guest@localhost//'
ONLINE_TIME_SPAN = timedelta(seconds=5 * 60)

print('Trying to import local config')
try:
    from .settings_local import *
    print('Local config loaded')
except ImportError:
    print('No local config found')

if 'pytest' in sys.modules:
    from .settings_test import *
    print('Test config loaded')
