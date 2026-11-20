"""Qoldiq jurnali (stock ledger) — omborga tegadigan yagona kirish nuqtasi.

Barcha hujjatlar (kirim, savdo, qaytarish, ko'chirish, inventarizatsiya) qoldiqni faqat
``post_moves`` orqali o'zgartiradi. Funksiya:
  * balans qatorlarini ``SELECT … FOR UPDATE`` bilan qulflaydi (mahsulot id tartibida — deadlock yo'q);
  * kirimda o'rtacha tortilgan tannarxni qayta hisoblaydi;
  * chiqimda joriy o'rtacha tannarxni yozib qo'yadi (foyda hisobi uchun);
  * qoldiq yetmasa — hech narsa yozmasdan ``InsufficientStock`` ko'taradi.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from apps.catalog.models import Product
from apps.core.exceptions import DomainError, InsufficientStock
from apps.core.money import q_price, q_qty

from .models import StockBalance, StockMove, Warehouse

ZERO = Decimal("0")


@dataclass(frozen=True)
class MoveLine:
    product_id: int
    qty: Decimal  # asosiy birlikda; + kirim, − chiqim
    # Kirimda — majburiy tannarx (so'mda).
    # Chiqimda — odatda berilmaydi (o'rtacha tannarx olinadi). Berilsa — bu kirimni bekor qilish
    # (storno): tovar aynan shu tannarx bilan chiqariladi va o'rtacha tannarx qayta tiklanadi.
    unit_cost: Decimal | None = None


def _check_products(tenant, product_ids: set[int]) -> dict[int, Product]:
    products = Product.objects.filter(tenant=tenant, pk__in=product_ids).select_related("base_unit")
    found = {p.pk: p for p in products}
    missing = product_ids - set(found)
    if missing:
        raise DomainError(
            "Mahsulot topilmadi", code="product_not_found", details={"product_ids": sorted(missing)}
        )
    return found


@transaction.atomic
def post_moves(
    *,
    tenant,
    warehouse: Warehouse,
    lines: Iterable[MoveLine],
    doc_type: str,
    doc_id: int,
    user=None,
    note: str = "",
    allow_negative: bool | None = None,
) -> list[StockMove]:
    lines = list(lines)
    if not lines:
        raise DomainError("Harakat qatorlari bo'sh", code="empty_moves")
    if warehouse.tenant_id != tenant.pk:
        raise DomainError("Ombor topilmadi", code="warehouse_not_found")
    if not warehouse.is_active:
        raise DomainError("Ombor faol emas", code="warehouse_inactive")
    if allow_negative is None:
        allow_negative = tenant.get_setting("negative_stock") == "allow"

    product_ids = {line.product_id for line in lines}
    products = _check_products(tenant, product_ids)

    # Balans qatorlari bo'lmasa — yaratamiz (parallel so'rovda ham xavfsiz)
    StockBalance.objects.bulk_create(
        [StockBalance(tenant=tenant, warehouse=warehouse, product_id=pid) for pid in product_ids],
        ignore_conflicts=True,
    )
    balances = {
        b.product_id: b
        for b in StockBalance.objects.select_for_update()
        .filter(warehouse=warehouse, product_id__in=product_ids)
        .order_by("product_id")
    }

    moves: list[StockMove] = []
    shortages: list[dict] = []
    for line in lines:
        product = products[line.product_id]
        qty = q_qty(line.qty)
        if qty == ZERO:
            raise DomainError(
                "Miqdor 0 bo'lishi mumkin emas", code="zero_qty", details={"product_id": product.pk}
            )
        if not product.base_unit.allow_fraction and qty != qty.to_integral_value():
            raise DomainError(
                f"'{product.name}' faqat butun sonda hisoblanadi",
                code="fraction_not_allowed",
                details={"product_id": product.pk, "qty": str(qty)},
            )
        balance = balances[product.pk]

        if qty > ZERO:
            if line.unit_cost is None or line.unit_cost < ZERO:
                raise DomainError(
                    "Kirim uchun tannarx majburiy",
                    code="cost_required",
                    details={"product_id": product.pk},
                )
            cost = q_price(line.unit_cost)
            new_qty = balance.qty + qty
            if balance.qty <= ZERO:
                balance.avg_cost = cost
            else:
                balance.avg_cost = q_price((balance.qty * balance.avg_cost + qty * cost) / new_qty)
            balance.qty = new_qty
            unit_cost = cost
        else:
            available = balance.qty
            if available + qty < ZERO and not allow_negative:
                shortages.append(
                    {
                        "product_id": product.pk,
                        "name": product.name,
                        "requested": str(-qty),
                        "available": str(available),
                    }
                )
                continue
            new_qty = balance.qty + qty
            if line.unit_cost is not None:  # storno: aniq tannarx bilan qaytarish
                unit_cost = q_price(line.unit_cost)
                if new_qty > ZERO:
                    restored = (balance.qty * balance.avg_cost + qty * unit_cost) / new_qty
                    balance.avg_cost = q_price(max(restored, ZERO))
            else:
                unit_cost = balance.avg_cost
            balance.qty = new_qty

        moves.append(
            StockMove(
                tenant=tenant,
                warehouse=warehouse,
                product_id=product.pk,
                qty=qty,
                unit_cost=unit_cost,
                qty_after=balance.qty,
                doc_type=doc_type,
                doc_id=doc_id,
                note=note,
                created_by=user,
            )
        )

    if shortages:
        raise InsufficientStock(details=shortages)

    StockMove.objects.bulk_create(moves)
    for balance in balances.values():
        balance.save(update_fields=["qty", "avg_cost", "updated_at"])
    return moves


def recalc_balance(warehouse: Warehouse, product_id: int) -> tuple[Decimal, Decimal]:
    """Jurnaldan qoldiq va o'rtacha tannarxni qayta hisoblaydi (tekshiruv/tuzatish uchun)."""
    qty, avg = ZERO, ZERO
    for move in StockMove.objects.filter(warehouse=warehouse, product_id=product_id).order_by(
        "created_at", "id"
    ):
        if move.qty > ZERO:
            new_qty = qty + move.qty
            avg = (
                move.unit_cost
                if qty <= ZERO
                else q_price((qty * avg + move.qty * move.unit_cost) / new_qty)
            )
            qty = new_qty
        else:
            qty += move.qty
    return qty, avg
