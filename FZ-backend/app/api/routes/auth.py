import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.auth import MerchantSession
from app.models.merchant import Merchant, MerchantTier
from app.schemas.auth import (
    AuthCodeCreate,
    AuthCodeOut,
    AuthLoginCreate,
    AuthLoginOut,
    MerchantMeOut,
    MerchantOut,
)
from app.services.merchant_membership import effective_merchant_tier_value
from app.services.supabase_otp import (
    SupabaseOtpError,
    SupabaseOtpInvalidError,
    SupabaseOtpNotConfiguredError,
    supabase_otp_client,
)

router = APIRouter(prefix="/auth")
bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]
AuthCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]

SESSION_EXPIRES_DAYS = 30


def _merchant_out(merchant: Merchant) -> MerchantOut:
    return MerchantOut(
        id=merchant.id,
        email=merchant.email,
        tier=effective_merchant_tier_value(merchant),
    )


@router.post(
    "/send-code",
    response_model=AuthCodeOut,
    response_model_by_alias=True,
    response_model_exclude_none=True,
)
async def send_code(payload: AuthCodeCreate) -> AuthCodeOut:
    try:
        await supabase_otp_client.send_email_code(payload.email)
    except SupabaseOtpNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except SupabaseOtpError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error

    return AuthCodeOut(ok=True, expires_in=settings.supabase_otp_expires_seconds)


@router.post("/login", response_model=AuthLoginOut)
async def login(payload: AuthLoginCreate, db: DbSession) -> AuthLoginOut:
    try:
        await supabase_otp_client.verify_email_code(payload.email, payload.code)
    except SupabaseOtpInvalidError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码错误或已过期",
        ) from error
    except SupabaseOtpNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except SupabaseOtpError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error

    now = datetime.now(UTC)
    merchant_result = await db.execute(select(Merchant).where(Merchant.email == payload.email))
    merchant = merchant_result.scalar_one_or_none()
    if merchant is None:
        merchant = Merchant(
            email=payload.email,
            tier=MerchantTier.free,
            vip_started_at=None,
            vip_expires_at=None,
        )
        db.add(merchant)
        await db.flush()

    session = MerchantSession(
        merchant_id=merchant.id,
        token=str(uuid.uuid4()),
        expires_at=now + timedelta(days=SESSION_EXPIRES_DAYS),
    )
    db.add(session)
    await db.commit()
    await db.refresh(merchant)

    return AuthLoginOut(token=session.token, merchant=_merchant_out(merchant))


@router.get("/me", response_model=MerchantMeOut, response_model_by_alias=True)
async def me(credentials: AuthCredentials, db: DbSession) -> MerchantMeOut:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    now = datetime.now(UTC)
    result = await db.execute(
        select(MerchantSession, Merchant)
        .join(Merchant, Merchant.id == MerchantSession.merchant_id)
        .where(
            MerchantSession.token == credentials.credentials,
            MerchantSession.expires_at > now,
        )
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    merchant_session, merchant = row
    return MerchantMeOut(
        id=merchant.id,
        email=merchant.email,
        tier=effective_merchant_tier_value(merchant),
        session_expires_at=merchant_session.expires_at,
    )


@router.post("/logout")
async def logout(credentials: AuthCredentials, db: DbSession) -> dict[str, bool]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    result = await db.execute(
        select(MerchantSession).where(MerchantSession.token == credentials.credentials)
    )
    merchant_session = result.scalar_one_or_none()
    if merchant_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    await db.delete(merchant_session)
    await db.commit()
    return {"ok": True}
