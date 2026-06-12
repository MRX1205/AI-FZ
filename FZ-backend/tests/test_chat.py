from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.main import app
from app.services.jade_agent import JadeAgentResult, jade_agent

client = TestClient(app)


def setup_function() -> None:
    engine = create_engine(settings.sync_database_url)
    with engine.begin() as connection:
        connection.execute(text("delete from chat_messages"))
        connection.execute(text("delete from chat_sessions"))


async def mock_reply(content: str, history: list[dict[str, str]]) -> JadeAgentResult:
    return JadeAgentResult(content=f"收到：{content}")


def test_chat_jade_need_returns_three_products() -> None:
    jade_agent.reply = mock_reply
    session_response = client.post(
        "/api/chat/sessions",
        json={"visitorId": "pytest-visitor", "merchantId": None},
    )
    assert session_response.status_code == 200
    session_id = session_response.json()["sessionId"]

    message_response = client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"content": "10万预算 帝王绿手镯"},
    )
    assert message_response.status_code == 200
    data = message_response.json()

    assert data["userMessage"]["role"] == "user"
    assert data["assistantMessage"]["role"] == "assistant"
    assert data["assistantMessage"]["content"]
    assert data["assistantMessage"]["matchedProducts"] is None

    history_response = client.get(f"/api/chat/sessions/{session_id}/messages")
    assert history_response.status_code == 200
    assert len(history_response.json()["messages"]) == 2


def test_chat_non_jade_need_returns_text_reply() -> None:
    jade_agent.reply = mock_reply
    session_id = client.post(
        "/api/chat/sessions",
        json={"visitorId": "pytest-visitor-2", "merchantId": None},
    ).json()["sessionId"]

    message_response = client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"content": "今天上海天气怎么样"},
    )
    assert message_response.status_code == 200
    assistant_message = message_response.json()["assistantMessage"]

    assert assistant_message["matchedProducts"] is None
    assert assistant_message["content"]
