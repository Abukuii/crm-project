from decimal import Decimal

import pytest

from apps.catalog.models import Product, Unit
from apps.core.exceptions import DomainError, InsufficientStock
from apps.inventory.models import StockBalance, StockMove, Warehouse
from apps.inventory.services import MoveLine, post_moves, recalc_balance

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def wh(tenant):
    return Warehouse.objects.get(tenant=tenant)


@pytest.fixture
def cement(tenant):
    return Product.objects.create(
        tenant=tenant,
        sku="C1",
        name="Sement",
        base_unit=Unit.objects.get(tenant=tenant, name="qop"),
    )


@pytest.fixture
def cable(tenant):
    return Product.objects.create(
        tenant=tenant,
        sku="K1",
        name="Kabel",
        base_unit=Unit.objects.get(tenant=tenant, name="metr"),
    )


def _post(tenant, wh, *lines, doc_id=1, **kw):
    return post_moves(
        tenant=tenant, warehouse=wh, lines=lines, doc_type="test", doc_id=doc_id, **kw
    )


def _balance(wh, product):
    return StockBalance.objects.get(warehouse=wh, product=product)


class TestWeightedAverageCost:
    def test_incoming_recomputes_average(self, tenant, wh, cement):
        _post(tenant, wh, MoveLine(cement.pk, D("10"), D("50000")))
        _post(tenant, wh, MoveLine(cement.pk, D("30"), D("54000")))
        b = _balance(wh, cement)
        assert b.qty == D("40")
        assert b.avg_cost == D("53000")  # (10*50000 + 30*54000) / 40

    def test_outgoing_uses_average_and_keeps_it(self, tenant, wh, cement):
        _post(
            tenant,
            wh,
            MoveLine(cement.pk, D("10"), D("50000")),
            MoveLine(cement.pk, D("30"), D("54000")),
        )
        moves = _post(tenant, wh, MoveLine(cement.pk, D("-15")), doc_id=2)
        assert moves[0].unit_cost == D("53000")
        assert moves[0].qty_after == D("25")
        b = _balance(wh, cement)
        assert (b.qty, b.avg_cost) == (D("25"), D("53000"))

    def test_ledger_matches_balance(self, tenant, wh, cement):
        _post(tenant, wh, MoveLine(cement.pk, D("7"), D("48000")))
        _post(tenant, wh, MoveLine(cement.pk, D("-3")), doc_id=2)
        _post(tenant, wh, MoveLine(cement.pk, D("6"), D("51000")), doc_id=3)
        b = _balance(wh, cement)
        assert recalc_balance(wh, cement.pk) == (b.qty, b.avg_cost)

    def test_fractional_qty_for_metric_units(self, tenant, wh, cable):
        _post(tenant, wh, MoveLine(cable.pk, D("100"), D("7500")))
        _post(tenant, wh, MoveLine(cable.pk, D("-2.5")), doc_id=2)
        assert _balance(wh, cable).qty == D("97.5")


class TestGuards:
    def test_insufficient_stock_writes_nothing(self, tenant, wh, cement, cable):
        _post(
            tenant,
            wh,
            MoveLine(cement.pk, D("5"), D("50000")),
            MoveLine(cable.pk, D("10"), D("7000")),
        )
        with pytest.raises(InsufficientStock) as exc:
            _post(tenant, wh, MoveLine(cable.pk, D("-1")), MoveLine(cement.pk, D("-6")), doc_id=2)
        assert exc.value.details == [
            {"product_id": cement.pk, "name": "Sement", "requested": "6.000", "available": "5.000"}
        ]
        assert StockMove.objects.filter(doc_id=2).count() == 0
        assert _balance(wh, cable).qty == D("10")

    def test_negative_allowed_by_tenant_setting(self, tenant, wh, cement):
        tenant.settings = {"negative_stock": "allow"}
        tenant.save()
        _post(tenant, wh, MoveLine(cement.pk, D("-2")))
        assert _balance(wh, cement).qty == D("-2")
        _post(tenant, wh, MoveLine(cement.pk, D("5"), D("50000")), doc_id=2)
        b = _balance(wh, cement)
        assert (b.qty, b.avg_cost) == (D("3"), D("50000"))

    def test_fraction_rejected_for_piece_units(self, tenant, wh, cement):
        with pytest.raises(DomainError) as exc:
            _post(tenant, wh, MoveLine(cement.pk, D("1.5"), D("50000")))
        assert exc.value.code == "fraction_not_allowed"

    def test_incoming_requires_cost(self, tenant, wh, cement):
        with pytest.raises(DomainError) as exc:
            _post(tenant, wh, MoveLine(cement.pk, D("1")))
        assert exc.value.code == "cost_required"

    def test_other_tenant_product_rejected(self, tenant, wh, make_tenant):
        other = make_tenant().tenant
        foreign = Product.objects.create(
            tenant=other, sku="X", name="X", base_unit=Unit.objects.get(tenant=other, name="dona")
        )
        with pytest.raises(DomainError) as exc:
            _post(tenant, wh, MoveLine(foreign.pk, D("1"), D("1")))
        assert exc.value.code == "product_not_found"

    def test_moves_are_immutable(self, tenant, wh, cement):
        move = _post(tenant, wh, MoveLine(cement.pk, D("1"), D("1")))[0]
        move = StockMove.objects.get(pk=move.pk)
        with pytest.raises(RuntimeError):
            move.save()
        with pytest.raises(RuntimeError):
            move.delete()


class TestApi:
    def test_balances_hide_cost_without_permission(
        self, tenant, wh, cement, owner_api, api, make_user, setup
    ):
        _post(tenant, wh, MoveLine(cement.pk, D("10"), D("50000")))
        owner_row = owner_api.get("/api/v1/inventory/balances/").json()["results"][0]
        assert owner_row["avg_cost"] == "50000.0000"
        assert owner_row["total_cost"] == "500000.00"

        cashier = make_user("Kassir")
        cashier.branches.add(setup.branch)
        row = api(cashier).get("/api/v1/inventory/balances/").json()["results"][0]
        assert row["qty"] == "10.000"
        assert "avg_cost" not in row and "total_cost" not in row

    def test_branch_restriction(self, tenant, wh, cement, api, make_user):
        _post(tenant, wh, MoveLine(cement.pk, D("10"), D("50000")))
        no_branch = make_user("Kassir")  # filial biriktirilmagan
        assert api(no_branch).get("/api/v1/inventory/balances/").json()["count"] == 0

    def test_low_stock_filter(self, tenant, wh, cement, cable, owner_api):
        cement.min_stock = D("20")
        cement.save()
        _post(tenant, wh, MoveLine(cement.pk, D("10"), D("1")), MoveLine(cable.pk, D("10"), D("1")))
        rows = owner_api.get("/api/v1/inventory/balances/", {"low_stock": "true"}).json()["results"]
        assert [r["product_name"] for r in rows] == ["Sement"]
