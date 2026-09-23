"""
Django settings for the Book AI RAG backend.

All secrets and environment-specific values come from environment variables
(optionally loaded from a `.env` file). Nothing sensitive is hard-coded here.
"""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BASE_DIR.parent

env = environ.Env(
    DEBUG=(bool, False),
    RAG_TOP_K=(int, 6),
    RAG_SIMILARITY_THRESHOLD=(float, 0.78),
    CHUNK_SIZE=(int, 800),
    CHUNK_OVERLAP=(int, 150),
    MAX_PDF_SIZE_MB=(int, 100),
    CHAT_HISTORY_MESSAGES=(int, 8),
    EMBEDDING_BATCH_SIZE=(int, 32),
    EMBEDDING_PRELOAD=(bool, False),
    MYSQL_PORT=(int, 3306),
    QDRANT_PORT=(int, 6333),
)

# Load a .env file if present: backend/.env (local overrides) first, then the
# repo-root .env used by docker-compose. Real environment variables always win.
for _candidate in (BASE_DIR / ".env", REPO_DIR / ".env"):
    if _candidate.exists():
        environ.Env.read_env(str(_candidate))
        break

SECRET_KEY = env("DJANGO_SECRET_KEY", default="unsafe-dev-secret-key-change-me")
DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])

FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:5173")

# ------------------------------------------------------------------------------
# Applications
# ------------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third party
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "drf_spectacular",
    # local
    "apps.accounts",
    "apps.documents",
    "apps.rag",
    "apps.chats",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

# ------------------------------------------------------------------------------
# Database — MySQL only (no PostgreSQL / pgvector)
# ------------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("MYSQL_DATABASE", default="bookai"),
        "USER": env("MYSQL_USER", default="bookai"),
        "PASSWORD": env("MYSQL_PASSWORD", default=""),
        "HOST": env("MYSQL_HOST", default="mysql"),
        "PORT": env("MYSQL_PORT"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        "TEST": {
            "CHARSET": "utf8mb4",
            "COLLATION": "utf8mb4_unicode_ci",
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ------------------------------------------------------------------------------
# I18N / static / media
# ------------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", default=str(BASE_DIR / "media")))

MAX_PDF_SIZE_MB = env("MAX_PDF_SIZE_MB")
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_PDF_SIZE_MB * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# ------------------------------------------------------------------------------
# REST framework / JWT / OpenAPI
# ------------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": "config.exceptions.api_exception_handler",
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    )
    if DEBUG
    else ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.UserRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {"user": env("API_THROTTLE_RATE", default="600/min")},
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_MINUTES", default=60)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_DAYS", default=7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Book AI — Document-grounded RAG API",
    "DESCRIPTION": (
        "Upload PDF books and chat with them. Answers are grounded strictly in the "
        "selected document; sources (page numbers + excerpts) are produced by the backend."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[FRONTEND_URL])
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# ------------------------------------------------------------------------------
# Celery / Redis
# ------------------------------------------------------------------------------

REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)

# ------------------------------------------------------------------------------
# Qdrant (vectors only)
# ------------------------------------------------------------------------------

QDRANT_HOST = env("QDRANT_HOST", default="qdrant")
QDRANT_PORT = env("QDRANT_PORT")
QDRANT_API_KEY = env("QDRANT_API_KEY", default=None)
QDRANT_COLLECTION = env("QDRANT_COLLECTION", default="document_chunks")

# ------------------------------------------------------------------------------
# Embeddings / RAG / LLM
# ------------------------------------------------------------------------------

EMBEDDING_MODEL = env("EMBEDDING_MODEL", default="intfloat/multilingual-e5-base")
EMBEDDING_BATCH_SIZE = env("EMBEDDING_BATCH_SIZE")
EMBEDDING_PRELOAD = env("EMBEDDING_PRELOAD")

RAG_TOP_K = env("RAG_TOP_K")
RAG_SIMILARITY_THRESHOLD = env("RAG_SIMILARITY_THRESHOLD")
CHUNK_SIZE = env("CHUNK_SIZE")  # measured in characters (~200 tokens), see README
CHUNK_OVERLAP = env("CHUNK_OVERLAP")
CHAT_HISTORY_MESSAGES = env("CHAT_HISTORY_MESSAGES")
RAG_NOT_FOUND_ANSWER = "Bu ma'lumot yuklangan kitobda topilmadi."

# The Gemini key is read ONLY from the environment. It is never logged or
# returned by any API endpoint.
GEMINI_API_KEY = env("GEMINI_API_KEY", default="")
GEMINI_MODEL = env("GEMINI_MODEL", default="gemini-2.5-flash")
LLM_PROVIDER = env("LLM_PROVIDER", default="gemini")

# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------

_LOG_LEVEL = env("LOG_LEVEL", default="INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": _LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": _LOG_LEVEL, "propagate": False},
        # Model-download HTTP chatter is not useful at INFO.
        "httpx": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "httpcore": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "huggingface_hub": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "sentence_transformers": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
