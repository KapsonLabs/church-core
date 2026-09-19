from django.core.management.base import BaseCommand

from apps.accounts.models import AccessPermission, Resource


class Command(BaseCommand):
    help = "Create permission definitions for the optional info app."

    def handle(self, *args, **options):
        resource, _ = Resource.objects.get_or_create(code="info", defaults={"name": "Information"})
        for action in ("read", "manage"):
            AccessPermission.objects.get_or_create(resource=resource, action=action, defaults={"codename": f"info.{action}"})
        self.stdout.write(self.style.SUCCESS("Info permissions are ready."))
