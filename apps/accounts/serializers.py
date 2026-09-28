from django.contrib.auth import authenticate, password_validation
from rest_framework import serializers

from apps.organization.models import Branch, Organization

from .models import AccessPermission, Resource, Role, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "phone_number", "date_of_birth", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserDetailsSerializer(UserSerializer):
    """Compact compatibility serializer used by optional example apps."""
    pass


class SessionOrganizationSerializer(serializers.ModelSerializer):
    branch_count = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "description", "email", "phone_number", "website", "physical_address", "logo", "is_active", "branch_count", "created_at", "updated_at"]

    def get_branch_count(self, organization):
        return organization.branches.filter(is_active=True).count()


class SessionBranchSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    organization = SessionOrganizationSerializer(read_only=True)

    class Meta:
        model = Branch
        fields = ["id", "organization_id", "organization", "name", "code", "email", "phone_number", "address", "city", "country", "is_active", "created_at", "updated_at"]


class RoleShortDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name", "slug"]


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "password", "first_name", "last_name", "phone_number"]
        read_only_fields = ["id"]

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(request=self.context.get("request"), username=attrs["email"], password=attrs["password"])
        if not user or not user.is_active:
            raise serializers.ValidationError("Invalid credentials or inactive account.")
        attrs["user"] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value):
        password_validation.validate_password(value, self.context["request"].user)
        return value


class ResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = ["id", "name", "code", "description", "is_active"]


class AccessPermissionSerializer(serializers.ModelSerializer):
    resource = ResourceSerializer(read_only=True)

    class Meta:
        model = AccessPermission
        fields = ["id", "resource", "action", "codename", "description", "is_active"]


class RoleSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField()
    permission_ids = serializers.PrimaryKeyRelatedField(source="permissions", queryset=AccessPermission.objects.filter(is_active=True), many=True, required=False)
    permissions = AccessPermissionSerializer(many=True, read_only=True)

    class Meta:
        model = Role
        fields = ["id", "organization_id", "name", "slug", "description", "permission_ids", "permissions", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "permissions", "created_at", "updated_at"]

    def validate(self, attrs):
        from apps.organization.models import Organization

        organization_id = attrs.get("organization_id", getattr(self.instance, "organization_id", None))
        if organization_id and not Organization.objects.filter(id=organization_id, is_active=True).exists():
            raise serializers.ValidationError({"organization_id": "Organization does not exist or is inactive."})
        if self.instance and "organization_id" in attrs and attrs["organization_id"] != self.instance.organization_id:
            raise serializers.ValidationError({"organization_id": "A role cannot be moved to another organization."})
        return attrs
