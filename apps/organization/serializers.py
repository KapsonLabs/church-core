from django.contrib.auth import get_user_model
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
