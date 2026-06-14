from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    engine = create_engine(settings.sync_database_url)
    with engine.begin() as connection:
        connection.execute(text("delete from merchant_vip_orders"))
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
            text(
                "update merchants set tier = 'vip', vip_started_at = now(), "
                "vip_expires_at = now() + interval '1 year' where email = :email"
            ),
            {"email": email},
        )


def test_leads_require_login() -> None:
    response = client.get("/api/merchant/leads")

    assert response.status_code == 401


def test_free_leads_are_seeded_and_mask_buyer_email() -> None:
    session = login("free-leads@example.com")

    response = client.get("/api/merchant/leads", headers=auth_headers(session["token"]))

    assert response.status_code == 200
    data = response.json()
    assert data["merchant"]["tier"] == "free"
    assert len(data["leads"]) == 4
    assert data["leads"][0]["buyerEmail"] == "****@***.com"


def test_leads_status_filter() -> None:
    session = login("filter-leads@example.com")

    pending_response = client.get(
        "/api/merchant/leads?status=pending",
        headers=auth_headers(session["token"]),
    )
    contacted_response = client.get(
        "/api/merchant/leads?status=contacted",
        headers=auth_headers(session["token"]),
    )

    assert pending_response.status_code == 200
    assert contacted_response.status_code == 200
    assert {lead["status"] for lead in pending_response.json()["leads"]} == {"pending"}
    assert {lead["status"] for lead in contacted_response.json()["leads"]} == {"contacted"}


def test_free_lead_detail_masks_buyer_email() -> None:
    session = login("free-detail@example.com")
    list_response = client.get("/api/merchant/leads", headers=auth_headers(session["token"]))
    lead_id = list_response.json()["leads"][0]["id"]

    response = client.get(f"/api/merchant/leads/{lead_id}", headers=auth_headers(session["token"]))

    assert response.status_code == 200
    assert response.json()["buyerEmail"] == "****@***.com"


def test_vip_lead_detail_shows_full_buyer_email() -> None:
    session = login("vip-detail@example.com")
    make_vip("vip-detail@example.com")
    list_response = client.get("/api/merchant/leads", headers=auth_headers(session["token"]))
    lead_id = list_response.json()["leads"][0]["id"]

    response = client.get(f"/api/merchant/leads/{lead_id}", headers=auth_headers(session["token"]))

    assert response.status_code == 200
    assert response.json()["buyerEmail"] == "buyer1@email.com"


def test_vip_can_mark_lead_contacted() -> None:
    session = login("vip-mark@example.com")
    make_vip("vip-mark@example.com")
    list_response = client.get(
        "/api/merchant/leads?status=pending",
        headers=auth_headers(session["token"]),
    )
    lead_id = list_response.json()["leads"][0]["id"]

    patch_response = client.patch(
        f"/api/merchant/leads/{lead_id}/status",
        json={"status": "contacted"},
        headers=auth_headers(session["token"]),
    )
    detail_response = client.get(
        f"/api/merchant/leads/{lead_id}",
        headers=auth_headers(session["token"]),
    )

    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "contacted"
    assert detail_response.json()["status"] == "contacted"


def test_free_cannot_mark_lead_contacted() -> None:
    session = login("free-mark@example.com")
    list_response = client.get("/api/merchant/leads", headers=auth_headers(session["token"]))
    lead_id = list_response.json()["leads"][0]["id"]

    response = client.patch(
        f"/api/merchant/leads/{lead_id}/status",
        json={"status": "contacted"},
        headers=auth_headers(session["token"]),
    )

    assert response.status_code == 403


def test_notifications_differ_by_tier() -> None:
    free_session = login("free-notice@example.com")
    vip_session = login("vip-notice@example.com")
    make_vip("vip-notice@example.com")

    free_response = client.get(
        "/api/merchant/notifications",
        headers=auth_headers(free_session["token"]),
    )
    vip_response = client.get(
        "/api/merchant/notifications",
        headers=auth_headers(vip_session["token"]),
    )

    assert free_response.status_code == 200
    assert vip_response.status_code == 200
    assert {notice["type"] for notice in free_response.json()["notifications"]} == {"new_lead"}
    assert {notice["type"] for notice in vip_response.json()["notifications"]} == {
        "new_lead",
        "vip_expiring",
    }
