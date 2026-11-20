"""Mahsulotni saqlash: birliklar, shtrix-kodlar va narxlar bitta tranzaksiyada."""

from django.db import transaction

from apps.core import audit
from apps.core.counters import next_number
from apps.core.money import q_price

from .models import Barcode, Price, PriceHistory, Product, ProductUnit

PRODUCT_FIELDS = (
    "name",
    "sku",
    "category",
    "brand",
    "base_unit",
    "price_currency",
    "mxik_code",
    "description",
    "min_stock",
    "is_archived",
)


def generate_sku(tenant) -> str:
    while True:
        sku = f"{next_number(tenant, 'product_sku'):06d}"
        if not Product.objects.filter(tenant=tenant, sku=sku).exists():
            return sku


def _sync_units(product: Product, units: list[dict]) -> dict[int, ProductUnit]:
    """Qo'shimcha birliklarni berilgan ro'yxatga moslaydi. Qaytaradi: {unit_id: ProductUnit}."""
    wanted = {u["unit"].pk: u for u in units}
    existing = {pu.unit_id: pu for pu in product.units.all()}
    for unit_id, pu in existing.items():
        if unit_id not in wanted:
            pu.delete()
    result = {}
    for unit_id, data in wanted.items():
        pu = existing.get(unit_id)
        if pu is None:
            pu = ProductUnit.objects.create(
                tenant=product.tenant, product=product, unit=data["unit"], factor=data["factor"]
            )
        elif pu.factor != data["factor"]:
            pu.factor = data["factor"]
            pu.save(update_fields=["factor", "updated_at"])
        result[unit_id] = pu
    return result


def _sync_barcodes(
    product: Product, barcodes: list[str], units: list[dict], unit_map: dict[int, ProductUnit]
) -> None:
    product.barcodes.all().delete()
    rows = [Barcode(tenant=product.tenant, product=product, code=c) for c in barcodes]
    rows += [
        Barcode(
            tenant=product.tenant,
            product=product,
            product_unit=unit_map[u["unit"].pk],
            code=u["barcode"],
        )
        for u in units
        if u.get("barcode")
    ]
    Barcode.objects.bulk_create(rows)


def _sync_prices(product: Product, prices: list[dict], user) -> list[dict]:
    current = {p.price_type_id: p for p in product.prices.all()}
    changes = []
    for item in prices:
        price_type, amount = item["price_type"], q_price(item["amount"])
        price = current.get(price_type.pk)
        old = price.amount if price else None
        if old is not None and old == amount:
            continue
        if price is None:
            Price.objects.create(
                tenant=product.tenant, product=product, price_type=price_type, amount=amount
            )
        else:
            price.amount = amount
            price.save(update_fields=["amount", "updated_at"])
        PriceHistory.objects.create(
            tenant=product.tenant,
            product=product,
            price_type=price_type,
            old_amount=old,
            new_amount=amount,
            currency=product.price_currency,
            changed_by=user,
        )
        changes.append({"price_type": price_type.name, "old": old, "new": amount})
    return changes


@transaction.atomic
def save_product(
    *, tenant, user, data: dict, instance: Product | None = None, request=None
) -> Product:
    units = data.pop("units", None)
    barcodes = data.pop("barcodes", None)
    prices = data.pop("prices", None)

    creating = instance is None
    product = instance or Product(tenant=tenant)
    for field in PRODUCT_FIELDS:
        if field in data:
            setattr(product, field, data[field])
    if not product.sku:
        product.sku = generate_sku(tenant)
    product.save()

    if units is not None or barcodes is not None:
        units = (
            units
            if units is not None
            else [
                {
                    "unit": pu.unit,
                    "factor": pu.factor,
                    "barcode": next((b.code for b in pu.barcodes.all()), None),
                }
                for pu in product.units.select_related("unit")
            ]
        )
        unit_map = _sync_units(product, units)
        if barcodes is None:
            barcodes = list(
                product.barcodes.filter(product_unit__isnull=True).values_list("code", flat=True)
            )
        _sync_barcodes(product, barcodes, units, unit_map)

    price_changes = _sync_prices(product, prices, user) if prices is not None else []

    audit.record(
        action="product.create" if creating else "product.update",
        entity="product",
        entity_id=product.pk,
        tenant=tenant,
        user=user,
        request=request,
        after={"name": product.name, "sku": product.sku, "prices": price_changes},
    )
    return product
