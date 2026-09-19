import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("organization", "0001_initial"), ("accounts", "0002_role"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="OrganizationMembership", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("is_active", models.BooleanField(default=True)), ("joined_at", models.DateTimeField(auto_now_add=True)),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="organization.organization")),
            ("role", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="memberships", to="accounts.role")),
            ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="organization_memberships", to=settings.AUTH_USER_MODEL)),
        ], options={"constraints": [models.UniqueConstraint(fields=("organization", "user"), name="unique_org_membership")]}),
        migrations.CreateModel(name="BranchMembership", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("is_active", models.BooleanField(default=True)), ("joined_at", models.DateTimeField(auto_now_add=True)),
            ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="organization.branch")),
            ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="branch_memberships", to=settings.AUTH_USER_MODEL)),
        ], options={"constraints": [models.UniqueConstraint(fields=("branch", "user"), name="unique_branch_membership")]}),
    ]
