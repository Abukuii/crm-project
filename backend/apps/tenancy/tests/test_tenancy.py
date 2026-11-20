import pytest

from apps.accounts.models import Role
from apps.catalog.models import PriceType, Unit
from apps.inventory.models import Warehouse

pytestmark = pytest.mark.django_db


def test_provision_creates_defaults(setup):
    tenant = setup.tenant
    assert Warehouse.objects.filter(tenant=tenant, branch=setup.branch).count() == 1
    assert set(Role.objects.filter(tenant=tenant).values_list("name", flat=True)) == {
        "Egasi",
        "Menejer",
        "Kassir",
        "Omborchi",
        "Buxgalter",
    }
    assert Unit.objects.filter(tenant=tenant, name="metr", allow_fraction=True).exists()
    assert PriceType.objects.get(tenant=tenant, is_default=True).name == "Chakana"
    assert setup.owner.is_owner


def test_unique_slug(make_tenant):
    assert make_tenant("Do'kon").tenant.slug != make_tenant("Do'kon").tenant.slug


def test_settings_validation(owner_api):
    bad = owner_api.patch("/api/v1/tenancy/current/", {"settings": {"foo": 1}}, format="json")
    assert bad.status_code == 400
    ok = owner_api.patch(
        "/api/v1/tenancy/current/", {"settings": {"negative_stock": "allow"}}, format="json"
    )
    assert ok.status_code == 200
    assert ok.json()["effective_settings"]["negative_stock"] == "allow"
    assert ok.json()["effective_settings"]["rate_source"] == "cbu"


def test_cashier_cannot_change_settings(api, make_user):
    client = api(make_user("Kassir"))
    assert client.get("/api/v1/tenancy/current/").status_code == 200
    assert client.patch("/api/v1/tenancy/current/", {"name": "X"}, format="json").status_code == 403
