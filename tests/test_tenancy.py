from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.organization.models import Branch, BranchMembership, Organization, OrganizationMembership
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

    def test_member_without_branch_permission_lists_only_active_memberships(self):
        facilitator = get_user_model().objects.create_user(email="facilitator@example.com", password="password")
        grant(facilitator, self.org_a)
        BranchMembership.objects.create(branch=self.branch_a, user=facilitator)
        unassigned = Branch.objects.create(organization=self.org_a, name="A2", code="A2")
        inactive_branch = Branch.objects.create(organization=self.org_a, name="A3", code="A3", is_active=False)
        BranchMembership.objects.create(branch=inactive_branch, user=facilitator)
        inactive_membership_branch = Branch.objects.create(organization=self.org_a, name="A4", code="A4")
        BranchMembership.objects.create(branch=inactive_membership_branch, user=facilitator, is_active=False)
        self.client.force_authenticate(facilitator)

        response = self.client.get("/api/v1/organizations/branches/", {"organization_id": self.org_a.id})

        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.json()["data"]["results"]}
        self.assertEqual(ids, {str(self.branch_a.id)})
        self.assertNotIn(str(unassigned.id), ids)

    def test_branch_reader_lists_all_organization_branches(self):
        inactive = Branch.objects.create(organization=self.org_a, name="A2", code="A2", is_active=False)

        response = self.client.get("/api/v1/organizations/branches/", {"organization_id": self.org_a.id})

        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.json()["data"]["results"]}
        self.assertEqual(ids, {str(self.branch_a.id), str(inactive.id)})

    def test_branch_membership_does_not_grant_branch_creation(self):
        facilitator = get_user_model().objects.create_user(email="facilitator@example.com", password="password")
        grant(facilitator, self.org_a)
        BranchMembership.objects.create(branch=self.branch_a, user=facilitator)
        self.client.force_authenticate(facilitator)

        response = self.client.post(
            "/api/v1/organizations/branches/",
            {"organization_id": self.org_a.id, "name": "Denied", "code": "DENIED"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

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

    def test_atomic_tenant_user_management(self):
        role = OrganizationMembership.objects.get(organization=self.org_a, user=self.user).role
        second_branch = Branch.objects.create(organization=self.org_a, name="A2", code="A2")
        url = f"/api/v1/organizations/{self.org_a.id}/users/"
        response = self.client.post(url, {
            "email": "new.member@example.com", "password": "A-secure-demo-password!",
            "first_name": "New", "last_name": "Member", "phone_number": "+256700000002",
            "role_id": str(role.id), "membership_is_active": True,
            "branch_ids": [str(self.branch_a.id), str(second_branch.id)],
        }, format="json")
        self.assertEqual(response.status_code, 201, response.json())
        created = get_user_model().objects.get(email="new.member@example.com")
        self.assertEqual(BranchMembership.objects.filter(user=created, is_active=True).count(), 2)

        detail = f"{url}{created.id}/"
        updated = self.client.patch(detail, {
            "first_name": "Updated", "membership_is_active": False,
            "branch_ids": [str(self.branch_a.id)],
        }, format="json")
        self.assertEqual(updated.status_code, 200, updated.json())
        created.refresh_from_db()
        self.assertEqual(created.first_name, "Updated")
        self.assertTrue(created.is_active)
        self.assertFalse(OrganizationMembership.objects.get(organization=self.org_a, user=created).is_active)
        self.assertFalse(BranchMembership.objects.filter(user=created, is_active=True).exists())

    def test_tenant_user_create_rolls_back_invalid_related_ids(self):
        foreign_role = grant(get_user_model().objects.create_user(email="foreign-role@example.com"), self.org_b)
        before = get_user_model().objects.count()
        response = self.client.post(f"/api/v1/organizations/{self.org_a.id}/users/", {
            "email": "must-not-exist@example.com", "password": "A-secure-demo-password!",
            "role_id": str(foreign_role.id), "branch_ids": [str(self.branch_b.id)],
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(get_user_model().objects.count(), before)
