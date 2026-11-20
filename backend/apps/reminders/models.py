from django.conf import settings
from django.db import models

from apps.core.models import TenantModel


class Reminder(TenantModel):
    LEVEL_CHOICES = [("normal", "Oddiy"), ("important", "Muhim"), ("urgent", "Shoshilinch")]

    text = models.TextField("Matn")
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default="normal")
    due_date = models.DateField(null=True, blank=True)
    is_done = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        ordering = ["is_done", "due_date", "-created_at"]

    def __str__(self) -> str:
        return self.text[:50]
