from decimal import Decimal as D

import httpx
import pytest
from django.test import override_settings

from apps.finance.models import Expense, ExpenseCategory
from apps.notifications import telegram
from apps.notifications.tasks import notify_sale
from apps.sales.models import Sale

pytestmark = pytest.mark.django_db


def _sell(api, stock, qty="2", method="cash"):
    return api.post("/api/v1/sales/sales/", {
        "warehouse": stock.wh.pk, "items": [{"product": stock.cement.pk, "qty": qty}],
        "payments": [{"method": method, "amount": str(D("58000") * D(qty))}],
    }, format="json")  # fmt: skip


def test_dashboard_numbers(owner_api, stock):
    _sell(owner_api, stock)
    Expense.objects.create(
        tenant=stock.tenant,
        name="Ijara",
        amount=D("50000"),
        category=ExpenseCategory.objects.get(tenant=stock.tenant, name="Ijara"),
    )
    d = owner_api.get("/api/v1/reports/dashboard/").json()
    assert d["today"]["sales_count"] == 1
    assert d["today"]["revenue"] == "116000.00"
    assert d["today"]["gross_profit"] == "18000.00"
    assert d["month"]["net_profit"] == "-32000.00"
    assert d["today_by_method"] == {"cash": "116000.00"}
    assert d["top_products"][0]["name"] == "Sement M-400"
    assert len(d["week"]) == 7
    assert d["recent_sales"][0]["total"] == "116000.00"


def test_dashboard_hides_profit_without_cost_perm(api, make_user, stock):
    manager = make_user("Menejer")  # reports.view bor, cost.view yo'q
    d = api(manager).get("/api/v1/reports/dashboard/").json()
    assert "gross_profit" not in d["today"]


def test_cashier_has_no_dashboard(api, make_user, stock):
    assert api(make_user("Kassir")).get("/api/v1/reports/dashboard/").status_code == 403


class TestExpensesAndReminders:
    def test_expense_crud_and_total(self, owner_api, tenant):
        cat = ExpenseCategory.objects.get(tenant=tenant, name="Transport")
        r = owner_api.post("/api/v1/finance/expenses/",
                           {"name": "Yuk mashina", "category": cat.pk, "amount": "150000"},
                           format="json")  # fmt: skip
        assert r.status_code == 201, r.json()
        assert owner_api.get("/api/v1/finance/expenses/total/").json()["total"] == "150000.00"
        assert owner_api.delete(f"/api/v1/finance/expenses/{r.json()['id']}/").status_code == 204

    def test_cashier_cannot_add_expense(self, api, make_user):
        assert api(make_user("Kassir")).get("/api/v1/finance/expenses/").status_code == 403

    def test_reminders(self, api, make_user):
        client = api(make_user("Menejer"))
        r = client.post("/api/v1/notes/reminders/", {"text": "Sement buyurtma", "level": "urgent"},
                        format="json")  # fmt: skip
        assert r.status_code == 201
        client.patch(f"/api/v1/notes/reminders/{r.json()['id']}/", {"is_done": True}, format="json")
        assert client.get("/api/v1/notes/reminders/", {"is_done": "true"}).json()[0]["is_done"]


class TestTelegram:
    @override_settings(TELEGRAM_BOT_TOKEN="123:abc")
    def test_sale_message_sent_to_tenant_chat(self, owner_api, stock, monkeypatch):
        sent = []

        def handler(request):
            sent.append(request)
            return httpx.Response(200, json={"ok": True})

        transport = httpx.MockTransport(handler)
        real_client = httpx.Client
        monkeypatch.setattr(telegram.httpx, "Client", lambda **kw: real_client(transport=transport))
        stock.tenant.settings = {"telegram_chat_id": "-100123"}
        stock.tenant.save()

        _sell(owner_api, stock)
        sale = Sale.objects.get()
        assert notify_sale(sale.pk) is True
        body = sent[-1].read().decode()
        assert "-100123" in body and "Sement M-400" in body

    def test_no_chat_configured(self, owner_api, stock):
        _sell(owner_api, stock)
        assert notify_sale(Sale.objects.get().pk) is False
