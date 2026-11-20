from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.models import ImmutableModelMixin, TenantModel
from apps.core.money import PriceField, QtyField


class Warehouse(TenantModel):
    branch = models.ForeignKey(
        "tenancy.Branch", on_delete=models.PROTECT, related_name="warehouses"
    )
    name = models.CharField("Nomi", max_length=150)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="uniq_warehouse_tenant_name")
        ]

    def __str__(self) -> str:
        return self.name


class StockMove(ImmutableModelMixin, TenantModel):
    """Qoldiq harakati jurnali. Har bir kirim/chiqim — bitta o'zgarmas yozuv.

    ``qty`` asosiy birlikda: musbat — kirim, manfiy — chiqim.
    ``unit_cost`` — asosiy birlik tannarxi so'mda (chiqimda — o'sha paytdagi o'rtacha tannarx).
    """

    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="moves")
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="stock_moves"
    )
    qty = QtyField()
    unit_cost = PriceField()
    qty_after = QtyField()
    doc_type = models.CharField(max_length=32)
    doc_id = models.BigIntegerField()
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "product", "created_at"]),
            models.Index(fields=["doc_type", "doc_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.product_id} {self.qty:+} @ {self.warehouse_id}"


class StockBalance(TenantModel):
    """Joriy qoldiq va o'rtacha tannarx (jurnaldan hisoblanadi, tezlik uchun saqlanadi)."""

    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="balances")
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="balances"
    )
    qty = QtyField(default=Decimal("0"))
    avg_cost = PriceField(default=Decimal("0"))
    reserved = QtyField(default=Decimal("0"))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["warehouse", "product"], name="uniq_balance")
        ]
        indexes = [models.Index(fields=["tenant", "product"])]

    def __str__(self) -> str:
        return f"{self.product_id}@{self.warehouse_id}: {self.qty}"
