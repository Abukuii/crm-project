from decimal import Decimal as D

import pytest
from pywebpush import WebPushException

from apps.notifications.models import PushSubscription

pytestmark = pytest.mark.django_db

CONFIG = "/api/v1/notifications/push/config/"
SUBSCRIBE = "/api/v1/notifications/push/subscribe/"
UNSUBSCRIBE = "/api/v1/notifications/push/unsubscribe/"
TEST = "/api/v1/notifications/push/test/"
SALES = "/api/v1/sales/sales/"

ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc123"
SUB = {"endpoint": ENDPOINT, "keys": {"p256dh": "p256dh-kalit", "auth": "auth-kalit"}}


@pytest.fixture
def push_on(settings):
    settings.VAPID_PUBLIC_KEY = "BPublicKeyForTests"
    settings.VAPID_PRIVATE_KEY = "private-key-for-tests"
    settings.VAPID_SUBJECT = "mailto:admin@savdolarim.uz"


@pytest.fixture
def sent(monkeypatch):
    """webpush() chaqiruvlarini yig'adi (tarmoqqa chiqmaydi)."""
    calls: list[dict] = []
    monkeypatch.setattr("apps.notifications.push.webpush", lambda **kw: calls.append(kw))
    return calls


def _fail_with(status: int):
    class Resp:
        status_code = status
        text = ""

    def raiser(**_kw):
        raise WebPushException("xato", response=Resp())

    return raiser


class TestSubscription:
    def test_config_subscribe_test_unsubscribe(self, owner_api, push_on, sent):
        config = owner_api.get(CONFIG).json()
        assert (config["enabled"], config["public_key"], config["devices"]) == (
            True,
            "BPublicKeyForTests",
            0,
        )

        assert owner_api.post(SUBSCRIBE, SUB, format="json").status_code == 201
        # Takroriy obuna yangi qurilma yaratmaydi
        assert owner_api.post(SUBSCRIBE, SUB, format="json").json()["devices"] == 1

        assert owner_api.post(TEST).json() == {"sent": 1}
        assert sent[0]["subscription_info"]["endpoint"] == ENDPOINT
        assert "Savdo" in sent[0]["data"]

        assert owner_api.post(UNSUBSCRIBE, {"endpoint": ENDPOINT}, format="json").status_code == 204
        assert owner_api.get(CONFIG).json()["devices"] == 0

    def test_disabled_without_vapid_keys(self, owner_api, settings):
        settings.VAPID_PUBLIC_KEY = settings.VAPID_PRIVATE_KEY = ""
        assert owner_api.get(CONFIG).json() == {"enabled": False, "public_key": None, "devices": 0}
        r = owner_api.post(SUBSCRIBE, SUB, format="json")
        assert r.status_code == 400 and r.json()["error"]["code"] == "push_disabled"

    def test_test_without_subscription(self, owner_api, push_on):
        assert owner_api.post(TEST).json()["error"]["code"] == "no_subscription"

    def test_same_browser_different_user(self, api, owner_api, make_user, push_on):
        owner_api.post(SUBSCRIBE, SUB, format="json")
        cashier = make_user("Kassir")
        api(cashier).post(SUBSCRIBE, SUB, format="json")
        assert PushSubscription.objects.count() == 1
        assert PushSubscription.objects.get().user_id == cashier.pk

    def test_invalid_endpoint_rejected(self, owner_api, push_on):
        r = owner_api.post(SUBSCRIBE, {**SUB, "endpoint": "not-a-url"}, format="json")
        assert r.status_code == 400

    def test_expired_subscription_is_deleted(self, owner_api, push_on, monkeypatch):
        owner_api.post(SUBSCRIBE, SUB, format="json")
        monkeypatch.setattr("apps.notifications.push.webpush", _fail_with(410))
        assert owner_api.post(TEST).json()["error"]["code"] == "no_subscription"
        assert PushSubscription.objects.count() == 0

    def test_other_errors_keep_subscription(self, owner_api, push_on, monkeypatch):
        owner_api.post(SUBSCRIBE, SUB, format="json")
        monkeypatch.setattr("apps.notifications.push.webpush", _fail_with(500))
        owner_api.post(TEST)
        assert PushSubscription.objects.count() == 1

    def test_anonymous_cannot_subscribe(self, api):
        assert api().post(SUBSCRIBE, SUB, format="json").status_code == 401


def _subscribe(user, tenant, endpoint=ENDPOINT):
    return PushSubscription.objects.create(
        tenant=tenant, user=user, endpoint=endpoint, p256dh="p", auth="a"
    )


def _sell(api, stock, qty="2", **extra):
    return api.post(SALES, {
        "warehouse": stock.wh.pk,
        "items": [{"product": stock.cement.pk, "qty": qty}],
        "payments": [{"method": "cash", "amount": str(D("58000") * D(qty))}],
        **extra,
    }, format="json")  # fmt: skip


class TestSaleNotifications:
    def test_sale_notifies_owner_but_not_the_cashier(
        self, api, make_user, stock, push_on, sent, django_capture_on_commit_callbacks
    ):
        cashier = make_user("Kassir")
        cashier.branches.add(stock.branch)
        _subscribe(stock.owner, stock.tenant)
        _subscribe(cashier, stock.tenant, endpoint=ENDPOINT + "-cashier")

        with django_capture_on_commit_callbacks(execute=True):
            assert _sell(api(cashier), stock, qty="2").status_code == 201

        assert len(sent) == 1
        assert sent[0]["subscription_info"]["endpoint"] == ENDPOINT
        payload = sent[0]["data"]
        assert "Savdo #1" in payload and "116" in payload
        assert "Sement M-400 \\u00d7 2" in payload or "Sement M-400 × 2" in payload

    def test_sale_push_can_be_switched_off(
        self, owner_api, stock, push_on, sent, make_user, django_capture_on_commit_callbacks
    ):
        stock.tenant.settings = {"push_notify_sales": False}
        stock.tenant.save()
        manager = make_user("Menejer")
        _subscribe(manager, stock.tenant)
        with django_capture_on_commit_callbacks(execute=True):
            _sell(owner_api, stock)
        assert sent == []

    def test_low_stock_fires_once_on_crossing(
        self, owner_api, stock, push_on, sent, make_user, django_capture_on_commit_callbacks
    ):
        stock.cement.min_stock = D("98")
        stock.cement.save()
        storekeeper = make_user("Omborchi")
        _subscribe(storekeeper, stock.tenant)

        # 100 → 98: chegaradan o'tdi
        with django_capture_on_commit_callbacks(execute=True):
            _sell(owner_api, stock, qty="2")
        low = [c for c in sent if "tugayapti" in c["data"]]
        assert len(low) == 1
        assert "Sement M-400" in low[0]["data"]
        assert "/stock?low_stock=true" in low[0]["data"]

        # 98 → 96: allaqachon chegaradan past, qayta xabar yo'q
        sent.clear()
        with django_capture_on_commit_callbacks(execute=True):
            _sell(owner_api, stock, qty="2")
        assert [c for c in sent if "tugayapti" in c["data"]] == []

    def test_no_low_stock_push_without_min_stock(
        self, owner_api, stock, push_on, sent, make_user, django_capture_on_commit_callbacks
    ):
        _subscribe(make_user("Omborchi"), stock.tenant)
        with django_capture_on_commit_callbacks(execute=True):
            _sell(owner_api, stock, qty="99")
        assert [c for c in sent if "tugayapti" in c["data"]] == []
