from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.organization.models import Branch, BranchMembership, Organization
from apps.church.models import AgeGroup, Child, ChildAttendance, Event, Facilitator, FacilitatorAttendance, ServiceFacilitator
from apps.church.services import create_sunday_services, finalize_sunday_attendance
from tests.helpers import grant


def next_sunday():
    today = date.today()
    return today + timedelta(days=(6 - today.weekday()) % 7)


def birthday_for_age(age):
    today = date.today()
    try:
        return today.replace(year=today.year - age)
    except ValueError:
        return today.replace(year=today.year - age, day=28)


class ChurchDomainTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Church Org", slug="church-org")
        self.branch = Branch.objects.create(organization=self.organization, name="Central", code="CENTRAL")
        self.user = get_user_model().objects.create_user(email="admin@example.com", password="password", first_name="Admin")
        grant(self.user, self.organization, "church-dashboard.read", "church-children.read", "church-children.manage", "church-age-groups.read", "church-age-groups.manage", "church-events.read", "church-events.manage", "church-facilitators.read", "church-facilitators.manage", "church-attendance.read", "church-attendance.manage", "church-reports.read")
        BranchMembership.objects.create(branch=self.branch, user=self.user)
        self.age_group = AgeGroup.objects.create(organization=self.organization, branch=self.branch, name="Age 10", minimum_age=10, maximum_age=10)

    def make_child(self, name="Amina"):
        return Child.objects.create(organization=self.organization, branch=self.branch, first_name=name, last_name="Child", date_of_birth=birthday_for_age(10), age_group=self.age_group, guardian_name="Guardian", guardian_contact=" 0700000000 ")

    def test_child_age_is_derived_from_dob_and_must_match_group(self):
        child = Child(organization=self.organization, branch=self.branch, first_name="No", last_name="Age", date_of_birth=birthday_for_age(11), age_group=self.age_group, guardian_name="G", guardian_contact="1")
        with self.assertRaises(ValidationError):
            child.full_clean()
        child.date_of_birth = birthday_for_age(10)
        child.full_clean()
        self.assertEqual(child.age, 10)
        self.assertEqual(child.guardian_contact, "1")

    def test_legacy_child_without_dob_has_unknown_age(self):
        child = Child(organization=self.organization, branch=self.branch, first_name="Legacy", last_name="Child", age_group=self.age_group, guardian_name="G", guardian_contact="1")
        child.full_clean()
        self.assertIsNone(child.age)

    def test_sunday_creation_is_atomic_and_rejects_duplicates(self):
        sunday = next_sunday()
        event = create_sunday_services(organization=self.organization, branch=self.branch, sunday_date=sunday, actor=self.user, sessions=[{"name": "First Service", "service_order": 1, "start_time": "08:00"}, {"name": "Second Service", "service_order": 2, "start_time": "10:00"}])
        self.assertEqual(event.sessions.count(), 2)
        with self.assertRaises(Exception):
            create_sunday_services(organization=self.organization, branch=self.branch, sunday_date=sunday, actor=self.user, sessions=[{"name": "Only", "service_order": 1, "start_time": "08:00"}])

    def test_finalize_creates_absences_and_is_idempotent(self):
        child = self.make_child()
        event = create_sunday_services(organization=self.organization, branch=self.branch, sunday_date=next_sunday(), actor=self.user, sessions=[{"name": "First", "service_order": 1, "start_time": "08:00"}])
        finalize_sunday_attendance(event, self.user)
        finalize_sunday_attendance(event, self.user)
        record = ChildAttendance.objects.get(child=child, event=event, service_session=None)
        self.assertEqual(record.attendance_status, "absent")
        self.assertEqual(record.age_group, self.age_group)

    def test_facilitator_attendance_requires_assignment(self):
        facilitator = Facilitator.objects.create(organization=self.organization, branch=self.branch, user=self.user)
        event = create_sunday_services(organization=self.organization, branch=self.branch, sunday_date=next_sunday(), actor=self.user, sessions=[{"name": "First", "service_order": 1, "start_time": "08:00"}])
        attendance = FacilitatorAttendance(service_session=event.sessions.get(), facilitator=facilitator, attendance_status="present", recorded_by=self.user)
        with self.assertRaises(ValidationError):
            attendance.full_clean()
        ServiceFacilitator.objects.create(service_session=event.sessions.get(), facilitator=facilitator, assigned_by=self.user)
        attendance.full_clean()


class ChurchApiTests(ChurchDomainTests):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.scope = {"organization_id": str(self.organization.id), "branch_id": str(self.branch.id)}

    def test_child_crud_is_branch_scoped(self):
        response = self.client.post("/api/v1/church/children/", {**self.scope, "first_name": "Amina", "last_name": "Child", "date_of_birth": birthday_for_age(10).isoformat(), "age_group": str(self.age_group.id), "guardian_name": "Parent", "guardian_contact": "0700", "is_active": False}, format="json")
        self.assertEqual(response.status_code, 201, response.json())
        self.assertTrue(response.json()["data"]["is_active"])
        self.assertNotIn("recorded_age", response.json()["data"])
        listed = self.client.get("/api/v1/church/children/", self.scope)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["data"]["count"], 1)

    def test_child_create_requires_date_of_birth_and_update_can_deactivate(self):
        missing = self.client.post("/api/v1/church/children/", {**self.scope, "first_name": "Amina", "last_name": "Child", "age_group": str(self.age_group.id), "guardian_name": "Parent", "guardian_contact": "0700"}, format="json")
        self.assertEqual(missing.status_code, 400)
        self.assertIn("date_of_birth", missing.json()["errors"])
        child = self.make_child()
        changed = self.client.patch(f"/api/v1/church/children/{child.id}/", {**self.scope, "is_active": False}, format="json")
        self.assertEqual(changed.status_code, 200, changed.json())
        child.refresh_from_db()
        self.assertFalse(child.is_active)

    def test_age_group_and_event_creation_use_existing_manage_permissions(self):
        group_response = self.client.post(
            "/api/v1/church/age-groups/",
            {**self.scope, "name": "Age 11", "minimum_age": 11, "maximum_age": 11, "is_active": True},
            format="json",
        )
        event_response = self.client.post(
            "/api/v1/church/events/",
            {**self.scope, "name": "Children's Conference", "event_type": "conference", "event_date": date.today().isoformat(), "status": "scheduled"},
            format="json",
        )
        self.assertEqual(group_response.status_code, 201, group_response.json())
        self.assertEqual(event_response.status_code, 201, event_response.json())

    def test_bulk_attendance_rejects_duplicate_rows_by_upserting(self):
        child = self.make_child()
        event = create_sunday_services(organization=self.organization, branch=self.branch, sunday_date=next_sunday(), actor=self.user, sessions=[{"name": "First", "service_order": 1, "start_time": "08:00"}])
        session = event.sessions.get()
        url = f"/api/v1/church/service-sessions/{session.id}/attendance/bulk/"
        first = self.client.post(url, {**self.scope, "rows": [{"child_id": str(child.id), "attendance_status": "present"}]}, format="json")
        second = self.client.post(url, {**self.scope, "rows": [{"child_id": str(child.id), "attendance_status": "late"}]}, format="json")
        self.assertEqual(first.status_code, 200, first.json())
        self.assertEqual(second.status_code, 200, second.json())
        self.assertEqual(ChildAttendance.objects.get(child=child, service_session=session).attendance_status, "late")

    def test_sunday_api_returns_sessions_and_staff_totals(self):
        response = self.client.post("/api/v1/church/sunday-services/create/", {**self.scope, "sunday_date": next_sunday().isoformat(), "sessions": [{"name": "First Service", "service_order": 1, "start_time": "08:00"}]}, format="json")
        self.assertEqual(response.status_code, 201, response.json())
        session = response.json()["data"]["sessions"][0]
        self.assertEqual(session["attendance_summary"]["present"], 0)
        self.assertEqual(session["facilitators_assigned"], 0)

    def test_dashboard_monthly_attendance_uses_finalized_sunday_outcomes(self):
        child = self.make_child()
        year = date.today().year
        january_sunday = date(year, 1, 1) + timedelta(days=(6 - date(year, 1, 1).weekday()) % 7)
        event = Event.objects.create(organization=self.organization, branch=self.branch, name="January Sunday", event_type=Event.Type.SUNDAY_SERVICE, event_date=january_sunday, status=Event.Status.COMPLETED, attendance_finalized_at=timezone.now(), created_by=self.user)
        ChildAttendance.objects.create(child=child, event=event, age_group=self.age_group, attendance_status="absent", recorded_by=self.user)
        ChildAttendance.objects.create(child=child, event=event, service_session=event.sessions.create(name="Morning", service_order=1, start_time="08:00"), age_group=self.age_group, attendance_status="late", recorded_by=self.user)
        excused = self.make_child("Excused")
        ChildAttendance.objects.create(child=excused, event=event, age_group=self.age_group, attendance_status="excused", recorded_by=self.user)
        response = self.client.get("/api/v1/church/dashboard/summary/", self.scope)
        self.assertEqual(response.status_code, 200, response.json())
        monthly = response.json()["data"]["monthly_attendance"]
        self.assertEqual(monthly["year"], year)
        self.assertEqual(len(monthly["months"]), 12)
        self.assertEqual(monthly["months"][0], {"month": 1, "label": "January", "present": 1, "absent": 1})
        self.assertTrue(all(row["present"] == row["absent"] == 0 for row in monthly["months"][1:]))

    def test_ordinary_event_bulk_attendance(self):
        child = self.make_child()
        event = Event.objects.create(organization=self.organization, branch=self.branch, name="Outreach", event_type=Event.Type.OUTREACH, event_date=date.today(), created_by=self.user)
        response = self.client.post(f"/api/v1/church/events/{event.id}/attendance/bulk/", {**self.scope, "rows": [{"child_id": str(child.id), "attendance_status": "present"}]}, format="json")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertTrue(ChildAttendance.objects.filter(child=child, event=event, service_session=None, attendance_status="present").exists())

    def test_cross_branch_related_ids_are_rejected(self):
        other_branch = Branch.objects.create(organization=self.organization, name="Other", code="OTHER")
        other_group = AgeGroup.objects.create(organization=self.organization, branch=other_branch, name="Age 10", minimum_age=10, maximum_age=10)
        response = self.client.post("/api/v1/church/children/", {**self.scope, "first_name": "Wrong", "last_name": "Branch", "date_of_birth": birthday_for_age(10).isoformat(), "age_group": str(other_group.id), "guardian_name": "Parent", "guardian_contact": "0700"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_facilitator_update_changes_account_and_profile_atomically(self):
        facilitator = Facilitator.objects.create(organization=self.organization, branch=self.branch, user=self.user)
        response = self.client.patch(
            f"/api/v1/church/facilitators/{facilitator.id}/",
            {
                **self.scope,
                "first_name": "Grace",
                "last_name": "Namakula",
                "email": "grace@example.com",
                "phone_number": "+256700000001",
                "notes": "Lead teacher",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.json())
        self.user.refresh_from_db()
        facilitator.refresh_from_db()
        self.assertEqual(self.user.email, "grace@example.com")
        self.assertEqual(response.json()["data"]["first_name"], "Grace")
        self.assertEqual(facilitator.notes, "Lead teacher")

    def test_duplicate_facilitator_email_rolls_back_profile_update(self):
        facilitator = Facilitator.objects.create(organization=self.organization, branch=self.branch, user=self.user, notes="Original")
        get_user_model().objects.create_user(email="taken@example.com", password="password")
        response = self.client.patch(
            f"/api/v1/church/facilitators/{facilitator.id}/",
            {**self.scope, "email": "taken@example.com", "notes": "Changed"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        facilitator.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(facilitator.notes, "Original")
        self.assertEqual(self.user.email, "admin@example.com")

    def test_branch_membership_is_required(self):
        outsider = get_user_model().objects.create_user(email="outsider@example.com")
        grant(outsider, self.organization, "church-children.read")
        self.client.force_authenticate(outsider)
        response = self.client.get("/api/v1/church/children/", self.scope)
        self.assertEqual(response.status_code, 403)


class ChurchPermissionCommandTests(TestCase):
    def test_organization_option_creates_idempotent_administrator_role(self):
        organization = Organization.objects.create(name="Watoto Ministries", slug="watoto-ministries")
        facilitator_role = Role.objects.create(organization=organization, name="Facilitator", slug="facilitator")
        call_command("seed_church_permissions", organization=organization.slug)
        call_command("seed_church_permissions", organization=str(organization.id))
        role = Role.objects.get(organization=organization, slug="administrator")
        self.assertEqual(role.name, "Administrator")
        self.assertEqual(role.permissions.filter(codename__startswith="church-").count(), 12)
        facilitator_role.refresh_from_db()
        self.assertTrue(facilitator_role.permissions.filter(codename="church-events.manage").exists())
        self.assertFalse(facilitator_role.permissions.filter(codename="church-age-groups.manage").exists())
        self.assertFalse(facilitator_role.permissions.filter(codename="church-facilitators.manage").exists())
