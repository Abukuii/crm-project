from django.db import models

from apps.core.models import TenantModel, TimeStampedModel
from apps.core.money import CURRENCY_CHOICES, UZS

# Tenant sozlamalarining standart qiymatlari (Tenant.settings JSON ichida ustidan yoziladi)
SETTING_DEFAULTS: dict = {
    # "forbid" — manfiy qoldiqqa sotish taqiqlangan, "allow" — ruxsat
    "negative_stock": "forbid",
    "low_stock_threshold": "10",
    # "cbu" — Markaziy bank kursi, "manual" — do'konning o'z kursi
    "rate_source": "cbu",
    # Telegram: savdo xabarlari yuboriladigan guruh/kanal ID'si
    "telegram_chat_id": "",
    "telegram_notify_sales": True,
    # True — kassada smena ochilmasa sotish mumkin emas
    "require_shift": False,
    # Brauzer/telefon bildirishnomalari
    "push_notify_sales": True,
    "push_notify_low_stock": True,
}


class Tenant(TimeStampedModel):
    name = models.CharField("Nomi", max_length=200)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)
    inn = models.CharField("INN", max_length=20, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    address = models.CharField(max_length=300, blank=True)
    base_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default=UZS)
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Tenant (biznes)"
        verbose_name_plural = "Tenantlar"

    def __str__(self) -> str:
        return self.name

    def get_setting(self, key: str):
        return self.settings.get(key, SETTING_DEFAULTS.get(key))


class Branch(TenantModel):
    name = models.CharField("Nomi", max_length=200)
    address = models.CharField(max_length=300, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Filial"
        verbose_name_plural = "Filiallar"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="uniq_branch_tenant_name")
        ]

    def __str__(self) -> str:
        return self.name
