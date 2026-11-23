from decimal import Decimal as D

import pytest

from apps.inventory.models import StockBalance
from apps.sales.models import Customer, Receivable, Shift

pytestmark = pytest.mark.django_db
SALES = "/api/v1/sales/sales/"
SHIFTS = "/api/v1/sales/shifts/"


def _bal(shop, product):
    return StockBalance.objects.get(warehouse=shop.wh, product=product).qty


def _sell(api, shop, qty="2", payments=None, **extra):
    total = str(D("58000") * D(qty))
    body = {"warehouse": shop.wh.pk, "items": [{"product": shop.cement.pk, "qty": qty}],
            "payments": payments or [{"method": "cash", "amount": total}], **extra}  # fmt: skip
    r = api.post(SALES, body, format="json")
    assert r.status_code == 201, r.json()
    return r.json()


def _open(api, shop, cash="100000"):
    r = api.post(f"{SHIFTS}open/", {"warehouse": shop.wh.pk, "opening_cash": cash}, format="json")
    assert r.status_code == 201, r.json()
    return r.json()


class TestShift:
    def test_full_cycle_with_z_report(self, owner_api, stock):
        assert owner_api.get(f"{SHIFTS}current/").status_code == 204
        shift = _open(owner_api, stock)
        assert owner_api.get(f"{SHIFTS}current/").json()["id"] == shift["id"]

        sale = _sell(owner_api, stock, qty="2")  # 116 000 naqd
        assert sale["shift_number"] == shift["number"]
        _sell(owner_api, stock, qty="1", payments=[{"method": "card", "amount": "58000"}])
        owner_api.post(f"{SHIFTS}{shift['id']}/cash/", {"kind": "out", "amount": "50000",
                                                         "note": "Inkassatsiya"}, format="json")  # fmt: skip
        owner_api.post(f"{SHIFTS}{shift['id']}/cash/", {"kind": "in", "amount": "10000"},
                       format="json")  # fmt: skip
        line = sale["lines"][0]["id"]
        owner_api.post(f"{SALES}{sale['id']}/returns/",
                       {"items": [{"line": line, "qty": "1"}], "refund_method": "cash"},
                       format="json")  # fmt: skip

        x = owner_api.get(f"{SHIFTS}{shift['id']}/report/").json()
        assert x["sales_count"] == 2
        assert x["sales_total"] == "174000.00"
        assert x["by_method"] == {"cash": "116000.00", "card": "58000.00"}
        assert x["returns_total"] == "58000.00"
        assert x["net_revenue"] == "116000.00"
        # 100 000 + 116 000 − 50 000 + 10 000 − 58 000
        assert x["expected_cash"] == "118000.00"

        z = owner_api.post(f"{SHIFTS}{shift['id']}/close/", {"counted_cash": "117000"},
                           format="json").json()  # fmt: skip
        assert (z["counted_cash"], z["difference"]) == ("117000.00", "-1000.00")
        assert Shift.objects.get(pk=shift["id"]).status == "closed"
        # Yopilgan smena hisobotti o'zgarmaydi
        _sell(owner_api, stock, qty="1")
        assert owner_api.get(f"{SHIFTS}{shift['id']}/report/").json()["sales_count"] == 2

    def test_only_one_open_shift(self, owner_api, stock):
        _open(owner_api, stock)
        r = owner_api.post(f"{SHIFTS}open/", {"warehouse": stock.wh.pk, "opening_cash": "0"},
                           format="json")  # fmt: skip
        assert r.json()["error"]["code"] == "shift_already_open"

    def test_cash_out_cannot_exceed_drawer(self, owner_api, stock):
        shift = _open(owner_api, stock, cash="20000")
        r = owner_api.post(f"{SHIFTS}{shift['id']}/cash/", {"kind": "out", "amount": "30000"},
                           format="json")  # fmt: skip
        assert r.json()["error"]["code"] == "not_enough_cash"

    def test_require_shift_setting(self, owner_api, stock):
        stock.tenant.settings = {"require_shift": True}
        stock.tenant.save()
        r = owner_api.post(SALES, {"warehouse": stock.wh.pk,
                                   "items": [{"product": stock.cement.pk, "qty": "1"}],
                                   "payments": [{"method": "cash", "amount": "58000"}]},
                           format="json")  # fmt: skip
        assert r.status_code == 409 and r.json()["error"]["code"] == "shift_required"
        _open(owner_api, stock)
        _sell(owner_api, stock, qty="1")

    def test_cashier_sees_only_own_shifts_and_cannot_close_others(self, api, owner_api, make_user,
                                                                  stock):  # fmt: skip
        owner_shift = _open(owner_api, stock)
        cashier = make_user("Kassir")
        cashier.branches.add(stock.branch)
        client = api(cashier)
        assert client.get(SHIFTS).json()["count"] == 0
        assert client.post(f"{SHIFTS}{owner_shift['id']}/close/", {"counted_cash": "0"},
                           format="json").status_code == 404  # fmt: skip

    def test_debt_payment_in_cash_counts_in_drawer(self, owner_api, stock):
        cust = Customer.objects.create(tenant=stock.tenant, name="Botir")
        _sell(owner_api, stock, qty="1", payments=[{"method": "credit", "amount": "58000"}],
              customer=cust.pk)  # fmt: skip
        shift = _open(owner_api, stock, cash="0")
        owner_api.post(f"/api/v1/sales/customers/{cust.pk}/payments/", {"amount": "20000"},
                       format="json")  # fmt: skip
        x = owner_api.get(f"{SHIFTS}{shift['id']}/report/").json()
        assert x["debt_payments"] == {"cash": "20000.00"}
        assert x["expected_cash"] == "20000.00"


class TestReturns:
    def test_partial_return_restores_stock_and_limits_qty(self, owner_api, stock):
        sale = _sell(owner_api, stock, qty="5")
        line = sale["lines"][0]["id"]
        url = f"{SALES}{sale['id']}/returns/"
        r = owner_api.post(url, {"items": [{"line": line, "qty": "2"}], "refund_method": "cash",
                                 "reason": "Singan qop"}, format="json")  # fmt: skip
        assert r.status_code == 201, r.json()
        body = r.json()
        assert body["returned_total"] == "116000.00"
        assert body["lines"][0]["returned_qty"] == "2.000"
        assert body["profit"] == "27000.00"  # (5−2) × (58 000 − 49 000)
        assert _bal(stock, stock.cement) == D("97")

        too_many = owner_api.post(url, {"items": [{"line": line, "qty": "4"}],
                                        "refund_method": "cash"}, format="json")  # fmt: skip
        assert too_many.json()["error"]["code"] == "qty_exceeds"
        assert too_many.json()["error"]["details"]["available"] == "3.000"

    def test_return_reduces_credit_debt(self, owner_api, stock):
        cust = Customer.objects.create(tenant=stock.tenant, name="Usta")
        sale = _sell(owner_api, stock, qty="3", payments=[{"method": "credit", "amount": "174000"}],
                     customer=cust.pk)  # fmt: skip
        line = sale["lines"][0]["id"]
        r = owner_api.post(f"{SALES}{sale['id']}/returns/",
                           {"items": [{"line": line, "qty": "1"}], "refund_method": "debt"},
                           format="json")  # fmt: skip
        assert r.status_code == 201
        rec = Receivable.objects.get(sale_id=sale["id"])
        assert (rec.amount, rec.status) == (D("116000"), "open")
        # Qolgan hammasi qaytsa qarz yopiladi
        owner_api.post(f"{SALES}{sale['id']}/returns/",
                       {"items": [{"line": line, "qty": "2"}], "refund_method": "debt"},
                       format="json")  # fmt: skip
        rec.refresh_from_db()
        assert (rec.amount, rec.status) == (D("0"), "closed")

    def test_debt_refund_needs_open_debt(self, owner_api, stock):
        sale = _sell(owner_api, stock, qty="1")
        r = owner_api.post(f"{SALES}{sale['id']}/returns/",
                           {"items": [{"line": sale["lines"][0]["id"], "qty": "1"}],
                            "refund_method": "debt"}, format="json")  # fmt: skip
        assert r.json()["error"]["code"] == "no_open_debt"

    def test_cannot_cancel_after_return(self, owner_api, stock):
        sale = _sell(owner_api, stock, qty="2")
        owner_api.post(f"{SALES}{sale['id']}/returns/",
                       {"items": [{"line": sale["lines"][0]["id"], "qty": "1"}],
                        "refund_method": "cash"}, format="json")  # fmt: skip
        r = owner_api.post(f"{SALES}{sale['id']}/cancel/")
        assert r.json()["error"]["code"] == "sale_has_returns"

    def test_foreign_line_rejected(self, owner_api, stock):
        a = _sell(owner_api, stock, qty="1")
        b = _sell(owner_api, stock, qty="1")
        r = owner_api.post(f"{SALES}{a['id']}/returns/",
                           {"items": [{"line": b["lines"][0]["id"], "qty": "1"}],
                            "refund_method": "cash"}, format="json")  # fmt: skip
        assert r.json()["error"]["code"] == "line_not_found"

    def test_cashier_cannot_return(self, api, owner_api, make_user, stock):
        sale = _sell(owner_api, stock, qty="1")
        cashier = make_user("Kassir")
        cashier.branches.add(stock.branch)
        r = api(cashier).post(f"{SALES}{sale['id']}/returns/",
                              {"items": [{"line": sale["lines"][0]["id"], "qty": "1"}],
                               "refund_method": "cash"}, format="json")  # fmt: skip
        assert r.status_code == 403

    def test_reports_subtract_returns(self, owner_api, stock):
        sale = _sell(owner_api, stock, qty="2")
        owner_api.post(f"{SALES}{sale['id']}/returns/",
                       {"items": [{"line": sale["lines"][0]["id"], "qty": "1"}],
                        "refund_method": "cash"}, format="json")  # fmt: skip
        d = owner_api.get("/api/v1/reports/dashboard/").json()["today"]
        assert (d["revenue"], d["returns"], d["gross_profit"]) == (
            "58000.00",
            "58000.00",
            "9000.00",
        )
        s = owner_api.get(f"{SALES}summary/").json()
        assert (s["total"], s["returns"], s["profit"]) == ("116000.00", "58000.00", "9000.00")
