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


def test_dashboard_requires_login() -> None:
    response = client.get("/api/merchant/dashboard")

    assert response.status_code == 401


def test_dashboard_returns_free_merchant_summary() -> None:
    session = login("free-dashboard@example.com")

    response = client.get(
        "/api/merchant/dashboard",
        headers={"Authorization": f"Bearer {session['token']}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["merchant"]["tier"] == "free"
    assert data["stats"]["listedProducts"] == 2
    assert data["stats"]["productLimit"] == 2
    assert data["recentLeads"][0]["buyerEmail"] == "buyer1@email.com"


def test_dashboard_returns_vip_merchant_summary() -> None:
    session = login("vip-dashboard@example.com")
    engine = create_engine(settings.sync_database_url)
    with engine.begin() as connection:
        connection.execute(
            text("update merchants set tier = 'vip' where email = :email"),
            {"email": "vip-dashboard@example.com"},
        )

    response = client.get(
        "/api/merchant/dashboard",
        headers={"Authorization": f"Bearer {session['token']}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["merchant"]["tier"] == "vip"
    assert data["stats"]["listedProducts"] == 100
    assert data["stats"]["productLimit"] == 100
