from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.main import app
from app.services.embeddings import EmbeddingResult, ProductEmbeddingError, embedding_client
from app.services.jade_agent import JadeAgentResult, jade_agent
from app.services.visitor_product_matcher import looks_like_product_need, parse_visitor_need

client = TestClient(app)


def setup_function() -> None:
    engine = create_engine(settings.sync_database_url)
    with engine.begin() as connection:
        connection.execute(text("delete from chat_messages"))
        connection.execute(text("delete from chat_sessions"))
        connection.execute(text("delete from merchant_product_embeddings"))
        connection.execute(text("delete from merchant_notifications"))
        connection.execute(text("delete from merchant_leads"))
        connection.execute(text("delete from merchant_product_images"))
        connection.execute(text("delete from merchant_products"))
        connection.execute(text("delete from merchant_sessions"))
        connection.execute(text("delete from auth_codes"))
        connection.execute(text("delete from merchants"))


def seed_product(
    *,
    email: str,
    title: str,
    tags: list[str],
    price_cents: int,
    match_params: dict[str, str],
    embedding: list[float] | None = None,
    tier: str = "free",
) -> str:
    engine = create_engine(settings.sync_database_url)
    with engine.begin() as connection:
        merchant_id = connection.execute(
            text(
                "insert into merchants (email, tier, vip_started_at, vip_expires_at) "
                "values (:email, :tier, null, null) returning id"
            ),
            {"email": email, "tier": tier},
        ).scalar_one()
        product_id = connection.execute(
            text(
                "insert into merchant_products "
                "(merchant_id, title, summary, detail, tags, price_cents, status, image_urls, "
                "match_params, search_text, published_at) "
                "values (:merchant_id, :title, :summary, :detail, CAST(:tags AS jsonb), "
                ":price_cents, 'listed', CAST(:image_urls AS jsonb), "
                "CAST(:match_params AS jsonb), :search_text, :published_at) returning id"
            ),
            {
                "merchant_id": merchant_id,
                "title": title,
                "summary": "高翠网测试商品",
                "detail": "适合用于游客需求匹配的测试商品",
                "tags": _json(tags),
                "price_cents": price_cents,
                "image_urls": _json(["/mock-products/jade-1.png"]),
                "match_params": _json(match_params),
                "search_text": (
                    f"商品标题：{title}\n商品标签：{'、'.join(tags)}\n"
                    f"品类：{match_params.get('category', '未知')}\n"
                    f"颜色：{match_params.get('color', '未知')}\n"
                    f"种水：{match_params.get('water', '未知')}"
                ),
                "published_at": datetime.now(UTC),
            },
        ).scalar_one()
        if embedding is not None:
            connection.execute(
                text(
                    "insert into merchant_product_embeddings "
                    "(merchant_id, product_id, model, dimensions, content_hash, embedding) "
                    "values (:merchant_id, :product_id, 'text-embedding-v4', 1024, "
                    ":content_hash, :embedding)"
                ),
                {
                    "merchant_id": merchant_id,
                    "product_id": product_id,
                    "content_hash": "a" * 64,
                    "embedding": _vector(embedding),
                },
            )
    return str(product_id)


def _json(value: object) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)


def _vector(value: list[float]) -> str:
    return "[" + ",".join(str(item) for item in value) + "]"


async def fake_embed_document(text: str, timeout_seconds: float = 30) -> EmbeddingResult:
    assert "需求：" in text or "商品标题：" in text
    return EmbeddingResult(
        provider="dashscope",
        model="text-embedding-v4",
        dimensions=1024,
        embedding=[0.2] * 1024,
    )


def create_session() -> str:
    response = client.post(
        "/api/chat/sessions",
        json={"visitorId": "pytest-visitor", "merchantId": None},
    )
    assert response.status_code == 200
    return response.json()["sessionId"]


def test_parse_visitor_need_extracts_budget_category_and_color() -> None:
    need = parse_visitor_need("10万预算 帝王绿手镯")

    assert need.budget_cents == 10_000_000
    assert need.category == "手镯"
    assert "帝王绿" in need.colors
    assert "预算：100000元" in need.search_text
    assert looks_like_product_need("10万预算 帝王绿手镯")
    assert not looks_like_product_need("你好，今天可以介绍一下平台吗")


def test_chat_messages_keep_mimo_text_reply(monkeypatch) -> None:
    async def mock_reply(content: str, history: list[dict[str, str]]) -> JadeAgentResult:
        assert content == "你好，介绍一下高翠网"
        assert history[-1]["content"] == content
        return JadeAgentResult(content="收到：你好，介绍一下高翠网")

    monkeypatch.setattr(jade_agent, "reply", mock_reply)
    session_id = create_session()

    response = client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"content": "你好，介绍一下高翠网"},
    )

    assert response.status_code == 200
    assistant_message = response.json()["assistantMessage"]
    assert assistant_message["content"] == "收到：你好，介绍一下高翠网"
    assert assistant_message["matchedProducts"] is None


def test_chat_matches_endpoint_matches_listed_products_with_embedding(monkeypatch) -> None:
    monkeypatch.setattr(embedding_client, "embed_document", fake_embed_document)
    hand_product_id = seed_product(
        email="hand@example.com",
        title="帝王绿手镯",
        tags=["帝王绿", "手镯"],
        price_cents=9_800_000,
        match_params={"category": "手镯", "color": "帝王绿", "water": "冰种"},
        embedding=[0.2] * 1024,
        tier="vip",
    )
    seed_product(
        email="pendant@example.com",
        title="冰种吊坠",
        tags=["冰种", "吊坠"],
        price_cents=1_800_000,
        match_params={"category": "吊坠", "color": "晴底", "water": "冰种"},
        embedding=[0.2] * 1024,
    )
    session_id = create_session()

    message_response = client.post(
        f"/api/chat/sessions/{session_id}/matches",
        json={"content": "10万预算 帝王绿手镯"},
    )

    assert message_response.status_code == 200
    data = message_response.json()
    products = data["assistantMessage"]["matchedProducts"]
    assert data["userMessage"]["role"] == "user"
    assert data["assistantMessage"]["role"] == "assistant"
    assert data["assistantMessage"]["content"] == "已根据预算、品类和商品特征为您匹配相近货源。"
    assert len(products) == 1
    assert products[0]["id"] == hand_product_id
    assert products[0]["merchantTier"] == "vip"

    history_response = client.get(f"/api/chat/sessions/{session_id}/messages")
    assert history_response.status_code == 200
    assert len(history_response.json()["messages"]) == 2
    assert history_response.json()["messages"][1]["matchedProducts"][0]["id"] == hand_product_id


def test_chat_matches_endpoint_falls_back_to_rule_search_when_embedding_fails(monkeypatch) -> None:
    async def fail_embed_document(text: str, timeout_seconds: float = 30) -> EmbeddingResult:
        raise ProductEmbeddingError("timeout")

    monkeypatch.setattr(embedding_client, "embed_document", fail_embed_document)
    product_id = seed_product(
        email="fallback@example.com",
        title="冰种平安扣",
        tags=["冰种", "平安扣", "无纹无裂"],
        price_cents=19_000_00,
        match_params={"category": "平安扣", "color": "晴底", "water": "冰种", "flaw": "无纹无裂"},
    )
    session_id = create_session()

    response = client.post(
        f"/api/chat/sessions/{session_id}/matches",
        json={"content": "冰种平安扣 预算2万 无纹无裂"},
    )

    assert response.status_code == 200
    assistant_message = response.json()["assistantMessage"]
    assert assistant_message["content"] == "暂未找到完全匹配货源，先为您推荐相近商品。"
    assert assistant_message["matchedProducts"][0]["id"] == product_id


def test_chat_matches_endpoint_returns_empty_matches_when_no_listed_products(monkeypatch) -> None:
    monkeypatch.setattr(embedding_client, "embed_document", fake_embed_document)
    session_id = create_session()

    response = client.post(
        f"/api/chat/sessions/{session_id}/matches",
        json={"content": "10万预算 帝王绿手镯"},
    )

    assert response.status_code == 200
    assistant_message = response.json()["assistantMessage"]
    assert assistant_message["content"] == "暂未找到合适货源，建议补充预算、品类或尺寸。"
    assert assistant_message["matchedProducts"] == []
