from django.core.management.base import BaseCommand

from apps.accounts.models import AccessPermission, Resource


PERMISSIONS = {
    "organizations": ["read", "manage"],
    "branches": ["read", "manage"],
    "members": ["read", "manage"],
    "roles": ["read", "manage"],
}


class Command(BaseCommand):
    help = "Create or update the boilerplate's core RBAC resources and permissions."

    def handle(self, *args, **options):
        for resource_code, actions in PERMISSIONS.items():
            resource, _ = Resource.objects.update_or_create(
                code=resource_code,
                defaults={"name": resource_code.replace("-", " ").title(), "is_active": True},
            )
            for action in actions:
                AccessPermission.objects.update_or_create(
                    resource=resource,
                    action=action,
                    defaults={"codename": f"{resource_code}.{action}", "is_active": True},
                )
        self.stdout.write(self.style.SUCCESS("Core permissions are ready."))
