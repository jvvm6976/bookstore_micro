import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-)r^!p54gyy^usmz727wv%*cw)+zt)1^e3%nfcq^r$eq@(pl26&'
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'app',
    'rest_framework',
    'corsheaders',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CORS_ALLOW_ALL_ORIGINS = True
ROOT_URLCONF = 'user_service_config.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]

WSGI_APPLICATION = 'user_service_config.wsgi.application'

import pymysql
pymysql.install_as_MySQLdb()

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME', 'ecommerce_user'),
        'USER': os.getenv('DB_USER', 'root'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'root'),
        'HOST': os.getenv('DB_HOST', 'db-mysql'),
        'PORT': os.getenv('DB_PORT', '3306'),
    }
}

AUTH_USER_MODEL = 'app.User'
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['app.authentication.CustomJWTAuthentication'],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
}

JWT_SECRET = os.getenv('JWT_SECRET', SECRET_KEY)
JWT_ACCESS_MINUTES = int(os.getenv('JWT_ACCESS_MINUTES', 60))
JWT_REFRESH_DAYS = int(os.getenv('JWT_REFRESH_DAYS', 7))

# rest_framework_simplejwt configuration
SIMPLE_JWT = {
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': os.getenv('JWT_SECRET', SECRET_KEY),
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=JWT_ACCESS_MINUTES),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=JWT_REFRESH_DAYS),
}
