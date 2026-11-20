"""Kirim hujjatlari va yetkazib beruvchi qarzi."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import DecimalField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.catalog.units import check_fraction, unit_factor
from apps.core import audit
from apps.core.counters import next_number
from apps.core.exceptions import DomainError
from apps.core.money import UZS, q_money, q_price, q_qty
from apps.currency.services import get_rate
from apps.inventory.services import MoveLine, post_moves

from .models import Purchase, PurchaseLine, Supplier, SupplierPayment

ZERO = Decimal("0")
DOC_TYPE = "purchase"


# ── Kirim hujjati ────────────────────────────────────────────────────────────
def _validate_header(tenant, user, data: dict, kind: str) -> None:
    supplier = data.get("supplier")
    warehouse = data["warehouse"]
    if not user.can_access_branch(warehouse.branch_id):
        raise DomainError("Bu omborga ruxsat yo'q", code="branch_forbidden", status_code=403)
    if kind == Purchase.KIND_OPENING and supplier is not None:
        raise DomainError("Boshlang'ich qoldiqda yetkazib beruvchi bo'lmaydi", code="invalid")
    if supplier is not None and data.get("currency", supplier.currency) != supplier.currency:
        raise DomainError(
            f"Yetkazib beruvchi hisobi {supplier.currency} da yuritiladi",
            code="currency_mismatch",
        )


@transaction.atomic
def save_draft(*, tenant, user, data: dict, instance: Purchase | None = None, request=None):
    lines = data.pop("lines", None)
    if instance is None:
        kind = data.get("kind", Purchase.KIND_PURCHASE)
        if "currency" not in data and data.get("supplier") is not None:
            data["currency"] = data["supplier"].currency
        _validate_header(tenant, user, data, kind)
        purchase = Purchase(
            tenant=tenant, number=next_number(tenant, "purchase"), created_by=user, kind=kind
        )
    else:
        purchase = Purchase.objects.select_for_update().get(pk=instance.pk)
        if purchase.status != Purchase.DRAFT:
            raise DomainError("Faqat qoralamani tahrirlash mumkin", code="not_draft")
        merged = {
            "supplier": purchase.supplier, "warehouse": purchase.warehouse,
            "currency": purchase.currency, **data,
        }  # fmt: skip
        _validate_header(tenant, user, merged, purchase.kind)

    for field in ("supplier", "warehouse", "date", "currency", "extra_costs", "note"):
        if field in data:
            setattr(purchase, field, data[field])
    purchase.save()

    if lines is not None:
        purchase.lines.all().delete()
        rows = []
        for i, line in enumerate(lines):
            product, unit = line["product"], line["unit"]
            if product.is_archived:
                raise DomainError(f"'{product.name}' arxivlangan", code="product_archived")
            factor = unit_factor(product, unit)
            qty = q_qty(line["qty"])
            base_qty = q_qty(qty * factor)
            check_fraction(product, base_qty)
            price = q_price(line["price"])
            rows.append(PurchaseLine(
                tenant=tenant, purchase=purchase, product=product, unit=unit, factor=factor,
                qty=qty, base_qty=base_qty, price=price, total=q_money(qty * price), position=i,
            ))  # fmt: skip
        PurchaseLine.objects.bulk_create(rows)
        purchase.subtotal = q_money(sum((r.total for r in rows), ZERO))
        purchase.save(update_fields=["subtotal", "updated_at"])

    audit.record(
        action="purchase.save", entity="purchase", entity_id=purchase.pk, tenant=tenant,
        user=user, request=request,
        after={"number": purchase.number, "subtotal": purchase.subtotal},
    )  # fmt: skip
    return purchase


def _allocate_costs(lines: list[PurchaseLine], rate: Decimal, extra: Decimal) -> None:
    """Qo'shimcha xarajatni qatorlarga summa ulushi bo'yicha taqsimlab, tannarxni hisoblaydi."""
    values = [line.total * rate for line in lines]
    total_value = sum(values, ZERO)
    total_qty = sum((line.base_qty for line in lines), ZERO)
    for line, value in zip(lines, values, strict=True):
        if extra:
            share = extra * (value / total_value if total_value else line.base_qty / total_qty)
        else:
            share = ZERO
        line.unit_cost = q_price((value + share) / line.base_qty)


@transaction.atomic
def post_purchase(*, tenant, user, purchase: Purchase, request=None) -> Purchase:
    purchase = Purchase.objects.select_for_update().get(pk=purchase.pk, tenant=tenant)
    if purchase.status != Purchase.DRAFT:
        raise DomainError("Hujjat allaqachon o'tkazilgan", code="not_draft")
    lines = list(purchase.lines.select_related("product"))
    if not lines:
        raise DomainError("Hujjatda tovar yo'q", code="empty_document")

    rate = (
        Decimal("1")
        if purchase.currency == UZS
        else get_rate(tenant, purchase.currency, purchase.date).rate
    )
    _allocate_costs(lines, rate, purchase.extra_costs)
    post_moves(
        tenant=tenant, warehouse=purchase.warehouse, doc_type=DOC_TYPE, doc_id=purchase.pk,
        user=user, note=f"Kirim #{purchase.number}",
        lines=[MoveLine(line.product_id, line.base_qty, line.unit_cost) for line in lines],
    )  # fmt: skip
    PurchaseLine.objects.bulk_update(lines, ["unit_cost"])

    purchase.rate = rate
    purchase.total_uzs = q_money(purchase.subtotal * rate + purchase.extra_costs)
    purchase.status = Purchase.POSTED
    purchase.posted_at = timezone.now()
    purchase.posted_by = user
    purchase.save()
    audit.record(
        action="purchase.post", entity="purchase", entity_id=purchase.pk, tenant=tenant,
        user=user, request=request,
        after={"number": purchase.number, "total_uzs": purchase.total_uzs},
    )  # fmt: skip
    return purchase


@transaction.atomic
def cancel_purchase(*, tenant, user, purchase: Purchase, request=None) -> Purchase:
    """O'tkazilgan kirimni bekor qilish: tovar aynan kirim tannarxi bilan chiqariladi."""
    purchase = Purchase.objects.select_for_update().get(pk=purchase.pk, tenant=tenant)
    if purchase.status != Purchase.POSTED:
        raise DomainError("Faqat o'tkazilgan hujjat bekor qilinadi", code="not_posted")
    lines = list(purchase.lines.all())
    post_moves(
        tenant=tenant, warehouse=purchase.warehouse, doc_type=DOC_TYPE, doc_id=purchase.pk,
        user=user, note=f"Kirim #{purchase.number} bekor qilindi", allow_negative=False,
        lines=[MoveLine(line.product_id, -line.base_qty, line.unit_cost) for line in lines],
    )  # fmt: skip
    purchase.status = Purchase.CANCELLED
    purchase.cancelled_at = timezone.now()
    purchase.cancelled_by = user
    purchase.save()
    audit.record(
        action="purchase.cancel", entity="purchase", entity_id=purchase.pk, tenant=tenant,
        user=user, request=request, after={"number": purchase.number},
    )  # fmt: skip
    return purchase


# ── Yetkazib beruvchi qarzi ─────────────────────────────────────────────────
_DEC = DecimalField(max_digits=18, decimal_places=2)


def with_balance(qs):
    """Har bir yetkazib beruvchiga ``balance`` (biz qarzdormiz: + ) annotatsiyasi."""
    purchased = (
        Purchase.objects.filter(supplier=OuterRef("pk"), status=Purchase.POSTED)
        .values("supplier").annotate(s=Sum("subtotal")).values("s")
    )  # fmt: skip
    paid = (
        SupplierPayment.objects.filter(supplier=OuterRef("pk"), is_cancelled=False)
        .values("supplier").annotate(s=Sum("amount")).values("s")
    )  # fmt: skip
    return qs.annotate(
        purchased=Coalesce(Subquery(purchased, output_field=_DEC), Value(ZERO, _DEC)),
        paid=Coalesce(Subquery(paid, output_field=_DEC), Value(ZERO, _DEC)),
    )


def supplier_balance(supplier: Supplier) -> Decimal:
    row = with_balance(Supplier.objects.filter(pk=supplier.pk)).values("purchased", "paid").get()
    return q_money(row["purchased"] - row["paid"])


def add_payment(*, tenant, user, supplier: Supplier, amount: Decimal, on: date | None = None,
                note: str = "", request=None) -> SupplierPayment:  # fmt: skip
    if amount <= ZERO:
        raise DomainError("Summa 0 dan katta bo'lishi kerak", code="invalid_amount")
    payment = SupplierPayment.objects.create(
        tenant=tenant, supplier=supplier, amount=q_money(amount),
        date=on or timezone.localdate(), note=note, created_by=user,
    )  # fmt: skip
    audit.record(
        action="supplier.payment", entity="supplier", entity_id=supplier.pk, tenant=tenant,
        user=user, request=request, after={"amount": payment.amount, "payment_id": payment.pk},
    )  # fmt: skip
    return payment


@dataclass
class StatementRow:
    date: date
    kind: str  # purchase | payment
    ref: str
    debit: Decimal  # qarz oshdi (kirim)
    credit: Decimal  # qarz kamaydi (to'lov)
    balance: Decimal


def statement(supplier: Supplier, date_from: date | None, date_to: date | None) -> dict:
    """Akt sverka: davr boshidagi qoldiq, harakatlar va yakuniy qoldiq."""
    purchases = Purchase.objects.filter(supplier=supplier, status=Purchase.POSTED)
    payments = SupplierPayment.objects.filter(supplier=supplier, is_cancelled=False)

    opening = ZERO
    if date_from:
        opening = (
            purchases.filter(date__lt=date_from).aggregate(s=Sum("subtotal"))["s"] or ZERO
        ) - (payments.filter(date__lt=date_from).aggregate(s=Sum("amount"))["s"] or ZERO)
        purchases, payments = (
            purchases.filter(date__gte=date_from),
            payments.filter(date__gte=date_from),
        )
    if date_to:
        purchases, payments = (
            purchases.filter(date__lte=date_to),
            payments.filter(date__lte=date_to),
        )

    events = [
        (p.date, 0, p.pk, "purchase", f"Kirim #{p.number}", p.subtotal, ZERO) for p in purchases
    ]
    events += [(p.date, 1, p.pk, "payment", p.note or "To'lov", ZERO, p.amount) for p in payments]
    events.sort(key=lambda e: (e[0], e[1], e[2]))

    balance, rows = opening, []
    for day, _, _, kind, ref, debit, credit in events:
        balance += debit - credit
        rows.append(StatementRow(day, kind, ref, debit, credit, q_money(balance)))
    return {
        "supplier": supplier.name,
        "currency": supplier.currency,
        "opening": q_money(opening),
        "rows": rows,
        "debit_total": q_money(sum((r.debit for r in rows), ZERO)),
        "credit_total": q_money(sum((r.credit for r in rows), ZERO)),
        "closing": q_money(balance),
    }


def purchases_for_user(qs, user):
    allowed = user.allowed_branch_ids()
    return qs if allowed is None else qs.filter(warehouse__branch_id__in=allowed)
