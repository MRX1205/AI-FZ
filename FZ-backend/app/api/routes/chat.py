from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.chat import ChatMessage, ChatSession
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageOut,
    ChatMessagePairOut,
    ChatSessionCreate,
    ChatSessionOut,
)
from app.services.jade_agent import jade_agent

router = APIRouter(prefix="/chat")


def _message_out(message: ChatMessage) -> ChatMessageOut:
    return ChatMessageOut.model_validate(
        {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "matched_products": message.matched_products,
            "created_at": message.created_at,
        }
    )


async def _get_session_or_404(session_id: UUID, db: AsyncSession) -> ChatSession:
    session = await db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    return session


DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post("/sessions", response_model=ChatSessionOut, response_model_by_alias=True)
async def create_session(payload: ChatSessionCreate, db: DbSession) -> ChatSessionOut:
    session = ChatSession(visitor_id=payload.visitor_id, merchant_id=payload.merchant_id)
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return ChatSessionOut(session_id=session.id, messages=[])


@router.get(
    "/sessions/{session_id}/messages",
    response_model=ChatSessionOut,
    response_model_by_alias=True,
)
async def get_messages(session_id: UUID, db: DbSession) -> ChatSessionOut:
    await _get_session_or_404(session_id, db)
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = [_message_out(message) for message in result.scalars()]

    return ChatSessionOut(session_id=session_id, messages=messages)


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatMessagePairOut,
    response_model_by_alias=True,
)
async def create_message(
    session_id: UUID,
    payload: ChatMessageCreate,
    db: DbSession,
) -> ChatMessagePairOut:
    await _get_session_or_404(session_id, db)
    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
    )
    previous_messages = list(reversed(history_result.scalars().all()))
    history = [
        {"role": message.role, "content": message.content}
        for message in previous_messages
        if message.role in {"user", "assistant"}
    ]
    history.append({"role": "user", "content": payload.content})
    agent_result = await jade_agent.reply(payload.content, history)

    user_message = ChatMessage(session_id=session_id, role="user", content=payload.content)
    assistant_message = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=agent_result.content,
        matched_products=None,
    )
    db.add_all([user_message, assistant_message])
    await db.commit()
    await db.refresh(user_message)
    await db.refresh(assistant_message)

    return ChatMessagePairOut(
        user_message=_message_out(user_message),
        assistant_message=_message_out(assistant_message),
    )
