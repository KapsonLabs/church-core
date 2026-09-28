from django.contrib.auth import get_user_model
from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import HasTenantPermission, IsOrganizationMember
from .models import Branch, BranchMembership, BranchSettings, Organization, OrganizationMembership
from .serializers import BranchMembershipSerializer, BranchSerializer, BranchSettingsSerializer, OrganizationMembershipSerializer, OrganizationSerializer, TenantUserSerializer


class OrganizationListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationSerializer

    def get_queryset(self):
        queryset = Organization.objects.annotate(branch_count=Count("branches")).order_by("name")
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(memberships__user=self.request.user, memberships__is_active=True).distinct()

    def perform_create(self, serializer):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Only platform administrators can create organizations.")
        serializer.save()


class OrganizationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]
    lookup_url_kwarg = "organization_id"

    @property
    def required_permissions(self):
        return {}

    def get_queryset(self):
        queryset = Organization.objects.annotate(branch_count=Count("branches")).order_by("name")
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(memberships__user=self.request.user, memberships__is_active=True)

    def _check_write(self):
        organization = self.get_object()
        if not self.request.user.has_tenant_perm("organizations.manage", organization):
            raise PermissionDenied("Missing organizations.manage permission.")

    def perform_update(self, serializer):
        self._check_write()
        serializer.save()

    def perform_destroy(self, instance):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Only platform administrators can delete organizations.")
        instance.delete()


class BranchListCreateView(generics.ListCreateAPIView):
    serializer_class = BranchSerializer
    required_permissions = {"POST": "branches.manage"}

    def get_permissions(self):
        permission_classes = [IsAuthenticated]
        if self.request.method == "POST":
            permission_classes.append(HasTenantPermission)
        else:
            permission_classes.append(IsOrganizationMember)
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        organization_id = self.request.query_params.get("organization_id")
        queryset = Branch.objects.filter(organization_id=organization_id)
        organization = Organization.objects.filter(id=organization_id, is_active=True).first()
        if self.request.user.is_superuser or self.request.user.has_tenant_perm("branches.read", organization):
            return queryset
        return queryset.filter(
            is_active=True,
            memberships__user=self.request.user,
            memberships__is_active=True,
        ).distinct()


class BranchDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated, HasTenantPermission]
    required_permissions = {"GET": "branches.read", "PUT": "branches.manage", "PATCH": "branches.manage", "DELETE": "branches.manage"}

    def get_queryset(self):
        return Branch.objects.filter(organization_id=self.kwargs["organization_id"])


class BranchSettingsView(generics.RetrieveUpdateAPIView):
    serializer_class = BranchSettingsSerializer
    permission_classes = [IsAuthenticated, HasTenantPermission]
    required_permissions = {"GET": "branches.read", "PUT": "branches.manage", "PATCH": "branches.manage"}
    lookup_url_kwarg = "branch_id"

    def get_queryset(self):
        return BranchSettings.objects.filter(branch__organization_id=self.kwargs["organization_id"])

    def get_object(self):
        branch = get_object_or_404(Branch, id=self.kwargs["branch_id"], organization_id=self.kwargs["organization_id"])
        settings_object, _ = BranchSettings.objects.get_or_create(branch=branch)
        self.check_object_permissions(self.request, settings_object)
        return settings_object


class OrganizationMembershipListCreateView(generics.ListCreateAPIView):
    serializer_class = OrganizationMembershipSerializer
    permission_classes = [IsAuthenticated, HasTenantPermission]
    required_permissions = {"GET": "members.read", "POST": "members.manage"}

    def get_queryset(self):
        return OrganizationMembership.objects.filter(organization_id=self.kwargs["organization_id"]).select_related("user", "role")

    def perform_create(self, serializer):
        serializer.save(organization_id=self.kwargs["organization_id"])


class OrganizationMembershipDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = OrganizationMembershipSerializer
    permission_classes = [IsAuthenticated, HasTenantPermission]
    required_permissions = {"GET": "members.read", "PUT": "members.manage", "PATCH": "members.manage", "DELETE": "members.manage"}

    def get_queryset(self):
        return OrganizationMembership.objects.filter(organization_id=self.kwargs["organization_id"]).select_related("user", "role")


class BranchMembershipListCreateView(generics.ListCreateAPIView):
    serializer_class = BranchMembershipSerializer
    permission_classes = [IsAuthenticated, HasTenantPermission]
    required_permissions = {"GET": "members.read", "POST": "members.manage"}

    def get_queryset(self):
        return BranchMembership.objects.filter(branch_id=self.kwargs["branch_id"], branch__organization_id=self.kwargs["organization_id"]).select_related("user", "branch")

    def perform_create(self, serializer):
        branch = get_object_or_404(
            Branch,
            id=self.kwargs["branch_id"],
            organization_id=self.kwargs["organization_id"],
        )
        serializer.save(branch=branch)


class BranchMembershipDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BranchMembershipSerializer
    permission_classes = [IsAuthenticated, HasTenantPermission]
    required_permissions = {"GET": "members.read", "PUT": "members.manage", "PATCH": "members.manage", "DELETE": "members.manage"}

    def get_queryset(self):
        return BranchMembership.objects.filter(branch__organization_id=self.kwargs["organization_id"])


class TenantUserListCreateView(generics.ListCreateAPIView):
    serializer_class = TenantUserSerializer
    permission_classes = [IsAuthenticated, HasTenantPermission]
    required_permissions = {"GET": "members.read", "POST": "members.manage"}

    def get_queryset(self):
        return get_user_model().objects.filter(organization_memberships__organization_id=self.kwargs["organization_id"]).distinct().order_by("first_name", "last_name", "email")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["organization"] = get_object_or_404(Organization, id=self.kwargs["organization_id"], is_active=True)
        return context


class TenantUserDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = TenantUserSerializer
    permission_classes = [IsAuthenticated, HasTenantPermission]
    required_permissions = {"GET": "members.read", "PUT": "members.manage", "PATCH": "members.manage"}
    lookup_url_kwarg = "user_id"

    def get_queryset(self):
        return get_user_model().objects.filter(organization_memberships__organization_id=self.kwargs["organization_id"]).distinct()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["organization"] = get_object_or_404(Organization, id=self.kwargs["organization_id"], is_active=True)
        return context
