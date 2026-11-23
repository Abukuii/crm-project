"""Qaytarish: savdo qatorlarining bir qismi yoki hammasi."""

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.catalog.units import check_fraction
from apps.core import audit
from apps.core.counters import next_number
from apps.core.exceptions import DomainError
from apps.core.money import q_money, q_qty
from apps.inventory.services import MoveLine, post_moves

from .models import Receivable, Sale, SaleReturn, SaleReturnLine
from .shifts import current_shift

ZERO = Decimal("0")
DOC_TYPE = "sale_return"


@dataclass
class ReturnItem:
    sale_line_id: int
    qty: Decimal  # savdo qatori birligida


def returned_qty_by_line(sale: Sale) -> dict[int, Decimal]:
    return dict(
        SaleReturnLine.objects.filter(sale_line__sale=sale, sale_return__status=SaleReturn.POSTED)
        .values_list("sale_line_id").annotate(s=Sum("qty")).values_list("sale_line_id", "s")
    )  # fmt: skip


@transaction.atomic
def create_return(*, tenant, user, sale: Sale, items: list[ReturnItem], refund_method: str,
                  reason: str = "", request=None) -> SaleReturn:  # fmt: skip
    sale = Sale.objects.select_for_update().get(pk=sale.pk, tenant=tenant)
    if sale.status != Sale.POSTED:
        raise DomainError("Bekor qilingan savdodan qaytarib bo'lmaydi", code="sale_cancelled")
    if not user.can_access_branch(sale.warehouse.branch_id):
        raise DomainError("Bu omborga ruxsat yo'q", code="branch_forbidden", status_code=403)
    items = [i for i in items if i.qty]
    if not items:
        raise DomainError("Qaytariladigan tovar tanlanmagan", code="empty_return")
    if refund_method not in dict(SaleReturn.REFUND_CHOICES):
        raise DomainError("To'lov usuli noto'g'ri", code="invalid_method")

    lines = {ln.pk: ln for ln in sale.lines.select_related("product__base_unit")}
    already = returned_qty_by_line(sale)
    rows: list[SaleReturnLine] = []
    seen: set[int] = set()
    for item in items:
        line = lines.get(item.sale_line_id)
        if line is None or item.sale_line_id in seen:
            raise DomainError("Savdo qatori topilmadi", code="line_not_found",
                              details={"line": item.sale_line_id})  # fmt: skip
        seen.add(line.pk)
        qty = q_qty(item.qty)
        left = line.qty - already.get(line.pk, ZERO)
        if qty <= ZERO or qty > left:
            raise DomainError(
                f"'{line.product.name}': ko'pi bilan {left} qaytarish mumkin", code="qty_exceeds",
                details={"line": line.pk, "available": str(left)},
            )  # fmt: skip
        base_qty = q_qty(qty * line.factor)
        check_fraction(line.product, base_qty)
        rows.append(SaleReturnLine(
            tenant=tenant, sale_line=line, qty=qty, base_qty=base_qty,
            amount=q_money(line.price * qty), unit_cost=line.unit_cost or ZERO,
            cost_total=q_money((line.unit_cost or ZERO) * base_qty),
        ))  # fmt: skip

    total = q_money(sum((r.amount for r in rows), ZERO))
    if refund_method == SaleReturn.DEBT:
        receivable = (
            Receivable.objects.select_for_update()
            .filter(sale=sale, status=Receivable.OPEN).first()
        )  # fmt: skip
        if receivable is None:
            raise DomainError("Bu savdo bo'yicha ochiq qarz yo'q", code="no_open_debt")
        if total > receivable.remaining:
            raise DomainError(
                f"Qaytarish summasi qolgan qarzdan ({receivable.remaining}) ko'p",
                code="refund_exceeds_debt", details={"remaining": str(receivable.remaining)},
            )  # fmt: skip
        receivable.amount -= total
        if receivable.paid >= receivable.amount:
            receivable.status = Receivable.CLOSED
        receivable.save(update_fields=["amount", "status", "updated_at"])

    ret = SaleReturn.objects.create(
        tenant=tenant, number=next_number(tenant, "return"), sale=sale, shift=current_shift(user),
        refund_method=refund_method, total=total,
        cost_total=q_money(sum((r.cost_total for r in rows), ZERO)), reason=reason, created_by=user,
    )  # fmt: skip
    for r in rows:
        r.sale_return = ret
    SaleReturnLine.objects.bulk_create(rows)
    post_moves(
        tenant=tenant, warehouse=sale.warehouse, doc_type=DOC_TYPE, doc_id=ret.pk, user=user,
        note=f"Qaytarish #{ret.number} (savdo #{sale.number})",
        lines=[MoveLine(r.sale_line.product_id, r.base_qty, r.unit_cost) for r in rows],
    )  # fmt: skip
    audit.record(action="sale.return", entity="sale", entity_id=sale.pk, tenant=tenant, user=user,
                 request=request,
                 after={"return": ret.number, "total": total, "method": refund_method})  # fmt: skip
    return ret


@transaction.atomic
def cancel_return(
    *, tenant, user, sale_return: SaleReturn, reason: str = "", request=None
) -> SaleReturn:
    """Qaytarishni bekor qilish (xato qaytarish): tovar yana ombordan chiqadi,
    pul kassaga qaytadi (joriy smenada hisoblanadi), qarzdan ayirilgan bo'lsa — qarz tiklanadi."""
    ret = (
        SaleReturn.objects.select_for_update()
        .select_related("sale__warehouse")
        .get(pk=sale_return.pk, tenant=tenant)
    )
    sale = Sale.objects.select_for_update().get(pk=ret.sale_id)
    if ret.status != SaleReturn.POSTED:
        raise DomainError("Qaytarish allaqachon bekor qilingan", code="return_already_cancelled")
    if not user.can_access_branch(sale.warehouse.branch_id):
        raise DomainError("Bu omborga ruxsat yo'q", code="branch_forbidden", status_code=403)

    lines = list(ret.lines.select_related("sale_line"))
    # Tovar qaytarishdagi aniq tannarx bilan chiqariladi; omborda yetmasa — InsufficientStock
    post_moves(
        tenant=tenant, warehouse=sale.warehouse, doc_type=DOC_TYPE, doc_id=ret.pk, user=user,
        note=f"Qaytarish #{ret.number} bekor qilindi", allow_negative=False,
        lines=[MoveLine(r.sale_line.product_id, -r.base_qty, r.unit_cost) for r in lines],
    )  # fmt: skip

    if ret.refund_method == SaleReturn.DEBT:
        receivable = Receivable.objects.select_for_update().filter(sale=sale).first()
        if receivable is None:
            raise DomainError("Savdoning qarz yozuvi topilmadi", code="no_receivable")
        receivable.amount += ret.total
        if receivable.status == Receivable.CLOSED and receivable.paid < receivable.amount:
            receivable.status = Receivable.OPEN
        receivable.save(update_fields=["amount", "status", "updated_at"])

    ret.status = SaleReturn.CANCELLED
    ret.cancelled_at = timezone.now()
    ret.cancelled_by = user
    ret.cancel_reason = reason
    ret.cancel_shift = current_shift(user)
    ret.save()
    audit.record(action="sale.return_cancel", entity="sale", entity_id=sale.pk, tenant=tenant,
                 user=user, request=request,
                 after={"return": ret.number, "total": ret.total, "reason": reason})  # fmt: skip
    return ret
