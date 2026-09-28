from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AbsenteeReportView, AgeGroupReportView, AgeGroupViewSet, AttendanceReportView,
    ChildAttendanceViewSet, ChildHistoryReportView, ChildViewSet, DashboardSummaryView,
    EventAttendanceReportView, EventViewSet, FacilitatorAttendanceReportView,
    FacilitatorAttendanceViewSet, FacilitatorViewSet, RepeatedAbsenteeReportView,
    ServiceAttendanceReportView, ServiceFacilitatorViewSet, ServiceSessionViewSet,
    SundayCreateView, SundayLookupView, UpcomingSundayView,
)

router = DefaultRouter()
router.register("age-groups", AgeGroupViewSet)
router.register("children", ChildViewSet)
router.register("facilitators", FacilitatorViewSet)
router.register("events", EventViewSet)
router.register("service-sessions", ServiceSessionViewSet)
router.register("attendance", ChildAttendanceViewSet)
router.register("service-facilitators", ServiceFacilitatorViewSet)
router.register("facilitator-attendance", FacilitatorAttendanceViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("sunday-services/create/", SundayCreateView.as_view()),
    path("sunday-services/today/", SundayLookupView.as_view()),
    path("sunday-services/upcoming/", UpcomingSundayView.as_view()),
    path("dashboard/summary/", DashboardSummaryView.as_view()),
    path("reports/sunday-attendance/", AttendanceReportView.as_view()),
    path("reports/service-attendance/", ServiceAttendanceReportView.as_view()),
    path("reports/event-attendance/", EventAttendanceReportView.as_view()),
    path("reports/age-groups/", AgeGroupReportView.as_view()),
    path("reports/absentees/", AbsenteeReportView.as_view()),
    path("reports/repeated-absentees/", RepeatedAbsenteeReportView.as_view()),
    path("reports/facilitator-attendance/", FacilitatorAttendanceReportView.as_view()),
    path("reports/children/<uuid:child_id>/history/", ChildHistoryReportView.as_view()),
]

