from django.db import transaction
from django.db.models import F

from .models import Counter


def next_number(tenant, key: str) -> int:
    """Tenant ichida ``key`` bo'yicha keyingi raqam. Parallel so'rovlarda ham takrorlanmaydi."""
    with transaction.atomic():
        counter, _ = Counter.objects.get_or_create(tenant=tenant, key=key)
        Counter.objects.filter(pk=counter.pk).update(value=F("value") + 1)
        counter.refresh_from_db(fields=["value"])
        return counter.value
