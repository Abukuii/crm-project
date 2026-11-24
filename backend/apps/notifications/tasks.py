import logging

import httpx
from celery import shared_task

from .push import send_to_users, users_with_perm
from .telegram import fmt, sale_message, send_message

logger = logging.getLogger(__name__)


@shared_task(autoretry_for=(httpx.HTTPError,), retry_backoff=30, max_retries=5)
def notify_sale(sale_id: int) -> bool:
    """Telegram guruhiga savdo haqida xabar."""
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


@shared_task(ignore_result=True)
def push_sale(sale_id: int) -> int:
    """Savdo haqida push — egasi va menejerlarga (sotuvchining o'ziga emas)."""
    from apps.sales.models import Sale

    sale = (
        Sale.objects.select_related("tenant", "cashier")
        .prefetch_related("lines__product")
        .filter(pk=sale_id).first()
    )  # fmt: skip
    if sale is None or not sale.tenant.get_setting("push_notify_sales"):
        return 0
    lines = list(sale.lines.all())
    items = ", ".join(f"{ln.product.name} × {ln.qty.normalize():f}" for ln in lines[:3])
    if len(lines) > 3:
        items += f" va yana {len(lines) - 3} ta"
    cashier = sale.cashier.get_full_name() or sale.cashier.username
    return send_to_users(
        users_with_perm(sale.tenant, "reports.view", exclude_ids=[sale.cashier_id]),
        title=f"Savdo #{sale.number} — {fmt(sale.total)} so'm",
        body=f"{items} · {cashier}",
        url="/sales",
        tag=f"sale-{sale.pk}",
    )


@shared_task(ignore_result=True)
def push_low_stock(tenant_id: int, product_ids: list[int], warehouse: str = "") -> int:
    """Tovar minimal qoldiqqa tushganda — ombor bilan ishlaydiganlarga."""
    from apps.catalog.models import Product
    from apps.tenancy.models import Tenant

    tenant = Tenant.objects.filter(pk=tenant_id).first()
    if tenant is None or not tenant.get_setting("push_notify_low_stock"):
        return 0
    names = list(Product.objects.filter(pk__in=product_ids).values_list("name", flat=True)[:5])
    if not names:
        return 0
    body = ", ".join(names)
    if len(product_ids) > len(names):
        body += f" va yana {len(product_ids) - len(names)} ta"
    return send_to_users(
        users_with_perm(tenant, "inventory.manage"),
        title="Tovar tugayapti" + (f" — {warehouse}" if warehouse else ""),
        body=body,
        url="/stock?low_stock=true",
        tag="low-stock",
    )
