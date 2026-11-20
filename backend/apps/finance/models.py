from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TenantModel
from apps.core.money import MoneyField

DEFAULT_EXPENSE_CATEGORIES = ["Ijara", "Maosh", "Transport", "Kommunal", "Soliq", "Boshqa"]


class ExpenseCategory(TenantModel):
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="uniq_expensecat_name")
        ]

    def __str__(self) -> str:
        return self.name


class Expense(TenantModel):
    name = models.CharField("Xarajat nomi", max_length=200)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name="expenses")
    amount = MoneyField()
    date = models.DateField(default=timezone.localdate, db_index=True)
    branch = models.ForeignKey(
        "tenancy.Branch", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self) -> str:
        return f"{self.name} — {self.amount}"
