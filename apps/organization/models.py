import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=25, blank=True)
    website = models.URLField(blank=True)
    physical_address = models.CharField(max_length=500, blank=True)
    logo = models.ImageField(upload_to="organization_logos/%Y/%m/%d/", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Branch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="branches")
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=25, blank=True)
    address = models.CharField(max_length=500, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization__name", "name"]
        constraints = [models.UniqueConstraint(fields=["organization", "code"], name="unique_branch_code_per_org")]

    def __str__(self):
        return f"{self.organization} - {self.name}"


class BranchSettings(models.Model):
    branch = models.OneToOneField(Branch, on_delete=models.CASCADE, related_name="settings")
    timezone = models.CharField(max_length=50, default="UTC")
    currency = models.CharField(max_length=10, default="USD")
    language = models.CharField(max_length=10, default="en")
    date_format = models.CharField(max_length=20, default="YYYY-MM-DD")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings for {self.branch}"


class OrganizationMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="organization_memberships")
    role = models.ForeignKey("accounts.Role", on_delete=models.SET_NULL, null=True, blank=True, related_name="memberships")
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "user"], name="unique_org_membership")]

    def clean(self):
        if self.role and self.role.organization_id != self.organization_id:
            raise ValidationError({"role": "Role must belong to the same organization."})

    def __str__(self):
        return f"{self.user} @ {self.organization}"


class BranchMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="branch_memberships")
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["branch", "user"], name="unique_branch_membership")]

    def clean(self):
        if self.user_id and self.branch_id and not OrganizationMembership.objects.filter(
            user_id=self.user_id, organization_id=self.branch.organization_id, is_active=True
        ).exists():
            raise ValidationError({"user": "User must be an active organization member first."})

    def __str__(self):
        return f"{self.user} @ {self.branch}"
