from .base import *  # noqa: F403

DEBUG = env.bool("DEBUG", default=True)  # noqa: F405
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])  # noqa: F405
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=False)  # noqa: F405
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=False)  # noqa: F405
