"""
Django settings for recommender_ai_service.
Used ONLY for ORM (interaction tracking DB).
FastAPI handles HTTP via main.py / uvicorn.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-ai-service-key-change-in-prod')
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'app',
]

MIDDLEWARE = []

ROOT_URLCONF = 'recommender_ai_service.urls'
WSGI_APPLICATION = 'recommender_ai_service.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE':   'django.db.backends.postgresql',
        'NAME':     os.getenv('POSTGRES_DB',       os.getenv('DB_NAME',     'bookstore_recommender')),
        'USER':     os.getenv('POSTGRES_USER',     os.getenv('DB_USER',     'postgres')),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', os.getenv('DB_PASSWORD', 'root')),
        'HOST':     os.getenv('DB_HOST',           'db-postgres'),
        'PORT':     os.getenv('DB_PORT',           '5432'),
    }
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = False
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
