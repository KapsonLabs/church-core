from django.urls import path

from .views import BranchDetailView, BranchListCreateView, BranchMembershipDetailView, BranchMembershipListCreateView, BranchSettingsView, OrganizationDetailView, OrganizationListCreateView, OrganizationMembershipDetailView, OrganizationMembershipListCreateView

app_name = "organization"
urlpatterns = [
    path("", OrganizationListCreateView.as_view(), name="list-create"),
    path("<uuid:organization_id>/", OrganizationDetailView.as_view(), name="detail"),
    path("branches/", BranchListCreateView.as_view(), name="branch-list-create"),
    path("<uuid:organization_id>/branches/<uuid:pk>/", BranchDetailView.as_view(), name="branch-detail"),
    path("<uuid:organization_id>/branches/<uuid:branch_id>/settings/", BranchSettingsView.as_view(), name="branch-settings"),
    path("<uuid:organization_id>/memberships/", OrganizationMembershipListCreateView.as_view(), name="membership-list-create"),
    path("<uuid:organization_id>/memberships/<uuid:pk>/", OrganizationMembershipDetailView.as_view(), name="membership-detail"),
    path("<uuid:organization_id>/branches/<uuid:branch_id>/memberships/", BranchMembershipListCreateView.as_view(), name="branch-membership-list-create"),
    path("<uuid:organization_id>/branch-memberships/<uuid:pk>/", BranchMembershipDetailView.as_view(), name="branch-membership-detail"),
]
