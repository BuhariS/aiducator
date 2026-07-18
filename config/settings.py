from pathlib import Path
import os

import dj_database_url
import environ


BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(BASE_DIR / ".env")
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "local-development-only")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    return int(os.environ.get(name, default))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "dashboard.apps.DashboardConfig",
    "organizations",
    "courses",
    "enrollments",
    "assessments",
    "ai_engine",
    "gamification",
    "notifications",
    "analytics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=env_int("DB_CONN_MAX_AGE", 600),
        ssl_require=env_bool("DB_SSL_REQUIRE", False),
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-ng"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE", 60 * 60 * 8)
SESSION_EXPIRE_AT_BROWSER_CLOSE = env_bool("SESSION_EXPIRE_AT_BROWSER_CLOSE", False)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", not DEBUG)
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 0 if DEBUG else 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

PASSWORD_RESET_TIMEOUT = env_int("PASSWORD_RESET_TIMEOUT", 3600)
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "AIDUCATOR <no-reply@aiducator.local>")

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_ALWAYS_EAGER = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "0") == "1"
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_TRACK_STARTED = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE

STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "filesystem").lower()
MEDIA_URL = os.environ.get("MEDIA_URL", "/media/")
MEDIA_ROOT = BASE_DIR / "media"
if STORAGE_BACKEND == "s3":
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": os.environ.get("AWS_STORAGE_BUCKET_NAME", ""),
                "region_name": os.environ.get("AWS_S3_REGION_NAME", ""),
                "endpoint_url": os.environ.get("AWS_S3_ENDPOINT_URL") or None,
                "querystring_auth": env_bool("AWS_QUERYSTRING_AUTH", False),
                "file_overwrite": False,
            },
        },
        "staticfiles": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": os.environ.get("AWS_STATIC_BUCKET_NAME", ""),
                "region_name": os.environ.get("AWS_S3_REGION_NAME", ""),
                "endpoint_url": os.environ.get("AWS_S3_ENDPOINT_URL") or None,
                "querystring_auth": False,
            },
        },
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

AI_LLM_PROVIDER = os.environ.get("AI_LLM_PROVIDER", "fake")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "")
AI_PROMPT_VERSION = os.environ.get("AI_PROMPT_VERSION", "grading-v1")
AI_COURSE_PROMPT_VERSION = os.environ.get("AI_COURSE_PROMPT_VERSION", "course-generation-v1")
AI_INPUT_COST_PER_1K = os.environ.get("AI_INPUT_COST_PER_1K", "0")
AI_OUTPUT_COST_PER_1K = os.environ.get("AI_OUTPUT_COST_PER_1K", "0")

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "application": {
            "format": "{asctime} {levelname} {name} request={request_id} {message}",
            "style": "{",
            "defaults": {"request_id": "-"},
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "application"},
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "aiducator": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}
