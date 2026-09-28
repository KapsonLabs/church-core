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

The church module uses both the worker and Beat. Beat creates the next day's Sunday services every Saturday at 23:59 in `Africa/Kampala`.

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

## Church VPS deployment

The production script deploys directly from `/root/projects/Church`. It expects the backend at `/root/projects/Church/church-core`, the frontend at `/root/projects/Church/church-frontend`, and a committed production frontend artifact at `/root/projects/Church/church-frontend/dist/index.html`. Build the frontend with its production API URL and KingdomKids branding before committing and pushing `dist`; the server does not install Node dependencies or build the frontend.

Before the first deployment, create `church-core/.env` with production values, including a long random `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `ALLOWED_HOSTS=children.church.iolabz.ug`, `CORS_ALLOWED_ORIGINS=https://children.church.iolabz.ug`, `SESSION_COOKIE_SECURE=true`, and `CSRF_COOKIE_SECURE=true`.

```bash
SSL_EMAIL=admin@example.com sudo -E bash deploy.sh
```

The script validates and applies committed migrations, collects Django static files into `church-core/staticfiles`, keeps uploads in `church-core/media`, serves the committed frontend `dist` directory directly, configures `church.service`, `church-celery.service`, `church-celery-beat.service`, and Nginx, and obtains the Let's Encrypt certificate. It deliberately runs the application services as root because the supplied source checkout is under `/root`; moving the checkout to a dedicated service account is recommended for stronger process isolation.

The deployment does not create an administrator interactively. Create the first superuser separately:

```bash
DJANGO_SETTINGS_MODULE=config.settings.production .venv/bin/python manage.py createsuperuser
```

## Customize after cloning

1. Rename the repository and update the title in this README.
2. Replace example domains, database credentials, email sender, allowed hosts, and browser origins in `.env`.
3. Keep `config` as the conventional Django package, or rename it consistently in `manage.py`, WSGI, ASGI, and Celery entrypoints.
4. Remove unused optional apps or enable selected examples using [the optional-app guide](docs/optional-apps.md).
5. Add project-specific resources and permissions through an idempotent seed command.

See [architecture](docs/architecture.md) and [extension guide](docs/extending.md) before adding tenant-owned data.

The enabled Children's Church feature is documented in [docs/church.md](docs/church.md).
