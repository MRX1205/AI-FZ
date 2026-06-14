from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    engine = create_engine(settings.sync_database_url)
    with engine.begin() as connection:
        connection.execute(text("delete from merchant_vip_orders"))
        connection.execute(text("delete from merchant_sessions"))
        connection.execute(text("delete from auth_codes"))
        connection.execute(text("delete from merchants"))


def test_send_code_and_login_creates_free_merchant() -> None:
    send_response = client.post("/api/auth/send-code", json={"email": "Merchant@Example.com"})
    assert send_response.status_code == 200
    assert "devCode" not in send_response.json()

    login_response = client.post(
        "/api/auth/login",
        json={"email": "merchant@example.com", "code": "123456"},
    )
    assert login_response.status_code == 200
    data = login_response.json()

    assert data["token"]
    assert data["merchant"]["email"] == "merchant@example.com"
    assert data["merchant"]["tier"] == "free"

    me_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {data['token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "merchant@example.com"


def test_login_rejects_wrong_code() -> None:
    client.post("/api/auth/send-code", json={"email": "merchant@example.com"})

    response = client.post(
        "/api/auth/login",
        json={"email": "merchant@example.com", "code": "000000"},
    )

    assert response.status_code == 400


def test_send_code_returns_clear_error_when_supabase_is_not_configured(monkeypatch) -> None:
    from app.services.supabase_otp import SupabaseOtpNotConfiguredError, supabase_otp_client

    async def fail_send_email_code(email: str) -> None:
        raise SupabaseOtpNotConfiguredError("邮箱验证码服务未配置")

    monkeypatch.setattr(supabase_otp_client, "send_email_code", fail_send_email_code)

    response = client.post("/api/auth/send-code", json={"email": "merchant@example.com"})

    assert response.status_code == 503
    assert response.json()["detail"] == "邮箱验证码服务未配置"
