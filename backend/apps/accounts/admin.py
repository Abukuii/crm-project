from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Role, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "tenant", "first_name", "last_name", "is_active", "last_login")
    list_filter = ("tenant", "is_active", "is_superuser")
    fieldsets = (
        *BaseUserAdmin.fieldsets,
        ("CRM", {"fields": ("tenant", "phone", "roles", "branches", "language", "theme")}),
    )
    filter_horizontal = ("roles", "branches", "groups", "user_permissions")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "is_system", "max_discount_percent")
    list_filter = ("tenant",)
