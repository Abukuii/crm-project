import pytest
from django.conf import settings

from apps.accounts.apps import sync_system_roles
from apps.accounts.models import Role
from apps.accounts.perms import DEFAULT_ROLES

COOKIE = settings.JWT_REFRESH_COOKIE["name"]
pytestmark = pytest.mark.django_db


def _login(client, username, password="Str0ng-pass!"):
    return client.post(
        "/api/v1/auth/login/", {"username": username, "password": password}, format="json"
    )


class TestLogin:
    def test_success_returns_access_and_sets_httponly_cookie(self, api, owner):
        client = api()
        response = _login(client, owner.username)
        assert response.status_code == 200
        body = response.json()
        assert body["access"]
        assert body["user"]["username"] == owner.username
        assert "catalog.manage" in body["user"]["permissions"]
        cookie = response.cookies[COOKIE]
        assert cookie["httponly"]
        assert "refresh" not in body  # refresh faqat cookie'da

    def test_wrong_password_uniform_error(self, api, owner):
        response = _login(api(), owner.username, "wrong")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_credentials"

    def test_inactive_tenant_cannot_login(self, api, setup):
        setup.tenant.is_active = False
        setup.tenant.save()
        assert _login(api(), setup.owner.username).status_code == 401

    def test_access_token_works(self, api, owner):
        client = api()
        access = _login(client, owner.username).json()["access"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        assert client.get("/api/v1/auth/me/").status_code == 200


class TestRefreshLogout:
    def test_refresh_via_cookie_and_rotation(self, api, owner):
        from django.core.cache import cache

        client = api()
        _login(client, owner.username)
        old = client.cookies[COOKIE].value
        response = client.post("/api/v1/auth/refresh/")
        assert response.status_code == 200
        assert response.json()["access"]
        assert client.cookies[COOKIE].value != old

        # Grace oynasi: ikkinchi vkladka eski cookie bilan kelsa ham sessiya uzilmaydi
        client.cookies[COOKIE] = old
        assert client.post("/api/v1/auth/refresh/").status_code == 200

        # Grace tugagach eski (aylantirilgan) token ishlamaydi
        cache.clear()
        client.cookies[COOKIE] = old
        assert client.post("/api/v1/auth/refresh/").status_code == 401

    def test_refresh_without_cookie(self, api):
        assert api().post("/api/v1/auth/refresh/").status_code == 401

    def test_logout_blacklists(self, api, owner):
        client = api()
        _login(client, owner.username)
        token = client.cookies[COOKIE].value
        assert client.post("/api/v1/auth/logout/").status_code == 204
        client.cookies[COOKIE] = token
        assert client.post("/api/v1/auth/refresh/").status_code == 401


class TestPin:
    def test_pin_switch_within_tenant(self, api, owner, make_user):
        cashier = make_user("Kassir")
        cashier.set_pin("1234")
        cashier.save()
        client = api(owner)
        users = client.get("/api/v1/auth/pin-users/").json()
        assert [u["id"] for u in users] == [cashier.pk]

        bad = client.post("/api/v1/auth/pin-login/", {"user_id": cashier.pk, "pin": "0000"})
        assert bad.status_code == 401
        ok = client.post("/api/v1/auth/pin-login/", {"user_id": cashier.pk, "pin": "1234"})
        assert ok.status_code == 200
        assert ok.json()["user"]["username"] == cashier.username

    def test_pin_cannot_cross_tenant(self, api, owner, make_tenant):
        other = make_tenant().owner
        other.set_pin("1234")
        other.save()
        response = api(owner).post("/api/v1/auth/pin-login/", {"user_id": other.pk, "pin": "1234"})
        assert response.status_code == 401


class TestUsersAndRoles:
    def test_owner_creates_cashier(self, owner_api, tenant, setup):
        kassir = Role.objects.get(tenant=tenant, name="Kassir")
        response = owner_api.post(
            "/api/v1/accounts/users/",
            {
                "username": "ali",
                "password": "Kuchli-parol-1",
                "first_name": "Ali",
                "roles": [kassir.pk],
                "branches": [setup.branch.pk],
            },
            format="json",
        )
        assert response.status_code == 201, response.json()
        me = api_login_me("ali")
        kassir_spec = next(r for r in DEFAULT_ROLES if r["name"] == "Kassir")
        assert me["permissions"] == sorted(kassir_spec["permissions"])
        assert me["branch_ids"] == [setup.branch.pk]

    def test_cashier_cannot_manage_users(self, api, make_user):
        assert api(make_user("Kassir")).get("/api/v1/accounts/users/").status_code == 403

    def test_manager_cannot_grant_owner_role(self, api, make_user, tenant):
        manager = make_user("Menejer")
        manager.roles.add(
            Role.objects.create(tenant=tenant, name="HR", permissions=["users.manage"])
        )
        owner_role = Role.objects.get(tenant=tenant, name="Egasi")
        response = api(manager).post(
            "/api/v1/accounts/users/",
            {"username": "x1", "password": "Kuchli-parol-1", "roles": [owner_role.pk]},
            format="json",
        )
        assert response.status_code == 400

    def test_cannot_use_other_tenant_role(self, owner_api, make_tenant):
        foreign_role = Role.objects.get(tenant=make_tenant().tenant, name="Kassir")
        response = owner_api.post(
            "/api/v1/accounts/users/",
            {"username": "x2", "password": "Kuchli-parol-1", "roles": [foreign_role.pk]},
            format="json",
        )
        assert response.status_code == 400

    def test_system_role_is_protected(self, owner_api, tenant):
        role = Role.objects.get(tenant=tenant, name="Kassir")
        assert (
            owner_api.patch(
                f"/api/v1/accounts/roles/{role.pk}/", {"name": "X"}, format="json"
            ).status_code
            == 400
        )
        assert owner_api.delete(f"/api/v1/accounts/roles/{role.pk}/").status_code == 400

    def test_custom_role_rejects_unknown_perm(self, owner_api):
        response = owner_api.post(
            "/api/v1/accounts/roles/", {"name": "Test", "permissions": ["foo.bar"]}, format="json"
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "validation_error"


def api_login_me(username):
    from rest_framework.test import APIClient

    client = APIClient()
    response = client.post(
        "/api/v1/auth/login/", {"username": username, "password": "Kuchli-parol-1"}, format="json"
    )
    assert response.status_code == 200, response.json()
    return response.json()["user"]


def test_sync_system_roles_updates_outdated_permissions(tenant):
    role = Role.objects.get(tenant=tenant, name="Kassir")
    role.permissions = ["catalog.view"]
    role.save()
    assert sync_system_roles() == 1
    role.refresh_from_db()
    assert "debts.collect" in role.permissions
    assert sync_system_roles() == 0
