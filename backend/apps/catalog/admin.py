from django.contrib import admin

from .models import Brand, Category, Price, PriceType, Product, Unit


class PriceInline(admin.TabularInline):
    model = Price
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sku",
        "tenant",
        "category",
        "base_unit",
        "price_currency",
        "is_archived",
    )
    list_filter = ("tenant", "is_archived", "price_currency")
    search_fields = ("name", "sku", "search_text")
    inlines = [PriceInline]


admin.site.register([Unit, Category, Brand, PriceType])
