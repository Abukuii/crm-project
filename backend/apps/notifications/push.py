"""Web Push (VAPID) — brauzer va telefon bildirishnomalari.

VAPID kalitlari ``.env`` da bo'lmasa, push shunchaki o'chiq bo'ladi (xato bermaydi).
Kalitlarni yaratish: ``python manage.py generate_vapid_keys --env``.
"""

import json
import logging
from collections.abc import Iterable

from django.conf import settings
from django.utils import timezone
from pywebpush import WebPushException, webpush

from .models import PushSubscription

logger = logging.getLogger(__name__)

# Qurilma o'chiq bo'lsa, xabar shuncha vaqt saqlanadi (soniya)
TTL = 12 * 60 * 60


def is_enabled() -> bool:
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def users_with_perm(tenant, code: str, exclude_ids: Iterable[int] = ()) -> list[int]:
    """Tenant ichida ``code`` ruxsati bor faol xodimlar id'lari."""
    from apps.accounts.models import User

    skip = set(exclude_ids)
    users = User.objects.filter(tenant=tenant, is_active=True).prefetch_related("roles")
    return [u.pk for u in users if u.pk not in skip and u.has_perm_code(code)]


def send_to_users(user_ids: Iterable[int], *, title: str, body: str = "", url: str = "/",
                  tag: str | None = None) -> int:  # fmt: skip
    """Berilgan xodimlarning barcha qurilmalariga bildirishnoma yuboradi. Yuborilgan soni qaytadi."""
    user_ids = list(user_ids)
    if not user_ids or not is_enabled():
        return 0
    subs = list(PushSubscription.objects.filter(user_id__in=user_ids))
    if not subs:
        return 0

    payload = json.dumps({"title": title, "body": body, "url": url, "tag": tag}, ensure_ascii=False)
    sent, dead = 0, []
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                # Har bir yuborish uchun yangi lug'at: pywebpush unga "aud" ni qo'shadi
                vapid_claims={"sub": settings.VAPID_SUBJECT},
                ttl=TTL,
            )
            sent += 1
        except WebPushException as exc:
            status = getattr(exc, "status_code", None) or getattr(exc.response, "status_code", None)
            if status in (404, 410):
                # Obuna o'chirilgan (brauzer tozalangan yoki ilova olib tashlangan)
                dead.append(sub.pk)
            else:
                logger.warning("Push yuborilmadi (%s): %s", status, exc)
        except Exception:  # noqa: BLE001 — bitta qurilma butun yuborishni to'xtatmasin
            logger.exception("Push yuborishda kutilmagan xato")

    if dead:
        PushSubscription.objects.filter(pk__in=dead).delete()
    if sent:
        PushSubscription.objects.filter(pk__in=[s.pk for s in subs if s.pk not in dead]).update(
            last_sent_at=timezone.now()
        )
    return sent
