import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
BASE_DIR = Path(__file__).resolve().parent.parent
APP_MODE = os.environ.get('APP_MODE', 'production')
DEV = APP_MODE == 'development'
PRIVATE_STORAGE_CONFIRMED = os.environ.get('PRIVATE_STORAGE_CONFIRMED','')=='true'
REAL_MATERIALS_ENABLED = os.environ.get('REAL_MATERIALS_ENABLED','')=='true'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if not DEV: raise ImproperlyConfigured('DJANGO_SECRET_KEY is required')
    SECRET_KEY = 'synthetic-development-only-do-not-deploy'
DEBUG = False
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
INSTALLED_APPS = ['django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','django.contrib.admin','portal']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','whitenoise.middleware.WhiteNoiseMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','portal.middleware.AccessMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
DATA_DIR = Path(os.environ.get('DATA_DIR', BASE_DIR / 'runtime'))
DATA_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
DATABASES = {'default':{'ENGINE':'django.db.backends.sqlite3','NAME':DATA_DIR/'portal.sqlite3','OPTIONS':{'timeout':30}}}
MEDIA_ROOT = DATA_DIR/'private'
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR/'runtime/static'
LANGUAGE_CODE = 'ko-kr'
TIME_ZONE = 'Asia/Seoul'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEV
CSRF_COOKIE_SECURE = not DEV
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 3600
SESSION_SAVE_EVERY_REQUEST = False
SECURE_SSL_REDIRECT = not DEV
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_TRUSTED_ORIGINS = [x for x in os.environ.get('CSRF_TRUSTED_ORIGINS','').split(',') if x]
SECURE_HSTS_SECONDS = 31536000 if not DEV else 0
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
OPERATOR_NAME = os.environ.get('OPERATOR_NAME','')
OPERATOR_CONTACT = os.environ.get('OPERATOR_CONTACT','')
SMS_API_KEY = os.environ.get('SMS_API_KEY','')
SMS_API_SECRET = os.environ.get('SMS_API_SECRET','')
SMS_SENDER = os.environ.get('SMS_SENDER','')
import json
try:
    ADMIN_MFA_SECRETS = json.loads(os.environ.get('ADMIN_MFA_SECRETS','{}'))
except ValueError:
    raise ImproperlyConfigured('ADMIN_MFA_SECRETS must be a JSON object')
if not isinstance(ADMIN_MFA_SECRETS, dict): raise ImproperlyConfigured('ADMIN_MFA_SECRETS must be a JSON object')
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
FILE_UPLOAD_PERMISSIONS = 0o600
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o700
AUTH_PASSWORD_VALIDATORS = [{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'}]
