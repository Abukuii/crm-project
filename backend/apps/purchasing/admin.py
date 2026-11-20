from django.contrib import admin

from .models import Purchase, Supplier, SupplierPayment


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "tenant",
        "kind",
        "status",
        "supplier",
        "date",
        "subtotal",
        "currency",
    )
    list_filter = ("status", "kind", "tenant")


admin.site.register([Supplier, SupplierPayment])
