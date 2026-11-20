from decimal import Decimal as D

import pytest

from apps.inventory.models import StockBalance
from apps.purchasing.models import Purchase, Supplier

pytestmark = pytest.mark.django_db
URL = "/api/v1/purchasing/purchases/"


def _bal(shop, product):
    return StockBalance.objects.get(warehouse=shop.wh, product=product)


@pytest.fixture
def supplier(shop):
    return Supplier.objects.create(tenant=shop.tenant, name="Qizilqum sement", currency="UZS")


def _draft(api, shop, supplier, **extra):
    payload = {
        "supplier": supplier.pk if supplier else None,
        "warehouse": shop.wh.pk,
        "extra_costs": "200000",
        "lines": [
            {
                "product": shop.cement.pk,
                "unit": shop.units["qop"].pk,
                "qty": "40",
                "price": "48000",
            },
            {
                "product": shop.cable.pk,
                "unit": shop.units["rulon"].pk,
                "qty": "2",
                "price": "700000",
            },
        ],
    }
    payload.update(extra)
    return api.post(URL, payload, format="json")


class TestPurchaseFlow:
    def test_draft_post_cancel(self, owner_api, shop, supplier):
        r = _draft(owner_api, shop, supplier)
        assert r.status_code == 201, r.json()
        body = r.json()
        assert body["status"] == "draft"
        assert body["subtotal"] == "3320000.00"  # 40×48000 + 2×700000
        assert body["lines"][1]["base_qty"] == "200.000"  # 2 rulon × 100 m

        posted = owner_api.post(f"{URL}{body['id']}/post/").json()
        assert posted["status"] == "posted"
        assert posted["total_uzs"] == "3520000.00"
        # transport 200 000 summa ulushi bo'yicha: sement 1 920 000 / 3 320 000
        cement_cost = D(posted["lines"][0]["unit_cost"])
        assert cement_cost == D("50891.5663")  # (1920000 + 115662.65) / 40
        assert _bal(shop, shop.cement).qty == D("40")
        assert _bal(shop, shop.cable).qty == D("200")

        cancelled = owner_api.post(f"{URL}{body['id']}/cancel/").json()
        assert cancelled["status"] == "cancelled"
        assert _bal(shop, shop.cement).qty == D("0")

    def test_posted_cannot_be_edited_or_deleted(self, owner_api, shop, supplier):
        pid = _draft(owner_api, shop, supplier).json()["id"]
        owner_api.post(f"{URL}{pid}/post/")
        assert owner_api.patch(f"{URL}{pid}/", {"note": "x"}, format="json").status_code == 400
        assert owner_api.delete(f"{URL}{pid}/").status_code == 400
        assert owner_api.post(f"{URL}{pid}/post/").json()["error"]["code"] == "not_draft"

    def test_cancel_restores_average_cost(self, owner_api, stock, supplier):
        pid = _draft(owner_api, stock, supplier, extra_costs="0", lines=[
            {"product": stock.cement.pk, "unit": stock.units["qop"].pk, "qty": "100",
             "price": "53000"},
        ]).json()["id"]  # fmt: skip
        owner_api.post(f"{URL}{pid}/post/")
        assert _bal(stock, stock.cement).avg_cost == D("51000")
        owner_api.post(f"{URL}{pid}/cancel/")
        b = _bal(stock, stock.cement)
        assert (b.qty, b.avg_cost) == (D("100"), D("49000"))

    def test_cancel_blocked_when_goods_sold(self, owner_api, shop, supplier):
        from apps.inventory.services import MoveLine, post_moves

        pid = _draft(owner_api, shop, supplier).json()["id"]
        owner_api.post(f"{URL}{pid}/post/")
        post_moves(tenant=shop.tenant, warehouse=shop.wh, doc_type="t", doc_id=1,
                   lines=[MoveLine(shop.cement.pk, D("-30"))])  # fmt: skip
        r = owner_api.post(f"{URL}{pid}/cancel/")
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "insufficient_stock"

    def test_usd_purchase_uses_rate(self, owner_api, shop):
        usd = Supplier.objects.create(tenant=shop.tenant, name="Import", currency="USD")
        pid = _draft(owner_api, shop, usd, extra_costs="0", lines=[
            {"product": shop.cable.pk, "unit": shop.units["metr"].pk, "qty": "100", "price": "0.6"},
        ]).json()["id"]  # fmt: skip
        body = owner_api.post(f"{URL}{pid}/post/").json()
        assert body["currency"] == "USD"
        assert body["lines"][0]["unit_cost"] == "7500.0000"  # 0.6 × 12 500

    def test_currency_must_match_supplier(self, owner_api, shop, supplier):
        r = _draft(owner_api, shop, supplier, currency="USD")
        assert r.json()["error"]["code"] == "currency_mismatch"

    def test_unit_not_defined_for_product(self, owner_api, shop, supplier):
        r = _draft(owner_api, shop, supplier, lines=[
            {"product": shop.cement.pk, "unit": shop.units["rulon"].pk, "qty": "1", "price": "1"},
        ])  # fmt: skip
        assert r.json()["error"]["code"] == "unit_not_for_product"

    def test_cashier_has_no_access(self, api, make_user, shop):
        assert api(make_user("Kassir")).get(URL).status_code == 403


class TestSupplierDebt:
    def test_balance_payments_and_statement(self, owner_api, shop, supplier):
        sup_url = f"/api/v1/purchasing/suppliers/{supplier.pk}/"
        pid = _draft(owner_api, shop, supplier).json()["id"]
        owner_api.post(f"{URL}{pid}/post/")
        assert owner_api.get(sup_url).json()["balance"] == "3320000.00"  # transport qarzga kirmaydi

        r = owner_api.post(f"{sup_url}payments/", {"amount": "1000000", "note": "Naqd"},
                           format="json")  # fmt: skip
        assert r.status_code == 201
        assert owner_api.get(sup_url).json()["balance"] == "2320000.00"

        st = owner_api.get(f"{sup_url}statement/").json()
        assert [(row["kind"], row["balance"]) for row in st["rows"]] == [
            ("purchase", "3320000.00"),
            ("payment", "2320000.00"),
        ]
        assert st["closing"] == "2320000.00"

    def test_storekeeper_cannot_pay_supplier(self, api, make_user, supplier, setup):
        user = make_user("Omborchi")
        r = api(user).post(f"/api/v1/purchasing/suppliers/{supplier.pk}/payments/",
                           {"amount": "1"}, format="json")  # fmt: skip
        assert r.status_code == 403

    def test_opening_kind_has_no_supplier(self, owner_api, shop, supplier):
        r = _draft(owner_api, shop, supplier, kind=Purchase.KIND_OPENING)
        assert r.status_code == 400
