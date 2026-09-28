from django.contrib import admin

from .models import AgeGroup, Child, ChildAttendance, Event, Facilitator, FacilitatorAttendance, ServiceFacilitator, ServiceSession


@admin.register(AgeGroup)
class AgeGroupAdmin(admin.ModelAdmin):
    list_display = ["name", "branch", "minimum_age", "maximum_age", "is_active"]
    list_filter = ["is_active", "organization", "branch"]
    search_fields = ["name"]


@admin.register(Child)
class ChildAdmin(admin.ModelAdmin):
    list_display = ["first_name", "last_name", "age_group", "branch", "guardian_name", "is_active", "registration_date"]
    list_filter = ["is_active", "organization", "branch", "age_group"]
    search_fields = ["first_name", "last_name", "other_names", "guardian_name", "guardian_contact"]
    date_hierarchy = "registration_date"


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["name", "event_type", "event_date", "branch", "status", "attendance_finalized_at"]
    list_filter = ["event_type", "status", "organization", "branch"]
    search_fields = ["name", "description", "location"]
    date_hierarchy = "event_date"


@admin.register(ServiceSession)
class ServiceSessionAdmin(admin.ModelAdmin):
    list_display = ["name", "event", "service_order", "start_time", "status"]
    list_filter = ["status", "event__branch"]
    search_fields = ["name", "event__name"]


@admin.register(Facilitator)
class FacilitatorAdmin(admin.ModelAdmin):
    list_display = ["user", "branch", "default_age_group", "is_active"]
    list_filter = ["is_active", "organization", "branch", "default_age_group"]
    search_fields = ["user__first_name", "user__last_name", "user__email", "user__phone_number"]


@admin.register(ChildAttendance)
class ChildAttendanceAdmin(admin.ModelAdmin):
    list_display = ["child", "event", "service_session", "attendance_status", "recorded_by", "checked_in_at"]
    list_filter = ["attendance_status", "event__branch", "age_group"]
    search_fields = ["child__first_name", "child__last_name", "event__name"]
    date_hierarchy = "created_at"


@admin.register(ServiceFacilitator)
class ServiceFacilitatorAdmin(admin.ModelAdmin):
    list_display = ["facilitator", "service_session", "role", "assigned_by", "created_at"]
    list_filter = ["role", "service_session__event__branch"]
    search_fields = ["facilitator__user__first_name", "facilitator__user__last_name", "service_session__name"]


@admin.register(FacilitatorAttendance)
class FacilitatorAttendanceAdmin(admin.ModelAdmin):
    list_display = ["facilitator", "service_session", "attendance_status", "recorded_by", "checked_in_at"]
    list_filter = ["attendance_status", "service_session__event__branch"]
    search_fields = ["facilitator__user__first_name", "facilitator__user__last_name", "service_session__name"]
    date_hierarchy = "created_at"

