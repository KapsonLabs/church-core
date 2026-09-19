from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AccessPermission, Resource, Role, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "is_active", "is_staff")
    fieldsets = UserAdmin.fieldsets + (("Profile", {"fields": ("phone_number", "date_of_birth")}),)
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2", "is_staff", "is_superuser")}),)


admin.site.register(Resource)
admin.site.register(AccessPermission)
admin.site.register(Role)
