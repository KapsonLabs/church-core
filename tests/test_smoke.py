from importlib import import_module
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from redis.exceptions import ConnectionError
from rest_framework.test import APIClient


class SmokeTests(TestCase):
    def test_health_and_admin_start(self):
        self.assertEqual(self.client.get(reverse("health")).json(), {"status": "ok"})
        self.assertEqual(self.client.get("/admin/login/").status_code, 200)

    def test_core_asgi_does_not_import_optional_apps(self):
        module = import_module("config.asgi")
        self.assertIsNotNone(module.application)

    @patch("config.health.Redis.from_url")
    def test_readiness_reports_dependency_failure(self, redis_from_url):
        redis_from_url.return_value.ping.side_effect = ConnectionError()
        response = self.client.get(reverse("readiness"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["dependencies"]["redis"], "unavailable")


class AuthenticationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(email="member@example.com", password="strong-password-123")

    def test_login_refresh_logout_and_inactive_rejection(self):
        login = self.client.post("/api/v1/accounts/auth/login/", {"email": self.user.email, "password": "strong-password-123"}, format="json")
        self.assertEqual(login.status_code, 200)
        tokens = login.json()["data"]
        refresh = self.client.post("/api/v1/accounts/auth/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(refresh.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        rotated_refresh = refresh.json()["data"]["refresh"]
        self.assertEqual(self.client.post("/api/v1/accounts/auth/logout/", {"refresh": rotated_refresh}, format="json").status_code, 204)

        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.client.credentials()
        denied = self.client.post("/api/v1/accounts/auth/login/", {"email": self.user.email, "password": "strong-password-123"}, format="json")
        self.assertEqual(denied.status_code, 400)

    def test_password_change(self):
        self.client.force_authenticate(self.user)
        response = self.client.post("/api/v1/accounts/me/password/", {"current_password": "strong-password-123", "new_password": "different-strong-password-456"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("different-strong-password-456"))
