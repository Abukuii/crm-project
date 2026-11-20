from django.contrib import admin

from .models import Customer, CustomerPayment, Receivable, Sale


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "date", "status", "customer", "total", "cashier")
    list_filter = ("status", "tenant")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "tenant", "kind", "credit_limit")
    search_fields = ("name", "phone")


admin.site.register([Receivable, CustomerPayment])
