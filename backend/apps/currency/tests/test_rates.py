from datetime import date
from decimal import Decimal

import httpx
import pytest

from apps.currency.models import ExchangeRate
from apps.currency.services import RateNotFound, fetch_cbu_rates, get_rate, parse_cbu_payload

pytestmark = pytest.mark.django_db

CBU_SAMPLE = [
    {"Ccy": "USD", "Rate": "12650.55", "Nominal": "1", "Date": "20.11.2026"},
    {"Ccy": "EUR", "Rate": "13800.10", "Nominal": "1", "Date": "20.11.2026"},
    {"Ccy": "JPY", "Rate": "850.00", "Nominal": "10", "Date": "20.11.2026"},
    {"Ccy": "RUB", "Rate": "bad", "Nominal": "1", "Date": "20.11.2026"},
]


def test_parse_cbu_payload_filters_and_handles_nominal():
    rows = parse_cbu_payload(CBU_SAMPLE, ["USD", "JPY", "RUB"])
    assert rows == [
        ("USD", date(2026, 11, 20), Decimal("12650.5500")),
        ("JPY", date(2026, 11, 20), Decimal("85.0000")),
    ]


def test_fetch_cbu_rates_is_idempotent():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=CBU_SAMPLE))
    with httpx.Client(transport=transport) as client:
        assert fetch_cbu_rates(client) == 2  # USD, EUR (sozlamadagi ro'yxat)
        assert fetch_cbu_rates(client) == 2
    assert ExchangeRate.objects.filter(tenant__isnull=True).count() == 2


class TestGetRate:
    def _cbu(self, rate, on):
        ExchangeRate.objects.create(currency="USD", date=on, rate=rate, source="cbu")

    def _manual(self, tenant, rate, on):
        ExchangeRate.objects.create(
            tenant=tenant, currency="USD", date=on, rate=rate, source="manual"
        )

    def test_uzs_is_one(self, tenant):
        assert get_rate(tenant, "UZS").rate == 1

    def test_cbu_default_latest_on_or_before(self, tenant):
        self._cbu("12600", date(2026, 11, 18))
        self._cbu("12650", date(2026, 11, 20))
        assert get_rate(tenant, "USD", date(2026, 11, 19)).rate == Decimal("12600")
        assert get_rate(tenant, "usd", date(2026, 11, 21)).rate == Decimal("12650")

    def test_manual_source_preferred_when_configured(self, tenant):
        self._cbu("12650", date(2026, 11, 20))
        self._manual(tenant, "12800", date(2026, 11, 19))
        assert get_rate(tenant, "USD", date(2026, 11, 20)).source == "cbu"
        tenant.settings = {"rate_source": "manual"}
        tenant.save()
        info = get_rate(tenant, "USD", date(2026, 11, 20))
        assert (info.rate, info.source) == (Decimal("12800"), "manual")

    def test_other_tenant_manual_rate_ignored(self, tenant, make_tenant):
        self._manual(make_tenant().tenant, "99999", date(2026, 11, 20))
        with pytest.raises(RateNotFound):
            get_rate(tenant, "USD", date(2026, 11, 20))


class TestApi:
    def test_manual_rate_and_current(self, owner_api, tenant):
        tenant.settings = {"rate_source": "manual"}
        tenant.save()
        response = owner_api.post("/api/v1/currency/rates/", {"rate": "12700.50"}, format="json")
        assert response.status_code == 201, response.json()
        current = owner_api.get("/api/v1/currency/rates/current/").json()
        assert current["rate"] == "12700.5000"
        assert current["source"] == "manual"

    def test_cashier_cannot_set_rate(self, api, make_user):
        response = api(make_user("Kassir")).post(
            "/api/v1/currency/rates/", {"rate": "1"}, format="json"
        )
        assert response.status_code == 403

    def test_current_rate_missing(self, owner_api):
        response = owner_api.get("/api/v1/currency/rates/current/")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "rate_not_found"
