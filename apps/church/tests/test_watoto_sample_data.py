from datetime import date, time
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.accounts.models import AccessPermission, Role
from apps.organization.models import Branch, BranchMembership, Organization, OrganizationMembership
from apps.church.management.commands.seed_watoto_sample_data import BRANCH_CODE, BRANCH_NAME, DEFAULT_ADMIN_EMAIL, DEFAULT_PASSWORD
from apps.church.models import (
    AgeGroup,
    AttendanceStatus,
    Child,
    ChildAttendance,
    Event,
    Facilitator,
    FacilitatorAttendance,
    ServiceFacilitator,
    ServiceSession,
)


class WatotoSampleDataCommandTests(TestCase):
    command_options = {
        "year": 2026,
        "through_date": "2026-09-24",
        "seed": 2026,
    }

    def run_command(self):
        stdout = StringIO()
        call_command("seed_watoto_sample_data", stdout=stdout, **self.command_options)
        return stdout.getvalue()

    def test_creates_complete_idempotent_sample_dataset(self):
        output = self.run_command()
        organization = Organization.objects.get(name="Watoto Ministries")
        branch = Branch.objects.get(organization=organization, name=BRANCH_NAME, code=BRANCH_CODE)

        groups = list(AgeGroup.objects.filter(branch=branch).order_by("minimum_age"))
        self.assertEqual([group.minimum_age for group in groups], [9, 10, 11, 12, 13])
        self.assertEqual(Child.objects.filter(branch=branch).count(), 225)
        self.assertTrue(all(child.age == child.age_group.minimum_age for child in Child.objects.filter(branch=branch).select_related("age_group")))

        facilitators = Facilitator.objects.filter(branch=branch).select_related("user")
        self.assertEqual(facilitators.count(), 12)
        self.assertEqual(OrganizationMembership.objects.filter(organization=organization, user__in=[item.user for item in facilitators]).count(), 12)
        self.assertEqual(BranchMembership.objects.filter(branch=branch, user__in=[item.user for item in facilitators]).count(), 12)
        self.assertTrue(get_user_model().objects.get(email="facilitator1@email.com").check_password(DEFAULT_PASSWORD))
        self.assertTrue(all("branches.read" not in item.user.get_tenant_permissions(organization) for item in facilitators))
        self.assertTrue(all("church-events.manage" in item.user.get_tenant_permissions(organization) for item in facilitators))
        self.assertTrue(all("church-age-groups.manage" not in item.user.get_tenant_permissions(organization) for item in facilitators))
        self.assertTrue(all("church-facilitators.manage" not in item.user.get_tenant_permissions(organization) for item in facilitators))

        administrator = get_user_model().objects.get(email=DEFAULT_ADMIN_EMAIL)
        administrator_role = Role.objects.get(organization=organization, slug="administrator")
        self.assertTrue(administrator.check_password(DEFAULT_PASSWORD))
        self.assertFalse(Facilitator.objects.filter(user=administrator).exists())
        self.assertEqual(
            set(administrator_role.permissions.values_list("id", flat=True)),
            set(AccessPermission.objects.filter(is_active=True).values_list("id", flat=True)),
        )
        self.assertTrue(OrganizationMembership.objects.filter(organization=organization, user=administrator, role=administrator_role, is_active=True).exists())
        self.assertTrue(BranchMembership.objects.filter(branch=branch, user=administrator, is_active=True).exists())

        events = Event.objects.filter(branch=branch, event_type=Event.Type.SUNDAY_SERVICE)
        self.assertEqual(events.count(), 38)
        self.assertEqual(events.filter(status=Event.Status.COMPLETED, attendance_finalized_at__isnull=False).count(), 38)
        self.assertEqual(ServiceSession.objects.filter(event__in=events).count(), 152)
        self.assertEqual(ServiceFacilitator.objects.filter(service_session__event__in=events).count(), 456)
        self.assertEqual(FacilitatorAttendance.objects.filter(service_session__event__in=events).count(), 456)
        self.assertEqual(ChildAttendance.objects.filter(event__in=events).count(), 225 * 38)

        first_event = events.order_by("event_date").first()
        self.assertEqual(first_event.event_date, date(2026, 1, 4))
        sessions = list(first_event.sessions.order_by("service_order"))
        self.assertEqual([session.name for session in sessions], ["Morning Service", "10am Service", "Midday Service", "Afternoon Service"])
        self.assertEqual([session.start_time for session in sessions], [time(8), time(10), time(12), time(15)])
        self.assertTrue(all(session.facilitator_assignments.count() == 3 for session in sessions))
        self.assertFalse(ChildAttendance.objects.filter(event__in=events).exclude(attendance_status__in=AttendanceStatus.values).exists())
        self.assertFalse(ChildAttendance.objects.filter(event__in=events).exclude(age_group__branch=branch).exists())
        for attendance in FacilitatorAttendance.objects.filter(
            service_session__event__in=events
        ).select_related("service_session", "facilitator"):
            self.assertTrue(
                ServiceFacilitator.objects.filter(
                    service_session=attendance.service_session,
                    facilitator=attendance.facilitator,
                ).exists()
            )

        before = {
            "organizations": Organization.objects.count(),
            "branches": Branch.objects.count(),
            "children": Child.objects.count(),
            "facilitators": Facilitator.objects.count(),
            "events": Event.objects.count(),
            "sessions": ServiceSession.objects.count(),
            "assignments": ServiceFacilitator.objects.count(),
            "child_attendance": ChildAttendance.objects.count(),
            "facilitator_attendance": FacilitatorAttendance.objects.count(),
        }
        status_snapshot = list(ChildAttendance.objects.order_by("event_id", "child_id").values_list("event_id", "child_id", "attendance_status"))
        second_output = self.run_command()
        after = {
            "organizations": Organization.objects.count(),
            "branches": Branch.objects.count(),
            "children": Child.objects.count(),
            "facilitators": Facilitator.objects.count(),
            "events": Event.objects.count(),
            "sessions": ServiceSession.objects.count(),
            "assignments": ServiceFacilitator.objects.count(),
            "child_attendance": ChildAttendance.objects.count(),
            "facilitator_attendance": FacilitatorAttendance.objects.count(),
        }
        self.assertEqual(after, before)
        self.assertEqual(list(ChildAttendance.objects.order_by("event_id", "child_id").values_list("event_id", "child_id", "attendance_status")), status_snapshot)
        self.assertIn("225 children", output)
        self.assertIn("225 children", second_output)
        self.assertIn(DEFAULT_ADMIN_EMAIL, output)

    def test_rejects_child_counts_outside_demo_range(self):
        with self.assertRaisesMessage(CommandError, "between 40 and 50"):
            call_command("seed_watoto_sample_data", children_per_group=39, **self.command_options)
