from django.contrib import admin

from .models import StockBalance, StockMove, Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("name", "branch", "tenant", "is_active")


@admin.register(StockBalance)
class StockBalanceAdmin(admin.ModelAdmin):
    list_display = ("product", "warehouse", "qty", "avg_cost", "updated_at")
    list_filter = ("warehouse",)

    def has_change_permission(self, request, obj=None):
        return False  # faqat jurnal orqali


@admin.register(StockMove)
class StockMoveAdmin(admin.ModelAdmin):
    list_display = ("created_at", "product", "warehouse", "qty", "unit_cost", "doc_type", "doc_id")
    list_filter = ("doc_type", "warehouse")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
