from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .views import ChangePasswordView, CurrentUserContextView, CurrentUserPermissionsView, CurrentUserView, LoginView, LogoutView, PermissionListView, RoleDetailView, RoleListCreateView, UserListCreateView

app_name = "accounts"
urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/verify/", TokenVerifyView.as_view(), name="token-verify"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="current-user"),
    path("me/context/", CurrentUserContextView.as_view(), name="current-user-context"),
    path("me/password/", ChangePasswordView.as_view(), name="change-password"),
    path("me/permissions/", CurrentUserPermissionsView.as_view(), name="current-user-permissions"),
    path("users/", UserListCreateView.as_view(), name="user-list-create"),
    path("permissions/", PermissionListView.as_view(), name="permission-list"),
    path("roles/", RoleListCreateView.as_view(), name="role-list-create"),
    path("organizations/<uuid:organization_id>/roles/<uuid:pk>/", RoleDetailView.as_view(), name="role-detail"),
]
