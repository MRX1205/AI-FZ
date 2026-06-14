from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.main import app
from app.services.alipay import (
    AlipayNotification,
    AlipayTradeQueryResult,
    AlipayVerificationError,
    alipay_client,
)
from app.services.vip_orders import add_months

client = TestClient(app)


def setup_function() -> None:
    engine = create_engine(settings.sync_database_url)
    with engine.begin() as connection:
        connection.execute(text("delete from merchant_vip_orders"))
        connection.execute(text("delete from merchant_product_embeddings"))
        connection.execute(text("delete from merchant_product_images"))
        connection.execute(text("delete from merchant_products"))
        connection.execute(text("delete from merchant_sessions"))
        connection.execute(text("delete from auth_codes"))
        connection.execute(text("delete from merchants"))


def login(email: str) -> dict:
    client.post("/api/auth/send-code", json={"email": email})
    response = client.post("/api/auth/login", json={"email": email, "code": "123456"})
    assert response.status_code == 200
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_account_returns_free_membership() -> None:
    session = login("free-account@example.com")

    response = client.get("/api/merchant/account", headers=auth_headers(session["token"]))

    assert response.status_code == 200
    data = response.json()
    assert data["merchant"]["tier"] == "free"
    assert data["listedCount"] == 0
    assert data["productLimit"] == 2
    assert data["leadAccess"] == "无查看权限"
    assert data["plans"][0]["amountCents"] == 299900


def test_create_vip_order_returns_pay_url() -> None:
    session = login("vip-order@example.com")

    response = client.post(
        "/api/merchant/account/vip-orders",
        json={"planMonths": 12, "payChannel": "page"},
        headers=auth_headers(session["token"]),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["amountCents"] == 299900
    assert data["payChannel"] == "page"
    assert data["payUrl"].startswith("https://example.com/alipay/page/")


def test_vip_order_cannot_be_read_by_other_merchant() -> None:
    owner = login("vip-owner@example.com")
    other = login("vip-other@example.com")
    create_response = client.post(
        "/api/merchant/account/vip-orders",
        json={"planMonths": 6, "payChannel": "wap"},
        headers=auth_headers(owner["token"]),
    )
    order_id = create_response.json()["id"]

    response = client.get(
        f"/api/merchant/account/vip-orders/{order_id}",
        headers=auth_headers(other["token"]),
    )

    assert response.status_code == 404


def test_sync_paid_order_upgrades_merchant(monkeypatch) -> None:
    session = login("vip-sync@example.com")
    create_response = client.post(
        "/api/merchant/account/vip-orders",
        json={"planMonths": 12, "payChannel": "page"},
        headers=auth_headers(session["token"]),
    )
    order = create_response.json()

    async def success_query_trade(*, order_no: str) -> AlipayTradeQueryResult:
        return AlipayTradeQueryResult(
            status="success",
            trade_status="TRADE_SUCCESS",
            trade_no="2088TESTPAID",
            total_amount="2999.00",
        )

    monkeypatch.setattr(alipay_client, "query_trade", success_query_trade)

    response = client.post(
        f"/api/merchant/account/vip-orders/{order['id']}/sync",
        headers=auth_headers(session["token"]),
    )

    assert response.status_code == 200
    data = response.json()["order"]
    assert data["status"] == "paid"
    me_response = client.get("/api/auth/me", headers=auth_headers(session["token"]))
    assert me_response.status_code == 200
    assert me_response.json()["tier"] == "vip"


def test_vip_renewal_extends_from_current_expiry(monkeypatch) -> None:
    session = login("vip-renew@example.com")
    engine = create_engine(settings.sync_database_url)
    with engine.begin() as connection:
        current_expires_at = connection.execute(
            text(
                "update merchants set tier = 'vip', vip_started_at = now() - interval '20 days', "
                "vip_expires_at = now() + interval '40 days' "
                "where email = :email returning vip_expires_at"
            ),
            {"email": "vip-renew@example.com"},
        ).scalar_one()

    create_response = client.post(
        "/api/merchant/account/vip-orders",
        json={"planMonths": 6, "payChannel": "page"},
        headers=auth_headers(session["token"]),
    )
    order = create_response.json()

    async def success_query_trade(*, order_no: str) -> AlipayTradeQueryResult:
        return AlipayTradeQueryResult(
            status="success",
            trade_status="TRADE_SUCCESS",
            trade_no="2088TESTRENEW",
            total_amount="1688.00",
        )

    monkeypatch.setattr(alipay_client, "query_trade", success_query_trade)

    response = client.post(
        f"/api/merchant/account/vip-orders/{order['id']}/sync",
        headers=auth_headers(session["token"]),
    )

    assert response.status_code == 200
    paid_order = response.json()["order"]
    expected_expires_at = add_months(current_expires_at.astimezone(UTC), 6)
    assert paid_order["grantStartedAt"] == current_expires_at.isoformat()
    assert paid_order["grantExpiresAt"] == expected_expires_at.isoformat()


def test_alipay_notify_rejects_bad_signature(monkeypatch) -> None:
    def fail_verify(raw_params: dict[str, str]) -> AlipayNotification:
        raise AlipayVerificationError("bad sign")

    monkeypatch.setattr(alipay_client, "verify_notification", fail_verify)

    response = client.post(
        "/api/payments/alipay/notify",
        data={"out_trade_no": "X", "sign": "bad"},
    )

    assert response.status_code == 400
    assert response.text == "failure"


def test_alipay_notify_marks_order_paid(monkeypatch) -> None:
    session = login("vip-notify@example.com")
    create_response = client.post(
        "/api/merchant/account/vip-orders",
        json={"planMonths": 12, "payChannel": "page"},
        headers=auth_headers(session["token"]),
    )
    order = create_response.json()

    def verify_notification(raw_params: dict[str, str]) -> AlipayNotification:
        return AlipayNotification(
            app_id="test-app-id",
            out_trade_no=order["orderNo"],
            trade_no="2088TESTNOTIFY",
            trade_status="TRADE_SUCCESS",
            total_amount="2999.00",
            seller_id=None,
            notify_time=datetime.now(UTC) + timedelta(seconds=1),
        )

    monkeypatch.setattr(alipay_client, "verify_notification", verify_notification)
    monkeypatch.setattr(settings, "alipay_app_id", "test-app-id")

    response = client.post(
        "/api/payments/alipay/notify",
        data={"out_trade_no": order["orderNo"], "sign": "ok"},
    )

    assert response.status_code == 200
    assert response.text == "success"
    order_response = client.get(
        f"/api/merchant/account/vip-orders/{order['id']}",
        headers=auth_headers(session["token"]),
    )
    assert order_response.status_code == 200
    assert order_response.json()["status"] == "paid"
