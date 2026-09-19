# Django Multi-Tenant API Boilerplate

A small Django 5.2 and Django REST Framework starter with email/JWT authentication, organizations, branches, memberships, tenant-scoped RBAC, Celery, and Channels. CRM, knowledge-base, and KPI applications are retained as optional examples and are disabled by default.

## Prerequisites

- Python 3.11+
- PostgreSQL
- Redis

The project intentionally does not manage these services or require Docker.

## Start locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/development.txt
cp .env.example .env
createdb boilerplate
python manage.py migrate
python manage.py seed_permissions
python manage.py createsuperuser
python manage.py runserver
```

Start background processes only when the project uses them:

```bash
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info
daphne config.asgi:application
```

The liveness and dependency endpoints are `/health/` and `/ready/`. API routes are under `/api/v1/`; Django admin is under `/admin/`.

## First organization

Create the first organization as a superuser in Django admin or `POST /api/v1/organizations/`. Create an organization role, assign the required permissions created by `seed_permissions`, and add users through organization memberships. Users receive tenant permissions only from their active organization membership's role.

## Tests and production checks

```bash
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test
DJANGO_SETTINGS_MODULE=config.settings.production \
SECRET_KEY='replace-this' \
ALLOWED_HOSTS='api.example.com' \
CORS_ALLOWED_ORIGINS='https://app.example.com' \
DATABASE_URL='postgresql://user:password@localhost/database' \
python manage.py check --deploy
```

Production must use `config.settings.production`. Configure all values described in `.env.example`, terminate TLS at the application or trusted proxy, and run migrations plus `collectstatic` during deployment.

## Customize after cloning

1. Rename the repository and update the title in this README.
2. Replace example domains, database credentials, email sender, allowed hosts, and browser origins in `.env`.
3. Keep `config` as the conventional Django package, or rename it consistently in `manage.py`, WSGI, ASGI, and Celery entrypoints.
4. Remove unused optional apps or enable selected examples using [the optional-app guide](docs/optional-apps.md).
5. Add project-specific resources and permissions through an idempotent seed command.

See [architecture](docs/architecture.md) and [extension guide](docs/extending.md) before adding tenant-owned data.
