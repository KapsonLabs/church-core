from django.contrib import admin

from .models import Branch, BranchMembership, BranchSettings, Organization, OrganizationMembership

admin.site.register(Organization)
admin.site.register(Branch)
admin.site.register(BranchSettings)
admin.site.register(OrganizationMembership)
admin.site.register(BranchMembership)
