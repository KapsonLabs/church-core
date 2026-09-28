from django.core.management.base import BaseCommand, CommandError

from apps.organization.models import Branch, Organization
from apps.church.models import AgeGroup


class Command(BaseCommand):
    help = "Create the default Age 10 through Age 14 groups for a branch."

    def add_arguments(self, parser):
        parser.add_argument("--organization", required=True)
        parser.add_argument("--branch", required=True)

    def handle(self, *args, **options):
        try:
            organization = Organization.objects.get(id=options["organization"])
            branch = Branch.objects.get(id=options["branch"], organization=organization)
        except (Organization.DoesNotExist, Branch.DoesNotExist) as exc:
            raise CommandError("Organization/branch pair does not exist.") from exc
        for age in range(10, 15):
            AgeGroup.objects.update_or_create(branch=branch, name=f"Age {age}", defaults={"organization": organization, "minimum_age": age, "maximum_age": age, "is_active": True})
        self.stdout.write(self.style.SUCCESS(f"Default age groups are ready for {branch}."))

