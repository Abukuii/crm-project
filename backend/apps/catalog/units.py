"""Mahsulot birliklari: tanlangan birlikning asosiy birlikka koeffitsienti."""

from decimal import Decimal

from apps.core.exceptions import DomainError

from .models import Product, ProductUnit, Unit

ONE = Decimal("1")


def unit_factor(product: Product, unit: Unit) -> Decimal:
    if unit.pk == product.base_unit_id:
        return ONE
    pu = ProductUnit.objects.filter(product=product, unit=unit).only("factor").first()
    if pu is None:
        raise DomainError(
            f"'{product.name}' uchun '{unit.short}' birligi belgilanmagan",
            code="unit_not_for_product",
            details={"product_id": product.pk, "unit_id": unit.pk},
        )
    return pu.factor


def check_fraction(product: Product, base_qty: Decimal) -> None:
    if not product.base_unit.allow_fraction and base_qty != base_qty.to_integral_value():
        raise DomainError(
            f"'{product.name}' faqat butun sonda hisoblanadi",
            code="fraction_not_allowed",
            details={"product_id": product.pk, "qty": str(base_qty)},
        )
