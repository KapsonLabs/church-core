from django.db import connections
from django.db.utils import OperationalError
from django.http import JsonResponse
from redis import Redis
from redis.exceptions import RedisError
from django.conf import settings


def health(_request):
    return JsonResponse({"status": "ok"})


def readiness(_request):
    dependencies = {"database": "ok", "redis": "ok"}
    try:
        connections["default"].cursor().execute("SELECT 1")
    except OperationalError:
        dependencies["database"] = "unavailable"
    try:
        Redis.from_url(settings.REDIS_URL).ping()
    except RedisError:
        dependencies["redis"] = "unavailable"
    ready = all(value == "ok" for value in dependencies.values())
    return JsonResponse(
        {"status": "ok" if ready else "unavailable", "dependencies": dependencies},
        status=200 if ready else 503,
    )
