# designed by mew
"""Small-server defaults. Secrets, database, uploads and logs live outside releases."""

import os
import secrets
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("LAB_DATA_DIR", BASE_DIR / "var")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DEBUG = os.environ.get("LAB_ENV", "development") != "production"
SECRET_KEY = os.environ.get("LAB_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("Production requires LAB_SECRET_KEY.")
    keyfile = DATA_DIR / ".development-secret"
    if not keyfile.exists():
        keyfile.write_text(secrets.token_urlsafe(64))
        keyfile.chmod(0o600)
    SECRET_KEY = keyfile.read_text().strip()
ALLOWED_HOSTS = os.environ.get("LAB_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver").split(",")
CSRF_TRUSTED_ORIGINS = [
    u
    for u in os.environ.get(
        "LAB_CSRF_ORIGINS", "http://127.0.0.1:4173,http://localhost:4173"
    ).split(",")
    if u
]
INSTALLED_APPS = [
    "cms.apps.CmsConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "axes",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "lab.sqlite3",
        "OPTIONS": {"timeout": 30, "transaction_mode": "IMMEDIATE"},
    }
}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]
# Nginx must replace forwarding headers and connect over loopback.
AXES_CLIENT_IP_CALLABLE = "cms.authentication.client_ip"
AXES_RESET_ON_SUCCESS = True
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True
MEDIA_URL = "/media/"
MEDIA_ROOT = DATA_DIR / "media"
FRONTEND_DIR = BASE_DIR / "frontend" / "dist"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
SECURE_CONTENT_TYPE_NOSNIFF = True
if not DEBUG:
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False
