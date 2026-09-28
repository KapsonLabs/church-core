import uuid
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class TenantBranchModel(models.Model):
    organization = models.ForeignKey("organization.Organization", on_delete=models.CASCADE)
    branch = models.ForeignKey("organization.Branch", on_delete=models.CASCADE)

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.branch_id and self.organization_id and self.branch.organization_id != self.organization_id:
            raise ValidationError({"branch": "Branch must belong to the selected organization."})


class AgeGroup(TenantBranchModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    minimum_age = models.PositiveSmallIntegerField()
    maximum_age = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["minimum_age", "name"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "name"], name="unique_church_age_group_name_branch"),
            models.CheckConstraint(condition=models.Q(minimum_age__lte=models.F("maximum_age")), name="church_age_group_valid_range"),
        ]

    def clean(self):
        super().clean()
        if self.minimum_age is not None and self.maximum_age is not None and self.minimum_age > self.maximum_age:
            raise ValidationError({"maximum_age": "Maximum age must be greater than or equal to minimum age."})

    def __str__(self):
        return f"{self.name} ({self.branch})"


class Child(TenantBranchModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    other_names = models.CharField(max_length=200, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    age_group = models.ForeignKey(AgeGroup, on_delete=models.PROTECT, related_name="children")
    guardian_name = models.CharField(max_length=255)
    guardian_contact = models.CharField(max_length=100)
    location = models.CharField(max_length=255, blank=True)
    registration_date = models.DateField(default=date.today)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["first_name", "last_name"]
        indexes = [models.Index(fields=["branch", "is_active"])]

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))

    def age_on(self, on_date):
        if not self.date_of_birth:
            return None
        return on_date.year - self.date_of_birth.year - ((on_date.month, on_date.day) < (self.date_of_birth.month, self.date_of_birth.day))

    def clean(self):
        super().clean()
        if self.date_of_birth and self.date_of_birth > date.today():
            raise ValidationError({"date_of_birth": "Date of birth cannot be in the future."})
        if self.age_group_id and self.branch_id and self.organization_id:
            if self.age_group.branch_id != self.branch_id or self.age_group.organization_id != self.organization_id:
                raise ValidationError({"age_group": "Age group must belong to the same branch."})
            current_age = self.age
            if current_age is not None and not (self.age_group.minimum_age <= current_age <= self.age_group.maximum_age):
                raise ValidationError({"age_group": "The child's age is outside this age group's range."})
        self.guardian_contact = self.guardian_contact.strip()

    def __str__(self):
        return " ".join(part for part in [self.first_name, self.other_names, self.last_name] if part)


class Facilitator(TenantBranchModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="church_facilitator_profiles")
    default_age_group = models.ForeignKey(AgeGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="facilitators")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__first_name", "user__last_name", "user__email"]
        constraints = [models.UniqueConstraint(fields=["branch", "user"], name="unique_church_facilitator_branch_user")]
        indexes = [models.Index(fields=["branch", "is_active"])]

    def clean(self):
        super().clean()
        if self.default_age_group_id and self.branch_id and self.default_age_group.branch_id != self.branch_id:
            raise ValidationError({"default_age_group": "Age group must belong to the same branch."})
        if self.user_id and self.organization_id:
            if not self.user.organization_memberships.filter(organization_id=self.organization_id, is_active=True).exists():
                raise ValidationError({"user": "User must be an active organization member."})
            if not self.user.branch_memberships.filter(branch_id=self.branch_id, is_active=True).exists():
                raise ValidationError({"user": "User must be an active member of this branch."})

    def __str__(self):
        return self.user.get_full_name() or self.user.email


class Event(TenantBranchModel):
    class Type(models.TextChoices):
        SUNDAY_SERVICE = "sunday_service", "Sunday service"
        OUTREACH = "outreach", "Outreach"
        CONFERENCE = "conference", "Children's conference"
        CAMP = "camp", "Camp"
        TRAINING = "training", "Training"
        REHEARSAL = "rehearsal", "Rehearsal"
        SPECIAL_SERVICE = "special_service", "Special service"
        TRIP = "trip", "Trip"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    event_type = models.CharField(max_length=30, choices=Type.choices)
    description = models.TextField(blank=True)
    event_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_church_events")
    attendance_finalized_at = models.DateTimeField(null=True, blank=True)
    attendance_finalized_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="finalized_church_events")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-event_date", "start_time"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "event_date"], condition=models.Q(event_type="sunday_service") & ~models.Q(status="cancelled"), name="unique_active_sunday_event_branch_date"),
        ]
        indexes = [models.Index(fields=["branch", "event_date"]), models.Index(fields=["branch", "event_type"])]

    def clean(self):
        super().clean()
        if self.start_time and self.end_time and self.end_time < self.start_time:
            raise ValidationError({"end_time": "End time cannot precede start time."})
        if self.event_type == self.Type.SUNDAY_SERVICE and self.event_date and self.event_date.weekday() != 6:
            raise ValidationError({"event_date": "Sunday services must be scheduled on a Sunday."})

    def __str__(self):
        return f"{self.name} — {self.event_date}"


class ServiceSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name="sessions")
    service_order = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=150)
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Event.Status.choices, default=Event.Status.SCHEDULED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["event__event_date", "service_order"]
        constraints = [
            models.UniqueConstraint(fields=["event", "service_order"], name="unique_church_session_order"),
            models.UniqueConstraint(fields=["event", "name"], name="unique_church_session_name"),
            models.CheckConstraint(condition=models.Q(service_order__gt=0), name="church_session_positive_order"),
        ]

    def clean(self):
        super().clean()
        if self.event_id and self.event.event_type != Event.Type.SUNDAY_SERVICE:
            raise ValidationError({"event": "Service sessions require a Sunday service event."})
        if self.start_time and self.end_time and self.end_time < self.start_time:
            raise ValidationError({"end_time": "End time cannot precede start time."})

    def __str__(self):
        return f"{self.event}: {self.name}"


class AttendanceStatus(models.TextChoices):
    PRESENT = "present", "Present"
    ABSENT = "absent", "Absent"
    EXCUSED = "excused", "Excused"
    LATE = "late", "Late"


class ChildAttendance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    child = models.ForeignKey(Child, on_delete=models.PROTECT, related_name="attendance_records")
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name="child_attendance")
    service_session = models.ForeignKey(ServiceSession, on_delete=models.PROTECT, null=True, blank=True, related_name="child_attendance")
    age_group = models.ForeignKey(AgeGroup, on_delete=models.PROTECT, related_name="attendance_snapshots")
    attendance_status = models.CharField(max_length=20, choices=AttendanceStatus.choices)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="recorded_child_attendance")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-event__event_date", "child__first_name"]
        constraints = [
            models.UniqueConstraint(fields=["child", "event"], condition=models.Q(service_session__isnull=True), name="unique_child_event_attendance"),
            models.UniqueConstraint(fields=["child", "service_session"], condition=models.Q(service_session__isnull=False), name="unique_child_session_attendance"),
        ]
        indexes = [models.Index(fields=["child", "event"]), models.Index(fields=["child", "service_session"])]

    def clean(self):
        super().clean()
        if self.child_id and self.event_id and (self.child.branch_id != self.event.branch_id or self.child.organization_id != self.event.organization_id):
            raise ValidationError({"child": "Child and event must belong to the same branch."})
        if self.service_session_id and self.service_session.event_id != self.event_id:
            raise ValidationError({"service_session": "Service session must belong to the selected event."})
        if self.event_id and self.event.event_type == Event.Type.SUNDAY_SERVICE and not self.service_session_id and self.attendance_status != AttendanceStatus.ABSENT:
            raise ValidationError({"service_session": "Sunday attendance requires a service session."})
        if self.event_id and self.event.event_type != Event.Type.SUNDAY_SERVICE and self.service_session_id:
            raise ValidationError({"service_session": "Only Sunday services may use a service session."})
        if self.age_group_id and self.child_id and self.age_group.branch_id != self.child.branch_id:
            raise ValidationError({"age_group": "Attendance age group must belong to the child's branch."})

    def __str__(self):
        return f"{self.child} — {self.event}: {self.get_attendance_status_display()}"


class ServiceFacilitator(models.Model):
    class Role(models.TextChoices):
        LEAD = "lead", "Lead"
        ASSISTANT = "assistant", "Assistant"
        TEACHER = "teacher", "Teacher"
        VOLUNTEER = "volunteer", "Volunteer"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service_session = models.ForeignKey(ServiceSession, on_delete=models.PROTECT, related_name="facilitator_assignments")
    facilitator = models.ForeignKey(Facilitator, on_delete=models.PROTECT, related_name="service_assignments")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VOLUNTEER)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="church_facilitator_assignments")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["service_session", "role"]
        constraints = [models.UniqueConstraint(fields=["service_session", "facilitator"], name="unique_church_facilitator_assignment")]

    def clean(self):
        super().clean()
        if self.service_session_id and self.facilitator_id and self.service_session.event.branch_id != self.facilitator.branch_id:
            raise ValidationError({"facilitator": "Facilitator and service must belong to the same branch."})


class FacilitatorAttendance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service_session = models.ForeignKey(ServiceSession, on_delete=models.PROTECT, related_name="facilitator_attendance")
    facilitator = models.ForeignKey(Facilitator, on_delete=models.PROTECT, related_name="attendance_records")
    attendance_status = models.CharField(max_length=20, choices=AttendanceStatus.choices)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="recorded_facilitator_attendance")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-service_session__event__event_date", "facilitator"]
        constraints = [models.UniqueConstraint(fields=["service_session", "facilitator"], name="unique_church_facilitator_attendance")]
        indexes = [models.Index(fields=["facilitator", "service_session"])]

    def clean(self):
        super().clean()
        if self.service_session_id and self.facilitator_id:
            if self.service_session.event.branch_id != self.facilitator.branch_id:
                raise ValidationError({"facilitator": "Facilitator and service must belong to the same branch."})
            if not ServiceFacilitator.objects.filter(service_session_id=self.service_session_id, facilitator_id=self.facilitator_id).exists():
                raise ValidationError({"facilitator": "Facilitator must be assigned to this service."})
