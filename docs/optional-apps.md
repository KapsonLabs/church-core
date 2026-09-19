# Optional example apps

The CRM, info, and KPI apps are disabled by default. Their models, migrations, routes, commands, and service code are examples rather than core contracts.

## Enable an app

1. Add its dotted name to `INSTALLED_APPS` in the selected settings file:

   ```python
   INSTALLED_APPS += ["apps.info"]
   ```

2. Add its versioned route to `config/urls.py`:

   ```python
   path("api/v1/info/", include("apps.info.urls")),
   ```

3. Run `python manage.py migrate` and the app's seed command.
4. Add the app's resource/action permissions to a role before calling its endpoints.

For CRM WebSockets, replace the core ASGI application with a `ProtocolTypeRouter` that mounts `apps.crm.routing.websocket_urlpatterns` behind authenticated origin validation. Do this only when CRM is installed. KPI tasks are discovered by Celery only when `apps.kpis` is installed.

## Example-specific setup

- **CRM:** ticketing, messaging, notifications, and WebSockets. Run `python manage.py seed_crm_examples`. Its tenant root is `Ticket.branch.organization`.
- **Info:** Organization-scoped FAQs, SOPs, policies, and training content. Run `python manage.py seed_info_permissions` and `python manage.py load_info_data --organization-id <uuid>`.
- **KPI:** definitions, assignments, reports, aggregation tasks, and a formula DSL. Run `python manage.py seed_kpi_permissions` and `python manage.py generate_kpi_sample_data --help`; sample data requires an organization, branch, users, and roles.

Treat example seed data as development-only. Copy an app into product code only after retaining its organization-scoped queryset and permission tests.
