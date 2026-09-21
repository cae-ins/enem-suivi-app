from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parents[3]


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-development-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,api,testserver")
INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "corsheaders", "rest_framework", "drf_spectacular", "web.backend.files",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware", "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "web.backend.config.urls"
WSGI_APPLICATION = "web.backend.config.wsgi.application"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request", "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql", "NAME": os.getenv("POSTGRES_DB", "enem_suivi"),
    "USER": os.getenv("POSTGRES_USER", "enem_app"), "PASSWORD": os.getenv("POSTGRES_PASSWORD", "enem-local-only"),
    "HOST": os.getenv("POSTGRES_HOST", "postgres"), "PORT": os.getenv("POSTGRES_PORT", "5432"), "CONN_MAX_AGE": 60,
}}
if env_bool("DJANGO_USE_SQLITE", False):
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "test-web.sqlite3"}}
elif database_url := os.getenv("DATABASE_URL"):
    parsed = urlparse(database_url)
    DATABASES["default"].update(NAME=parsed.path.lstrip("/"), USER=parsed.username, PASSWORD=parsed.password,
                                HOST=parsed.hostname, PORT=parsed.port or 5432)

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Abidjan"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CORS_ALLOWED_ORIGINS = env_list("CORS_ORIGINS", "http://localhost:4200,http://localhost:8080")
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
}
SPECTACULAR_SETTINGS = {"TITLE": "ENEM Suivi API", "VERSION": "0.1.0"}
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_PUBLIC_ENDPOINT = os.getenv("MINIO_PUBLIC_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "enem-local")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "enem-local-only")
MINIO_SECURE = env_bool("MINIO_SECURE", False)
MINIO_INPUT_BUCKET = os.getenv("MINIO_INPUT_BUCKET", "enem-entrees")
MINIO_REFERENCE_BUCKET = os.getenv("MINIO_REFERENCE_BUCKET", "enem-references")
MINIO_OUTPUT_BUCKET = os.getenv("MINIO_OUTPUT_BUCKET", "enem-resultats")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TASK_TRACK_STARTED = True

if not DEBUG and (
    SECRET_KEY == "unsafe-development-key-change-me"
    or DATABASES["default"].get("PASSWORD") == "enem-local-only"
    or MINIO_SECRET_KEY == "enem-local-only"
):
    raise ImproperlyConfigured("Les secrets de developpement sont interdits lorsque DJANGO_DEBUG=false")
