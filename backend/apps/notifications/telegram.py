"""Telegram orqali xabar yuborish.

Bitta platforma boti (``TELEGRAM_BOT_TOKEN``), har bir do'kon o'z sozlamasida ``telegram_chat_id``
(guruh yoki kanal) ni ko'rsatadi. Bot o'sha guruhga qo'shilgan bo'lishi kerak.
"""

import html
import logging
from decimal import Decimal

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

METHOD_LABELS = {"cash": "💵 Naqd", "card": "💳 Karta", "transfer": "🏦 O'tkazma",
                 "credit": "⏳ Nasiya"}  # fmt: skip


def fmt(amount: Decimal) -> str:
    return f"{amount:,.0f}".replace(",", " ")


def send_message(chat_id: str, text: str, client: httpx.Client | None = None) -> bool:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or not chat_id:
        return False
    own = client is None
    client = client or httpx.Client(timeout=10)
    try:
        response = client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },  # fmt: skip
        )
        response.raise_for_status()
        return True
    finally:
        if own:
            client.close()


def sale_message(sale) -> str:
    e = html.escape
    lines = [
        f"🛒 <b>Yangi savdo #{sale.number}</b>",
        f"📅 {sale.created_at:%d.%m.%Y %H:%M}",
        f"👨‍💼 Sotuvchi: {e(sale.cashier.get_full_name() or sale.cashier.username)}",
    ]
    if sale.customer:
        phone = f" ({e(sale.customer.phone)})" if sale.customer.phone else ""
        lines.append(f"👤 Mijoz: {e(sale.customer.name)}{phone}")
    lines.append("")
    lines.append("📦 <b>Mahsulotlar:</b>")
    for ln in sale.lines.all():
        qty = f"{ln.qty.normalize():f}"
        lines.append(f"  • {e(ln.product.name)} × {qty} {e(ln.unit.short)} = {fmt(ln.total)} so'm")
    lines.append("")
    if sale.discount_total:
        lines.append(f"🏷 Chegirma: {fmt(sale.discount_total)} so'm")
    lines.append(f"💰 <b>Jami: {fmt(sale.total)} so'm</b>")
    for p in sale.payments.all():
        lines.append(f"{METHOD_LABELS.get(p.method, p.method)}: {fmt(p.amount)} so'm")
    return "\n".join(lines)
