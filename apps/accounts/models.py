import uuid

from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserManager(DjangoUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Email is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("Superuser must have is_staff=True and is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_("email address"), unique=True)
    username = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(max_length=25, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        ordering = ["email"]

    def __str__(self):
        return self.email

    def has_tenant_perm(self, codename, organization):
        if self.is_superuser:
            return True
        if not self.is_active or organization is None:
            return False
        return self.organization_memberships.filter(
            organization=organization,
            is_active=True,
            role__is_active=True,
            role__permissions__codename=codename,
            role__permissions__is_active=True,
        ).exists()

    def get_tenant_permissions(self, organization):
        if not organization:
            return set()
        if self.is_superuser:
            return set(AccessPermission.objects.filter(is_active=True).values_list("codename", flat=True))
        return set(
            AccessPermission.objects.filter(
                is_active=True,
                roles__is_active=True,
                roles__memberships__user=self,
                roles__memberships__organization=organization,
                roles__memberships__is_active=True,
            ).values_list("codename", flat=True)
        )


class Resource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    code = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AccessPermission(models.Model):
    ACTION_CHOICES = [
        ("create", "Create"), ("read", "Read"), ("update", "Update"),
        ("delete", "Delete"), ("manage", "Manage"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name="permissions")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    codename = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["resource__code", "action"]
        constraints = [models.UniqueConstraint(fields=["resource", "action"], name="unique_resource_action")]

    def __str__(self):
        return self.codename


class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organization.Organization", on_delete=models.CASCADE, related_name="roles")
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(AccessPermission, related_name="roles", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="unique_role_name_per_org"),
            models.UniqueConstraint(fields=["organization", "slug"], name="unique_role_slug_per_org"),
        ]

    def __str__(self):
        return f"{self.organization}: {self.name}"
