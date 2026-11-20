"""Pul va miqdor bilan ishlash qoidalari.

Qoida: pul va miqdor faqat ``Decimal`` — ``float`` ishlatish taqiqlangan.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import models

MONEY_STEP = Decimal("0.01")  # summalar (so'm/dollar)
PRICE_STEP = Decimal("0.0001")  # narx, tannarx, kurs (dollar sentlari va kasr birliklar uchun)
QTY_STEP = Decimal("0.001")  # miqdor (metr, kg, m³)

UZS = "UZS"
USD = "USD"
CURRENCY_CHOICES = [(UZS, "So'm"), (USD, "AQSh dollari")]


def to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        # float'ni str orqali o'giramiz, aks holda 0.1 → 0.1000000000000000055...
        return Decimal(repr(value))
    return Decimal(value)


def q_money(value) -> Decimal:
    return to_decimal(value).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)


def q_price(value) -> Decimal:
    return to_decimal(value).quantize(PRICE_STEP, rounding=ROUND_HALF_UP)


def q_qty(value) -> Decimal:
    return to_decimal(value).quantize(QTY_STEP, rounding=ROUND_HALF_UP)


def MoneyField(**kwargs) -> models.DecimalField:  # noqa: N802 — maydon "konstruktori"
    kwargs.setdefault("default", Decimal("0"))
    return models.DecimalField(max_digits=18, decimal_places=2, **kwargs)


def PriceField(**kwargs) -> models.DecimalField:  # noqa: N802
    return models.DecimalField(max_digits=18, decimal_places=4, **kwargs)


def QtyField(**kwargs) -> models.DecimalField:  # noqa: N802
    return models.DecimalField(max_digits=14, decimal_places=3, **kwargs)
