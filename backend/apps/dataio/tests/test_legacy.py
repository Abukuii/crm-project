import io
import sqlite3
from decimal import Decimal as D

import pytest
from django.contrib.auth.hashers import make_password
from django.core.management import CommandError, call_command

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.currency.models import ExchangeRate
from apps.finance.models import Expense
from apps.inventory.models import StockBalance
from apps.reminders.models import Reminder
from apps.sales.models import Customer, Receivable, Sale

pytestmark = pytest.mark.django_db

SCHEMA = """
CREATE TABLE crm_dollarkurs (id INTEGER PRIMARY KEY, kurs NUMERIC, yangilangan TEXT);
CREATE TABLE crm_mahsulot (id INTEGER PRIMARY KEY, nomi TEXT, qoldi INTEGER, narxi NUMERIC,
  valyuta TEXT, yaratilgan TEXT, yangilangan TEXT);
CREATE TABLE crm_kirim (id INTEGER PRIMARY KEY, mahsulot_id INTEGER, soni INTEGER, narxi NUMERIC,
  valyuta TEXT, asl_narx NUMERIC, foiz NUMERIC, narx_turi TEXT, dollar_kursi NUMERIC, izoh TEXT,
  sana TEXT, yaratilgan TEXT);
CREATE TABLE crm_mijoz (id INTEGER PRIMARY KEY, ism_familiya TEXT, telefon TEXT, manzil TEXT,
  yaratilgan TEXT);
CREATE TABLE crm_savdo (id INTEGER PRIMARY KEY, mijoz_id INTEGER, sana TEXT, tolov_turi TEXT,
  jami_summa NUMERIC, bosh_tolov NUMERIC, to_langan INTEGER, izoh TEXT, yaratilgan TEXT);
CREATE TABLE crm_savdoitem (id INTEGER PRIMARY KEY, savdo_id INTEGER, mahsulot_id INTEGER,
  soni INTEGER, narxi NUMERIC, kelishilgan_narx NUMERIC);
CREATE TABLE crm_tolovtarixi (id INTEGER PRIMARY KEY, savdo_id INTEGER, summa NUMERIC, sana TEXT,
  izoh TEXT, yaratilgan TEXT);
CREATE TABLE crm_xarajat (id INTEGER PRIMARY KEY, nomi TEXT, summa NUMERIC, kategoriya TEXT,
  sana TEXT, izoh TEXT, yaratilgan TEXT);
CREATE TABLE crm_eslatma (id INTEGER PRIMARY KEY, matn TEXT, daraja TEXT, bajarildi INTEGER,
  yaratilgan TEXT);
CREATE TABLE auth_user (id INTEGER PRIMARY KEY, username TEXT, password TEXT, first_name TEXT,
  last_name TEXT, email TEXT, is_active INTEGER, is_superuser INTEGER, date_joined TEXT);
CREATE TABLE auth_group (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE auth_user_groups (id INTEGER PRIMARY KEY, user_id INTEGER, group_id INTEGER);
"""


@pytest.fixture
def legacy_db(tmp_path):
    path = tmp_path / "old.sqlite3"
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    ts = "2026-05-10 10:00:00"
    con.executemany("INSERT INTO crm_dollarkurs VALUES (?,?,?)", [(1, "12600", ts)])
    con.executemany("INSERT INTO crm_mahsulot VALUES (?,?,?,?,?,?,?)", [
        (1, "Sement M-400", 40, "58000", "uzs", ts, ts),
        (2, "Kabel (USD)", 10, "1", "usd", ts, ts),  # 1 dollar
        (3, "Eski tugagan", -2, "5000", "uzs", ts, ts),
    ])  # fmt: skip
    con.executemany("INSERT INTO crm_kirim VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [
        (1, 1, 50, "58000", "uzs", "49000", "0", "aniq", None, "", "2026-05-01", ts),
    ])  # fmt: skip
    con.executemany("INSERT INTO crm_mijoz VALUES (?,?,?,?,?)", [
        (1, "Usta Botir", "+998 90 111-22-33", "Chilonzor", ts),
        (2, "Botir aka", "998901112233", "", ts),  # o'sha telefon (+ yo'q) — alohida
        (3, "Ali", "+998901112233", "", ts),  # 1-mijoz bilan bir xil — birlashadi
    ])  # fmt: skip
    con.executemany("INSERT INTO crm_savdo VALUES (?,?,?,?,?,?,?,?,?)", [
        (1, None, "2026-05-11", "naqd", "116000", "0", 1, "", ts),
        (2, 1, "2026-05-12", "nasiya", "174000", "24000", 0, "", ts),  # qarz 150 000, 50 000 to'langan
        (3, 1, "2026-05-13", "nasiya", "58000", "0", 1, "", ts),  # "to'liq to'landi" tugmasi bilan
        (4, None, "2026-05-14", "nasiya", "58000", "0", 0, "", ts),  # mijozsiz nasiya
        (5, None, "2026-05-15", "plastik", "50000", "0", 1, "", ts),
    ])  # fmt: skip
    con.executemany("INSERT INTO crm_savdoitem VALUES (?,?,?,?,?,?)", [
        (1, 1, 1, 2, "58000", None),
        (2, 2, 1, 3, "58000", None),
        (3, 3, 1, 1, "58000", None),
        (4, 4, 1, 1, "58000", None),
        (5, 5, 1, 1, "58000", "50000"),  # kelishilgan narx
    ])  # fmt: skip
    con.executemany("INSERT INTO crm_tolovtarixi VALUES (?,?,?,?,?,?)", [
        (1, 2, "30000", "2026-05-13", "naqd", ts),
        (2, 2, "20000", "2026-05-14", "", ts),
    ])  # fmt: skip
    con.executemany("INSERT INTO crm_xarajat VALUES (?,?,?,?,?,?,?)", [
        (1, "Do'kon ijarasi", "3000000", "ijara", "2026-05-01", "", ts),
        (2, "Yuk", "150000", "transport", "2026-05-02", "", ts),
    ])  # fmt: skip
    con.executemany("INSERT INTO crm_eslatma VALUES (?,?,?,?,?)", [
        (1, "Sement buyurtma", "shoshilinch", 0, ts),
    ])  # fmt: skip
    con.executemany("INSERT INTO auth_group VALUES (?,?)", [(1, "Admin"), (2, "Menejer")])
    con.executemany("INSERT INTO auth_user VALUES (?,?,?,?,?,?,?,?,?)", [
        (1, "boss", make_password("eski-parol-1"), "Otabek", "", "", 1, 1, ts),
        (2, "sotuvchi", make_password("eski-parol-2"), "Vali", "", "", 1, 0, ts),
    ])  # fmt: skip
    con.executemany("INSERT INTO auth_user_groups VALUES (?,?,?)", [(1, 2, 2)])
    con.commit()
    con.close()
    return f"sqlite:///{path}"


def _run(*args):
    out = io.StringIO()
    call_command("import_legacy", *args, stdout=out)
    return out.getvalue()


def test_full_import_and_reconciliation(legacy_db):
    out = _run("--source", legacy_db, "--name", "Savdolarim", "--owner", "egasi",
               "--password", "Yangi-parol-123")  # fmt: skip
    assert "Qoldiq (dona)  50 -> 50  OK" in out
    assert "Ochiq qarz     100000.00 -> 100000.00  OK" in out

    cement = Product.objects.get(sku="L1")
    assert cement.prices.get().amount == D("58000")
    bal = StockBalance.objects.get(product=cement)
    assert (bal.qty, bal.avg_cost) == (D("40"), D("49000"))  # oxirgi xarid narxi
    cable = Product.objects.get(sku="L2")
    assert cable.price_currency == "USD"
    assert StockBalance.objects.get(product=cable).avg_cost == D("12600")  # 1 $ × kurs (taxminiy)
    assert not StockBalance.objects.filter(product__sku="L3", qty__gt=0).exists()

    # Mijozlar: +998901112233 bir xil telefonlar birlashdi
    assert Customer.objects.filter(phone="+998901112233").count() == 1
    assert Customer.objects.count() == 2

    # Savdolar: 5 ta, qoldiqqa ta'sir qilmagan, kelishilgan narx va tannarx
    assert Sale.objects.count() == 5
    s5 = Sale.objects.get(note__startswith="Eski #5")
    assert (s5.total, s5.discount_total, s5.cost_total) == (D("50000"), D("8000"), D("49000"))
    assert s5.payments.get().method == "card"

    # Nasiya: #2 — 150 000 dan 50 000 to'langan; #3 — eski "to'landi" bilan yopilgan; #4 — mijozsiz
    r2 = Receivable.objects.get(sale__note__startswith="Eski #2")
    assert (r2.amount, r2.paid, r2.status) == (D("150000"), D("50000"), "open")
    r3 = Receivable.objects.get(sale__note__startswith="Eski #3")
    assert r3.status == "closed"
    assert not Receivable.objects.filter(sale__note__startswith="Eski #4").exists()
    assert Sale.objects.get(note__startswith="Eski #4").payments.get().method == "cash"

    assert Expense.objects.count() == 2
    assert Reminder.objects.get().level == "urgent"
    assert ExchangeRate.objects.get(source="manual").rate == D("12600")

    # Foydalanuvchilar eski parol bilan kira oladi
    boss = User.objects.get(username="boss")
    assert boss.check_password("eski-parol-1") and boss.is_owner
    seller = User.objects.get(username="sotuvchi")
    assert {r.name for r in seller.roles.all()} == {"Menejer"}
    assert seller.branches.exists()


def test_reimport_blocked_and_dry_run(legacy_db):
    _run(
        "--source",
        legacy_db,
        "--name",
        "Do'kon",
        "--owner",
        "egasi",
        "--password",
        "Yangi-parol-123",
    )
    from apps.tenancy.models import Tenant

    slug = Tenant.objects.get().slug
    with pytest.raises(CommandError, match="allaqachon"):
        _run("--source", legacy_db, "--tenant", slug)


def test_dry_run_saves_nothing(legacy_db, make_tenant):
    tenant = make_tenant("Bo'sh do'kon").tenant
    out = _run("--source", legacy_db, "--tenant", tenant.slug, "--dry-run")
    assert "TEKSHIRUV" in out and "mahsulotlar" in out
    assert Product.objects.filter(tenant=tenant).count() == 0
    assert Sale.objects.filter(tenant=tenant).count() == 0


def test_username_conflict_gets_prefix(legacy_db, make_tenant):
    User.objects.create_user(username="boss", password="x")
    tenant = make_tenant("Ikkinchi").tenant
    out = _run("--source", legacy_db, "--tenant", tenant.slug)
    assert f"{tenant.slug}_boss" in out
    assert User.objects.filter(username=f"{tenant.slug}_boss", tenant=tenant).exists()


def test_wrong_source(tmp_path, make_tenant):
    empty = tmp_path / "empty.sqlite3"
    sqlite3.connect(empty).close()
    tenant = make_tenant().tenant
    with pytest.raises(CommandError, match="jadvali yo'q"):
        _run("--source", f"sqlite:///{empty}", "--tenant", tenant.slug)
