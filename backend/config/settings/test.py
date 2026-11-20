from .base import *  # noqa: F403
from .base import env

SECRET_KEY = "test-secret-key-0123456789abcdef0123456789abcdef"
MIDDLEWARE = [m for m in MIDDLEWARE if "whitenoise" not in m]  # noqa: F405
DEBUG = False

# CI'da DATABASE_URL orqali PostgreSQL beriladi; lokal tez sinov uchun SQLite.
DATABASES = {"default": env.db("DATABASE_URL", default="sqlite://:memory:")}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
AUTH_PASSWORD_VALIDATORS = []
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CELERY_TASK_ALWAYS_EAGER = True
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {"login": "1000/min", "pin": "1000/min"},
}
