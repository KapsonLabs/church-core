from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import AgeGroup, Child, ChildAttendance, Event, ServiceSession


@transaction.atomic
def create_sunday_services(*, organization, branch, sunday_date, sessions, actor=None, name="", location=""):
    if Event.objects.filter(branch=branch, event_date=sunday_date, event_type=Event.Type.SUNDAY_SERVICE).exclude(status=Event.Status.CANCELLED).exists():
        raise ValidationError({"sunday_date": "A Sunday service already exists for this branch and date."})
    event = Event(
        organization=organization, branch=branch, name=name or f"Sunday Service, {sunday_date:%d %B %Y}",
        event_type=Event.Type.SUNDAY_SERVICE, event_date=sunday_date, location=location,
        status=Event.Status.SCHEDULED, created_by=actor,
    )
    # Automated schedule creation has no request user. The database field is
    # nullable so omit the form-level blank check for that deliberate case.
    event.full_clean(exclude=["created_by"] if actor is None else None)
    event.save()
    for item in sessions:
        session = ServiceSession(event=event, **item)
        session.full_clean()
        session.save()
    return event


@transaction.atomic
def finalize_sunday_attendance(event, actor):
    if event.event_type != Event.Type.SUNDAY_SERVICE:
        raise ValidationError({"event": "Only Sunday services can be finalized."})
    attended_ids = ChildAttendance.objects.filter(
        event=event, attendance_status__in=["present", "late", "excused"]
    ).values_list("child_id", flat=True)
    candidates = Child.objects.filter(
        branch=event.branch, organization=event.organization, is_active=True,
        registration_date__lte=event.event_date,
    ).exclude(id__in=attended_ids)
    for child in candidates.select_related("age_group"):
        ChildAttendance.objects.update_or_create(
            child=child, event=event, service_session=None,
            defaults={"age_group": child.age_group, "attendance_status": "absent", "recorded_by": actor},
        )
    event.attendance_finalized_at = timezone.now()
    event.attendance_finalized_by = actor
    event.save(update_fields=["attendance_finalized_at", "attendance_finalized_by", "updated_at"])
    return event


def sunday_child_outcomes(event):
    outcomes = {}
    rank = {"absent": 1, "excused": 2, "present": 3, "late": 3}
    for child_id, status in event.child_attendance.values_list("child_id", "attendance_status"):
        if rank.get(status, 0) > rank.get(outcomes.get(child_id), 0):
            outcomes[child_id] = status
    return outcomes


def attendance_counts(event, session=None):
    if session:
        statuses = session.child_attendance.values_list("attendance_status", flat=True)
        counts = {key: 0 for key in ["present", "late", "absent", "excused"]}
        for status in statuses:
            counts[status] += 1
        return counts
    outcomes = sunday_child_outcomes(event) if event.event_type == Event.Type.SUNDAY_SERVICE else {
        child_id: status for child_id, status in event.child_attendance.filter(service_session__isnull=True).values_list("child_id", "attendance_status")
    }
    return {key: sum(1 for value in outcomes.values() if value == key) for key in ["present", "late", "absent", "excused"]}
