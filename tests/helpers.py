from apps.accounts.models import AccessPermission, Resource, Role
from apps.organization.models import OrganizationMembership


def grant(user, organization, *codenames):
    role = Role.objects.create(organization=organization, name=f"Role for {user.email}", slug=f"role-{user.id}")
    for codename in codenames:
        resource_code, action = codename.split(".", 1)
        resource, _ = Resource.objects.get_or_create(code=resource_code, defaults={"name": resource_code.title()})
        permission, _ = AccessPermission.objects.get_or_create(
            codename=codename,
            defaults={"resource": resource, "action": action},
        )
        role.permissions.add(permission)
    OrganizationMembership.objects.create(user=user, organization=organization, role=role)
    return role
