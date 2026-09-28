from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.organization.models import Branch, Organization
from apps.church.services import create_sunday_services


class Command(BaseCommand):
    help = "Create a Sunday event and numbered service sessions."

    def add_arguments(self, parser):
        parser.add_argument("--organization", required=True)
        parser.add_argument("--branch", required=True)
        parser.add_argument("--date", required=True, help="YYYY-MM-DD")
        parser.add_argument("--service", action="append", required=True, help='Repeat as "Name,HH:MM"')
        parser.add_argument("--actor-email")

    def handle(self, *args, **options):
        try:
            organization = Organization.objects.get(id=options["organization"])
            branch = Branch.objects.get(id=options["branch"], organization=organization)
            sunday = datetime.strptime(options["date"], "%Y-%m-%d").date()
            actor = get_user_model().objects.filter(email=options.get("actor_email")).first() if options.get("actor_email") else None
            sessions = []
            for order, value in enumerate(options["service"], 1):
                name, start = value.rsplit(",", 1)
                sessions.append({"name": name.strip(), "service_order": order, "start_time": datetime.strptime(start.strip(), "%H:%M").time()})
            event = create_sunday_services(organization=organization, branch=branch, sunday_date=sunday, sessions=sessions, actor=actor)
        except (ValueError, Organization.DoesNotExist, Branch.DoesNotExist) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Created {event}."))

