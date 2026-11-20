import logging

import httpx
from celery import shared_task

from .telegram import sale_message, send_message

logger = logging.getLogger(__name__)


@shared_task(autoretry_for=(httpx.HTTPError,), retry_backoff=30, max_retries=5)
def notify_sale(sale_id: int) -> bool:
    from apps.sales.models import Sale

    sale = (
        Sale.objects.select_related("tenant", "cashier", "customer")
        .prefetch_related("lines__product", "lines__unit", "payments")
        .filter(pk=sale_id).first()
    )  # fmt: skip
    if sale is None:
        return False
    chat_id = sale.tenant.get_setting("telegram_chat_id")
    if not chat_id or not sale.tenant.get_setting("telegram_notify_sales"):
        return False
    return send_message(str(chat_id), sale_message(sale))
