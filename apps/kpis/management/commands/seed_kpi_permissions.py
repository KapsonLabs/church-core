from django.core.management.base import BaseCommand

from apps.accounts.models import AccessPermission, Resource


class Command(BaseCommand):
    help = "Create permission definitions for the optional KPI app."

    def handle(self, *args, **options):
        resource, _ = Resource.objects.get_or_create(code="kpis", defaults={"name": "KPIs"})
        for action in ("read", "manage"):
            AccessPermission.objects.get_or_create(resource=resource, action=action, defaults={"codename": f"kpis.{action}"})
        self.stdout.write(self.style.SUCCESS("KPI permissions are ready."))
