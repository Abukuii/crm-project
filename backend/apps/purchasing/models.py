from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TenantModel
from apps.core.money import CURRENCY_CHOICES, UZS, MoneyField, PriceField, QtyField


class Supplier(TenantModel):
    name = models.CharField("Nomi", max_length=200)
    phone = models.CharField(max_length=32, blank=True)
    inn = models.CharField("INN", max_length=20, blank=True)
    # Qarz shu valyutada yuritiladi; kirim hujjati ham shu valyutada bo'ladi
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default=UZS)
    note = models.TextField(blank=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="uniq_supplier_tenant_name")
        ]

    def __str__(self) -> str:
        return self.name


class Purchase(TenantModel):
    """Kirim hujjati. Qoralama → o'tkazilgan (qoldiq oshadi) → bekor qilingan (storno)."""

    KIND_PURCHASE = "purchase"
    KIND_OPENING = "opening"
    KIND_CHOICES = [(KIND_PURCHASE, "Kirim"), (KIND_OPENING, "Boshlang'ich qoldiq")]

    DRAFT, POSTED, CANCELLED = "draft", "posted", "cancelled"
    STATUS_CHOICES = [(DRAFT, "Qoralama"), (POSTED, "O'tkazilgan"), (CANCELLED, "Bekor qilingan")]

    number = models.PositiveIntegerField()
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=KIND_PURCHASE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=DRAFT, db_index=True)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, null=True, blank=True, related_name="purchases"
    )
    warehouse = models.ForeignKey(
        "inventory.Warehouse", on_delete=models.PROTECT, related_name="purchases"
    )
    date = models.DateField(default=timezone.localdate)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default=UZS)
    rate = PriceField(null=True, blank=True)  # o'tkazilganda qayd etiladi
    extra_costs = MoneyField(help_text="Transport, yuklash va h.k. (so'mda)")
    subtotal = MoneyField(help_text="Tovarlar summasi (hujjat valyutasida)")
    total_uzs = MoneyField(help_text="Tovarlar + qo'shimcha xarajatlar, so'mda")
    note = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        ordering = ["-date", "-number"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="uniq_purchase_number")
        ]

    def __str__(self) -> str:
        return f"Kirim #{self.number}"


class PurchaseLine(TenantModel):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    unit = models.ForeignKey("catalog.Unit", on_delete=models.PROTECT, related_name="+")
    factor = QtyField()  # 1 unit = factor × asosiy birlik
    qty = QtyField()
    base_qty = QtyField()
    price = PriceField()  # 1 ``unit`` narxi, hujjat valyutasida
    total = MoneyField()
    unit_cost = PriceField(null=True, blank=True)  # asosiy birlik tannarxi so'mda (o'tkazilganda)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]


class SupplierPayment(TenantModel):
    """Yetkazib beruvchiga to'lov (yetkazib beruvchi valyutasida)."""

    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="payments")
    amount = MoneyField()
    date = models.DateField(default=timezone.localdate)
    note = models.CharField(max_length=300, blank=True)
    is_cancelled = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        ordering = ["-date", "-id"]
