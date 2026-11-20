from decimal import Decimal

import pytest

from apps.catalog.models import Category, PriceHistory, PriceType, Product, Unit

pytestmark = pytest.mark.django_db
URL = "/api/v1/catalog/products/"


@pytest.fixture
def refs(tenant):
    return {
        "dona": Unit.objects.get(tenant=tenant, name="dona"),
        "pachka": Unit.objects.get(tenant=tenant, name="pachka"),
        "quti": Unit.objects.get(tenant=tenant, name="quti"),
        "metr": Unit.objects.get(tenant=tenant, name="metr"),
        "chakana": PriceType.objects.get(tenant=tenant, name="Chakana"),
        "ulgurji": PriceType.objects.get(tenant=tenant, name="Ulgurji"),
    }


def _payload(refs, **extra):
    data = {
        "name": "Shurup 4x50",
        "base_unit": refs["dona"].pk,
        "units": [{"unit": refs["pachka"].pk, "factor": "100", "barcode": "4780000000200"}],
        "barcodes": ["4780000000100"],
        "prices": [{"price_type": refs["chakana"].pk, "amount": "350"}],
    }
    data.update(extra)
    return data


class TestCreate:
    def test_full_product_with_auto_sku(self, owner_api, refs):
        response = owner_api.post(URL, _payload(refs), format="json")
        assert response.status_code == 201, response.json()
        body = response.json()
        assert body["sku"] == "000001"
        assert body["barcodes"] == ["4780000000100"]
        assert body["units"][0]["factor"] == "100.000"
        assert body["units"][0]["barcode"] == "4780000000200"
        assert body["prices"][0]["amount"] == "350.0000"
        assert PriceHistory.objects.filter(product_id=body["id"]).count() == 1

    def test_usd_price_keeps_cents(self, owner_api, refs):
        response = owner_api.post(
            URL,
            _payload(
                refs,
                price_currency="USD",
                barcodes=[],
                units=[],
                prices=[{"price_type": refs["chakana"].pk, "amount": "12.50"}],
            ),
            format="json",
        )
        assert response.status_code == 201
        assert Product.objects.get(pk=response.json()["id"]).prices.get().amount == Decimal("12.5")

    def test_duplicate_barcode_rejected(self, owner_api, refs):
        owner_api.post(URL, _payload(refs), format="json")
        response = owner_api.post(URL, _payload(refs, name="Boshqa", units=[]), format="json")
        assert response.status_code == 400
        assert "barcodes" in response.json()["error"]["details"]

    def test_base_unit_cannot_be_extra_unit(self, owner_api, refs):
        response = owner_api.post(
            URL, _payload(refs, units=[{"unit": refs["dona"].pk, "factor": "1"}]), format="json"
        )
        assert response.status_code == 400

    def test_foreign_tenant_category_rejected(self, owner_api, refs, make_tenant):
        foreign = Category.objects.create(tenant=make_tenant().tenant, name="Begona")
        response = owner_api.post(URL, _payload(refs, category=foreign.pk), format="json")
        assert response.status_code == 400


class TestUpdate:
    def test_price_change_is_recorded(self, owner_api, refs):
        pid = owner_api.post(URL, _payload(refs), format="json").json()["id"]
        response = owner_api.patch(
            f"{URL}{pid}/",
            {
                "prices": [
                    {"price_type": refs["chakana"].pk, "amount": "400"},
                    {"price_type": refs["ulgurji"].pk, "amount": "320"},
                ]
            },
            format="json",
        )
        assert response.status_code == 200
        history = owner_api.get(f"{URL}{pid}/price-history/").json()["results"]
        assert {(h["price_type_name"], h["old_amount"], h["new_amount"]) for h in history} == {
            ("Chakana", None, "350.0000"),
            ("Chakana", "350.0000", "400.0000"),
            ("Ulgurji", None, "320.0000"),
        }

    def test_unchanged_price_not_recorded(self, owner_api, refs):
        pid = owner_api.post(URL, _payload(refs), format="json").json()["id"]
        owner_api.patch(
            f"{URL}{pid}/",
            {"name": "Yangi nom", "prices": [{"price_type": refs["chakana"].pk, "amount": "350"}]},
            format="json",
        )
        assert PriceHistory.objects.filter(product_id=pid).count() == 1

    def test_updating_only_barcodes_keeps_units(self, owner_api, refs):
        pid = owner_api.post(URL, _payload(refs), format="json").json()["id"]
        body = owner_api.patch(f"{URL}{pid}/", {"barcodes": ["111", "222"]}, format="json").json()
        assert sorted(body["barcodes"]) == ["111", "222"]
        assert body["units"][0]["barcode"] == "4780000000200"

    def test_storekeeper_cannot_edit_prices(self, api, make_user, refs):
        user = make_user("Omborchi")
        role = user.roles.first()
        role.permissions = [*role.permissions, "catalog.manage"]
        role.save()
        response = api(user).post(URL, _payload(refs), format="json")
        assert response.status_code == 400
        assert "prices" in response.json()["error"]["details"]

    def test_delete_archives(self, owner_api, refs):
        pid = owner_api.post(URL, _payload(refs), format="json").json()["id"]
        assert owner_api.delete(f"{URL}{pid}/").status_code == 204
        assert Product.objects.get(pk=pid).is_archived is True


class TestSearchAndLookup:
    @pytest.fixture
    def products(self, owner_api, refs):
        for name in ["Цемент М-400 (50 кг)", "Armatura 12mm", "G'isht qizil"]:
            owner_api.post(URL, {"name": name, "base_unit": refs["dona"].pk}, format="json")

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("sement", "Цемент М-400 (50 кг)"),
            ("m400", "Цемент М-400 (50 кг)"),
            ("гишт", "G'isht qizil"),
            ("ARMATURA 12", "Armatura 12mm"),
        ],
    )
    def test_translit_search(self, owner_api, products, query, expected):
        results = owner_api.get(URL, {"search": query}).json()["results"]
        assert [r["name"] for r in results] == [expected]

    def test_by_barcode_returns_unit_factor(self, owner_api, refs):
        owner_api.post(URL, _payload(refs), format="json")
        body = owner_api.get(f"{URL}by-barcode/", {"code": "4780000000200"}).json()
        assert body["unit"] == refs["pachka"].pk
        assert body["factor"] == "100.000"
        missing = owner_api.get(f"{URL}by-barcode/", {"code": "000"})
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "barcode_not_found"


class TestIsolationAndPermissions:
    def test_other_tenant_cannot_see_product(self, owner_api, refs, api, make_tenant):
        pid = owner_api.post(URL, _payload(refs), format="json").json()["id"]
        stranger = api(make_tenant().owner)
        assert stranger.get(f"{URL}{pid}/").status_code == 404
        assert stranger.get(URL).json()["count"] == 0
        assert stranger.patch(f"{URL}{pid}/", {"name": "x"}, format="json").status_code == 404

    def test_cashier_reads_but_cannot_write(self, api, make_user, refs):
        client = api(make_user("Kassir"))
        assert client.get(URL).status_code == 200
        response = client.post(URL, {"name": "x", "base_unit": refs["dona"].pk}, format="json")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"

    def test_anonymous_rejected(self, api):
        response = api().get(URL)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "not_authenticated"


class TestCategories:
    def test_category_cycle_rejected(self, owner_api):
        a = owner_api.post("/api/v1/catalog/categories/", {"name": "A"}, format="json").json()
        b = owner_api.post(
            "/api/v1/catalog/categories/", {"name": "B", "parent": a["id"]}, format="json"
        ).json()
        response = owner_api.patch(
            f"/api/v1/catalog/categories/{a['id']}/", {"parent": b["id"]}, format="json"
        )
        assert response.status_code == 400

    def test_filter_by_parent_category_includes_children(self, owner_api, refs):
        parent = owner_api.post(
            "/api/v1/catalog/categories/", {"name": "Santexnika"}, format="json"
        ).json()
        child = owner_api.post(
            "/api/v1/catalog/categories/",
            {"name": "Kranlar", "parent": parent["id"]},
            format="json",
        ).json()
        owner_api.post(
            URL,
            {"name": "Kran", "base_unit": refs["dona"].pk, "category": child["id"]},
            format="json",
        )
        results = owner_api.get(URL, {"category": parent["id"]}).json()["results"]
        assert [r["name"] for r in results] == ["Kran"]

    def test_used_category_cannot_be_deleted(self, owner_api, refs):
        cat = owner_api.post("/api/v1/catalog/categories/", {"name": "C"}, format="json").json()
        owner_api.post(
            URL, {"name": "P", "base_unit": refs["dona"].pk, "category": cat["id"]}, format="json"
        )
        response = owner_api.delete(f"/api/v1/catalog/categories/{cat['id']}/")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "protected"
