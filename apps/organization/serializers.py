from django.contrib.auth import get_user_model
from django.contrib.auth import password_validation
from django.db import transaction
from rest_framework import serializers

from apps.accounts.models import Role
from .models import Branch, BranchMembership, BranchSettings, Organization, OrganizationMembership

User = get_user_model()


class OrganizationShortDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "slug"]


class BranchShortDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "name", "code"]


class OrganizationSerializer(serializers.ModelSerializer):
    branch_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "description", "email", "phone_number", "website", "physical_address", "logo", "is_active", "branch_count", "created_at", "updated_at"]
        read_only_fields = ["id", "branch_count", "created_at", "updated_at"]


class BranchSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField()

    class Meta:
        model = Branch
        fields = ["id", "organization_id", "name", "code", "email", "phone_number", "address", "city", "country", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        if self.instance and "organization_id" in attrs and attrs["organization_id"] != self.instance.organization_id:
            raise serializers.ValidationError({"organization_id": "A branch cannot be moved to another organization."})
        return attrs


class BranchSettingsSerializer(serializers.ModelSerializer):
    branch_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = BranchSettings
        fields = ["branch_id", "timezone", "currency", "language", "date_format", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class OrganizationMembershipSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(source="user", queryset=User.objects.all())
    role_id = serializers.PrimaryKeyRelatedField(source="role", queryset=Role.objects.filter(is_active=True), allow_null=True, required=False)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model = OrganizationMembership
        fields = ["id", "organization_id", "user_id", "user_email", "role_id", "role_name", "is_active", "joined_at"]
        read_only_fields = ["id", "joined_at"]

    def validate(self, attrs):
        organization_id = attrs.get("organization_id", getattr(self.instance, "organization_id", None))
        if organization_id is None:
            organization_id = self.context["view"].kwargs.get("organization_id")
        role = attrs.get("role")
        if role and role.organization_id != organization_id:
            raise serializers.ValidationError({"role_id": "Role must belong to this organization."})
        if self.instance and organization_id != self.instance.organization_id:
            raise serializers.ValidationError({"organization_id": "A membership cannot be moved."})
        return attrs


class BranchMembershipSerializer(serializers.ModelSerializer):
    branch_id = serializers.UUIDField(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(source="user", queryset=User.objects.all())
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = BranchMembership
        fields = ["id", "branch_id", "user_id", "user_email", "is_active", "joined_at"]
        read_only_fields = ["id", "joined_at"]

    def validate(self, attrs):
        branch_id = attrs.get("branch_id", getattr(self.instance, "branch_id", None))
        if branch_id is None:
            branch_id = self.context["view"].kwargs.get("branch_id")
        user = attrs.get("user", getattr(self.instance, "user", None))
        branch = Branch.objects.filter(id=branch_id).first()
        if not branch:
            raise serializers.ValidationError({"branch_id": "Branch does not exist."})
        if user and not OrganizationMembership.objects.filter(user=user, organization=branch.organization, is_active=True).exists():
            raise serializers.ValidationError({"user_id": "User must first be an active organization member."})
        if self.instance and branch_id != self.instance.branch_id:
            raise serializers.ValidationError({"branch_id": "A membership cannot be moved."})
        return attrs


class TenantUserSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, required=False)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    role_id = serializers.UUIDField(required=False, allow_null=True)
    role_name = serializers.CharField(read_only=True)
    membership_is_active = serializers.BooleanField(default=True)
    branch_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def _organization(self):
        return self.context["organization"]

    def validate(self, attrs):
        organization = self._organization()
        if not self.instance and not attrs.get("password"):
            raise serializers.ValidationError({"password": "This field is required."})
        if attrs.get("password"):
            password_validation.validate_password(attrs["password"], self.instance)
        email = attrs.get("email")
        if email and User.objects.exclude(pk=getattr(self.instance, "pk", None)).filter(email__iexact=email).exists():
            raise serializers.ValidationError({"email": "A user with this email already exists."})
        role_id = attrs.get("role_id")
        if role_id and not Role.objects.filter(id=role_id, organization=organization, is_active=True).exists():
            raise serializers.ValidationError({"role_id": "Role must belong to this organization and be active."})
        branch_ids = set(attrs.get("branch_ids", []))
        valid_ids = set(Branch.objects.filter(id__in=branch_ids, organization=organization, is_active=True).values_list("id", flat=True))
        if valid_ids != branch_ids:
            raise serializers.ValidationError({"branch_ids": "One or more branches are invalid for this organization."})
        return attrs

    def to_representation(self, user):
        organization = self._organization()
        membership = user.organization_memberships.select_related("role").get(organization=organization)
        branch_ids = user.branch_memberships.filter(branch__organization=organization, is_active=True).values_list("branch_id", flat=True)
        return {
            "id": str(user.id), "email": user.email, "first_name": user.first_name,
            "last_name": user.last_name, "phone_number": user.phone_number,
            "role_id": str(membership.role_id) if membership.role_id else None,
            "role_name": membership.role.name if membership.role else None,
            "membership_is_active": membership.is_active,
            "branch_ids": [str(value) for value in branch_ids],
            "created_at": user.created_at, "updated_at": user.updated_at,
        }

    def _sync_branches(self, user, branch_ids, active):
        organization = self._organization()
        selected = set(branch_ids) if active else set()
        existing = {row.branch_id: row for row in user.branch_memberships.filter(branch__organization=organization)}
        for branch in Branch.objects.filter(organization=organization, id__in=selected):
            membership = existing.pop(branch.id, None)
            if membership:
                if not membership.is_active:
                    membership.is_active = True
                    membership.save(update_fields=["is_active"])
            else:
                BranchMembership.objects.create(branch=branch, user=user, is_active=True)
        for membership in existing.values():
            if membership.is_active:
                membership.is_active = False
                membership.save(update_fields=["is_active"])

    @transaction.atomic
    def create(self, validated_data):
        organization = self._organization()
        password = validated_data.pop("password")
        role_id = validated_data.pop("role_id", None)
        branch_ids = validated_data.pop("branch_ids", [])
        membership_is_active = validated_data.pop("membership_is_active", True)
        user = User.objects.create_user(password=password, **validated_data)
        OrganizationMembership.objects.create(organization=organization, user=user, role_id=role_id, is_active=membership_is_active)
        self._sync_branches(user, branch_ids, membership_is_active)
        return user

    @transaction.atomic
    def update(self, user, validated_data):
        organization = self._organization()
        validated_data.pop("password", None)
        membership = user.organization_memberships.get(organization=organization)
        role_id = validated_data.pop("role_id", membership.role_id)
        branch_ids = validated_data.pop("branch_ids", list(user.branch_memberships.filter(branch__organization=organization, is_active=True).values_list("branch_id", flat=True)))
        membership_is_active = validated_data.pop("membership_is_active", membership.is_active)
        for field, value in validated_data.items():
            setattr(user, field, value)
        user.full_clean(exclude=["password", "username"])
        user.save()
        membership.role_id = role_id
        membership.is_active = membership_is_active
        membership.full_clean()
        membership.save(update_fields=["role", "is_active"])
        self._sync_branches(user, branch_ids, membership_is_active)
        return user
