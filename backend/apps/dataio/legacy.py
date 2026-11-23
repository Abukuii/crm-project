"""Eski tizimdan (savdo_sayt / crm_project2, "savdolarim.uz" 1.0) ma'lumot ko'chirish.

Manba — eski PostgreSQL bazasi (yoki sinov uchun SQLite). Faqat O'QILADI, hech narsa yozilmaydi.
Hammasi bitta tranzaksiyada: xato bo'lsa — hech narsa saqlanmaydi.

Ko'chiriladi: mahsulotlar (+ joriy qoldiq "boshlang'ich qoldiq" hujjati sifatida), mijozlar,
savdo tarixi (qoldiqqa ta'sir qilmaydi), nasiya qarzlari va to'lovlar, xarajatlar, eslatmalar,
dollar kursi va foydalanuvchilar (parol xeshlari o'zgarmaydi — eski parol bilan kiriladi).
"""

import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.catalog.models import PriceType, Product, Unit
from apps.catalog.services import save_product
from apps.core import audit
from apps.core.counters import next_number
from apps.core.money import USD, UZS, q_money, q_price
from apps.currency.models import ExchangeRate
from apps.finance.models import Expense, ExpenseCategory
from apps.inventory.models import Warehouse
from apps.purchasing.models import Purchase
from apps.purchasing.services import post_purchase, save_draft
from apps.reminders.models import Reminder
from apps.sales.models import (
    Customer,
    CustomerPayment,
    PaymentAllocation,
    Receivable,
    Sale,
    SaleLine,
    SalePayment,
)
from apps.tenancy.models import Tenant

ZERO = Decimal("0")
LEGACY_NOTE = "Eski tizimdan ko'chirildi"
LEGACY_SKU = "L{id}"
EXPENSE_CATEGORIES = {"ijara": "Ijara", "transport": "Transport", "maosh": "Maosh",
                      "kommunal": "Kommunal", "boshqa": "Boshqa"}  # fmt: skip
REMINDER_LEVELS = {"oddiy": "normal", "muhim": "important", "shoshilinch": "urgent"}


class LegacyImportError(Exception):
    pass


# ── Manba ────────────────────────────────────────────────────────────────────
class Source:
    """Eski bazadan o'qish (faqat SELECT). ``postgres://...`` yoki ``sqlite:///fayl``."""

    def __init__(self, url: str):
        if url.startswith("sqlite:///"):
            self.conn = sqlite3.connect(url[len("sqlite:///") :])
            self.conn.row_factory = sqlite3.Row
            self.kind = "sqlite"
        elif url.startswith(("postgres://", "postgresql://")):
            import psycopg
            from psycopg.rows import dict_row

            self.conn = psycopg.connect(url, row_factory=dict_row)
            self.conn.read_only = True
            self.kind = "postgres"
        else:
            raise LegacyImportError(
                "Manba manzili postgres://... yoki sqlite:///... bo'lishi kerak"
            )

    def has_table(self, name: str) -> bool:
        if self.kind == "sqlite":
            sql = "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?"
        else:
            sql = "SELECT 1 FROM information_schema.tables WHERE table_name=%s"
        return self.conn.execute(sql, (name,)).fetchone() is not None

    def rows(self, sql: str) -> list[dict]:
        return [dict(r) for r in self.conn.execute(sql).fetchall()]

    def close(self) -> None:
        self.conn.close()


# ── Yordamchilar ─────────────────────────────────────────────────────────────
def _dec(value) -> Decimal:
    return Decimal(str(value)) if value is not None else ZERO


def _date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _dt(value) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace(" ", "T")[:26])
    return dt if timezone.is_aware(dt) else timezone.make_aware(dt)


def _phone(value) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit() or ch == "+")


@dataclass
class Report:
    counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    warnings: list[str] = field(default_factory=list)
    old_stock_units: int = 0
    new_stock_units: Decimal = ZERO
    old_debt: Decimal = ZERO
    new_debt: Decimal = ZERO

    def add(self, key: str, n: int = 1) -> None:
        self.counts[key] += n


# ── Asosiy ko'chirish ────────────────────────────────────────────────────────
@transaction.atomic
def import_legacy(*, source: Source, tenant: Tenant, owner: User, dry_run: bool = False) -> Report:
    if Product.objects.filter(legacy_marker(), tenant=tenant).exists():
        raise LegacyImportError("Bu biznesga eski ma'lumotlar allaqachon ko'chirilgan")
    for table in ("crm_mahsulot", "crm_mijoz", "crm_savdo", "crm_savdoitem"):
        if not source.has_table(table):
            raise LegacyImportError(f"Eski bazada '{table}' jadvali yo'q — manba noto'g'ri")

    rep = Report()
    warehouse = Warehouse.objects.filter(tenant=tenant, is_active=True).order_by("id").first()
    if warehouse is None:
        raise LegacyImportError("Faol ombor yo'q")
    unit = Unit.objects.get(tenant=tenant, name="dona")
    retail = PriceType.objects.filter(tenant=tenant).order_by("-is_default", "sort", "id").first()

    # 1. Dollar kursi (eski — bitta yozuv)
    rate = None
    if source.has_table("crm_dollarkurs"):
        for r in source.rows("SELECT kurs, yangilangan FROM crm_dollarkurs ORDER BY id DESC"):
            rate = q_price(_dec(r["kurs"]))
            ExchangeRate.objects.update_or_create(
                tenant=tenant, currency=USD, date=_date(r["yangilangan"]),
                defaults={"rate": rate, "source": ExchangeRate.SOURCE_MANUAL, "created_by": owner},
            )  # fmt: skip
            rep.add("dollar_kursi")
            break

    # 2. Mahsulotlar + taxminiy tannarx
    last_cost: dict[int, Decimal] = {}
    if source.has_table("crm_kirim"):
        kirim = source.rows(
            "SELECT mahsulot_id, asl_narx, valyuta, dollar_kursi FROM crm_kirim "
            "WHERE asl_narx IS NOT NULL ORDER BY id"
        )
        for k in kirim:  # oxirgisi qoladi
            cost = _dec(k["asl_narx"])
            if k["valyuta"] == "usd":
                cost *= _dec(k["dollar_kursi"]) or rate or ZERO
            if cost > ZERO:
                last_cost[k["mahsulot_id"]] = q_price(cost)

    products: dict[int, Product] = {}
    opening_lines = []
    for m in source.rows("SELECT id, nomi, qoldi, narxi, valyuta FROM crm_mahsulot ORDER BY id"):
        currency = USD if m["valyuta"] == "usd" else UZS
        price = _dec(m["narxi"])
        p = save_product(tenant=tenant, user=owner, data={
            "name": (m["nomi"] or f"Mahsulot {m['id']}")[:255], "sku": LEGACY_SKU.format(id=m["id"]),
            "base_unit": unit, "price_currency": currency,
            "description": LEGACY_NOTE,
            "prices": [{"price_type": retail, "amount": price}] if price > ZERO else [],
        })  # fmt: skip
        products[m["id"]] = p
        rep.add("mahsulotlar")
        qty = int(m["qoldi"] or 0)
        rep.old_stock_units += max(qty, 0)
        if qty > 0:
            cost = last_cost.get(m["id"])
            if cost is None:
                # Xarid narxi saqlanmagan — sotish narxi tannarx deb olinadi (foyda kam ko'rsatiladi)
                cost = price * (rate or ZERO) if currency == USD else price
                rep.add("tannarx_taxminiy")
            opening_lines.append({"product": p, "unit": unit, "qty": Decimal(qty), "price": cost})
        elif qty < 0:
            rep.warnings.append(f"'{p.name}': eski qoldiq manfiy ({qty}) — 0 deb olindi")

    if opening_lines:
        doc = save_draft(tenant=tenant, user=owner, data={
            "kind": Purchase.KIND_OPENING, "warehouse": warehouse, "currency": UZS,
            "note": "Eski tizimdan ko'chirilgan qoldiq", "lines": opening_lines,
        })  # fmt: skip
        post_purchase(tenant=tenant, user=owner, purchase=doc)
        rep.new_stock_units = sum((ln["qty"] for ln in opening_lines), ZERO)

    # 3. Mijozlar (telefon bo'yicha birlashtiriladi)
    customers: dict[int, Customer] = {}
    by_phone: dict[str, Customer] = {
        c.phone: c for c in Customer.objects.filter(tenant=tenant).exclude(phone="")
    }
    for c in source.rows("SELECT id, ism_familiya, telefon, manzil FROM crm_mijoz ORDER BY id"):
        phone = _phone(c["telefon"])
        existing = by_phone.get(phone) if phone else None
        if existing is not None:
            customers[c["id"]] = existing
            rep.add("mijoz_birlashtirildi")
            continue
        obj = Customer.objects.create(tenant=tenant, name=(c["ism_familiya"] or "—")[:200],
                                      phone=phone, address=(c["manzil"] or "")[:300])  # fmt: skip
        customers[c["id"]] = obj
        if phone:
            by_phone[phone] = obj
        rep.add("mijozlar")

    # 4. Savdo tarixi (qoldiqqa TA'SIR QILMAYDI — joriy qoldiq 2-bosqichda olingan)
    items_by_sale: dict[int, list[dict]] = defaultdict(list)
    for it in source.rows(
        "SELECT savdo_id, mahsulot_id, soni, narxi, kelishilgan_narx FROM crm_savdoitem ORDER BY id"
    ):
        items_by_sale[it["savdo_id"]].append(it)
    payments_by_sale: dict[int, list[dict]] = defaultdict(list)
    if source.has_table("crm_tolovtarixi"):
        for t in source.rows("SELECT savdo_id, summa, sana, izoh FROM crm_tolovtarixi ORDER BY id"):
            payments_by_sale[t["savdo_id"]].append(t)

    # Tarixiy savdolar tannarxi: oxirgi xarid narxi, bo'lmasa qoldiqdagi taxminiy tannarx
    opening_cost = {ln["product"].pk: ln["price"] for ln in opening_lines}
    unit_cost = {
        old_id: last_cost.get(old_id) or opening_cost.get(p.pk) for old_id, p in products.items()
    }

    sales = source.rows(
        "SELECT id, mijoz_id, sana, tolov_turi, jami_summa, bosh_tolov, to_langan, izoh, yaratilgan "
        "FROM crm_savdo ORDER BY id"
    )
    for s in sales:
        items = [i for i in items_by_sale.get(s["id"], []) if i["mahsulot_id"] in products]
        if not items:
            rep.warnings.append(f"Eski savdo #{s['id']}: tovar qatorlari yo'q — o'tkazib yuborildi")
            continue
        customer = customers.get(s["mijoz_id"]) if s["mijoz_id"] else None
        sale = Sale.objects.create(
            tenant=tenant, number=next_number(tenant, "sale"), date=_date(s["sana"]),
            warehouse=warehouse, cashier=owner, customer=customer, price_type=retail,
            note=(f"Eski #{s['id']}. " + (s["izoh"] or ""))[:300],
        )  # fmt: skip
        Sale.objects.filter(pk=sale.pk).update(created_at=_dt(s["yaratilgan"]))
        subtotal = total = cost_total = ZERO
        lines = []
        for pos, it in enumerate(items):
            qty = Decimal(int(it["soni"] or 0))
            list_price = q_money(_dec(it["narxi"]))
            price = q_money(_dec(it["kelishilgan_narx"])) if it["kelishilgan_narx"] else list_price
            line_total = q_money(price * qty)
            uc = unit_cost.get(it["mahsulot_id"]) or price
            line_cost = q_money(uc * qty)
            lines.append(SaleLine(
                tenant=tenant, sale=sale, product=products[it["mahsulot_id"]], unit=unit,
                factor=Decimal(1), qty=qty, base_qty=qty, list_price=list_price, price=price,
                discount=q_money((list_price - price) * qty) if price < list_price else ZERO,
                total=line_total, unit_cost=uc, cost_total=line_cost, position=pos,
            ))  # fmt: skip
            subtotal += q_money(list_price * qty)
            total += line_total
            cost_total += line_cost
        SaleLine.objects.bulk_create(lines)
        Sale.objects.filter(pk=sale.pk).update(
            subtotal=subtotal, total=total, discount_total=q_money(subtotal - total),
            cost_total=cost_total,
        )  # fmt: skip
        rep.add("savdolar")

        method = {"naqd": "cash", "plastik": "card"}.get(s["tolov_turi"])
        if s["tolov_turi"] != "nasiya":
            SalePayment.objects.create(
                tenant=tenant, sale=sale, method=method or "cash", amount=total
            )
            continue
        down = min(q_money(_dec(s["bosh_tolov"])), total)
        credit = q_money(total - down)
        if customer is None:
            rep.warnings.append(f"Eski nasiya savdo #{s['id']}: mijozsiz — naqd deb olindi")
            SalePayment.objects.create(tenant=tenant, sale=sale, method="cash", amount=total)
            continue
        if down > ZERO:
            SalePayment.objects.create(tenant=tenant, sale=sale, method="cash", amount=down)
        if credit <= ZERO:
            continue
        SalePayment.objects.create(tenant=tenant, sale=sale, method="credit", amount=credit)
        rec = Receivable.objects.create(tenant=tenant, customer=customer, sale=sale, amount=credit,
                                        due_date=_date(s["sana"]) + timedelta(days=30))  # fmt: skip
        old_paid = sum((_dec(t["summa"]) for t in payments_by_sale.get(s["id"], [])), ZERO)
        if s["to_langan"] in (False, 0, "0", "f", "false"):
            rep.old_debt += max(credit - old_paid, ZERO)  # eski tizim ko'rsatgan qarz
        paid = ZERO
        for t in payments_by_sale.get(s["id"], []):
            amount = min(q_money(_dec(t["summa"])), credit - paid)
            if amount <= ZERO:
                continue
            pay = CustomerPayment.objects.create(
                tenant=tenant, customer=customer, amount=amount, method="cash",
                date=_date(t["sana"]), note=(t["izoh"] or "Eski tizim")[:300], created_by=owner,
            )  # fmt: skip
            PaymentAllocation.objects.create(
                tenant=tenant, payment=pay, receivable=rec, amount=amount
            )
            paid += amount
            rep.add("nasiya_tolovlari")
        # Eski "to'liq to'landi" tugmasi to'lov yozmas edi — qolganini yopuvchi to'lov sifatida olamiz
        if (s["to_langan"] in (True, 1, "1", "t", "true")) and paid < credit:
            rest = credit - paid
            pay = CustomerPayment.objects.create(
                tenant=tenant, customer=customer, amount=rest, method="cash", date=_date(s["sana"]),
                note="Eski tizimda to'langan deb belgilangan", created_by=owner,
            )  # fmt: skip
            PaymentAllocation.objects.create(
                tenant=tenant, payment=pay, receivable=rec, amount=rest
            )
            paid = credit
            rep.add("yopilgan_eski_qarz")
        rec.paid = paid
        rec.status = Receivable.CLOSED if paid >= credit else Receivable.OPEN
        rec.save(update_fields=["paid", "status", "updated_at"])
        rep.new_debt += credit - paid
        rep.add("nasiya_qarzlar")

    # 5. Xarajatlar
    if source.has_table("crm_xarajat"):
        cats = {c.name: c for c in ExpenseCategory.objects.filter(tenant=tenant)}
        for x in source.rows(
            "SELECT nomi, summa, kategoriya, sana, izoh FROM crm_xarajat ORDER BY id"
        ):
            name = EXPENSE_CATEGORIES.get(x["kategoriya"], "Boshqa")
            cat = cats.get(name) or ExpenseCategory.objects.create(tenant=tenant, name=name)
            cats[name] = cat
            Expense.objects.create(tenant=tenant, name=(x["nomi"] or "—")[:200], category=cat,
                                   amount=q_money(_dec(x["summa"])), date=_date(x["sana"]),
                                   note=x["izoh"] or "", created_by=owner)  # fmt: skip
            rep.add("xarajatlar")

    # 6. Eslatmalar
    if source.has_table("crm_eslatma"):
        for e in source.rows("SELECT matn, daraja, bajarildi FROM crm_eslatma ORDER BY id"):
            Reminder.objects.create(tenant=tenant, text=e["matn"] or "",
                                    level=REMINDER_LEVELS.get(e["daraja"], "normal"),
                                    is_done=bool(e["bajarildi"]), created_by=owner)  # fmt: skip
            rep.add("eslatmalar")

    # 7. Foydalanuvchilar (parol xeshi o'zgarmaydi)
    _import_users(source, tenant, rep)

    audit.record(action="legacy.import", entity="tenant", entity_id=tenant.pk, tenant=tenant,
                 user=owner, after=dict(rep.counts))  # fmt: skip
    if dry_run:
        transaction.set_rollback(True)
    return rep


def legacy_marker():
    """Ko'chirilgan mahsulotlarni ajratuvchi shart — takroriy ko'chirishdan himoya."""
    return Q(description=LEGACY_NOTE)


def _import_users(source: Source, tenant: Tenant, rep: Report) -> None:
    if not source.has_table("auth_user"):
        return
    roles = {r.name: r for r in Role.objects.filter(tenant=tenant)}
    groups: dict[int, set[str]] = defaultdict(set)
    if source.has_table("auth_user_groups") and source.has_table("auth_group"):
        for g in source.rows(
            "SELECT ug.user_id, g.name FROM auth_user_groups ug JOIN auth_group g ON g.id = ug.group_id"
        ):
            groups[g["user_id"]].add(g["name"])
    branch_ids = list(tenant_branches(tenant))
    for u in source.rows(
        "SELECT id, username, password, first_name, last_name, email, is_active, is_superuser, "
        "date_joined FROM auth_user ORDER BY id"
    ):
        username = u["username"]
        if User.objects.filter(username=username).exists():
            username = f"{tenant.slug}_{username}"[:150]
            if User.objects.filter(username=username).exists():
                rep.warnings.append(
                    f"Foydalanuvchi '{u['username']}' — login band, o'tkazib yuborildi"
                )
                continue
            rep.warnings.append(f"Login '{u['username']}' band edi — '{username}' deb yaratildi")
        user = User(
            username=username, password=u["password"], first_name=u["first_name"] or "",
            last_name=u["last_name"] or "", email=u["email"] or "",
            is_active=bool(u["is_active"]), tenant=tenant,
        )  # fmt: skip
        user.save()
        is_admin = bool(u["is_superuser"]) or "Admin" in groups[u["id"]]
        role = (
            roles["Egasi"]
            if is_admin
            else roles["Menejer"]
            if "Menejer" in groups[u["id"]]
            else roles["Kassir"]
        )
        user.roles.add(role)
        if not is_admin:
            user.branches.add(*branch_ids)
        rep.add("foydalanuvchilar")


def tenant_branches(tenant: Tenant):
    from apps.tenancy.models import Branch

    return Branch.objects.filter(tenant=tenant).values_list("id", flat=True)
