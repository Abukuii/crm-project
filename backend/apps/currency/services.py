import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import httpx
from django.conf import settings
from django.utils import timezone

from apps.core import audit
from apps.core.exceptions import DomainError
from apps.core.money import UZS, q_price

from .models import ExchangeRate

logger = logging.getLogger(__name__)


class RateNotFound(DomainError):
    default_code = "rate_not_found"
    default_detail = "Valyuta kursi topilmadi. Kursni kiriting."


@dataclass(frozen=True)
class RateInfo:
    currency: str
    rate: Decimal
    date: date
    source: str


def _latest(qs, currency: str, on: date) -> ExchangeRate | None:
    return qs.filter(currency=currency, date__lte=on).order_by("-date").first()


def get_rate(tenant, currency: str, on: date | None = None) -> RateInfo:
    """Tenant uchun ``on`` sanadagi kurs. Tartib tenant sozlamasi ``rate_source`` bo'yicha."""
    currency = currency.upper()
    on = on or timezone.localdate()
    if currency == UZS:
        return RateInfo(UZS, Decimal("1"), on, "base")

    manual = ExchangeRate.objects.filter(tenant=tenant)
    cbu = ExchangeRate.objects.filter(tenant__isnull=True)
    order = (manual, cbu) if tenant.get_setting("rate_source") == "manual" else (cbu, manual)
    for qs in order:
        found = _latest(qs, currency, on)
        if found is not None:
            return RateInfo(currency, found.rate, found.date, found.source)
    raise RateNotFound(details={"currency": currency, "date": on.isoformat()})


def set_manual_rate(
    *, tenant, user, currency: str, rate: Decimal, on: date | None = None, request=None
) -> ExchangeRate:
    on = on or timezone.localdate()
    obj, created = ExchangeRate.objects.update_or_create(
        tenant=tenant,
        currency=currency.upper(),
        date=on,
        defaults={"rate": q_price(rate), "source": ExchangeRate.SOURCE_MANUAL, "created_by": user},
    )
    audit.record(
        action="rate.set",
        entity="exchange_rate",
        entity_id=obj.pk,
        tenant=tenant,
        user=user,
        request=request,
        after={"currency": obj.currency, "rate": obj.rate, "date": obj.date},
    )
    return obj


def parse_cbu_payload(
    payload: list[dict], currencies: list[str]
) -> list[tuple[str, date, Decimal]]:
    """CBU JSON: [{"Ccy": "USD", "Rate": "12650.55", "Nominal": "1", "Date": "20.11.2026"}, ...]"""
    wanted = {c.upper() for c in currencies}
    result = []
    for item in payload:
        ccy = str(item.get("Ccy", "")).upper()
        if ccy not in wanted:
            continue
        try:
            rate = Decimal(str(item["Rate"]).replace(",", "."))
            nominal = Decimal(str(item.get("Nominal") or "1"))
            on = datetime.strptime(item["Date"], "%d.%m.%Y").date()
        except (KeyError, ValueError, InvalidOperation):
            logger.warning("CBU javobida noto'g'ri qator: %s", item)
            continue
        if nominal <= 0 or rate <= 0:
            continue
        result.append((ccy, on, q_price(rate / nominal)))
    return result


def fetch_cbu_rates(client: httpx.Client | None = None) -> int:
    """CBU'dan joriy kurslarni oladi va saqlaydi. Qaytaradi: saqlangan kurslar soni."""
    own_client = client is None
    client = client or httpx.Client(timeout=10)
    try:
        response = client.get(settings.CBU_RATES_URL)
        response.raise_for_status()
        rows = parse_cbu_payload(response.json(), settings.CBU_CURRENCIES)
    finally:
        if own_client:
            client.close()
    for ccy, on, rate in rows:
        ExchangeRate.objects.update_or_create(
            tenant=None,
            currency=ccy,
            date=on,
            defaults={"rate": rate, "source": ExchangeRate.SOURCE_CBU},
        )
    logger.info("CBU kurslari yangilandi: %s", rows)
    return len(rows)
