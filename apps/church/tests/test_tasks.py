from datetime import date, time

from django.test import TestCase

from apps.organization.models import Branch, Organization
from apps.church.models import Event, ServiceSession
from apps.church.services import create_sunday_services
from apps.church.tasks import create_next_sunday_services


class AutomaticSundayTaskTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Task Church", slug="task-church")
        self.branch = Branch.objects.create(organization=self.organization, name="Central", code="CENTRAL")

    def test_uses_defaults_and_is_idempotent(self):
        first = create_next_sunday_services("2026-10-04")
        second = create_next_sunday_services("2026-10-04")
        event = Event.objects.get(branch=self.branch, event_date=date(2026, 10, 4))
        self.assertEqual(first, {"created": 1, "skipped": 0, "failed": 0})
        self.assertEqual(second, {"created": 0, "skipped": 1, "failed": 0})
        self.assertEqual(list(event.sessions.values_list("name", flat=True)), ["Morning Service", "10am Service", "Midday Service", "Afternoon Service"])

    def test_clones_schedule_without_assignments(self):
        previous = create_sunday_services(
            organization=self.organization, branch=self.branch, sunday_date=date(2026, 9, 27), location="Main Hall",
            sessions=[{"service_order": 1, "name": "Family Service", "start_time": time(9), "end_time": time(11), "location": "Room A", "notes": "Bring materials"}],
        )
        create_next_sunday_services("2026-10-04")
        event = Event.objects.get(branch=self.branch, event_date=date(2026, 10, 4))
        session = ServiceSession.objects.get(event=event)
        self.assertEqual(event.location, "Main Hall")
        self.assertEqual((session.name, session.start_time, session.location, session.notes), ("Family Service", time(9), "Room A", "Bring materials"))
        self.assertFalse(session.facilitator_assignments.exists())
        self.assertNotEqual(event.id, previous.id)
