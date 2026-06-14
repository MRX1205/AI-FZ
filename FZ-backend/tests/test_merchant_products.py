import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.main import app
from app.services.embeddings import EmbeddingResult, ProductEmbeddingError, embedding_client
from app.services.jade_agent import MimoCompletionError, jade_agent
from app.services.product_image_recognition_agent import (
    PRODUCT_IMAGE_RECOGNITION_AGENT_ROLE,
    ProductImageRecognitionResult,
    product_image_recognition_agent,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def fake_embedding_client(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_embed_document(text: str) -> EmbeddingResult:
        assert text.strip()
        return EmbeddingResult(
            provider="dashscope",
            model="text-embedding-v4",
            dimensions=1024,
            embedding=[0.1] * 1024,
        )

    monkeypatch.setattr(embedding_client, "embed_document", fake_embed_document)


def setup_function() -> None:
    engine = create_engine(settings.sync_database_url)
    with engine.begin() as connection:
        connection.execute(text("delete from merchant_product_embeddings"))
        connection.execute(text("delete from merchant_notifications"))
        connection.execute(text("delete from merchant_leads"))
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
    assert len(data["products"][0]["imageUrls"]) >= 1


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

    persisted_response = client.get(
        f"/api/merchant/products/{product_id}",
        headers=auth_headers(session["token"]),
    )
    assert persisted_response.status_code == 200
    assert persisted_response.json()["summary"] == "更新简介"
    assert persisted_response.json()["tags"] == ["冰种", "收藏"]

    engine = create_engine(settings.sync_database_url)
    with engine.begin() as connection:
        product_row = connection.execute(
            text("select search_text from merchant_products where id = :id"),
            {"id": product_id},
        ).one()
        embedding_count = connection.execute(
            text("select count(*) from merchant_product_embeddings where product_id = :id"),
            {"id": product_id},
        ).scalar_one()
    assert "商品标题：更新后的翡翠" in product_row.search_text
    assert embedding_count == 1


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


def test_product_unlist_persists_to_database() -> None:
    session = login("products-unlist@example.com")
    listed_response = client.get(
        "/api/merchant/products?status=listed",
        headers=auth_headers(session["token"]),
    )
    product_id = listed_response.json()["products"][0]["id"]

    update_response = client.patch(
        f"/api/merchant/products/{product_id}/status",
        json={"status": "unlisted"},
        headers=auth_headers(session["token"]),
    )
    detail_response = client.get(
        f"/api/merchant/products/{product_id}",
        headers=auth_headers(session["token"]),
    )

    assert update_response.status_code == 200
    assert update_response.json()["status"] == "unlisted"
    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "unlisted"


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

    list_after_delete = client.get("/api/merchant/products", headers=auth_headers(session["token"]))
    assert list_after_delete.status_code == 200
    assert list_after_delete.json()["counts"]["all"] == 2


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
    assert response.json()["imageUrls"][0].startswith("/uploads/merchants/")


def test_replace_product_image_by_index() -> None:
    session = login("products-image-index@example.com")
    list_response = client.get("/api/merchant/products", headers=auth_headers(session["token"]))
    product = list_response.json()["products"][0]

    response = client.post(
        f"/api/merchant/products/{product['id']}/images/replace",
        data={"imageIndex": "1"},
        files={"file": ("jade.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        headers=auth_headers(session["token"]),
    )

    assert response.status_code == 200
    assert response.json()["imageUrls"][0] == product["imageUrls"][0]
    assert response.json()["imageUrls"][1].startswith("/uploads/merchants/")


def test_generate_product_draft_requires_login() -> None:
    response = client.post(
        "/api/merchant/products/drafts/generate",
        files={"images": ("jade.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )

    assert response.status_code == 401


def test_current_publish_draft_ignores_seed_draft() -> None:
    session = login("products-current-draft-empty@example.com")

    response = client.get(
        "/api/merchant/products/current-draft",
        headers=auth_headers(session["token"]),
    )

    assert response.status_code == 200
    assert response.json()["product"] is None
    assert response.json()["quota"]["listedCount"] == 1


def test_append_images_creates_restorable_publish_draft() -> None:
    session = login("products-draft-images@example.com")

    upload_response = client.post(
        "/api/merchant/products/drafts/images",
        files={"images": ("jade.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        headers=auth_headers(session["token"]),
    )
    current_response = client.get(
        "/api/merchant/products/current-draft",
        headers=auth_headers(session["token"]),
    )

    assert upload_response.status_code == 200
    assert upload_response.json()["imageUrls"][0].startswith("/uploads/merchants/")
    assert current_response.status_code == 200
    assert current_response.json()["product"]["id"] == upload_response.json()["id"]
    assert current_response.json()["product"]["title"] == ""


def test_delete_product_image_persists() -> None:
    session = login("products-draft-delete-image@example.com")
    upload_response = client.post(
        "/api/merchant/products/drafts/images",
        files={"images": ("jade.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        headers=auth_headers(session["token"]),
    )
    product_id = upload_response.json()["id"]

    delete_response = client.delete(
        f"/api/merchant/products/{product_id}/images/0",
        headers=auth_headers(session["token"]),
    )
    current_response = client.get(
        "/api/merchant/products/current-draft",
        headers=auth_headers(session["token"]),
    )

    assert delete_response.status_code == 200
    assert delete_response.json()["imageUrls"] == []
    assert current_response.status_code == 200
    assert current_response.json()["product"]["imageUrls"] == []


def test_generate_product_draft_requires_image() -> None:
    session = login("products-draft-no-image@example.com")

    response = client.post(
        "/api/merchant/products/drafts/generate",
        headers=auth_headers(session["token"]),
    )

    assert response.status_code == 400


def test_product_image_recognition_agent_role_is_image_specific() -> None:
    assert "商品图片识别生成 Agent" in PRODUCT_IMAGE_RECOGNITION_AGENT_ROLE
    assert "商家上传的翡翠商品图片" in PRODUCT_IMAGE_RECOGNITION_AGENT_ROLE
    assert "不负责发布商品" in PRODUCT_IMAGE_RECOGNITION_AGENT_ROLE


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


def test_append_image_draft_and_publish() -> None:
    session = login("products-publish@example.com")

    draft_response = client.post(
        "/api/merchant/products/drafts/images",
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
    assert draft["title"] == ""
    assert draft["imageUrls"][0].startswith("/uploads/merchants/")
    assert publish_response.status_code == 200
    assert publish_response.json()["status"] == "listed"
    assert publish_response.json()["publishedAt"]

    engine = create_engine(settings.sync_database_url)
    with engine.begin() as connection:
        product_row = connection.execute(
            text("select search_text from merchant_products where id = :id"),
            {"id": draft["id"]},
        ).one()
        embedding_row = connection.execute(
            text(
                "select provider, model, dimensions, content_hash "
                "from merchant_product_embeddings where product_id = :id"
            ),
            {"id": draft["id"]},
        ).one()
    assert "商品标题：发布后的翡翠" in product_row.search_text
    assert embedding_row.provider == "dashscope"
    assert embedding_row.model == "text-embedding-v4"
    assert embedding_row.dimensions == 1024
    assert len(embedding_row.content_hash) == 64


def test_generate_product_draft_saves_when_quota_full_but_publish_fails(monkeypatch) -> None:
    async def fake_generate_product_copy(image_urls: list[str]) -> ProductImageRecognitionResult:
        assert image_urls[0].startswith("data:image/")
        return ProductImageRecognitionResult(
            title="AI生成翡翠",
            summary="AI生成简介",
            detail="AI生成详情",
            tags=["冰种"],
            price_cents=4_800_000,
            match_params={
                "category": "手镯",
                "water": "冰种",
                "color": "未知",
                "shape": "未知",
                "size": "未知",
                "flaw": "未知",
                "purpose": "未知",
                "certificate": "未知",
                "visibleFeatures": "图片可见翡翠",
            },
        )

    monkeypatch.setattr(
        product_image_recognition_agent,
        "generate_product_copy_from_images",
        fake_generate_product_copy,
    )
    session = login("products-draft-quota@example.com")
    draft_create_response = client.post(
        "/api/merchant/products/drafts/images",
        files={"images": ("jade.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        headers=auth_headers(session["token"]),
    )
    draft_id = draft_create_response.json()["id"]
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
    generated = response.json()
    publish_response = client.patch(
        f"/api/merchant/products/{generated['id']}/publish",
        json={
            "title": generated["title"],
            "summary": generated["summary"],
            "detail": generated["detail"],
            "tags": generated["tags"],
            "priceCents": generated["priceCents"],
        },
        headers=auth_headers(session["token"]),
    )

    assert response.status_code == 200
    assert generated["status"] == "draft"
    assert generated["imageUrls"][0].startswith("/uploads/merchants/")
    assert publish_response.status_code == 400


def test_generate_product_draft_saves_match_params_and_search_text(monkeypatch) -> None:
    async def fake_generate_product_copy(image_urls: list[str]) -> ProductImageRecognitionResult:
        return ProductImageRecognitionResult(
            title="冰种手镯加字",
            summary="清透细腻适合日常佩戴的翡翠手镯",
            detail="图片可见整体色调清爽，适合发布前由商家补充圈口、证书和实物瑕疵。",
            tags=["冰种", "手镯"],
            price_cents=0,
            match_params={
                "category": "手镯",
                "water": "冰种",
                "color": "清爽",
                "shape": "圆条",
                "size": "未知",
                "flaw": "未知",
                "purpose": "日常佩戴",
                "certificate": "未知",
                "visibleFeatures": "清透",
            },
        )

    monkeypatch.setattr(
        product_image_recognition_agent,
        "generate_product_copy_from_images",
        fake_generate_product_copy,
    )
    session = login("products-generate-search@example.com")

    response = client.post(
        "/api/merchant/products/drafts/generate",
        files={"images": ("jade.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        headers=auth_headers(session["token"]),
    )
    product_id = response.json()["id"]

    engine = create_engine(settings.sync_database_url)
    with engine.begin() as connection:
        row = connection.execute(
            text("select title, match_params, search_text from merchant_products where id = :id"),
            {"id": product_id},
        ).one()
        embedding_count = connection.execute(
            text("select count(*) from merchant_product_embeddings where product_id = :id"),
            {"id": product_id},
        ).scalar_one()

    assert response.status_code == 200
    assert row.title == "冰种手镯加字"
    assert row.match_params["category"] == "手镯"
    assert "品类：手镯" in row.search_text
    assert embedding_count == 0


def test_product_image_recognition_agent_cleans_overlong_json(monkeypatch) -> None:
    calls: list[list[dict]] = []

    async def fake_chat_completion(messages: list[dict], **kwargs: object) -> str:
        calls.append(messages)
        assert kwargs["raise_on_error"] is True
        return (
            '{"title":"冰种满绿翡翠手镯超长标题",'
            '"summary":"这是一段超过五十个字的商品简介，用来验证Agent会把简介截断到规定长度以内，避免前端展示溢出。",'
            '"detail":"'
            + ("细腻通透，" * 80)
            + '",'
            '"tags":["冰种","满绿","翡翠手镯","正圈","55圈口","无纹裂","送礼","收藏","清透","细腻","多余"],'
            '"priceCents":123456,'
            '"matchParams":{"category":"手镯","visibleFeatures":"清透"}}'
        )

    monkeypatch.setattr(
        "app.services.product_image_recognition_agent.jade_agent.chat_completion",
        fake_chat_completion,
    )

    result = client.post(
        "/api/merchant/products/drafts/generate",
        files={"images": ("jade.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        headers=auth_headers(login("products-agent-clean@example.com")["token"]),
    )
    data = result.json()

    assert result.status_code == 200
    assert len(data["title"]) <= 10
    assert len(data["summary"]) <= 50
    assert len(data["detail"]) <= 300
    assert len(data["tags"]) == 10
    assert calls


def test_product_image_recognition_agent_retries_invalid_json(
    monkeypatch,
) -> None:
    async def fake_chat_completion(messages: list[dict], **kwargs: object) -> str:
        return "不是JSON"

    monkeypatch.setattr(
        "app.services.product_image_recognition_agent.jade_agent.chat_completion",
        fake_chat_completion,
    )
    session = login("products-agent-invalid-json@example.com")
    draft_response = client.post(
        "/api/merchant/products/drafts/images",
        files={"images": ("jade.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        headers=auth_headers(session["token"]),
    )
    draft_id = draft_response.json()["id"]

    response = client.post(
        "/api/merchant/products/drafts/generate",
        data={"productId": draft_id},
        headers=auth_headers(session["token"]),
    )
    detail_response = client.get(
        f"/api/merchant/products/{draft_id}",
        headers=auth_headers(session["token"]),
    )

    assert response.status_code == 502
    assert detail_response.status_code == 200
    assert detail_response.json()["title"] == ""
    assert detail_response.json()["imageUrls"][0].startswith("/uploads/merchants/")


def test_product_image_recognition_agent_returns_mimo_error(
    monkeypatch,
) -> None:
    async def fake_chat_completion(messages: list[dict], **kwargs: object) -> str:
        raise MimoCompletionError("MiMo调用失败：invalid api key")

    monkeypatch.setattr(
        "app.services.product_image_recognition_agent.jade_agent.chat_completion",
        fake_chat_completion,
    )
    session = login("products-agent-mimo-error@example.com")

    response = client.post(
        "/api/merchant/products/drafts/generate",
        files={"images": ("jade.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        headers=auth_headers(session["token"]),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "MiMo调用失败：invalid api key"


@pytest.mark.asyncio
async def test_mimo_completion_disables_thinking_and_reads_content(monkeypatch) -> None:
    captured_payload: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": '{"ok":true}'}}]}

    class FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            return None

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, *args: object, **kwargs: object) -> FakeResponse:
            captured_payload.update(kwargs["json"])
            return FakeResponse()

    monkeypatch.setattr("app.services.jade_agent.httpx.AsyncClient", FakeAsyncClient)

    reply = await jade_agent.chat_completion([{"role": "user", "content": "hello"}])

    assert reply == '{"ok":true}'
    assert captured_payload["thinking"] == {"type": "disabled"}


@pytest.mark.asyncio
async def test_mimo_completion_reads_reasoning_content_fallback(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": "", "reasoning_content": '{"ok":true}'}}]}

    class FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            return None

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, *args: object, **kwargs: object) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("app.services.jade_agent.httpx.AsyncClient", FakeAsyncClient)

    reply = await jade_agent.chat_completion([{"role": "user", "content": "hello"}])

    assert reply == '{"ok":true}'


def test_publish_fails_when_embedding_generation_fails(monkeypatch) -> None:
    async def fail_embed_document(text: str) -> EmbeddingResult:
        raise ProductEmbeddingError("商品向量生成失败，请稍后重试")

    monkeypatch.setattr(embedding_client, "embed_document", fail_embed_document)
    session = login("products-embedding-fail@example.com")

    draft_response = client.post(
        "/api/merchant/products/drafts/images",
        files={"images": ("jade.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        headers=auth_headers(session["token"]),
    )
    draft = draft_response.json()
    response = client.patch(
        f"/api/merchant/products/{draft['id']}/publish",
        json={
            "title": "发布失败货",
            "summary": "发布简介",
            "detail": "发布后的商品详情",
            "tags": ["冰种"],
            "priceCents": 4_800_000,
        },
        headers=auth_headers(session["token"]),
    )

    detail_response = client.get(
        f"/api/merchant/products/{draft['id']}",
        headers=auth_headers(session["token"]),
    )

    assert response.status_code == 502
    assert detail_response.json()["status"] == "draft"


def test_public_product_detail_only_returns_listed_product() -> None:
    session = login("public-detail@example.com")
    draft_response = client.get(
        "/api/merchant/products?status=draft",
        headers=auth_headers(session["token"]),
    )
    listed_response = client.get(
        "/api/merchant/products?status=listed",
        headers=auth_headers(session["token"]),
    )
    draft_id = draft_response.json()["products"][0]["id"]
    listed_product = listed_response.json()["products"][0]

    listed_detail = client.get(f"/api/products/{listed_product['id']}")
    draft_detail = client.get(f"/api/products/{draft_id}")

    assert listed_detail.status_code == 200
    assert listed_detail.json()["id"] == listed_product["id"]
    assert listed_detail.json()["merchantTier"] == "free"
    assert listed_detail.json()["imageUrls"]
    assert draft_detail.status_code == 404


def test_public_product_contact_creates_lead_and_prevents_duplicate() -> None:
    session = login("public-contact@example.com")
    listed_response = client.get(
        "/api/merchant/products?status=listed",
        headers=auth_headers(session["token"]),
    )
    product = listed_response.json()["products"][0]

    contact_response = client.post(
        f"/api/products/{product['id']}/contact",
        json={"buyerEmail": "buyer@example.com"},
    )
    duplicate_response = client.post(
        f"/api/products/{product['id']}/contact",
        json={"buyerEmail": "buyer@example.com"},
    )
    leads_response = client.get(
        "/api/merchant/leads?status=pending",
        headers=auth_headers(session["token"]),
    )

    assert contact_response.status_code == 200
    assert contact_response.json()["ok"] is True
    assert duplicate_response.status_code == 200
    assert duplicate_response.json()["ok"] is False

    created_leads = [
        lead for lead in leads_response.json()["leads"] if lead["productTitle"] == product["title"]
    ]
    assert len(created_leads) == 1
    assert created_leads[0]["productId"] == product["id"]
    assert created_leads[0]["buyerEmail"] == "****@***.com"

    engine = create_engine(settings.sync_database_url)
    with engine.begin() as connection:
        lead_count = connection.execute(
            text(
                "select count(*) from merchant_leads "
                "where product_id = :product_id and buyer_email = :email"
            ),
            {"product_id": product["id"], "email": "buyer@example.com"},
        ).scalar_one()
        notification_count = connection.execute(
            text(
                "select count(*) from merchant_notifications "
                "where merchant_id = :merchant_id and type = 'new_lead'"
            ),
            {"merchant_id": session["merchant"]["id"]},
        ).scalar_one()
    assert lead_count == 1
    assert notification_count >= 1
