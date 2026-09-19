from django.core.management.base import BaseCommand

from apps.crm.models import TicketCategory
from apps.accounts.models import AccessPermission, Resource


class Command(BaseCommand):
    help = "Create neutral CRM example categories."

    def handle(self, *args, **options):
        resource, _ = Resource.objects.get_or_create(code="crm", defaults={"name": "CRM"})
        for action in ("read", "manage"):
            AccessPermission.objects.get_or_create(
                resource=resource, action=action,
                defaults={"codename": f"crm.{action}"},
            )
        for name in ("General", "Technical support", "Billing"):
            TicketCategory.objects.get_or_create(name=name, defaults={"description": f"{name} requests"})
        self.stdout.write(self.style.SUCCESS("CRM example categories are ready."))
