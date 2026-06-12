from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    engine = create_engine(settings.sync_database_url)
    with engine.begin() as connection:
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


def test_profile_requires_login() -> None:
    response = client.get("/api/merchant/profile")

    assert response.status_code == 401


def test_profile_returns_notification_settings() -> None:
    session = login("profile@example.com")

    response = client.get("/api/merchant/profile", headers=auth_headers(session["token"]))

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "profile@example.com"
    assert data["notifications"]["webNotificationEnabled"] is True
    assert data["notifications"]["emailNotificationEnabled"] is True


def test_update_profile_email_with_code() -> None:
    session = login("old-profile@example.com")
    code_response = client.post(
        "/api/merchant/profile/email-code",
        json={"email": "new-profile@example.com"},
        headers=auth_headers(session["token"]),
    )
    assert code_response.status_code == 200
    assert code_response.json()["devCode"] == "123456"

    response = client.patch(
        "/api/merchant/profile/email",
        json={"email": "new-profile@example.com", "code": "123456"},
        headers=auth_headers(session["token"]),
    )

    assert response.status_code == 200
    assert response.json()["email"] == "new-profile@example.com"


def test_update_profile_email_rejects_wrong_code() -> None:
    session = login("wrong-code@example.com")
    client.post(
        "/api/merchant/profile/email-code",
        json={"email": "wrong-code-new@example.com"},
        headers=auth_headers(session["token"]),
    )

    response = client.patch(
        "/api/merchant/profile/email",
        json={"email": "wrong-code-new@example.com", "code": "000000"},
        headers=auth_headers(session["token"]),
    )

    assert response.status_code == 400


def test_update_profile_email_rejects_duplicate_email() -> None:
    login("duplicate-target@example.com")
    session = login("duplicate-source@example.com")
    client.post(
        "/api/merchant/profile/email-code",
        json={"email": "duplicate-target@example.com"},
        headers=auth_headers(session["token"]),
    )

    response = client.patch(
        "/api/merchant/profile/email",
        json={"email": "duplicate-target@example.com", "code": "123456"},
        headers=auth_headers(session["token"]),
    )

    assert response.status_code == 400


def test_update_notifications_keeps_web_notification_enabled() -> None:
    session = login("notifications@example.com")

    response = client.patch(
        "/api/merchant/profile/notifications",
        json={"emailNotificationEnabled": False},
        headers=auth_headers(session["token"]),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["webNotificationEnabled"] is True
    assert data["emailNotificationEnabled"] is False


def test_logout_invalidates_session() -> None:
    session = login("logout@example.com")

    logout_response = client.post("/api/auth/logout", headers=auth_headers(session["token"]))
    assert logout_response.status_code == 200

    profile_response = client.get("/api/merchant/profile", headers=auth_headers(session["token"]))
    assert profile_response.status_code == 401
