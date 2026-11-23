"""Dashboard ko'rsatkichlari (eski dashboard + haqiqiy tannarx asosidagi foyda)."""

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, F, Sum
from django.utils import timezone

from apps.core.money import q_money
from apps.finance.models import Expense
from apps.inventory.models import StockBalance
from apps.sales.models import Receivable, Sale, SaleLine, SalePayment, SaleReturn

ZERO = Decimal("0")


def _sales(tenant, start: date, end: date, branch_ids):
    qs = Sale.objects.filter(tenant=tenant, status=Sale.POSTED, date__gte=start, date__lte=end)
    if branch_ids is not None:
        qs = qs.filter(warehouse__branch_id__in=branch_ids)
    return qs


def _period(tenant, start, end, branch_ids, with_cost: bool) -> dict:
    sales = _sales(tenant, start, end, branch_ids)
    agg = sales.aggregate(n=Count("id"), total=Sum("total"), cost=Sum("cost_total"),
                          discount=Sum("discount_total"))  # fmt: skip
    # Qaytarishlar qaytarilgan sanasi bo'yicha ayiriladi (sof tushum)
    ret_qs = SaleReturn.objects.filter(tenant=tenant, date__gte=start, date__lte=end)
    if branch_ids is not None:
        ret_qs = ret_qs.filter(sale__warehouse__branch_id__in=branch_ids)
    ret = ret_qs.aggregate(total=Sum("total"), cost=Sum("cost_total"))
    returns = ret["total"] or ZERO
    total = (agg["total"] or ZERO) - returns
    cost = (agg["cost"] or ZERO) - (ret["cost"] or ZERO)
    exp_qs = Expense.objects.filter(tenant=tenant, date__gte=start, date__lte=end)
    if branch_ids is not None:
        exp_qs = exp_qs.filter(branch_id__in=branch_ids)
    expenses = exp_qs.aggregate(s=Sum("amount"))["s"] or ZERO
    data = {
        "sales_count": agg["n"],
        "revenue": q_money(total),
        "discount": q_money(agg["discount"] or ZERO),
        "avg_check": q_money(total / agg["n"]) if agg["n"] else ZERO,
        "expenses": q_money(expenses),
        "returns": q_money(returns),
    }
    if with_cost:
        gross = total - cost
        data["gross_profit"] = q_money(gross)
        data["net_profit"] = q_money(gross - expenses)
    return data


def dashboard(tenant, user, today: date | None = None) -> dict:
    today = today or timezone.localdate()
    branch_ids = user.allowed_branch_ids()
    with_cost = user.has_perm_code("cost.view")
    month_start = today.replace(day=1)
    prev_month_end = month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    yesterday = today - timedelta(days=1)

    week_start = today - timedelta(days=6)
    by_day = dict(
        _sales(tenant, week_start, today, branch_ids)
        .values_list("date").annotate(s=Sum("total")).values_list("date", "s")
    )  # fmt: skip
    week = [
        {"date": d.isoformat(), "revenue": q_money(by_day.get(d, ZERO))}
        for d in (week_start + timedelta(days=i) for i in range(7))
    ]

    by_method = dict(
        SalePayment.objects.filter(sale__in=_sales(tenant, today, today, branch_ids))
        .values_list("method").annotate(s=Sum("amount")).values_list("method", "s")
    )  # fmt: skip

    top = list(
        SaleLine.objects.filter(sale__in=_sales(tenant, month_start, today, branch_ids))
        .values("product_id", name=F("product__name"))
        .annotate(qty=Sum("base_qty"), revenue=Sum("total"))
        .order_by("-revenue")[:5]
    )  # fmt: skip

    open_r = Receivable.objects.filter(tenant=tenant, status=Receivable.OPEN)
    debt = open_r.aggregate(s=Sum(F("amount") - F("paid")))["s"] or ZERO
    overdue = open_r.filter(due_date__lt=today).aggregate(s=Sum(F("amount") - F("paid")))["s"]

    low_qs = StockBalance.objects.filter(tenant=tenant, qty__lte=F("product__min_stock"),
                                         product__is_archived=False)  # fmt: skip
    if branch_ids is not None:
        low_qs = low_qs.filter(warehouse__branch_id__in=branch_ids)

    recent = (
        _sales(tenant, today - timedelta(days=30), today, branch_ids)
        .select_related("customer").order_by("-created_at")[:6]
    )  # fmt: skip

    return {
        "today": _period(tenant, today, today, branch_ids, with_cost),
        "yesterday": _period(tenant, yesterday, yesterday, branch_ids, with_cost),
        "month": _period(tenant, month_start, today, branch_ids, with_cost),
        "prev_month": _period(tenant, prev_month_start, prev_month_end, branch_ids, with_cost),
        "week": week,
        "today_by_method": {k: q_money(v) for k, v in by_method.items()},
        "top_products": [
            {
                "product_id": t["product_id"],
                "name": t["name"],
                "qty": t["qty"],
                "revenue": q_money(t["revenue"]),
            }
            for t in top
        ],  # fmt: skip
        "debt": {
            "total": q_money(debt),
            "overdue": q_money(overdue or ZERO),
            "debtors": open_r.values("customer").distinct().count(),
        },
        "low_stock_count": low_qs.count(),
        "recent_sales": [
            {
                "id": s.id,
                "number": s.number,
                "created_at": s.created_at,
                "total": s.total,
                "customer": s.customer.name if s.customer else None,
            }
            for s in recent
        ],  # fmt: skip
    }
