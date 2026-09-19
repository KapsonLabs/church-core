from importlib import import_module
from unittest import skipUnless

from django.conf import settings
from django.test import SimpleTestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.organization.models import Organization
from tests.helpers import grant


@skipUnless("apps.crm" in settings.INSTALLED_APPS, "optional apps are disabled")
class OptionalAppTests(SimpleTestCase):
    def test_example_url_modules_import_when_apps_are_enabled(self):
        for module_name in ("apps.crm.urls", "apps.info.urls", "apps.kpis.urls"):
            self.assertIsNotNone(import_module(module_name).urlpatterns)

    def test_kpi_tasks_import(self):
        self.assertIsNotNone(import_module("apps.kpis.tasks"))

    def test_crm_websocket_routes_import(self):
        self.assertIsNotNone(import_module("apps.crm.routing").websocket_urlpatterns)


@skipUnless("apps.info" in settings.INSTALLED_APPS, "optional apps are disabled")
class OptionalInfoTenantTests(APITestCase):
    def test_categories_are_tenant_scoped(self):
        from apps.info.models import Category

        user = get_user_model().objects.create_user(email="info@example.com")
        org_a = Organization.objects.create(name="Info A", slug="info-a")
        org_b = Organization.objects.create(name="Info B", slug="info-b")
        grant(user, org_a, "info.read", "info.manage")
        category_a = Category.objects.create(organization=org_a, name="A", slug="a")
        category_b = Category.objects.create(organization=org_b, name="B", slug="b")
        self.client.force_authenticate(user)

        listing = self.client.get("/api/v1/info/categories/", {"organization_id": org_a.id})
        self.assertEqual(listing.status_code, 200)
        self.assertEqual([item["id"] for item in listing.json()["data"]], [str(category_a.id)])

        hidden = self.client.get(f"/api/v1/info/categories/{category_b.id}/", {"organization_id": org_a.id})
        self.assertEqual(hidden.status_code, 404)
