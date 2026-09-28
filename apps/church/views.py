import calendar
from datetime import date

from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organization.models import Branch, Organization
from .models import (
    AgeGroup, AttendanceStatus, Child, ChildAttendance, Event, Facilitator,
    FacilitatorAttendance, ServiceFacilitator, ServiceSession,
)
from .permissions import HasChurchPermission, scope_ids
from .serializers import (
    AgeGroupSerializer, BulkAssignmentSerializer, BulkAttendanceSerializer,
    BulkFacilitatorAttendanceSerializer, ChildAttendanceSerializer, ChildSerializer,
    EventSerializer, FacilitatorAttendanceSerializer, FacilitatorSerializer,
    ServiceFacilitatorSerializer, ServiceSessionSerializer, SundayCreateSerializer,
)
from .services import attendance_counts, create_sunday_services, finalize_sunday_attendance, sunday_child_outcomes


def bool_param(value):
    return str(value).lower() in {"1", "true", "yes"}


class ChurchScopedMixin:
    permission_classes = [IsAuthenticated, HasChurchPermission]

    def scope(self):
        organization_id, branch_id = scope_ids(self.request)
        organization = get_object_or_404(Organization, id=organization_id, is_active=True)
        branch = get_object_or_404(Branch, id=branch_id, organization=organization, is_active=True)
        return organization, branch

    def scoped(self, queryset, organization_field="organization_id", branch_field="branch_id"):
        organization, branch = self.scope()
        return queryset.filter(**{organization_field: organization.id, branch_field: branch.id})


class ChurchModelViewSet(ChurchScopedMixin, viewsets.ModelViewSet):
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def perform_create(self, serializer):
        organization, branch = self.scope()
        serializer.save(organization=organization, branch=branch)


class AgeGroupViewSet(ChurchModelViewSet):
    serializer_class = AgeGroupSerializer
    queryset = AgeGroup.objects.all()
    required_permissions = {"GET": "church-age-groups.read", "POST": "church-age-groups.manage", "PUT": "church-age-groups.manage", "PATCH": "church-age-groups.manage"}

    def get_queryset(self):
        queryset = self.scoped(super().get_queryset())
        if "is_active" in self.request.query_params:
            queryset = queryset.filter(is_active=bool_param(self.request.query_params["is_active"]))
        if self.request.query_params.get("search"):
            queryset = queryset.filter(name__icontains=self.request.query_params["search"])
        return queryset


class ChildViewSet(ChurchModelViewSet):
    serializer_class = ChildSerializer
    queryset = Child.objects.select_related("age_group")
    required_permissions = {"GET": "church-children.read", "POST": "church-children.manage", "PUT": "church-children.manage", "PATCH": "church-children.manage"}

    def get_queryset(self):
        queryset = self.scoped(super().get_queryset())
        params = self.request.query_params
        if params.get("age_group"):
            queryset = queryset.filter(age_group_id=params["age_group"])
        if "is_active" in params:
            queryset = queryset.filter(is_active=bool_param(params["is_active"]))
        if params.get("search"):
            term = params["search"]
            queryset = queryset.filter(Q(first_name__icontains=term) | Q(last_name__icontains=term) | Q(other_names__icontains=term) | Q(guardian_name__icontains=term) | Q(guardian_contact__icontains=term))
        return queryset

    def perform_create(self, serializer):
        organization, branch = self.scope()
        age_group = serializer.validated_data["age_group"]
        if age_group.branch_id != branch.id:
            raise ValidationError({"age_group": "Age group must belong to this branch"})
        serializer.save(organization=organization, branch=branch)

    def retrieve(self, request, *args, **kwargs):
        child = self.get_object()
        data = self.get_serializer(child).data
        records = child.attendance_records.select_related("event", "service_session", "age_group", "recorded_by")[:20]
        outcomes = {}
        rank = {AttendanceStatus.ABSENT: 1, AttendanceStatus.EXCUSED: 2, AttendanceStatus.PRESENT: 3, AttendanceStatus.LATE: 3}
        for event_id, value in child.attendance_records.values_list("event_id", "attendance_status"):
            if rank[value] > rank.get(outcomes.get(event_id), 0):
                outcomes[event_id] = value
        attended = sum(value in [AttendanceStatus.PRESENT, AttendanceStatus.LATE] for value in outcomes.values())
        absent = sum(value == AttendanceStatus.ABSENT for value in outcomes.values())
        denominator = attended + absent
        data["recent_attendance"] = ChildAttendanceSerializer(records, many=True).data
        data["statistics"] = {"attended": attended, "absent": absent, "attendance_percentage": round(attended * 100 / denominator, 1) if denominator else None}
        return Response(data)


class FacilitatorViewSet(ChurchModelViewSet):
    serializer_class = FacilitatorSerializer
    queryset = Facilitator.objects.select_related("user", "default_age_group")
    required_permissions = {"GET": "church-facilitators.read", "POST": "church-facilitators.manage", "PUT": "church-facilitators.manage", "PATCH": "church-facilitators.manage"}

    def get_queryset(self):
        queryset = self.scoped(super().get_queryset())
        params = self.request.query_params
        if "is_active" in params:
            queryset = queryset.filter(is_active=bool_param(params["is_active"]))
        if params.get("default_age_group"):
            queryset = queryset.filter(default_age_group_id=params["default_age_group"])
        if params.get("search"):
            term = params["search"]
            queryset = queryset.filter(Q(user__first_name__icontains=term) | Q(user__last_name__icontains=term) | Q(user__email__icontains=term) | Q(user__phone_number__icontains=term))
        return queryset

    def perform_create(self, serializer):
        organization, branch = self.scope()
        serializer.save(organization=organization, branch=branch)

    @action(detail=False, methods=["get"], url_path="me/assignments")
    def my_assignments(self, request):
        _, branch = self.scope()
        facilitator = get_object_or_404(Facilitator, branch=branch, user=request.user, is_active=True)
        assignments = facilitator.service_assignments.select_related("service_session__event").order_by("-service_session__event__event_date")
        return Response(ServiceFacilitatorSerializer(assignments, many=True).data)


class EventViewSet(ChurchModelViewSet):
    serializer_class = EventSerializer
    queryset = Event.objects.prefetch_related("sessions")
    required_permissions = {"GET": "church-events.read", "POST": "church-events.manage", "PUT": "church-events.manage", "PATCH": "church-events.manage"}

    def get_queryset(self):
        queryset = self.scoped(super().get_queryset())
        params = self.request.query_params
        filters = {key: params[key] for key in ["event_type", "status"] if params.get(key)}
        queryset = queryset.filter(**filters)
        if params.get("date"):
            queryset = queryset.filter(event_date=params["date"])
        if params.get("date_from"):
            queryset = queryset.filter(event_date__gte=params["date_from"])
        if params.get("date_to"):
            queryset = queryset.filter(event_date__lte=params["date_to"])
        if params.get("search"):
            term = params["search"]
            queryset = queryset.filter(Q(name__icontains=term) | Q(description__icontains=term) | Q(location__icontains=term))
        return queryset

    def perform_create(self, serializer):
        organization, branch = self.scope()
        event = Event(organization=organization, branch=branch, created_by=self.request.user, **serializer.validated_data)
        event.full_clean()
        event.save()
        serializer.instance = event

    @action(detail=True, methods=["post"], url_path="attendance/finalize", required_permissions={"POST": "church-attendance.manage"})
    def finalize_attendance(self, request, pk=None):
        event = self.get_object()
        finalize_sunday_attendance(event, request.user)
        return Response({"event": EventSerializer(event).data, "summary": attendance_counts(event)})

    @action(detail=True, methods=["get"], required_permissions={"GET": "church-attendance.read"})
    def roster(self, request, pk=None):
        event = self.get_object()
        if event.event_type == Event.Type.SUNDAY_SERVICE:
            raise ValidationError({"event": "Use a service-session roster for Sunday attendance."})
        children = Child.objects.filter(branch=event.branch, is_active=True, registration_date__lte=event.event_date).select_related("age_group")
        if request.query_params.get("age_group"):
            children = children.filter(age_group_id=request.query_params["age_group"])
        if request.query_params.get("search"):
            term = request.query_params["search"]
            children = children.filter(Q(first_name__icontains=term) | Q(last_name__icontains=term) | Q(other_names__icontains=term))
        existing = {row.child_id: row for row in event.child_attendance.filter(service_session__isnull=True)}
        return Response({"event": EventSerializer(event).data, "children": [{"child_id": child.id, "name": str(child), "age": child.age_on(event.event_date), "age_group_id": child.age_group_id, "age_group_name": child.age_group.name, "guardian_contact": child.guardian_contact, "attendance_status": existing[child.id].attendance_status if child.id in existing else None, "notes": existing[child.id].notes if child.id in existing else ""} for child in children], "summary": attendance_counts(event)})

    @action(detail=True, methods=["post"], url_path="attendance/bulk", required_permissions={"POST": "church-attendance.manage"})
    def bulk_attendance(self, request, pk=None):
        payload = BulkAttendanceSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        event = self.get_object()
        if event.event_type == Event.Type.SUNDAY_SERVICE:
            raise ValidationError({"event": "Use a service-session attendance endpoint for Sundays."})
        rows = list(payload.validated_data["rows"])
        if payload.validated_data["mark_all_present"]:
            rows.extend({"child_id": child_id, "attendance_status": AttendanceStatus.PRESENT, "notes": ""} for child_id in payload.validated_data["visible_child_ids"])
        deduplicated = {row["child_id"]: row for row in rows}
        children = {child.id: child for child in Child.objects.filter(id__in=deduplicated, branch=event.branch, is_active=True).select_related("age_group")}
        if len(children) != len(deduplicated):
            raise ValidationError({"rows": "One or more children are invalid for this branch."})
        with transaction.atomic():
            for child_id, row in deduplicated.items():
                value = row["attendance_status"]
                ChildAttendance.objects.update_or_create(child=children[child_id], event=event, service_session=None, defaults={"age_group": children[child_id].age_group, "attendance_status": value, "checked_in_at": timezone.now() if value in [AttendanceStatus.PRESENT, AttendanceStatus.LATE] else None, "recorded_by": request.user, "notes": row.get("notes", "")})
        return Response({"summary": attendance_counts(event)})


class ServiceSessionViewSet(ChurchScopedMixin, viewsets.ModelViewSet):
    serializer_class = ServiceSessionSerializer
    queryset = ServiceSession.objects.select_related("event")
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    required_permissions = {"GET": "church-events.read", "POST": "church-events.manage", "PUT": "church-events.manage", "PATCH": "church-events.manage"}

    def get_queryset(self):
        queryset = self.scoped(super().get_queryset(), "event__organization_id", "event__branch_id")
        params = self.request.query_params
        if params.get("event"):
            queryset = queryset.filter(event_id=params["event"])
        if params.get("date"):
            queryset = queryset.filter(event__event_date=params["date"])
        if params.get("status"):
            queryset = queryset.filter(status=params["status"])
        return queryset

    def perform_create(self, serializer):
        _, branch = self.scope()
        event = serializer.validated_data["event"]
        if event.branch_id != branch.id:
            raise ValidationError({"event": "Event must belong to this branch."})
        session = ServiceSession(**serializer.validated_data)
        session.full_clean()
        session.save()
        serializer.instance = session

    @action(detail=True, methods=["get"], required_permissions={"GET": "church-attendance.read"})
    def roster(self, request, pk=None):
        session = self.get_object()
        children = Child.objects.filter(branch=session.event.branch, is_active=True, registration_date__lte=session.event.event_date).select_related("age_group")
        if request.query_params.get("age_group"):
            children = children.filter(age_group_id=request.query_params["age_group"])
        if request.query_params.get("search"):
            term = request.query_params["search"]
            children = children.filter(Q(first_name__icontains=term) | Q(last_name__icontains=term) | Q(other_names__icontains=term))
        if not bool_param(request.query_params.get("include_already_attended", False)):
            attended_elsewhere = ChildAttendance.objects.filter(event=session.event, attendance_status__in=[AttendanceStatus.PRESENT, AttendanceStatus.LATE]).exclude(service_session=session).values("child_id")
            children = children.exclude(id__in=attended_elsewhere)
        existing = {row.child_id: row for row in session.child_attendance.all()}
        data = [{
            "child_id": child.id, "name": str(child), "age": child.age_on(session.event.event_date),
            "age_group_id": child.age_group_id, "age_group_name": child.age_group.name,
            "guardian_contact": child.guardian_contact,
            "attendance_status": existing[child.id].attendance_status if child.id in existing else None,
            "notes": existing[child.id].notes if child.id in existing else "",
        } for child in children]
        return Response({"session": ServiceSessionSerializer(session).data, "children": data, "summary": attendance_counts(session.event, session)})

    @action(detail=True, methods=["post"], url_path="attendance/bulk", required_permissions={"POST": "church-attendance.manage"})
    def bulk_attendance(self, request, pk=None):
        serializer = BulkAttendanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = self.get_object()
        rows = list(serializer.validated_data["rows"])
        if serializer.validated_data["mark_all_present"]:
            rows.extend({"child_id": child_id, "attendance_status": AttendanceStatus.PRESENT, "notes": ""} for child_id in serializer.validated_data["visible_child_ids"])
        deduplicated = {row["child_id"]: row for row in rows}
        children = {child.id: child for child in Child.objects.filter(id__in=deduplicated, branch=session.event.branch, is_active=True).select_related("age_group")}
        if len(children) != len(deduplicated):
            raise ValidationError({"rows": "One or more children are invalid for this branch."})
        with transaction.atomic():
            for child_id, row in deduplicated.items():
                status_value = row["attendance_status"]
                ChildAttendance.objects.update_or_create(
                    child=children[child_id], service_session=session,
                    defaults={"event": session.event, "age_group": children[child_id].age_group, "attendance_status": status_value, "checked_in_at": timezone.now() if status_value in [AttendanceStatus.PRESENT, AttendanceStatus.LATE] else None, "recorded_by": request.user, "notes": row.get("notes", "")},
                )
        return Response({"summary": attendance_counts(session.event, session)})

    @action(detail=True, methods=["post"], url_path="facilitators/bulk-assign", required_permissions={"POST": "church-facilitators.manage"})
    def bulk_assign(self, request, pk=None):
        serializer = BulkAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = self.get_object()
        rows = serializer.validated_data["assignments"]
        ids = [row["facilitator_id"] for row in rows]
        facilitators = {item.id: item for item in Facilitator.objects.filter(id__in=ids, branch=session.event.branch, is_active=True)}
        if len(facilitators) != len(set(ids)):
            raise ValidationError({"assignments": "One or more facilitators are invalid for this branch."})
        with transaction.atomic():
            session.facilitator_assignments.exclude(facilitator_id__in=ids).delete()
            for row in rows:
                ServiceFacilitator.objects.update_or_create(service_session=session, facilitator=facilitators[row["facilitator_id"]], defaults={"role": row["role"], "assigned_by": request.user})
        return Response(ServiceFacilitatorSerializer(session.facilitator_assignments.select_related("facilitator__user"), many=True).data)

    @action(detail=True, methods=["post"], url_path="facilitator-attendance/bulk", required_permissions={"POST": "church-attendance.manage"})
    def bulk_facilitator_attendance(self, request, pk=None):
        serializer = BulkFacilitatorAttendanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = self.get_object()
        rows = serializer.validated_data["rows"]
        assigned = {item.facilitator_id: item.facilitator for item in session.facilitator_assignments.select_related("facilitator__user")}
        can_manage = request.user.is_superuser or request.user.has_tenant_perm("church-facilitators.manage", session.event.organization)
        with transaction.atomic():
            for row in rows:
                facilitator = assigned.get(row["facilitator_id"])
                if not facilitator:
                    raise ValidationError({"rows": "Facilitator must be assigned to this service."})
                if not can_manage and facilitator.user_id != request.user.id:
                    raise PermissionDenied("You may only record your own attendance.")
                status_value = row["attendance_status"]
                FacilitatorAttendance.objects.update_or_create(service_session=session, facilitator=facilitator, defaults={"attendance_status": status_value, "checked_in_at": timezone.now() if status_value in [AttendanceStatus.PRESENT, AttendanceStatus.LATE] else None, "recorded_by": request.user, "notes": row.get("notes", "")})
        return Response(FacilitatorAttendanceSerializer(session.facilitator_attendance.select_related("facilitator__user"), many=True).data)


class ChildAttendanceViewSet(ChurchScopedMixin, viewsets.ModelViewSet):
    serializer_class = ChildAttendanceSerializer
    queryset = ChildAttendance.objects.select_related("child", "event", "service_session", "age_group")
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    required_permissions = {"GET": "church-attendance.read", "POST": "church-attendance.manage", "PUT": "church-attendance.manage", "PATCH": "church-attendance.manage"}

    def get_queryset(self):
        queryset = self.scoped(super().get_queryset(), "event__organization_id", "event__branch_id")
        params = self.request.query_params
        mappings = {"child": "child_id", "event": "event_id", "service": "service_session_id", "age_group": "age_group_id", "status": "attendance_status"}
        for key, field in mappings.items():
            if params.get(key):
                queryset = queryset.filter(**{field: params[key]})
        if params.get("date_from"):
            queryset = queryset.filter(event__event_date__gte=params["date_from"])
        if params.get("date_to"):
            queryset = queryset.filter(event__event_date__lte=params["date_to"])
        return queryset

    def perform_create(self, serializer):
        _, branch = self.scope()
        child = serializer.validated_data["child"]
        event = serializer.validated_data["event"]
        session = serializer.validated_data.get("service_session")
        if child.branch_id != branch.id or event.branch_id != branch.id or (session and session.event_id != event.id):
            raise ValidationError({"event": "Child, event and session must belong to this branch."})
        serializer.save(age_group=child.age_group, recorded_by=self.request.user, checked_in_at=timezone.now() if serializer.validated_data["attendance_status"] in [AttendanceStatus.PRESENT, AttendanceStatus.LATE] else None)


class ServiceFacilitatorViewSet(ChurchScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = ServiceFacilitatorSerializer
    queryset = ServiceFacilitator.objects.select_related("service_session__event", "facilitator__user")
    required_permissions = {"GET": "church-facilitators.read"}

    def get_queryset(self):
        queryset = self.scoped(super().get_queryset(), "service_session__event__organization_id", "service_session__event__branch_id")
        for key, field in {"service": "service_session_id", "facilitator": "facilitator_id", "role": "role"}.items():
            if self.request.query_params.get(key):
                queryset = queryset.filter(**{field: self.request.query_params[key]})
        return queryset


class FacilitatorAttendanceViewSet(ChurchScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = FacilitatorAttendanceSerializer
    queryset = FacilitatorAttendance.objects.select_related("service_session__event", "facilitator__user")
    required_permissions = {"GET": "church-attendance.read"}

    def get_queryset(self):
        queryset = self.scoped(super().get_queryset(), "service_session__event__organization_id", "service_session__event__branch_id")
        for key, field in {"service": "service_session_id", "facilitator": "facilitator_id", "status": "attendance_status"}.items():
            if self.request.query_params.get(key):
                queryset = queryset.filter(**{field: self.request.query_params[key]})
        return queryset


class SundayCreateView(ChurchScopedMixin, APIView):
    required_permissions = {"POST": "church-events.manage"}

    def post(self, request):
        serializer = SundayCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization, branch = self.scope()
        data = serializer.validated_data
        event = create_sunday_services(organization=organization, branch=branch, sunday_date=data["sunday_date"], sessions=data["sessions"], actor=request.user, name=data.get("name", ""), location=data.get("location", ""))
        return Response(EventSerializer(event).data, status=status.HTTP_201_CREATED)


class SundayLookupView(ChurchScopedMixin, APIView):
    required_permissions = {"GET": "church-events.read"}
    mode = "today"

    def get(self, request):
        _, branch = self.scope()
        queryset = Event.objects.filter(branch=branch, event_type=Event.Type.SUNDAY_SERVICE).exclude(status=Event.Status.CANCELLED).prefetch_related("sessions")
        if self.mode == "today":
            event = queryset.filter(event_date=date.today()).first()
        else:
            event = queryset.filter(event_date__gte=date.today()).order_by("event_date").first()
        return Response(EventSerializer(event).data if event else None)


class UpcomingSundayView(SundayLookupView):
    mode = "upcoming"


class DashboardSummaryView(ChurchScopedMixin, APIView):
    required_permissions = {"GET": "church-dashboard.read"}

    def get(self, request):
        _, branch = self.scope()
        events = Event.objects.filter(branch=branch).exclude(status=Event.Status.CANCELLED)
        upcoming = events.filter(event_date__gte=date.today()).order_by("event_date").first()
        recent_sunday = events.filter(event_type=Event.Type.SUNDAY_SERVICE, attendance_finalized_at__isnull=False).order_by("-event_date").first()
        counts = attendance_counts(recent_sunday) if recent_sunday else {key: 0 for key in ["present", "late", "absent", "excused"]}
        attended = counts["present"] + counts["late"]
        denominator = attended + counts["absent"]
        current_year = timezone.localdate().year
        monthly = [{"month": month, "label": calendar.month_name[month], "present": 0, "absent": 0} for month in range(1, 13)]
        finalized_sundays = events.filter(
            event_type=Event.Type.SUNDAY_SERVICE,
            attendance_finalized_at__isnull=False,
            event_date__year=current_year,
        ).prefetch_related("child_attendance")
        for event in finalized_sundays:
            event_counts = attendance_counts(event)
            bucket = monthly[event.event_date.month - 1]
            bucket["present"] += event_counts["present"] + event_counts["late"]
            bucket["absent"] += event_counts["absent"] + event_counts["excused"]
        for bucket in monthly:
            total = bucket["present"] + bucket["absent"]
            if total:
                bucket["present"] = round(bucket["present"] * 100 / total, 1)
                bucket["absent"] = round(bucket["absent"] * 100 / total, 1)
        return Response({
            "total_registered_children": Child.objects.filter(branch=branch).count(),
            "active_children": Child.objects.filter(branch=branch, is_active=True).count(),
            "upcoming_event": EventSerializer(upcoming).data if upcoming else None,
            "recent_sunday": EventSerializer(recent_sunday).data if recent_sunday else None,
            "recent_attendance": counts,
            "attendance_percentage": round(attended * 100 / denominator, 1) if denominator else None,
            "upcoming_events": EventSerializer(events.filter(event_date__gte=date.today()).order_by("event_date")[:5], many=True).data,
            "recent_events": EventSerializer(events.filter(event_date__lt=date.today()).order_by("-event_date")[:5], many=True).data,
            "monthly_attendance": {"year": current_year, "months": monthly},
        })


class AttendanceReportView(ChurchScopedMixin, APIView):
    required_permissions = {"GET": "church-reports.read"}
    report_type = "sunday"

    def get(self, request):
        _, branch = self.scope()
        events = Event.objects.filter(branch=branch)
        if request.query_params.get("date_from"):
            events = events.filter(event_date__gte=request.query_params["date_from"])
        if request.query_params.get("date_to"):
            events = events.filter(event_date__lte=request.query_params["date_to"])
        if request.query_params.get("event"):
            events = events.filter(id=request.query_params["event"])
        if self.report_type in {"sunday", "absentees", "repeated"}:
            events = events.filter(event_type=Event.Type.SUNDAY_SERVICE, attendance_finalized_at__isnull=False)
        if self.report_type == "repeated":
            rows = []
            children = Child.objects.filter(branch=branch).select_related("age_group")
            for child in children:
                records = ChildAttendance.objects.filter(child=child, event__in=events)
                attended_events = records.filter(attendance_status__in=[AttendanceStatus.PRESENT, AttendanceStatus.LATE]).values("event_id").distinct().count()
                excused_events = records.filter(attendance_status=AttendanceStatus.EXCUSED).values("event_id").distinct().count()
                missed_events = records.filter(attendance_status=AttendanceStatus.ABSENT).exclude(event_id__in=records.filter(attendance_status__in=[AttendanceStatus.PRESENT, AttendanceStatus.LATE]).values("event_id")).values("event_id").distinct().count()
                denominator = attended_events + missed_events
                if missed_events:
                    rows.append({"child_id": child.id, "child_name": str(child), "age_group": child.age_group.name, "attended": attended_events, "missed": missed_events, "excused": excused_events, "attendance_percentage": round(attended_events * 100 / denominator, 1) if denominator else None})
            return Response(sorted(rows, key=lambda row: (-row["missed"], row["child_name"])))
        if self.report_type == "facilitators":
            records = FacilitatorAttendance.objects.filter(service_session__event__in=events).values("facilitator_id", "facilitator__user__first_name", "facilitator__user__last_name", "facilitator__user__email", "attendance_status").annotate(total=Count("id"))
            return Response(list(records))
        if self.report_type == "age-groups":
            records = ChildAttendance.objects.filter(event__in=events).values("age_group_id", "age_group__name", "attendance_status").annotate(total=Count("id"))
            return Response(list(records))
        if self.report_type == "absentees":
            absent_ids = []
            for event in events:
                outcomes = sunday_child_outcomes(event)
                absent_ids.extend(record.id for record in event.child_attendance.filter(attendance_status=AttendanceStatus.ABSENT) if outcomes.get(record.child_id) == AttendanceStatus.ABSENT)
            records = ChildAttendance.objects.filter(id__in=absent_ids).select_related("child", "event", "age_group")
            return Response(ChildAttendanceSerializer(records, many=True).data)
        result = [{"event": EventSerializer(event).data, "summary": attendance_counts(event)} for event in events.order_by("-event_date")]
        return Response(result)


class EventAttendanceReportView(AttendanceReportView):
    report_type = "event"


class ServiceAttendanceReportView(AttendanceReportView):
    report_type = "service"

    def get(self, request):
        _, branch = self.scope()
        sessions = ServiceSession.objects.filter(event__branch=branch).select_related("event")
        if request.query_params.get("event"):
            sessions = sessions.filter(event_id=request.query_params["event"])
        if request.query_params.get("service"):
            sessions = sessions.filter(id=request.query_params["service"])
        return Response([{"session": ServiceSessionSerializer(item).data, "summary": attendance_counts(item.event, item)} for item in sessions])


class AgeGroupReportView(AttendanceReportView):
    report_type = "age-groups"


class AbsenteeReportView(AttendanceReportView):
    report_type = "absentees"


class RepeatedAbsenteeReportView(AttendanceReportView):
    report_type = "repeated"


class FacilitatorAttendanceReportView(AttendanceReportView):
    report_type = "facilitators"


class ChildHistoryReportView(ChurchScopedMixin, APIView):
    required_permissions = {"GET": "church-reports.read"}

    def get(self, request, child_id):
        _, branch = self.scope()
        child = get_object_or_404(Child, id=child_id, branch=branch)
        records = child.attendance_records.select_related("event", "service_session", "age_group")
        if request.query_params.get("date_from"):
            records = records.filter(event__event_date__gte=request.query_params["date_from"])
        if request.query_params.get("date_to"):
            records = records.filter(event__event_date__lte=request.query_params["date_to"])
        return Response({"child": ChildSerializer(child).data, "records": ChildAttendanceSerializer(records, many=True).data})
