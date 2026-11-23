import uuid
from datetime import timedelta
from decimal import Decimal as D

import pytest
from django.utils import timezone

from apps.inventory.models import StockBalance
from apps.sales.models import Customer, Receivable, Sale

pytestmark = pytest.mark.django_db
URL = "/api/v1/sales/sales/"
CUST = "/api/v1/sales/customers/"


def _bal(shop, product):
    return StockBalance.objects.get(warehouse=shop.wh, product=product).qty


def _sale(api, shop, items, payments, **extra):
    return api.post(URL, {"warehouse": shop.wh.pk, "items": items, "payments": payments, **extra},
                    format="json")  # fmt: skip


@pytest.fixture
def customer(stock):
    return Customer.objects.create(tenant=stock.tenant, name="Usta Botir", phone="+998901112233",
                                   payment_days=10)  # fmt: skip


class TestSale:
    def test_cash_sale_with_units_and_usd_price(self, owner_api, stock):
        r = _sale(
            owner_api,
            stock,
            [
                {"product": stock.cement.pk, "qty": "2"},
                {"product": stock.cable.pk, "unit": stock.units["rulon"].pk, "qty": "1"},
            ],
            [{"method": "cash", "amount": "1116000"}],
        )  # 2×58000 + 100m×0.8$×12500
        assert r.status_code == 201, r.json()
        body = r.json()
        assert body["total"] == "1116000.00"
        assert body["cost_total"] == "848000.00"  # 2×49000 + 100×7500
        assert body["profit"] == "268000.00"
        assert _bal(stock, stock.cement) == D("98")
        assert _bal(stock, stock.cable) == D("400")

    def test_negotiated_price_and_discount_limit(self, api, make_user, stock):
        cashier = make_user("Kassir")
        cashier.branches.add(stock.branch)
        client = api(cashier)
        ok = _sale(
            client,
            stock,
            [{"product": stock.cement.pk, "qty": "1", "price": "56000"}],
            [{"method": "card", "amount": "56000"}],
        )  # 3.4% — limit 5%
        assert ok.status_code == 201, ok.json()
        assert ok.json()["discount_total"] == "2000.00"
        assert "cost_total" not in ok.json()  # kassir tannarxni ko'rmaydi

        too_much = _sale(client, stock, [{"product": stock.cement.pk, "qty": "1", "price": "50000"}],
                         [{"method": "cash", "amount": "50000"}])  # fmt: skip
        assert too_much.status_code == 403
        assert too_much.json()["error"]["code"] == "discount_limit"

    def test_payment_must_match_total(self, owner_api, stock):
        r = _sale(owner_api, stock, [{"product": stock.cement.pk, "qty": "1"}],
                  [{"method": "cash", "amount": "50000"}])  # fmt: skip
        assert r.json()["error"]["code"] == "payment_mismatch"

    def test_insufficient_stock_rolls_back(self, owner_api, stock):
        r = _sale(owner_api, stock, [{"product": stock.cement.pk, "qty": "101"}],
                  [{"method": "cash", "amount": "5858000"}])  # fmt: skip
        assert r.status_code == 409
        assert Sale.objects.count() == 0
        assert _bal(stock, stock.cement) == D("100")

    def test_idempotent_client_uuid(self, owner_api, stock):
        key = str(uuid.uuid4())
        args = ([{"product": stock.cement.pk, "qty": "1"}], [{"method": "cash", "amount": "58000"}])
        first = _sale(owner_api, stock, *args, client_uuid=key).json()
        second = _sale(owner_api, stock, *args, client_uuid=key).json()
        assert first["id"] == second["id"]
        assert _bal(stock, stock.cement) == D("99")

    def test_customer_price_type_applies(self, owner_api, stock, customer):
        customer.price_type = stock.pts["Usta"]
        customer.save()
        r = _sale(owner_api, stock, [{"product": stock.cement.pk, "qty": "1"}],
                  [{"method": "cash", "amount": "55000"}], customer=customer.pk)  # fmt: skip
        assert r.status_code == 201
        assert r.json()["lines"][0]["list_price"] == "55000.00"

    def test_cancel_restores_stock(self, owner_api, stock):
        sid = _sale(owner_api, stock, [{"product": stock.cement.pk, "qty": "3"}],
                    [{"method": "cash", "amount": "174000"}]).json()["id"]  # fmt: skip
        r = owner_api.post(f"{URL}{sid}/cancel/", {"reason": "Xato"}, format="json")
        assert r.json()["status"] == "cancelled"
        assert _bal(stock, stock.cement) == D("100")
        assert owner_api.post(f"{URL}{sid}/cancel/").json()["error"]["code"] == "already_cancelled"

    def test_cashier_cannot_cancel_and_sees_only_own(self, api, make_user, owner_api, stock):
        _sale(owner_api, stock, [{"product": stock.cement.pk, "qty": "1"}],
              [{"method": "cash", "amount": "58000"}])  # fmt: skip
        cashier = make_user("Kassir")
        cashier.branches.add(stock.branch)
        client = api(cashier)
        assert client.get(URL).json()["count"] == 0
        sid = Sale.objects.get().pk
        assert client.post(f"{URL}{sid}/cancel/").status_code == 403

    def test_summary_and_pos_catalog(self, owner_api, stock):
        _sale(
            owner_api,
            stock,
            [{"product": stock.cement.pk, "qty": "2"}],
            [{"method": "cash", "amount": "100000"}, {"method": "card", "amount": "16000"}],
        )
        s = owner_api.get(f"{URL}summary/").json()
        assert (s["count"], s["total"], s["profit"]) == (1, "116000.00", "18000.00")
        assert s["by_method"] == {"cash": "100000.00", "card": "16000.00"}

        items = owner_api.get(f"{URL}pos-catalog/", {"warehouse": stock.wh.pk,
                                                    "search": "kabel"}).json()  # fmt: skip
        assert len(items) == 1
        cable = items[0]
        assert cable["stock"] == "500.000"
        assert [(u["unit_short"], u["price"]) for u in cable["units"]] == [
            ("m", "10000.00"),
            ("rulon", "1000000.00"),
        ]

    def test_pos_catalog_finds_unit_by_scanned_barcode(self, owner_api, stock):
        from apps.catalog.models import Barcode, ProductUnit

        rulon = ProductUnit.objects.get(product=stock.cable)
        Barcode.objects.create(tenant=stock.tenant, product=stock.cable, code="4780000000017")
        Barcode.objects.create(tenant=stock.tenant, product=stock.cable, product_unit=rulon,
                               code="4780000000024")  # fmt: skip
        items = owner_api.get(f"{URL}pos-catalog/", {"warehouse": stock.wh.pk,
                                                    "search": "4780000000024"}).json()  # fmt: skip
        assert [i["name"] for i in items] == ["Kabel VVG"]
        assert [(u["unit_short"], u["barcodes"]) for u in items[0]["units"]] == [
            ("m", ["4780000000017"]),
            ("rulon", ["4780000000024"]),
        ]


class TestCredit:
    def _credit_sale(self, api, stock, customer, qty="10", cash="0"):
        total = D("58000") * D(qty)
        payments = [{"method": "credit", "amount": str(total - D(cash))}]
        if D(cash):
            payments.append({"method": "cash", "amount": cash})
        return _sale(api, stock, [{"product": stock.cement.pk, "qty": qty}], payments,
                     customer=customer.pk)  # fmt: skip

    def test_credit_requires_customer(self, owner_api, stock):
        r = _sale(owner_api, stock, [{"product": stock.cement.pk, "qty": "1"}],
                  [{"method": "credit", "amount": "58000"}])  # fmt: skip
        assert r.json()["error"]["code"] == "customer_required"

    def test_credit_with_down_payment_and_due_date(self, owner_api, stock, customer):
        r = self._credit_sale(owner_api, stock, customer, cash="80000")
        assert r.status_code == 201, r.json()
        rec = Receivable.objects.get()
        assert rec.amount == D("500000")
        assert rec.due_date == timezone.localdate() + timedelta(days=10)
        row = owner_api.get(CUST, {"has_debt": "true"}).json()["results"][0]
        assert (row["name"], row["debt"]) == ("Usta Botir", "500000.00")

    def test_credit_limit(self, owner_api, stock, customer):
        customer.credit_limit = D("600000")
        customer.save()
        assert self._credit_sale(owner_api, stock, customer).status_code == 201
        r = self._credit_sale(owner_api, stock, customer, qty="1")
        assert r.json()["error"]["code"] == "credit_limit_exceeded"

    def test_payments_fifo_and_overpay(self, owner_api, stock, customer):
        self._credit_sale(owner_api, stock, customer, qty="1")  # 58 000
        self._credit_sale(owner_api, stock, customer, qty="2")  # 116 000
        pay = f"{CUST}{customer.pk}/payments/"
        assert (
            owner_api.post(pay, {"amount": "200000"}, format="json").json()["error"]["code"]
            == "overpayment"
        )
        r = owner_api.post(pay, {"amount": "100000", "method": "card"}, format="json")
        assert r.status_code == 201
        recs = list(Receivable.objects.order_by("id"))
        assert [(x.paid, x.status) for x in recs] == [(D("58000"), "closed"), (D("42000"), "open")]
        # qolgan qarzni to'liq yopish ("to'liq to'lash")
        owner_api.post(pay, {"amount": "74000"}, format="json")
        assert owner_api.get(f"{CUST}{customer.pk}/").json()["debt"] == "0.00"

    def test_cannot_cancel_paid_credit_sale(self, owner_api, stock, customer):
        sid = self._credit_sale(owner_api, stock, customer, qty="1").json()["id"]
        owner_api.post(f"{CUST}{customer.pk}/payments/", {"amount": "1000"}, format="json")
        r = owner_api.post(f"{URL}{sid}/cancel/")
        assert r.json()["error"]["code"] == "receivable_has_payments"

    def test_overdue_filter(self, owner_api, stock, customer):
        self._credit_sale(owner_api, stock, customer, qty="1")
        Receivable.objects.update(due_date=timezone.localdate() - timedelta(days=1))
        rows = owner_api.get(CUST, {"overdue": "true"}).json()["results"]
        assert rows[0]["overdue_debt"] == "58000.00"

    def test_duplicate_phone_rejected(self, owner_api, customer):
        r = owner_api.post(CUST, {"name": "X", "phone": "+998 90 111 22 33"}, format="json")
        assert r.status_code == 400
