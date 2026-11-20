from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TenantModel
from apps.core.money import CURRENCY_CHOICES, UZS, PriceField, QtyField
from apps.core.text import normalize, search_key


class Unit(TenantModel):
    name = models.CharField("Nomi", max_length=50)
    short = models.CharField("Qisqa", max_length=16)
    allow_fraction = models.BooleanField("Kasr miqdor", default=False)
    code = models.CharField("Soliq birlik kodi", max_length=16, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="uniq_unit_tenant_name")
        ]

    def __str__(self) -> str:
        return self.short


class Category(TenantModel):
    name = models.CharField("Nomi", max_length=150)
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="children"
    )
    sort = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort", "name"]
        verbose_name_plural = "Categories"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "parent", "name"], name="uniq_category_tenant_parent_name"
            )
        ]

    def __str__(self) -> str:
        return self.name


class Brand(TenantModel):
    name = models.CharField("Nomi", max_length=150)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="uniq_brand_tenant_name")
        ]

    def __str__(self) -> str:
        return self.name


class PriceType(TenantModel):
    name = models.CharField("Nomi", max_length=50)
    is_default = models.BooleanField(default=False)
    sort = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort", "name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="uniq_pricetype_tenant_name")
        ]

    def __str__(self) -> str:
        return self.name


class Product(TenantModel):
    """Mahsulot. Hech qachon o'chirilmaydi — faqat arxivlanadi (tarix buzilmasligi uchun)."""

    sku = models.CharField("Artikul", max_length=64)
    name = models.CharField("Nomi", max_length=255)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, null=True, blank=True, related_name="products"
    )
    brand = models.ForeignKey(
        Brand, on_delete=models.PROTECT, null=True, blank=True, related_name="products"
    )
    base_unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="+")
    price_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default=UZS)
    mxik_code = models.CharField("MXIK (IKPU) kodi", max_length=32, blank=True)
    description = models.TextField(blank=True)
    min_stock = QtyField(default=Decimal("0"), validators=[MinValueValidator(0)])
    is_archived = models.BooleanField(default=False, db_index=True)
    # Kirill/lotin farqisiz qidiruv uchun normallashtirilgan matn
    search_text = models.TextField(blank=True, editable=False)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "sku"], name="uniq_product_tenant_sku")
        ]
        indexes = [models.Index(fields=["tenant", "is_archived", "name"])]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.search_text = f"{normalize(self.name)} {search_key(self.name)} {normalize(self.sku)}"
        if "update_fields" in kwargs and kwargs["update_fields"] is not None:
            kwargs["update_fields"] = {*kwargs["update_fields"], "search_text"}
        super().save(*args, **kwargs)


class ProductUnit(TenantModel):
    """Qo'shimcha birlik: 1 ``unit`` = ``factor`` × asosiy birlik (masalan, 1 pachka = 10 dona)."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="units")
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="+")
    factor = QtyField(validators=[MinValueValidator(Decimal("0.001"))])

    class Meta:
        constraints = [models.UniqueConstraint(fields=["product", "unit"], name="uniq_productunit")]

    def __str__(self) -> str:
        return f"{self.product} — 1 {self.unit} = {self.factor}"


class Barcode(TenantModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="barcodes")
    # None — asosiy birlik shtrix-kodi
    product_unit = models.ForeignKey(
        ProductUnit, on_delete=models.CASCADE, null=True, blank=True, related_name="barcodes"
    )
    code = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uniq_barcode_tenant_code")
        ]

    def __str__(self) -> str:
        return self.code


class Price(TenantModel):
    """Asosiy birlik narxi (valyuta — ``product.price_currency``)."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="prices")
    price_type = models.ForeignKey(PriceType, on_delete=models.PROTECT, related_name="prices")
    amount = PriceField(validators=[MinValueValidator(0)])

    class Meta:
        constraints = [models.UniqueConstraint(fields=["product", "price_type"], name="uniq_price")]


class PriceHistory(TenantModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="price_history")
    price_type = models.ForeignKey(PriceType, on_delete=models.PROTECT, related_name="+")
    old_amount = PriceField(null=True, blank=True)
    new_amount = PriceField()
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]
