# Children's Church module

`apps.church` manages branch-specific children, age groups, events, Sunday service sessions, facilitators and attendance. It uses the existing account, organization, branch membership and permission models; facilitators do not have a separate login system.

## Domain and attendance rules

- Every root record belongs to one organization and one branch. Non-superusers need active organization and branch memberships.
- `Event` represents the overall activity. A Sunday event contains ordered `ServiceSession` records, so each service is tracked independently.
- Child attendance may target an ordinary event or a Sunday service session. Present and late count as attended; excused is excluded from the attendance-rate denominator.
- Finishing a Sunday creates event-level absent records for active children registered by that date who have no attended or excused record. Until then, missing records are unrecorded rather than absent. A later present/late record takes precedence in reports.
- Attendance stores the child's age group at recording time. Moving or deactivating a child therefore does not rewrite history.
- `ServiceFacilitator` is an assignment. `FacilitatorAttendance` separately records whether an assigned facilitator attended.

## Permissions

Run `python manage.py seed_church_permissions` to create the permission catalog. Pass `--organization <uuid-or-slug>` to also create or update that organization's `Administrator` role with every church permission and update an existing `Facilitator` role with the operational event/attendance grants. Assign roles and branch access through **Settings → User Management** and configure roles through **Settings → Permissions Management**. Facilitators receive dashboard/read permissions, `church-attendance.manage`, and `church-events.manage`; age-group and facilitator-profile management remain administrator-only.

All API calls require `organization_id` and `branch_id`. CRUD endpoints are below `/api/v1/church/` for age groups, children, events, service sessions, attendance, facilitators, assignments and facilitator attendance. Workflow endpoints include:

- `POST sunday-services/create/`
- `GET sunday-services/today/` and `upcoming/`
- `GET service-sessions/<id>/roster/`
- `POST service-sessions/<id>/attendance/bulk/`
- `GET events/<id>/roster/` and `POST events/<id>/attendance/bulk/`
- `POST events/<id>/attendance/finalize/`
- `POST service-sessions/<id>/facilitators/bulk-assign/`
- `POST service-sessions/<id>/facilitator-attendance/bulk/`
- `GET dashboard/summary/` and the endpoints below `reports/`

Common query filters include age group, active status, event type, status, event/session, attendance status, exact date and date range.

## Setup and administration

```bash
python manage.py migrate
python manage.py seed_church_permissions
python manage.py seed_church_permissions --organization <uuid-or-slug>
python manage.py seed_church_age_groups --organization <uuid> --branch <uuid>
python manage.py create_sunday_services --organization <uuid> --branch <uuid> --date 2026-10-04 \
  --service "First Service,08:00" --service "Second Service,10:00"
```

Use deactivation/cancellation instead of deleting records that participate in attendance history. Django Admin exposes all church models for inspection and correction.

## Watoto Ministries demo data

The following command creates a development-only dataset for **Watoto Ministries / DownTown**:

```bash
python manage.py seed_watoto_sample_data
```

It creates 45 children in each of the Age 9–13 groups (225 total), 12 facilitator accounts, and every elapsed Sunday in the current year with Morning, 10am, Midday and Afternoon sessions. Child attendance, facilitator assignments and facilitator attendance are deterministic and safe to seed repeatedly with the same options.

The administrator account is `admin@watotoministries.com`. Facilitator accounts use emails from `facilitator1@watotoministries.com` through `facilitator12@watotoministries.com`. Their default development password is `ChurchDemo2026!`. The administrator receives every active permission at seed time while facilitators retain their narrower operational role. Never use these shared credentials in production.

Useful overrides:

```bash
python manage.py seed_watoto_sample_data \
  --children-per-group 50 \
  --year 2026 \
  --through-date 2026-09-24 \
  --seed 2026 \
  --password 'AnotherDevelopmentPassword!' \
  --admin-email 'admin@watotoministries.com' \
  --admin-password 'AnotherAdminDevelopmentPassword!'
```

`--children-per-group` accepts 40–50. `--through-date` is inclusive, and the default is today so future attendance is not generated accidentally.

## Automatic Sundays

Celery Beat runs `apps.church.tasks.create_next_sunday_services` every Saturday at 23:59 in `Africa/Kampala`. It creates the next day's Sunday event for every active branch, cloning the latest Sunday schedule or using the four default Watoto service times. Attendance and facilitator assignments are never copied, retries are safe, and administrators retain a manual **Create Sunday** fallback in Events.

Both processes must be running:

```bash
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info
```

The frontend uses Events for ordinary events and Sunday services. Settings contains User Management, Permissions Management, Age Groups, and Attendance summaries (including absenteeism).
