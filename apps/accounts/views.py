from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from apps.organization.models import Branch, Organization
from .models import AccessPermission, Role, User
from .permissions import HasTenantPermission, IsOrganizationMember
from .serializers import AccessPermissionSerializer, ChangePasswordSerializer, LoginSerializer, RoleSerializer, SessionBranchSerializer, UserCreateSerializer, UserSerializer


def eligible_session_branches(user):
    """Return the active branch context a user may enter after authentication."""
    return (
        Branch.objects.filter(
            is_active=True,
            organization__is_active=True,
            memberships__user=user,
            memberships__is_active=True,
            organization__memberships__user=user,
            organization__memberships__is_active=True,
        )
        .select_related("organization")
        .order_by("organization__name", "name", "id")
        .distinct()
    )


class LoginView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        return Response({"data": {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
            "branches": SessionBranchSerializer(eligible_session_branches(user), many=True).data,
        }})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get("refresh")
        if not token:
            return Response({"errors": {"refresh": ["This field is required."]}}, status=status.HTTP_400_BAD_REQUEST)
        try:
            RefreshToken(token).blacklist()
        except Exception:
            return Response({"errors": {"refresh": ["Invalid refresh token."]}}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class CurrentUserContextView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        branches = SessionBranchSerializer(eligible_session_branches(request.user), many=True).data
        return Response({"data": {"branches": branches}})


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        return Response({"data": {"message": "Password changed."}})


class CurrentUserPermissionsView(APIView):
    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def get(self, request):
        organization = get_object_or_404(Organization, id=request.query_params.get("organization_id"))
        return Response({"data": sorted(request.user.get_tenant_permissions(organization))})


class UserListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, HasTenantPermission]
    required_permissions = {"GET": "members.read", "POST": "members.manage"}

    def get_serializer_class(self):
        return UserCreateSerializer if self.request.method == "POST" else UserSerializer

    def get_queryset(self):
        return User.objects.filter(organization_memberships__organization_id=self.request.query_params.get("organization_id"), organization_memberships__is_active=True).distinct()


class PermissionListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AccessPermissionSerializer
    queryset = AccessPermission.objects.filter(is_active=True).select_related("resource")


class RoleListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, HasTenantPermission]
    serializer_class = RoleSerializer
    required_permissions = {"GET": "roles.read", "POST": "roles.manage"}

    def get_queryset(self):
        return Role.objects.filter(organization_id=self.request.query_params.get("organization_id")).prefetch_related("permissions")


class RoleDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, HasTenantPermission]
    serializer_class = RoleSerializer
    required_permissions = {"GET": "roles.read", "PUT": "roles.manage", "PATCH": "roles.manage", "DELETE": "roles.manage"}

    def get_queryset(self):
        return Role.objects.filter(organization_id=self.kwargs["organization_id"]).prefetch_related("permissions")
