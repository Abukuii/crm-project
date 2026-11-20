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
