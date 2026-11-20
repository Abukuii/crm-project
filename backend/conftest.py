import itertools

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.tenancy.services import provision_tenant

_seq = itertools.count(1)


@pytest.fixture
def make_tenant(db):
    def _make(name: str | None = None):
        n = next(_seq)
        return provision_tenant(
            name=name or f"Do'kon {n}", owner_username=f"owner{n}", owner_password="Str0ng-pass!"
        )

    return _make


@pytest.fixture
def setup(make_tenant):
    """Asosiy tenant: tenant, filial, egasi."""
    return make_tenant("Qurilish Mollari")


@pytest.fixture
def tenant(setup):
    return setup.tenant


@pytest.fixture
def owner(setup):
    return setup.owner


@pytest.fixture
def make_user(tenant):
    def _make(role_name: str, username: str | None = None, tenant_=None, **kwargs):
        t = tenant_ or tenant
        user = User.objects.create_user(
            username=username or f"{role_name.lower()}{next(_seq)}",
            password="Str0ng-pass!",
            tenant=t,
            **kwargs,
        )
        user.roles.add(Role.objects.get(tenant=t, name=role_name))
        return user

    return _make


@pytest.fixture
def api():
    def _client(user=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user=user)
        return client

    return _client


@pytest.fixture
def owner_api(api, owner):
    return api(owner)


# ── Savdo/ombor testlari uchun umumiy ma'lumotlar ────────────────────────────
@pytest.fixture
def shop(setup):
    """Ombor, birliklar, narx turlari, 2 ta mahsulot (sement — qop, kabel — metr) va USD kurs."""
    from datetime import date
    from decimal import Decimal as D

    from apps.catalog.models import PriceType, ProductUnit, Unit
    from apps.catalog.services import save_product
    from apps.currency.models import ExchangeRate
    from apps.inventory.models import Warehouse

    t = setup.tenant
    units = {u.name: u for u in Unit.objects.filter(tenant=t)}
    pts = {p.name: p for p in PriceType.objects.filter(tenant=t)}
    cement = save_product(tenant=t, user=setup.owner, data={
        "name": "Sement M-400", "base_unit": units["qop"],
        "prices": [{"price_type": pts["Chakana"], "amount": D("58000")},
                   {"price_type": pts["Usta"], "amount": D("55000")}],
    })  # fmt: skip
    cable = save_product(tenant=t, user=setup.owner, data={
        "name": "Kabel VVG", "base_unit": units["metr"], "price_currency": "USD",
        "prices": [{"price_type": pts["Chakana"], "amount": D("0.80")}],
    })  # fmt: skip
    ProductUnit.objects.create(tenant=t, product=cable, unit=units["rulon"], factor=D("100"))
    ExchangeRate.objects.create(currency="USD", date=date(2020, 1, 1), rate=D("12500"),
                                source="cbu")  # fmt: skip
    return type("Shop", (), {
        "tenant": t, "owner": setup.owner, "branch": setup.branch,
        "wh": Warehouse.objects.get(tenant=t), "units": units, "pts": pts,
        "cement": cement, "cable": cable,
    })  # fmt: skip


@pytest.fixture
def stock(shop):
    """Boshlang'ich qoldiq: sement 100 qop × 49 000, kabel 500 m × 7 500."""
    from decimal import Decimal as D

    from apps.inventory.services import MoveLine, post_moves

    post_moves(tenant=shop.tenant, warehouse=shop.wh, doc_type="opening", doc_id=0, lines=[
        MoveLine(shop.cement.pk, D("100"), D("49000")),
        MoveLine(shop.cable.pk, D("500"), D("7500")),
    ])  # fmt: skip
    return shop
