import logging
from datetime import date, time, timedelta

from celery import shared_task
from django.db import IntegrityError
from django.utils import timezone

from apps.organization.models import Branch

from .models import Event
from .services import create_sunday_services


logger = logging.getLogger(__name__)

DEFAULT_SESSIONS = [
    {"service_order": 1, "name": "Morning Service", "start_time": time(8), "end_time": time(9, 30)},
    {"service_order": 2, "name": "10am Service", "start_time": time(10), "end_time": time(11, 30)},
    {"service_order": 3, "name": "Midday Service", "start_time": time(12), "end_time": time(13, 30)},
    {"service_order": 4, "name": "Afternoon Service", "start_time": time(15), "end_time": time(16, 30)},
]


def _session_template(previous):
    if not previous:
        return [dict(item) for item in DEFAULT_SESSIONS]
    sessions = list(previous.sessions.order_by("service_order"))
    if not sessions:
        return [dict(item) for item in DEFAULT_SESSIONS]
    return [
        {
            "service_order": session.service_order,
            "name": session.name,
            "start_time": session.start_time,
            "end_time": session.end_time,
            "location": session.location,
            "notes": session.notes,
        }
        for session in sessions
    ]


@shared_task
def create_next_sunday_services(target_date=None):
    """Create tomorrow's Sunday schedule for every active branch.

    Beat invokes this late on Saturday. ``target_date`` exists to make manual
    recovery and tests deterministic.
    """
    sunday = date.fromisoformat(target_date) if target_date else timezone.localdate() + timedelta(days=1)
    if sunday.weekday() != 6:
        raise ValueError("Automatic Sunday creation requires a Sunday target date.")

    counts = {"created": 0, "skipped": 0, "failed": 0}
    branches = Branch.objects.filter(is_active=True, organization__is_active=True).select_related("organization")
    for branch in branches.iterator():
        existing = Event.objects.filter(
            branch=branch,
            event_date=sunday,
            event_type=Event.Type.SUNDAY_SERVICE,
        ).exclude(status=Event.Status.CANCELLED)
        if existing.exists():
            counts["skipped"] += 1
            continue
        try:
            previous = (
                Event.objects.filter(
                    branch=branch,
                    event_type=Event.Type.SUNDAY_SERVICE,
                    event_date__lt=sunday,
                )
                .exclude(status=Event.Status.CANCELLED)
                .prefetch_related("sessions")
                .order_by("-event_date")
                .first()
            )
            create_sunday_services(
                organization=branch.organization,
                branch=branch,
                sunday_date=sunday,
                sessions=_session_template(previous),
                location=previous.location if previous else "",
            )
            counts["created"] += 1
        except IntegrityError:
            # A concurrent worker may have won the unique-constraint race.
            if existing.exists():
                counts["skipped"] += 1
            else:
                counts["failed"] += 1
                logger.exception("Could not create Sunday schedule for branch %s", branch.id)
        except Exception:
            counts["failed"] += 1
            logger.exception("Could not create Sunday schedule for branch %s", branch.id)
    return counts
