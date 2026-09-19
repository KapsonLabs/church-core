import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial"), ("organization", "0001_initial")]
    operations = [migrations.CreateModel(name="Role", fields=[
        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
        ("name", models.CharField(max_length=100)), ("slug", models.SlugField(max_length=100)),
        ("description", models.TextField(blank=True)), ("is_active", models.BooleanField(default=True)),
        ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
        ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="roles", to="organization.organization")),
        ("permissions", models.ManyToManyField(blank=True, related_name="roles", to="accounts.accesspermission")),
    ], options={"ordering": ["organization__name", "name"], "constraints": [
        models.UniqueConstraint(fields=("organization", "name"), name="unique_role_name_per_org"),
        models.UniqueConstraint(fields=("organization", "slug"), name="unique_role_slug_per_org"),
    ]})]
