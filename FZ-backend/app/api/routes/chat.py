import asyncio
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.chat import ChatMessage, ChatSession, VisitorNeedProfile
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageOut,
    ChatMessagePairOut,
    ChatSessionCreate,
    ChatSessionOut,
)
from app.services.jade_agent import jade_agent
from app.services.visitor_product_matcher import match_products_for_session

router = APIRouter(prefix="/chat")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _text_chunks(content: str, size: int = 8) -> list[str]:
    return [content[index : index + size] for index in range(0, len(content), size)]


def _need_profile_out(profile: VisitorNeedProfile | None) -> dict | None:
    if profile is None:
        return None
    return {
        "id": profile.id,
        "source_type": profile.source_type,
        "original_question": profile.original_question,
        "normalized_question": profile.normalized_question,
        "title": profile.title,
        "summary": profile.summary,
        "detail": profile.detail,
        "tags": profile.tags,
        "params": profile.params,
    }


def _message_out(
    message: ChatMessage,
    need_profile: VisitorNeedProfile | None = None,
) -> ChatMessageOut:
    profile = need_profile if need_profile is not None else message.need_profile
    return ChatMessageOut.model_validate(
        {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "need_profile": _need_profile_out(profile),
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


async def _recent_chat_history(session_id: UUID, db: AsyncSession) -> list[dict[str, str]]:
    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
    )
    previous_messages = list(reversed(history_result.scalars().all()))
    return [
        {"role": message.role, "content": message.content}
        for message in previous_messages
        if message.role in {"user", "assistant"}
    ]


async def _save_message_pair(
    *,
    session_id: UUID,
    user_content: str,
    assistant_content: str,
    matched_products: list[dict] | None,
    need_profile: VisitorNeedProfile | None = None,
    db: AsyncSession,
) -> ChatMessagePairOut:
    user_message = ChatMessage(session_id=session_id, role="user", content=user_content)
    assistant_message = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=assistant_content,
        matched_products=matched_products,
        need_profile_id=need_profile.id if need_profile else None,
    )
    db.add_all([user_message, assistant_message])
    await db.commit()
    await db.refresh(user_message)
    await db.refresh(assistant_message)

    return ChatMessagePairOut(
        user_message=_message_out(user_message),
        assistant_message=_message_out(assistant_message, need_profile=need_profile),
    )


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
        .options(selectinload(ChatMessage.need_profile))
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
    history = await _recent_chat_history(session_id, db)
    history.append({"role": "user", "content": payload.content})
    agent_result = await jade_agent.reply(payload.content, history)

    return await _save_message_pair(
        session_id=session_id,
        user_content=payload.content,
        assistant_content=agent_result.content,
        matched_products=None,
        need_profile=None,
        db=db,
    )


@router.post(
    "/sessions/{session_id}/matches",
    response_model=ChatMessagePairOut,
    response_model_by_alias=True,
)
async def create_match_message(
    session_id: UUID,
    payload: ChatMessageCreate,
    db: DbSession,
) -> ChatMessagePairOut:
    await _get_session_or_404(session_id, db)
    match_result = await match_products_for_session(
        session_id=session_id,
        content=payload.content,
        db=db,
    )

    return await _save_message_pair(
        session_id=session_id,
        user_content=payload.content,
        assistant_content=match_result.content,
        matched_products=[
            product.model_dump(by_alias=True) for product in match_result.products
        ],
        need_profile=match_result.need_profile,
        db=db,
    )


@router.post("/sessions/{session_id}/matches/stream")
async def create_match_message_stream(
    session_id: UUID,
    payload: ChatMessageCreate,
    db: DbSession,
) -> StreamingResponse:
    await _get_session_or_404(session_id, db)

    async def event_stream():
        try:
            match_result = await match_products_for_session(
                session_id=session_id,
                content=payload.content,
                db=db,
            )
            pair = await _save_message_pair(
                session_id=session_id,
                user_content=payload.content,
                assistant_content=match_result.content,
                matched_products=[
                    product.model_dump(by_alias=True) for product in match_result.products
                ],
                need_profile=match_result.need_profile,
                db=db,
            )
            for chunk in _text_chunks(pair.assistant_message.content):
                yield _sse("message_delta", {"content": chunk})
                await asyncio.sleep(0.035)
            yield _sse("match_result", pair.model_dump(by_alias=True, mode="json"))
            yield _sse("done", {"ok": True})
        except Exception as error:
            yield _sse("error", {"message": str(error) or "匹配失败，请稍后再试"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
