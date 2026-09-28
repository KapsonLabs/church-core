import uuid

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import AccessPermission, Resource, Role
from apps.organization.models import Organization


PERMISSIONS = {
    "church-dashboard": ["read"],
    "church-children": ["read", "manage"],
    "church-age-groups": ["read", "manage"],
    "church-events": ["read", "manage"],
    "church-facilitators": ["read", "manage"],
    "church-attendance": ["read", "manage"],
    "church-reports": ["read"],
}

FACILITATOR_PERMISSIONS = {
    "church-dashboard.read", "church-children.read", "church-age-groups.read",
    "church-events.read", "church-events.manage", "church-facilitators.read",
    "church-attendance.read", "church-attendance.manage", "church-reports.read",
}


class Command(BaseCommand):
    help = "Create or update Children's Church permission resources."

    def add_arguments(self, parser):
        parser.add_argument(
            "--organization",
            help="Organization UUID or slug for which to create/update the Administrator role.",
        )

    def handle(self, *args, **options):
        permissions = []
        for code, actions in PERMISSIONS.items():
            resource, _ = Resource.objects.update_or_create(code=code, defaults={"name": code.replace("-", " ").title(), "is_active": True})
            for action in actions:
                permission, _ = AccessPermission.objects.update_or_create(resource=resource, action=action, defaults={"codename": f"{code}.{action}", "is_active": True})
                permissions.append(permission)

        identifier = options.get("organization")
        if identifier:
            filters = {"slug": identifier}
            try:
                filters = {"id": uuid.UUID(identifier)}
            except ValueError:
                pass
            organization = Organization.objects.filter(**filters).first()
            if not organization:
                raise CommandError(f"Organization '{identifier}' was not found.")
            role, _ = Role.objects.update_or_create(
                organization=organization,
                slug="administrator",
                defaults={
                    "name": "Administrator",
                    "description": "Full Children's Church administration access.",
                    "is_active": True,
                },
            )
            role.permissions.add(*permissions)
            facilitator_role = Role.objects.filter(organization=organization, slug="facilitator").first()
            if facilitator_role:
                facilitator_role.permissions.add(*(permission for permission in permissions if permission.codename in FACILITATOR_PERMISSIONS))
            self.stdout.write(self.style.SUCCESS(f"Administrator role is ready for {organization.name}."))
        self.stdout.write(self.style.SUCCESS("Children's Church permissions are ready."))
