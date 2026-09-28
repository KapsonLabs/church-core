from rest_framework.permissions import BasePermission

from apps.organization.models import Branch, Organization


def scope_ids(request):
    organization_id = request.query_params.get("organization_id") or request.data.get("organization_id")
    branch_id = request.query_params.get("branch_id") or request.data.get("branch_id")
    return organization_id, branch_id


class HasChurchPermission(BasePermission):
    message = "You do not have access to this church branch."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        organization_id, branch_id = scope_ids(request)
        if not organization_id or not branch_id:
            self.message = "organization_id and branch_id are required."
            return False
        if not Branch.objects.filter(id=branch_id, organization_id=organization_id, is_active=True).exists():
            return False
        if request.user.is_superuser:
            return True
        organization = Organization.objects.filter(id=organization_id, is_active=True).first()
        required = getattr(view, "required_permissions", {})
        codename = required.get(request.method) if isinstance(required, dict) else required
        return bool(
            organization
            and codename
            and request.user.has_tenant_perm(codename, organization)
            and request.user.branch_memberships.filter(branch_id=branch_id, is_active=True).exists()
        )

