"""Kassa smenasi: ochish, naqd kiritish/chiqarish, X-hisobot (joriy) va Z-hisobot (yopilish)."""

from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from apps.core import audit
from apps.core.counters import next_number
from apps.core.exceptions import DomainError
from apps.core.money import q_money

from .models import CashMovement, Sale, SalePayment, SaleReturn, Shift

ZERO = Decimal("0")


def current_shift(user) -> Shift | None:
    return Shift.objects.filter(cashier=user, status=Shift.OPEN).select_related("warehouse").first()


@transaction.atomic
def open_shift(
    *, tenant, user, warehouse, opening_cash: Decimal, note: str = "", request=None
) -> Shift:
    if not user.can_access_branch(warehouse.branch_id):
        raise DomainError("Bu omborga ruxsat yo'q", code="branch_forbidden", status_code=403)
    if opening_cash < ZERO:
        raise DomainError("Summa manfiy bo'lmaydi", code="invalid_amount")
    if Shift.objects.select_for_update().filter(cashier=user, status=Shift.OPEN).exists():
        raise DomainError("Sizda ochiq smena bor", code="shift_already_open", status_code=409)
    shift = Shift.objects.create(
        tenant=tenant, number=next_number(tenant, "shift"), warehouse=warehouse, cashier=user,
        opening_cash=q_money(opening_cash), note=note,
    )  # fmt: skip
    audit.record(action="shift.open", entity="shift", entity_id=shift.pk, tenant=tenant, user=user,
                 request=request, after={"number": shift.number, "opening_cash": shift.opening_cash})  # fmt: skip
    return shift


def _check_owner(shift: Shift, user) -> None:
    if shift.cashier_id != user.pk and not user.is_owner:
        raise DomainError("Bu smena sizniki emas", code="not_your_shift", status_code=403)
    if shift.status != Shift.OPEN:
        raise DomainError("Smena yopilgan", code="shift_closed")


@transaction.atomic
def add_cash_movement(*, tenant, user, shift: Shift, kind: str, amount: Decimal, note: str = "",
                      request=None) -> CashMovement:  # fmt: skip
    shift = Shift.objects.select_for_update().get(pk=shift.pk, tenant=tenant)
    _check_owner(shift, user)
    if amount <= ZERO:
        raise DomainError("Summa 0 dan katta bo'lishi kerak", code="invalid_amount")
    if kind == CashMovement.OUT:
        available = Decimal(shift_report(shift)["expected_cash"])
        if amount > available:
            raise DomainError(f"Kassada faqat {available} so'm bor", code="not_enough_cash",
                              details={"available": str(available)})  # fmt: skip
    move = CashMovement.objects.create(tenant=tenant, shift=shift, kind=kind, amount=q_money(amount),
                                       note=note, created_by=user)  # fmt: skip
    audit.record(action=f"shift.cash_{kind}", entity="shift", entity_id=shift.pk, tenant=tenant,
                 user=user, request=request, after={"amount": move.amount, "note": note})  # fmt: skip
    return move


def _sum_by(qs, key: str, value: str) -> dict[str, Decimal]:
    return {
        k: q_money(v) for k, v in qs.values_list(key).annotate(s=Sum(value)).values_list(key, "s")
    }


def shift_report(shift: Shift) -> dict:
    """X-hisobot (ochiq smena uchun joriy holat) — Z-hisobot bilan bir xil tuzilma."""
    sales = Sale.objects.filter(shift=shift, status=Sale.POSTED)
    agg = sales.aggregate(n=Count("id"), total=Sum("total"), discount=Sum("discount_total"))
    by_method = _sum_by(SalePayment.objects.filter(sale__in=sales), "method", "amount")
    returns = SaleReturn.objects.filter(shift=shift)
    refunds = _sum_by(returns, "refund_method", "total")
    # Bekor qilingan qaytarishlar: pul shu smenaga qaytadi (qaytarish qaysi smenada bo'lganidan qat'i nazar).
    # Qaytarish va bekor qilish bir smenada bo'lsa, ikkalasi bir-birini yopadi.
    undone = SaleReturn.objects.filter(cancel_shift=shift)
    undone_refunds = _sum_by(undone, "refund_method", "total")
    debt = _sum_by(shift.debt_payments.all(), "method", "amount")
    moves = _sum_by(shift.cash_movements.all(), "kind", "amount")

    total = agg["total"] or ZERO
    returns_total = sum(refunds.values(), ZERO)
    undone_total = sum(undone_refunds.values(), ZERO)
    expected = (
        shift.opening_cash + by_method.get("cash", ZERO) + debt.get("cash", ZERO)
        + moves.get(CashMovement.IN, ZERO) - moves.get(CashMovement.OUT, ZERO)
        - refunds.get(SaleReturn.CASH, ZERO) + undone_refunds.get(SaleReturn.CASH, ZERO)
    )  # fmt: skip
    return {
        "shift": shift.number,
        "cashier": shift.cashier.get_full_name() or shift.cashier.username,
        "opened_at": shift.opened_at.isoformat(),
        "closed_at": shift.closed_at.isoformat() if shift.closed_at else None,
        "opening_cash": str(q_money(shift.opening_cash)),
        "sales_count": agg["n"],
        "sales_total": str(q_money(total)),
        "discount_total": str(q_money(agg["discount"] or ZERO)),
        "cancelled_count": Sale.objects.filter(shift=shift, status=Sale.CANCELLED).count(),
        "by_method": {k: str(v) for k, v in by_method.items()},
        "returns_count": returns.count(),
        "returns_total": str(q_money(returns_total)),
        "refunds_by_method": {k: str(v) for k, v in refunds.items()},
        "returns_cancelled_count": undone.count(),
        "returns_cancelled_total": str(q_money(undone_total)),
        "cancelled_refunds_by_method": {k: str(v) for k, v in undone_refunds.items()},
        "net_revenue": str(q_money(total - returns_total + undone_total)),
        "debt_payments": {k: str(v) for k, v in debt.items()},
        "cash_in": str(moves.get(CashMovement.IN, q_money(ZERO))),
        "cash_out": str(moves.get(CashMovement.OUT, q_money(ZERO))),
        "expected_cash": str(q_money(expected)),
    }


@transaction.atomic
def close_shift(*, tenant, user, shift: Shift, counted_cash: Decimal, note: str = "",
                request=None) -> Shift:  # fmt: skip
    shift = (
        Shift.objects.select_for_update().select_related("cashier").get(pk=shift.pk, tenant=tenant)
    )
    _check_owner(shift, user)
    if counted_cash < ZERO:
        raise DomainError("Summa manfiy bo'lmaydi", code="invalid_amount")
    shift.closed_at = timezone.now()
    report = shift_report(shift)
    expected = Decimal(report["expected_cash"])
    shift.expected_cash = expected
    shift.counted_cash = q_money(counted_cash)
    shift.difference = q_money(shift.counted_cash - expected)
    report.update(counted_cash=str(shift.counted_cash), difference=str(shift.difference))
    shift.report = report
    shift.status = Shift.CLOSED
    if note:
        shift.note = note
    shift.save()
    audit.record(action="shift.close", entity="shift", entity_id=shift.pk, tenant=tenant, user=user,
                 request=request,
                 after={"expected": expected, "counted": shift.counted_cash, "difference": shift.difference})  # fmt: skip
    return shift
