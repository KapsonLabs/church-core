import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="Organization", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("name", models.CharField(max_length=255, unique=True)),
            ("slug", models.SlugField(max_length=255, unique=True)),
            ("description", models.TextField(blank=True)), ("email", models.EmailField(blank=True, max_length=254)),
            ("phone_number", models.CharField(blank=True, max_length=25)), ("website", models.URLField(blank=True)),
            ("physical_address", models.CharField(blank=True, max_length=500)),
            ("logo", models.ImageField(blank=True, upload_to="organization_logos/%Y/%m/%d/")),
            ("is_active", models.BooleanField(default=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
        ], options={"ordering": ["name"]}),
        migrations.CreateModel(name="Branch", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("name", models.CharField(max_length=255)), ("code", models.CharField(max_length=50)),
            ("email", models.EmailField(blank=True, max_length=254)), ("phone_number", models.CharField(blank=True, max_length=25)),
            ("address", models.CharField(blank=True, max_length=500)), ("city", models.CharField(blank=True, max_length=100)),
            ("country", models.CharField(blank=True, max_length=100)), ("is_active", models.BooleanField(default=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="branches", to="organization.organization")),
        ], options={"ordering": ["organization__name", "name"], "constraints": [models.UniqueConstraint(fields=("organization", "code"), name="unique_branch_code_per_org")]}),
        migrations.CreateModel(name="BranchSettings", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("timezone", models.CharField(default="UTC", max_length=50)), ("currency", models.CharField(default="USD", max_length=10)),
            ("language", models.CharField(default="en", max_length=10)), ("date_format", models.CharField(default="YYYY-MM-DD", max_length=20)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("branch", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="settings", to="organization.branch")),
        ]),
    ]
