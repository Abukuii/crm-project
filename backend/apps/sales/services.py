"""Savdo (kassa), nasiya va mijoz to'lovlari."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import DecimalField, F, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.catalog.models import Price, PriceType, Product, Unit
from apps.catalog.units import check_fraction, unit_factor
from apps.core import audit
from apps.core.counters import next_number
from apps.core.exceptions import DomainError
from apps.core.money import USD, q_money, q_qty
from apps.currency.services import get_rate
from apps.inventory.models import Warehouse
from apps.inventory.services import MoveLine, post_moves

from .models import (
    Customer,
    CustomerPayment,
    PaymentAllocation,
    Receivable,
    Sale,
    SaleLine,
    SalePayment,
)

ZERO = Decimal("0")
HUNDRED = Decimal("100")
DOC_TYPE = "sale"
_DEC = DecimalField(max_digits=18, decimal_places=2)


@dataclass
class SaleItem:
    product: Product
    unit: Unit
    qty: Decimal
    price: Decimal | None = None  # kelishilgan narx (1 birlik, so'm); None — ro'yxat narxi


@dataclass
class PaymentIn:
    method: str
    amount: Decimal


# ── Narxlar ──────────────────────────────────────────────────────────────────
def default_price_type(tenant) -> PriceType | None:
    return PriceType.objects.filter(tenant=tenant).order_by("-is_default", "sort", "id").first()


def base_prices(products: list[Product], price_type: PriceType | None,
                fallback: PriceType | None) -> dict[int, Decimal]:  # fmt: skip
    """{product_id: asosiy birlik narxi (mahsulot valyutasida)} — mijoz narx turi, bo'lmasa standart."""
    ids = [p.pk for p in products]
    wanted = [pt.pk for pt in (price_type, fallback) if pt is not None]
    rows = Price.objects.filter(product_id__in=ids, price_type_id__in=wanted)
    by_type: dict[tuple[int, int], Decimal] = {
        (r.product_id, r.price_type_id): r.amount for r in rows
    }
    result = {}
    for pid in ids:
        for pt_id in wanted:
            if (pid, pt_id) in by_type:
                result[pid] = by_type[(pid, pt_id)]
                break
    return result


def to_uzs_per_unit(
    amount: Decimal, product: Product, factor: Decimal, rate: Decimal | None
) -> Decimal:
    """1 birlik narxi so'mda. Dollardan o'girilgan narx butun so'mgacha yaxlitlanadi."""
    value = amount * factor
    if product.price_currency == USD:
        return q_money((value * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return q_money(value)


# ── Nasiya hisobi ────────────────────────────────────────────────────────────
def customer_debt(customer: Customer) -> Decimal:
    agg = customer.receivables.filter(status=Receivable.OPEN).aggregate(
        s=Sum(F("amount") - F("paid"))
    )
    return q_money(agg["s"] or ZERO)


def with_debt(qs, today: date | None = None):
    today = today or timezone.localdate()
    open_r = Receivable.objects.filter(customer=OuterRef("pk"), status=Receivable.OPEN)
    debt = open_r.values("customer").annotate(s=Sum(F("amount") - F("paid"))).values("s")
    overdue = (
        open_r.filter(due_date__lt=today).values("customer")
        .annotate(s=Sum(F("amount") - F("paid"))).values("s")
    )  # fmt: skip
    return qs.annotate(
        debt=Coalesce(Subquery(debt, output_field=_DEC), Value(ZERO, _DEC)),
        overdue_debt=Coalesce(Subquery(overdue, output_field=_DEC), Value(ZERO, _DEC)),
    )


# ── Savdo ────────────────────────────────────────────────────────────────────
@transaction.atomic
def create_sale(
    *,
    tenant,
    user,
    warehouse: Warehouse,
    items: list[SaleItem],
    payments: list[PaymentIn],
    customer: Customer | None = None,
    client_uuid=None,
    due_date: date | None = None,
    note: str = "",
    request=None,
) -> Sale:
    if client_uuid is not None:
        existing = Sale.objects.filter(tenant=tenant, client_uuid=client_uuid).first()
        if existing is not None:
            return existing  # takroriy yuborish — avvalgi natija

    if not user.can_access_branch(warehouse.branch_id):
        raise DomainError("Bu omborga ruxsat yo'q", code="branch_forbidden", status_code=403)
    if not items:
        raise DomainError("Savat bo'sh", code="empty_cart")
    if customer is not None and customer.is_archived:
        raise DomainError("Mijoz arxivlangan", code="customer_archived")
    from .shifts import current_shift

    shift = current_shift(user)
    if shift is None and tenant.get_setting("require_shift"):
        raise DomainError("Avval smenani oching", code="shift_required", status_code=409)

    products = [i.product for i in items]
    for p in products:
        if p.is_archived:
            raise DomainError(f"'{p.name}' arxivlangan", code="product_archived")
    fallback = default_price_type(tenant)
    price_type = (customer.price_type if customer and customer.price_type else None) or fallback
    prices = base_prices(products, price_type, fallback)
    rate = get_rate(tenant, USD).rate if any(p.price_currency == USD for p in products) else None

    lines: list[SaleLine] = []
    for pos, item in enumerate(items):
        product = item.product
        qty = q_qty(item.qty)
        if qty <= ZERO:
            raise DomainError("Miqdor 0 dan katta bo'lishi kerak", code="invalid_qty")
        factor = unit_factor(product, item.unit)
        base_qty = q_qty(qty * factor)
        check_fraction(product, base_qty)
        if product.pk not in prices:
            raise DomainError(f"'{product.name}' uchun narx belgilanmagan", code="price_missing",
                              details={"product_id": product.pk})  # fmt: skip
        list_price = to_uzs_per_unit(prices[product.pk], product, factor, rate)
        price = q_money(item.price) if item.price is not None else list_price
        if price <= ZERO:
            raise DomainError("Narx 0 dan katta bo'lishi kerak", code="invalid_price")
        discount = q_money((list_price - price) * qty) if price < list_price else ZERO
        lines.append(SaleLine(
            tenant=tenant, product=product, unit=item.unit, factor=factor, qty=qty,
            base_qty=base_qty, list_price=list_price, price=price, discount=discount,
            total=q_money(price * qty), position=pos,
        ))  # fmt: skip

    total = q_money(sum((ln.total for ln in lines), ZERO))
    discount_total = q_money(sum((ln.discount for ln in lines), ZERO))
    subtotal = q_money(total + discount_total)

    if discount_total > ZERO and not user.has_perm_code("sales.discount_over_limit"):
        percent = discount_total * HUNDRED / subtotal
        if percent > user.max_discount_percent:
            raise DomainError(
                f"Chegirma limiti {user.max_discount_percent}% — so'ralgan {percent:.1f}%",
                code="discount_limit", status_code=403,
            )  # fmt: skip

    payments = [PaymentIn(p.method, q_money(p.amount)) for p in payments if p.amount]
    if any(p.amount < ZERO for p in payments):
        raise DomainError("To'lov summasi manfiy bo'lmaydi", code="invalid_amount")
    paid = q_money(sum((p.amount for p in payments), ZERO))
    if paid != total:
        raise DomainError(
            f"To'lovlar summasi ({paid}) jami summaga ({total}) teng emas",
            code="payment_mismatch", details={"total": str(total), "paid": str(paid)},
        )  # fmt: skip
    credit = q_money(sum((p.amount for p in payments if p.method == SalePayment.CREDIT), ZERO))
    if credit > ZERO:
        if customer is None:
            raise DomainError("Nasiya uchun mijozni tanlang", code="customer_required")
        if customer.credit_limit is not None:
            debt = customer_debt(customer)
            if debt + credit > customer.credit_limit:
                raise DomainError(
                    f"Kredit limiti oshadi: limit {customer.credit_limit}, joriy qarz {debt}",
                    code="credit_limit_exceeded",
                    details={"limit": str(customer.credit_limit), "debt": str(debt)},
                )

    sale = Sale.objects.create(
        tenant=tenant, number=next_number(tenant, "sale"), client_uuid=client_uuid,
        warehouse=warehouse, cashier=user, customer=customer, price_type=price_type, rate=rate,
        subtotal=subtotal, discount_total=discount_total, total=total, note=note, shift=shift,
    )  # fmt: skip
    moves = post_moves(
        tenant=tenant, warehouse=warehouse, doc_type=DOC_TYPE, doc_id=sale.pk, user=user,
        note=f"Savdo #{sale.number}",
        lines=[MoveLine(ln.product.pk, -ln.base_qty) for ln in lines],
    )  # fmt: skip
    # Minimal qoldiqdan pastga "tushgan" tovarlar (faqat kesib o'tgan payti — har savdoda emas)
    low_stock: set[int] = set()
    for ln, move in zip(lines, moves, strict=True):
        ln.sale = sale
        ln.unit_cost = move.unit_cost
        ln.cost_total = q_money(move.unit_cost * ln.base_qty)
        min_stock = ln.product.min_stock
        if min_stock > ZERO and move.qty_after <= min_stock < move.qty_after - move.qty:
            low_stock.add(ln.product.pk)
    SaleLine.objects.bulk_create(lines)
    sale.cost_total = q_money(sum((ln.cost_total for ln in lines), ZERO))
    sale.save(update_fields=["cost_total", "updated_at"])

    SalePayment.objects.bulk_create(
        [SalePayment(tenant=tenant, sale=sale, method=p.method, amount=p.amount) for p in payments]
    )
    if credit > ZERO:
        Receivable.objects.create(
            tenant=tenant, customer=customer, sale=sale, amount=credit,
            due_date=due_date or timezone.localdate() + timedelta(days=customer.payment_days),
        )  # fmt: skip

    audit.record(
        action="sale.create", entity="sale", entity_id=sale.pk, tenant=tenant, user=user,
        request=request, after={"number": sale.number, "total": total, "discount": discount_total},
    )  # fmt: skip
    transaction.on_commit(lambda: _notify(sale.pk, tenant.pk, sorted(low_stock), warehouse.name))
    return sale


def _notify(sale_id: int, tenant_id: int, low_stock: list[int], warehouse: str) -> None:
    from apps.notifications.tasks import notify_sale, push_low_stock, push_sale

    notify_sale.delay(sale_id)
    push_sale.delay(sale_id)
    if low_stock:
        push_low_stock.delay(tenant_id, low_stock, warehouse)


@transaction.atomic
def cancel_sale(*, tenant, user, sale: Sale, reason: str = "", request=None) -> Sale:
    """Savdoni bekor qilish (eski tizimdagi "o'chirish"): tovar omborga qaytadi."""
    sale = Sale.objects.select_for_update().get(pk=sale.pk, tenant=tenant)
    if sale.status != Sale.POSTED:
        raise DomainError("Savdo allaqachon bekor qilingan", code="already_cancelled")
    if sale.returns.filter(status="posted").exists():
        raise DomainError(
            "Bu savdodan qaytarish qilingan — bekor qilib bo'lmaydi", code="sale_has_returns"
        )
    receivable = Receivable.objects.select_for_update().filter(sale=sale).first()
    if receivable is not None and receivable.paid > ZERO:
        raise DomainError(
            "Bu nasiya bo'yicha to'lov olingan — avval to'lovni hal qiling",
            code="receivable_has_payments",
        )
    lines = list(sale.lines.all())
    post_moves(
        tenant=tenant, warehouse=sale.warehouse, doc_type=DOC_TYPE, doc_id=sale.pk, user=user,
        note=f"Savdo #{sale.number} bekor qilindi",
        lines=[MoveLine(ln.product_id, ln.base_qty, ln.unit_cost) for ln in lines],
    )  # fmt: skip
    if receivable is not None:
        receivable.status = Receivable.CANCELLED
        receivable.save(update_fields=["status", "updated_at"])
    sale.status = Sale.CANCELLED
    sale.cancelled_at = timezone.now()
    sale.cancelled_by = user
    sale.cancel_reason = reason
    sale.save()
    audit.record(
        action="sale.cancel", entity="sale", entity_id=sale.pk, tenant=tenant, user=user,
        request=request, after={"number": sale.number, "reason": reason},
    )  # fmt: skip
    return sale


# ── Nasiya to'lovlari ────────────────────────────────────────────────────────
@transaction.atomic
def receive_payment(
    *,
    tenant,
    user,
    customer: Customer,
    amount: Decimal,
    method: str = "cash",
    note: str = "",
    receivable: Receivable | None = None,
    request=None,
) -> CustomerPayment:
    amount = q_money(amount)
    if amount <= ZERO:
        raise DomainError("Summa 0 dan katta bo'lishi kerak", code="invalid_amount")
    qs = Receivable.objects.select_for_update().filter(customer=customer, status=Receivable.OPEN)
    if receivable is not None:
        qs = qs.filter(pk=receivable.pk)
    open_items = list(qs.order_by("due_date", "id"))
    debt = sum((r.remaining for r in open_items), ZERO)
    if amount > debt:
        raise DomainError(f"To'lov qarzdan ko'p. Qarz: {q_money(debt)}", code="overpayment",
                          details={"debt": str(q_money(debt))})  # fmt: skip

    from .shifts import current_shift

    payment = CustomerPayment.objects.create(
        tenant=tenant, customer=customer, amount=amount, method=method, note=note,
        created_by=user, shift=current_shift(user),
    )  # fmt: skip
    left = amount
    for r in open_items:
        if left <= ZERO:
            break
        part = min(left, r.remaining)
        PaymentAllocation.objects.create(tenant=tenant, payment=payment, receivable=r, amount=part)
        r.paid += part
        if r.paid >= r.amount:
            r.status = Receivable.CLOSED
        r.save(update_fields=["paid", "status", "updated_at"])
        left -= part

    audit.record(
        action="customer.payment", entity="customer", entity_id=customer.pk, tenant=tenant,
        user=user, request=request, after={"amount": amount, "payment_id": payment.pk},
    )  # fmt: skip
    return payment


def sales_for_user(qs, user):
    """Hisobot ruxsati bo'lmagan xodim faqat o'z savdolarini ko'radi; filial cheklovi ham."""
    allowed = user.allowed_branch_ids()
    if allowed is not None:
        qs = qs.filter(warehouse__branch_id__in=allowed)
    if not user.has_perm_code("reports.view"):
        qs = qs.filter(cashier=user)
    return qs
