"""Umumiy statistika: davr bo'yicha bitta Excel fayl (bir nechta varaq), 3 tilda sarlavhalar."""

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, F, Sum
from django.utils import timezone

from apps.core.money import q_money
from apps.finance.models import Expense
from apps.inventory.models import StockBalance
from apps.sales.models import CustomerPayment, Receivable, Sale, SaleLine, SalePayment, SaleReturn

from .excel import Sheet, build_sheets

ZERO = Decimal("0")

# Kalit — o'zbekcha matn; tarjima topilmasa o'zi ishlatiladi
TR: dict[str, dict[str, str]] = {
    "ru": {
        "Umumiy": "Сводка", "Kunlar": "По дням", "Mahsulotlar": "Товары",
        "To'lov turlari": "Способы оплаты", "Kassirlar": "Кассиры", "Xarajatlar": "Расходы",
        "Qarzdorlar": "Должники", "Ko'rsatkich": "Показатель", "Qiymat": "Значение",
        "Davr": "Период", "Do'kon": "Магазин", "Yaratilgan": "Сформирован",
        "Cheklar soni": "Количество чеков", "Savdo summasi": "Сумма продаж",
        "O'rtacha chek": "Средний чек", "Chegirmalar": "Скидки", "Tannarx": "Себестоимость",
        "Yalpi foyda": "Валовая прибыль", "Sof foyda": "Чистая прибыль",
        "Bekor qilingan savdolar": "Отменённые продажи", "Nasiyaga sotildi": "Продано в долг",
        "Nasiya to'lovlari olindi": "Получено оплат по долгам",
        "Jami qarz (hozir)": "Общий долг (сейчас)", "Muddati o'tgan qarz": "Просроченный долг",
        "Ombor qiymati (tannarxda)": "Стоимость склада (по себестоимости)",
        "Sana": "Дата", "Cheklar": "Чеки", "Savdo": "Продажи", "Foyda": "Прибыль",
        "Mahsulot": "Товар", "Artikul": "Артикул", "Miqdor": "Количество", "Birlik": "Ед.",
        "Summa": "Сумма", "Ulush, %": "Доля, %", "Usul": "Способ", "Kassir": "Кассир",
        "Kategoriya": "Категория", "Soni": "Кол-во", "Mijoz": "Клиент", "Telefon": "Телефон",
        "Qarz": "Долг", "Muddati o'tgan": "Просрочено", "Jami": "Итого",
        "Naqd": "Наличные", "Plastik karta": "Карта", "O'tkazma": "Перевод", "Nasiya": "Долг",
        "Statistika": "Статистика",
        "Qaytarishlar": "Возвраты",
        "Sof savdo": "Чистые продажи",
    },
    "en": {
        "Umumiy": "Summary", "Kunlar": "By day", "Mahsulotlar": "Products",
        "To'lov turlari": "Payment methods", "Kassirlar": "Cashiers", "Xarajatlar": "Expenses",
        "Qarzdorlar": "Debtors", "Ko'rsatkich": "Metric", "Qiymat": "Value",
        "Davr": "Period", "Do'kon": "Store", "Yaratilgan": "Generated",
        "Cheklar soni": "Receipts", "Savdo summasi": "Revenue", "O'rtacha chek": "Average receipt",
        "Chegirmalar": "Discounts", "Tannarx": "Cost of goods", "Yalpi foyda": "Gross profit",
        "Sof foyda": "Net profit", "Bekor qilingan savdolar": "Cancelled sales",
        "Nasiyaga sotildi": "Sold on credit", "Nasiya to'lovlari olindi": "Debt payments received",
        "Jami qarz (hozir)": "Total debt (now)", "Muddati o'tgan qarz": "Overdue debt",
        "Ombor qiymati (tannarxda)": "Inventory value (at cost)",
        "Sana": "Date", "Cheklar": "Receipts", "Savdo": "Revenue", "Foyda": "Profit",
        "Mahsulot": "Product", "Artikul": "SKU", "Miqdor": "Quantity", "Birlik": "Unit",
        "Summa": "Amount", "Ulush, %": "Share, %", "Usul": "Method", "Kassir": "Cashier",
        "Kategoriya": "Category", "Soni": "Count", "Mijoz": "Customer", "Telefon": "Phone",
        "Qarz": "Debt", "Muddati o'tgan": "Overdue", "Jami": "Total",
        "Naqd": "Cash", "Plastik karta": "Card", "O'tkazma": "Transfer", "Nasiya": "Credit",
        "Statistika": "Statistics",
        "Qaytarishlar": "Returns",
        "Sof savdo": "Net sales",
    },
}  # fmt: skip


def stats_workbook(tenant, user, date_from: date, date_to: date, lang: str = "uz") -> bytes:
    def t(text: str) -> str:
        return TR.get(lang, {}).get(text, text)

    with_cost = user.has_perm_code("cost.view")
    branch_ids = user.allowed_branch_ids()

    sales = Sale.objects.filter(tenant=tenant, date__gte=date_from, date__lte=date_to)
    expenses = Expense.objects.filter(tenant=tenant, date__gte=date_from, date__lte=date_to)
    if branch_ids is not None:
        sales = sales.filter(warehouse__branch_id__in=branch_ids)
        expenses = expenses.filter(branch_id__in=branch_ids)
    posted = sales.filter(status=Sale.POSTED)

    agg = posted.aggregate(n=Count("id"), total=Sum("total"), cost=Sum("cost_total"),
                           discount=Sum("discount_total"))  # fmt: skip
    gross_revenue = agg["total"] or ZERO
    ret_qs = SaleReturn.objects.filter(tenant=tenant, date__gte=date_from, date__lte=date_to)
    if branch_ids is not None:
        ret_qs = ret_qs.filter(sale__warehouse__branch_id__in=branch_ids)
    ret = ret_qs.aggregate(total=Sum("total"), cost=Sum("cost_total"))
    returns_total = ret["total"] or ZERO
    revenue = gross_revenue - returns_total  # sof savdo
    cost = (agg["cost"] or ZERO) - (ret["cost"] or ZERO)
    exp_total = expenses.aggregate(s=Sum("amount"))["s"] or ZERO
    by_method = dict(
        SalePayment.objects.filter(sale__in=posted).values_list("method")
        .annotate(s=Sum("amount")).values_list("method", "s")
    )  # fmt: skip
    debt_paid = (
        CustomerPayment.objects.filter(tenant=tenant, date__gte=date_from, date__lte=date_to)
        .aggregate(s=Sum("amount"))["s"] or ZERO
    )  # fmt: skip
    open_r = Receivable.objects.filter(tenant=tenant, status=Receivable.OPEN)
    today = timezone.localdate()
    debt_now = open_r.aggregate(s=Sum(F("amount") - F("paid")))["s"] or ZERO
    debt_overdue = (
        open_r.filter(due_date__lt=today).aggregate(s=Sum(F("amount") - F("paid")))["s"] or ZERO
    )

    method_names = {"cash": t("Naqd"), "card": t("Plastik karta"), "transfer": t("O'tkazma"),
                    "credit": t("Nasiya")}  # fmt: skip
    period = f"{date_from:%d.%m.%Y} — {date_to:%d.%m.%Y}"
    notes = [
        f"{t('Statistika')}: {tenant.name}",
        f"{t('Davr')}: {period}",
        f"{t('Yaratilgan')}: {timezone.localtime():%d.%m.%Y %H:%M}",
    ]

    # 1. Umumiy
    summary = [
        [t("Cheklar soni"), agg["n"]],
        [t("Savdo summasi"), q_money(gross_revenue)],
        [t("Qaytarishlar"), q_money(returns_total)],
        [t("Sof savdo"), q_money(revenue)],
        [t("O'rtacha chek"), q_money(gross_revenue / agg["n"]) if agg["n"] else ZERO],
        [t("Chegirmalar"), q_money(agg["discount"] or ZERO)],
    ]
    if with_cost:
        summary += [
            [t("Tannarx"), q_money(cost)],
            [t("Yalpi foyda"), q_money(revenue - cost)],
        ]
    summary.append([t("Xarajatlar"), q_money(exp_total)])
    if with_cost:
        summary.append([t("Sof foyda"), q_money(revenue - cost - exp_total)])
    summary += [
        [t("Bekor qilingan savdolar"), sales.filter(status=Sale.CANCELLED).count()],
        [t("Nasiyaga sotildi"), q_money(by_method.get("credit", ZERO))],
        [t("Nasiya to'lovlari olindi"), q_money(debt_paid)],
        [t("Jami qarz (hozir)"), q_money(debt_now)],
        [t("Muddati o'tgan qarz"), q_money(debt_overdue)],
    ]
    if with_cost:
        stock = StockBalance.objects.filter(tenant=tenant, qty__gt=0)
        if branch_ids is not None:
            stock = stock.filter(warehouse__branch_id__in=branch_ids)
        value = sum((b.qty * b.avg_cost for b in stock.only("qty", "avg_cost")), ZERO)
        summary.append([t("Ombor qiymati (tannarxda)"), q_money(value)])
    sheets = [Sheet(t("Umumiy"), [t("Ko'rsatkich"), t("Qiymat")], summary, [36, 22], notes=notes)]

    # 2. Kunlar bo'yicha
    day_sales = {
        r["date"]: r for r in posted.values("date").annotate(
            n=Count("id"), total=Sum("total"), cost=Sum("cost_total"))
    }  # fmt: skip
    day_exp = dict(expenses.values_list("date").annotate(s=Sum("amount")).values_list("date", "s"))
    day_rows = []
    d = date_from
    while d <= date_to:
        r = day_sales.get(d, {})
        total = r.get("total") or ZERO
        row = [d, r.get("n", 0), total]
        if with_cost:
            row += [r.get("cost") or ZERO, total - (r.get("cost") or ZERO)]
        row.append(day_exp.get(d, ZERO))
        day_rows.append(row)
        d += timedelta(days=1)
    day_head = [t("Sana"), t("Cheklar"), t("Savdo")]
    if with_cost:
        day_head += [t("Tannarx"), t("Foyda")]
    day_head.append(t("Xarajatlar"))
    footer = (
        [t("Jami"), agg["n"], gross_revenue]
        + ([agg["cost"] or ZERO, gross_revenue - (agg["cost"] or ZERO)] if with_cost else [])
        + [exp_total]
    )
    sheets.append(Sheet(t("Kunlar"), day_head, day_rows, [14, 10, 18, 18, 18, 16], footer=footer))

    # 3. Mahsulotlar
    prod = (
        SaleLine.objects.filter(sale__in=posted)
        .values(name=F("product__name"), sku=F("product__sku"), unit_short=F("product__base_unit__short"))
        .annotate(qty=Sum("base_qty"), revenue=Sum("total"), cost=Sum("cost_total"))
        .order_by("-revenue")
    )  # fmt: skip
    prod_head = [t("Mahsulot"), t("Artikul"), t("Miqdor"), t("Birlik"), t("Summa")]
    if with_cost:
        prod_head += [t("Tannarx"), t("Foyda")]
    prod_rows = []
    for r in prod:
        row = [r["name"], r["sku"], r["qty"], r["unit_short"], r["revenue"]]
        if with_cost:
            row += [r["cost"], r["revenue"] - r["cost"]]
        prod_rows.append(row)
    sheets.append(Sheet(t("Mahsulotlar"), prod_head, prod_rows, [40, 12, 12, 8, 18, 18, 18]))

    # 4. To'lov turlari
    paid_total = sum(by_method.values(), ZERO)
    sheets.append(Sheet(
        t("To'lov turlari"), [t("Usul"), t("Summa"), t("Ulush, %")],
        [[method_names.get(m, m), s, round(float(s / paid_total * 100), 1) if paid_total else 0]
         for m, s in sorted(by_method.items(), key=lambda x: -x[1])],
        [20, 18, 12], footer=[t("Jami"), paid_total, 100 if paid_total else 0],
    ))  # fmt: skip

    # 5. Kassirlar
    cashiers = (
        posted.values("cashier__username", "cashier__first_name", "cashier__last_name")
        .annotate(n=Count("id"), total=Sum("total")).order_by("-total")
    )  # fmt: skip
    sheets.append(Sheet(
        t("Kassirlar"), [t("Kassir"), t("Cheklar"), t("Savdo"), t("O'rtacha chek")],
        [[" ".join(filter(None, [c["cashier__first_name"], c["cashier__last_name"]]))
          or c["cashier__username"], c["n"], c["total"], q_money(c["total"] / c["n"])]
         for c in cashiers],
        [26, 10, 18, 16],
    ))  # fmt: skip

    # 6. Xarajatlar
    exp_rows = list(
        expenses.values_list("category__name").annotate(n=Count("id"), s=Sum("amount"))
        .order_by("-s").values_list("category__name", "n", "s")
    )  # fmt: skip
    sheets.append(Sheet(
        t("Xarajatlar"), [t("Kategoriya"), t("Soni"), t("Summa")], [list(r) for r in exp_rows],
        [24, 10, 18], footer=[t("Jami"), sum(r[1] for r in exp_rows), exp_total],
    ))  # fmt: skip

    # 7. Qarzdorlar (joriy holat)
    debtors = (
        open_r.values("customer__name", "customer__phone")
        .annotate(debt=Sum(F("amount") - F("paid"))).order_by("-debt")
    )  # fmt: skip
    overdue_map = dict(
        open_r.filter(due_date__lt=today).values_list("customer__name")
        .annotate(s=Sum(F("amount") - F("paid"))).values_list("customer__name", "s")
    )  # fmt: skip
    sheets.append(Sheet(
        t("Qarzdorlar"), [t("Mijoz"), t("Telefon"), t("Qarz"), t("Muddati o'tgan")],
        [[r["customer__name"], r["customer__phone"], r["debt"],
          overdue_map.get(r["customer__name"], ZERO)] for r in debtors],
        [30, 18, 18, 18], footer=[t("Jami"), None, debt_now, debt_overdue],
    ))  # fmt: skip

    return build_sheets(sheets)
