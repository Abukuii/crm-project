from decimal import Decimal

import pytest

from apps.core.counters import next_number
from apps.core.models import AuditLog
from apps.core.money import q_money, q_price, q_qty, to_decimal
from apps.core.text import normalize, search_key


class TestMoney:
    def test_float_is_converted_exactly(self):
        assert to_decimal(0.1) == Decimal("0.1")

    def test_rounding_half_up(self):
        assert q_money("2.345") == Decimal("2.35")
        assert q_price("12.50005") == Decimal("12.5001")
        assert q_qty("2.5004") == Decimal("2.500")


class TestText:
    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            ("Цемент М-400", "sement m 400"),
            ("SEMENT m400", "sement m400"),
            ("G'isht", "gisht"),
            ("Oʻzbek bo‘yoq", "ozbek boyoq"),
            ("Ғишт", "gisht"),
        ],
    )
    def test_normalize(self, source, expected):
        assert normalize(source) == expected

    def test_search_key_ignores_spaces(self):
        assert search_key("Цемент М-400") == search_key("sement m400")


@pytest.mark.django_db
class TestCounters:
    def test_sequence_per_tenant_and_key(self, make_tenant):
        a, b = make_tenant().tenant, make_tenant().tenant
        assert [next_number(a, "x") for _ in range(3)] == [1, 2, 3]
        assert next_number(b, "x") == 1
        assert next_number(a, "y") == 1


@pytest.mark.django_db
class TestAudit:
    def test_audit_is_immutable(self, tenant):
        log = AuditLog.objects.filter(tenant=tenant).first()
        assert log is not None  # provision_tenant yozuvi
        log.action = "changed"
        with pytest.raises(RuntimeError):
            log.save()
        with pytest.raises(RuntimeError):
            log.delete()


@pytest.mark.django_db
def test_health(api):
    response = api().get("/api/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": True}
