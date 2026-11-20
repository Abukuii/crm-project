from django.contrib import admin

from .models import Branch, Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "phone", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "inn")


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "is_active")
    list_filter = ("tenant",)
