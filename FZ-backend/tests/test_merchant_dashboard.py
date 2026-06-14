from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    engine = create_engine(settings.sync_database_url)
    with engine.begin() as connection:
        connection.execute(text("delete from merchant_leads"))
        connection.execute(text("delete from merchant_products"))
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
    assert data["stats"]["listedProducts"] == 0
    assert data["stats"]["productLimit"] == 2
    assert data["stats"]["todayLeads"] == 0
    assert data["stats"]["totalLeads"] == 0
    assert data["recentLeads"] == []


def test_dashboard_returns_vip_merchant_summary() -> None:
    session = login("vip-dashboard@example.com")
    engine = create_engine(settings.sync_database_url)
    with engine.begin() as connection:
        merchant_id = connection.execute(
            text(
                "update merchants set tier = 'vip', vip_started_at = now(), "
                "vip_expires_at = now() + interval '1 year' "
                "where email = :email returning id"
            ),
            {"email": "vip-dashboard@example.com"},
        ).scalar_one()
        product_id = connection.execute(
            text(
                "insert into merchant_products "
                "(merchant_id, title, summary, detail, tags, price_cents, status, image_urls, "
                "match_params, search_text, published_at) "
                "values (:merchant_id, '真实商品', '简介', '详情', '[]'::jsonb, 100, 'listed', "
                "'[]'::jsonb, '{}'::jsonb, '', now()) returning id"
            ),
            {"merchant_id": merchant_id},
        ).scalar_one()
        connection.execute(
            text(
                "insert into merchant_leads "
                "(merchant_id, product_id, submitted_at, buyer_email, message, product_title, "
                "product_price_cents, product_image_url, status) "
                "values (:merchant_id, :product_id, now(), 'buyer@example.com', "
                "'想看真实商品', '真实商品', 100, '/mock-products/jade-1.png', 'pending')"
            ),
            {"merchant_id": merchant_id, "product_id": product_id},
        )

    response = client.get(
        "/api/merchant/dashboard",
        headers={"Authorization": f"Bearer {session['token']}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["merchant"]["tier"] == "vip"
    assert data["stats"]["listedProducts"] == 1
    assert data["stats"]["productLimit"] == 100
    assert data["stats"]["todayLeads"] == 1
    assert data["stats"]["totalLeads"] == 1
    assert data["recentLeads"][0]["buyerEmail"] == "buyer@example.com"


def test_dashboard_treats_expired_vip_as_free() -> None:
    session = login("expired-vip-dashboard@example.com")
    engine = create_engine(settings.sync_database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "update merchants set tier = 'vip', vip_started_at = now() - interval '2 years', "
                "vip_expires_at = now() - interval '1 day' where email = :email"
            ),
            {"email": "expired-vip-dashboard@example.com"},
        )

    response = client.get(
        "/api/merchant/dashboard",
        headers={"Authorization": f"Bearer {session['token']}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["merchant"]["tier"] == "free"
    assert data["stats"]["productLimit"] == 2
