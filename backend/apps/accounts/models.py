from decimal import Decimal
from functools import cached_property

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.models import TenantModel

from .perms import ALL


class Role(TenantModel):
    name = models.CharField(max_length=100)
    permissions = models.JSONField(default=list, blank=True)
    max_discount_percent = models.DecimalField(
        "Maksimal chegirma (%)", max_digits=5, decimal_places=2, default=Decimal("0")
    )
    is_system = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="uniq_role_tenant_name")
        ]

    def __str__(self) -> str:
        return self.name


class User(AbstractUser):
    LANG_CHOICES = [("uz", "O'zbekcha"), ("ru", "Русский")]
    THEME_CHOICES = [("system", "Tizim"), ("light", "Yorug'"), ("dark", "Tun")]

    # tenant=None — platforma administratori (faqat Django admin orqali ishlaydi)
    tenant = models.ForeignKey(
        "tenancy.Tenant", on_delete=models.PROTECT, null=True, blank=True, related_name="users"
    )
    phone = models.CharField(max_length=32, blank=True)
    roles = models.ManyToManyField(Role, blank=True, related_name="users")
    # Bo'sh — filial cheklovi yo'q faqat "*" ruxsatli rol uchun; boshqalar uchun bo'sh = hech qaysi
    branches = models.ManyToManyField("tenancy.Branch", blank=True, related_name="users")
    pin_hash = models.CharField(max_length=128, blank=True)
    language = models.CharField(max_length=2, choices=LANG_CHOICES, default="uz")
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default="system")

    class Meta:
        ordering = ["username"]

    @cached_property
    def perm_codes(self) -> frozenset[str]:
        if not self.is_active or self.tenant_id is None:
            return frozenset()
        codes: set[str] = set()
        for perms in self.roles.values_list("permissions", flat=True):
            codes.update(perms or [])
        return frozenset(codes)

    def has_perm_code(self, code: str) -> bool:
        codes = self.perm_codes
        return ALL in codes or code in codes

    @property
    def is_owner(self) -> bool:
        return ALL in self.perm_codes

    @property
    def max_discount_percent(self) -> Decimal:
        values = list(self.roles.values_list("max_discount_percent", flat=True))
        return max(values) if values else Decimal("0")

    def allowed_branch_ids(self) -> list[int] | None:
        """None — barcha filiallar; aks holda ruxsat etilgan filiallar ro'yxati."""
        if self.is_owner:
            return None
        return list(self.branches.values_list("id", flat=True))

    def can_access_branch(self, branch_id: int) -> bool:
        allowed = self.allowed_branch_ids()
        return allowed is None or branch_id in allowed

    def set_pin(self, pin: str | None) -> None:
        self.pin_hash = make_password(pin) if pin else ""

    def check_pin(self, pin: str) -> bool:
        return bool(self.pin_hash) and check_password(pin, self.pin_hash)

    def invalidate_perm_cache(self) -> None:
        self.__dict__.pop("perm_codes", None)
