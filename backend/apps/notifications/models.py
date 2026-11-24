from django.conf import settings
from django.db import models

from apps.core.models import TenantModel


class PushSubscription(TenantModel):
    """Brauzer push obunasi — bitta qurilma + brauzer juftligi.

    ``endpoint`` brauzer bergan maxfiy manzil; u butun tizim bo'ylab yagona.
    Bir brauzerga boshqa xodim kirsa, obuna o'sha xodimga o'tadi.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions"
    )
    endpoint = models.CharField(max_length=512, unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    user_agent = models.CharField(max_length=300, blank=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "user"])]

    def __str__(self) -> str:
        return f"{self.user_id}: {self.endpoint[:40]}…"
