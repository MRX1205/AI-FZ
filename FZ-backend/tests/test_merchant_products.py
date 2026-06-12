from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    engine = create_engine(settings.sync_database_url)
    with engine.begin() as connection:
        connection.execute(text("delete from merchant_products"))
        connection.execute(text("delete from merchant_notifications"))
        connection.execute(text("delete from merchant_leads"))
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


def make_vip(email: str) -> None:
    engine = create_engine(settings.sync_database_url)
    with engine.begin() as connection:
        connection.execute(
            text("update merchants set tier = 'vip' where email = :email"),
            {"email": email},
        )


def test_products_require_login() -> None:
    response = client.get("/api/merchant/products")

    assert response.status_code == 401


def test_products_seed_counts_and_free_quota() -> None:
    session = login("products-free@example.com")

    response = client.get("/api/merchant/products", headers=auth_headers(session["token"]))

    assert response.status_code == 200
    data = response.json()
    assert len(data["products"]) == 3
    assert data["counts"] == {"all": 3, "listed": 1, "draft": 1, "unlisted": 1}
    assert data["quota"]["productLimit"] == 2
    assert data["quota"]["remaining"] == 1


def test_products_filter_by_status() -> None:
    session = login("products-filter@example.com")

    response = client.get(
        "/api/merchant/products?status=draft",
        headers=auth_headers(session["token"]),
    )

    assert response.status_code == 200
    assert {product["status"] for product in response.json()["products"]} == {"draft"}


def test_vip_product_quota_is_100() -> None:
    session = login("products-vip@example.com")
    make_vip("products-vip@example.com")

    response = client.get("/api/merchant/products", headers=auth_headers(session["token"]))

    assert response.status_code == 200
    data = response.json()
    assert data["merchant"]["tier"] == "vip"
    assert data["quota"]["productLimit"] == 100
    assert data["quota"]["listedCount"] == 10
    assert data["quota"]["remaining"] == 90


def test_product_detail_and_update() -> None:
    session = login("products-update@example.com")
    list_response = client.get("/api/merchant/products", headers=auth_headers(session["token"]))
    product_id = list_response.json()["products"][0]["id"]

    detail_response = client.get(
        f"/api/merchant/products/{product_id}",
        headers=auth_headers(session["token"]),
    )
    update_response = client.patch(
        f"/api/merchant/products/{product_id}",
        json={
            "title": "更新后的翡翠",
            "summary": "更新简介",
            "detail": "更新后的商品详情",
            "tags": ["冰种", "收藏"],
            "priceCents": 6_600_000,
        },
        headers=auth_headers(session["token"]),
    )

    assert detail_response.status_code == 200
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "更新后的翡翠"
    assert update_response.json()["priceCents"] == 6_600_000


def test_product_status_update_respects_free_quota() -> None:
    session = login("products-status@example.com")
    draft_response = client.get(
        "/api/merchant/products?status=draft",
        headers=auth_headers(session["token"]),
    )
    unlisted_response = client.get(
        "/api/merchant/products?status=unlisted",
        headers=auth_headers(session["token"]),
    )
    draft_id = draft_response.json()["products"][0]["id"]
    unlisted_id = unlisted_response.json()["products"][0]["id"]

    publish_response = client.patch(
        f"/api/merchant/products/{draft_id}/status",
        json={"status": "listed"},
        headers=auth_headers(session["token"]),
    )
    quota_response = client.patch(
        f"/api/merchant/products/{unlisted_id}/status",
        json={"status": "listed"},
        headers=auth_headers(session["token"]),
    )

    assert publish_response.status_code == 200
    assert publish_response.json()["status"] == "listed"
    assert quota_response.status_code == 400


def test_delete_product() -> None:
    session = login("products-delete@example.com")
    list_response = client.get("/api/merchant/products", headers=auth_headers(session["token"]))
    product_id = list_response.json()["products"][0]["id"]

    delete_response = client.delete(
        f"/api/merchant/products/{product_id}",
        headers=auth_headers(session["token"]),
    )
    detail_response = client.get(
        f"/api/merchant/products/{product_id}",
        headers=auth_headers(session["token"]),
    )

    assert delete_response.status_code == 200
    assert delete_response.json() == {"ok": True}
    assert detail_response.status_code == 404


def test_replace_product_image() -> None:
    session = login("products-image@example.com")
    list_response = client.get("/api/merchant/products", headers=auth_headers(session["token"]))
    product_id = list_response.json()["products"][0]["id"]

    response = client.post(
        f"/api/merchant/products/{product_id}/images/replace",
        files={"file": ("jade.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        headers=auth_headers(session["token"]),
    )

    assert response.status_code == 200
    assert response.json()["imageUrls"][0].startswith("/uploads/products/")


def test_generate_product_draft_requires_login() -> None:
    response = client.post(
        "/api/merchant/products/drafts/generate",
        files={"images": ("jade.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )

    assert response.status_code == 401


def test_generate_product_draft_requires_image() -> None:
    session = login("products-draft-no-image@example.com")

    response = client.post(
        "/api/merchant/products/drafts/generate",
        headers=auth_headers(session["token"]),
    )

    assert response.status_code == 400


def test_generate_product_draft_rejects_more_than_six_images() -> None:
    session = login("products-draft-too-many@example.com")
    files = [
        ("images", (f"jade-{index}.png", b"\x89PNG\r\n\x1a\n", "image/png"))
        for index in range(7)
    ]

    response = client.post(
        "/api/merchant/products/drafts/generate",
        files=files,
        headers=auth_headers(session["token"]),
    )

    assert response.status_code == 400


def test_generate_product_draft_and_publish() -> None:
    session = login("products-publish@example.com")

    draft_response = client.post(
        "/api/merchant/products/drafts/generate",
        files={"images": ("jade.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        headers=auth_headers(session["token"]),
    )
    draft = draft_response.json()
    publish_response = client.patch(
        f"/api/merchant/products/{draft['id']}/publish",
        json={
            "title": "发布后的翡翠",
            "summary": "发布简介",
            "detail": "发布后的商品详情",
            "tags": ["冰种", "AI生成"],
            "priceCents": 4_800_000,
        },
        headers=auth_headers(session["token"]),
    )

    assert draft_response.status_code == 200
    assert draft["status"] == "draft"
    assert draft["imageUrls"][0].startswith("/uploads/products/")
    assert publish_response.status_code == 200
    assert publish_response.json()["status"] == "listed"
    assert publish_response.json()["publishedAt"]


def test_generate_product_draft_respects_free_quota() -> None:
    session = login("products-draft-quota@example.com")
    client.post(
        "/api/merchant/products/drafts/generate",
        files={"images": ("jade.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        headers=auth_headers(session["token"]),
    )
    draft_response = client.get(
        "/api/merchant/products?status=draft",
        headers=auth_headers(session["token"]),
    )
    draft_id = draft_response.json()["products"][0]["id"]
    client.patch(
        f"/api/merchant/products/{draft_id}/publish",
        json={
            "title": "占满额度的翡翠",
            "summary": "发布简介",
            "detail": "发布后的商品详情",
            "tags": ["冰种"],
            "priceCents": 4_800_000,
        },
        headers=auth_headers(session["token"]),
    )

    response = client.post(
        "/api/merchant/products/drafts/generate",
        files={"images": ("jade.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        headers=auth_headers(session["token"]),
    )

    assert response.status_code == 400
