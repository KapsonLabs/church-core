from rest_framework.permissions import BasePermission

from apps.organization.models import Organization


def request_organization_id(request, view):
    return (view.kwargs.get("organization_id") or request.query_params.get("organization_id") or request.data.get("organization_id"))


class HasTenantPermission(BasePermission):
    message = "You do not have the required permission in this organization."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        required = getattr(view, "required_permissions", {})
        codename = required.get(request.method) if isinstance(required, dict) else required
        organization_id = request_organization_id(request, view)
        if not codename or not organization_id:
            return False
        organization = Organization.objects.filter(id=organization_id, is_active=True).first()
        return request.user.has_tenant_perm(codename, organization)


class IsOrganizationMember(BasePermission):
    message = "You are not an active member of this organization."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        organization_id = request_organization_id(request, view)
        return bool(organization_id) and request.user.organization_memberships.filter(
            organization_id=organization_id, is_active=True, organization__is_active=True
        ).exists()
