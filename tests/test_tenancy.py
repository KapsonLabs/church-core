from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.organization.models import Branch, BranchMembership, Organization
from .helpers import grant


class TenantIsolationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(email="a@example.com", password="password")
        self.other = get_user_model().objects.create_user(email="b@example.com", password="password")
        self.org_a = Organization.objects.create(name="Alpha", slug="alpha")
        self.org_b = Organization.objects.create(name="Beta", slug="beta")
        grant(self.user, self.org_a, "organizations.read", "branches.read", "branches.manage", "members.read", "members.manage", "roles.read", "roles.manage")
        grant(self.other, self.org_b, "organizations.read", "branches.read", "branches.manage")
        self.branch_a = Branch.objects.create(organization=self.org_a, name="A1", code="A1")
        self.branch_b = Branch.objects.create(organization=self.org_b, name="B1", code="B1")
        self.client.force_authenticate(self.user)

    def test_organization_list_is_scoped(self):
        response = self.client.get("/api/v1/organizations/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.json()["data"]["results"]}
        self.assertEqual(ids, {str(self.org_a.id)})

    def test_cannot_list_retrieve_update_or_delete_other_tenant_branch(self):
        listing = self.client.get("/api/v1/organizations/branches/", {"organization_id": self.org_b.id})
        self.assertEqual(listing.status_code, 403)
        detail = f"/api/v1/organizations/{self.org_b.id}/branches/{self.branch_b.id}/"
        self.assertEqual(self.client.get(detail).status_code, 403)
        self.assertEqual(self.client.patch(detail, {"name": "Leaked"}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(detail).status_code, 403)

    def test_branch_membership_requires_organization_membership(self):
        outsider = get_user_model().objects.create_user(email="outsider@example.com", password="password")
        url = f"/api/v1/organizations/{self.org_a.id}/branches/{self.branch_a.id}/memberships/"
        denied = self.client.post(url, {"branch_id": self.branch_a.id, "user_id": outsider.id}, format="json")
        self.assertEqual(denied.status_code, 400)

        grant(outsider, self.org_a)
        accepted = self.client.post(url, {"branch_id": self.branch_a.id, "user_id": outsider.id}, format="json")
        self.assertEqual(accepted.status_code, 201)
        self.assertTrue(BranchMembership.objects.filter(branch=self.branch_a, user=outsider).exists())

    def test_role_is_tenant_scoped(self):
        foreign_role = grant(get_user_model().objects.create_user(email="foreign@example.com"), self.org_b)
        membership_url = f"/api/v1/organizations/{self.org_a.id}/memberships/"
        response = self.client.post(membership_url, {"organization_id": self.org_a.id, "user_id": self.user.id, "role_id": foreign_role.id}, format="json")
        self.assertEqual(response.status_code, 400)
