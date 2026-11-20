from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantModel(TimeStampedModel):
    """Tenant'ga tegishli har bir yozuv uchun asos. Querysetlar har doim tenant bo'yicha filtrlanadi."""

    tenant = models.ForeignKey(
        "tenancy.Tenant", on_delete=models.PROTECT, related_name="+", db_index=True
    )

    class Meta:
        abstract = True


class ImmutableModelMixin:
    """Jurnal yozuvlari: yaratilgandan keyin o'zgartirib ham, o'chirib ham bo'lmaydi."""

    def save(self, *args, **kwargs):
        if self.pk is not None and not kwargs.pop("_allow_update", False):
            raise RuntimeError(f"{type(self).__name__} o'zgarmas yozuv — tahrirlash taqiqlangan")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError(f"{type(self).__name__} o'zgarmas yozuv — o'chirish taqiqlangan")


class Counter(models.Model):
    """Tenant ichidagi ketma-ket raqamlar (SKU, chek raqami va h.k.)."""

    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE, related_name="+")
    key = models.CharField(max_length=64)
    value = models.BigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "key"], name="uniq_counter_tenant_key")
        ]

    def __str__(self) -> str:
        return f"{self.key}={self.value}"


class AuditLog(ImmutableModelMixin, models.Model):
    tenant = models.ForeignKey(
        "tenancy.Tenant", on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    action = models.CharField(max_length=64)
    entity = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=64, blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["entity", "entity_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.entity}#{self.entity_id}"
