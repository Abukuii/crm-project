from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.money import PriceField


class ExchangeRate(models.Model):
    """1 birlik valyuta = ``rate`` so'm.

    ``tenant=None`` — Markaziy bank (CBU) kursi, barcha tenantlar uchun umumiy.
    ``tenant`` berilgan — do'konning o'z (qo'lda kiritilgan) kursi.
    """

    SOURCE_CBU = "cbu"
    SOURCE_MANUAL = "manual"
    SOURCE_CHOICES = [(SOURCE_CBU, "Markaziy bank"), (SOURCE_MANUAL, "Qo'lda")]

    tenant = models.ForeignKey(
        "tenancy.Tenant", on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    currency = models.CharField(max_length=3)
    date = models.DateField()
    rate = PriceField()
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["currency", "date"],
                condition=Q(tenant__isnull=True),
                name="uniq_rate_global",
            ),
            models.UniqueConstraint(
                fields=["tenant", "currency", "date"],
                condition=Q(tenant__isnull=False),
                name="uniq_rate_tenant",
            ),
        ]
        indexes = [models.Index(fields=["currency", "-date"])]

    def __str__(self) -> str:
        return f"1 {self.currency} = {self.rate} ({self.date}, {self.source})"
