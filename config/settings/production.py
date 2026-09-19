from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False

required = {
    "SECRET_KEY": SECRET_KEY,  # noqa: F405
    "ALLOWED_HOSTS": ALLOWED_HOSTS,  # noqa: F405
    "CORS_ALLOWED_ORIGINS": CORS_ALLOWED_ORIGINS,  # noqa: F405
    "DATABASE_URL": env("DATABASE_URL", default=""),  # noqa: F405
    "REDIS_URL": env("REDIS_URL", default=""),  # noqa: F405
}
missing = [name for name, value in required.items() if not value or value == "unsafe-development-key-change-me"]
if missing:
    raise ImproperlyConfigured(
        "Missing production settings: " + ", ".join(sorted(missing))
    )

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)  # noqa: F405
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
