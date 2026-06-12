import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.auth import AuthCode, MerchantSession
from app.models.merchant import Merchant, MerchantTier
from app.schemas.auth import (
    AuthCodeCreate,
    AuthCodeOut,
    AuthLoginCreate,
    AuthLoginOut,
    MerchantMeOut,
    MerchantOut,
)

router = APIRouter(prefix="/auth")
bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]
AuthCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]

DEV_CODE = "123456"
CODE_EXPIRES_SECONDS = 300
SESSION_EXPIRES_DAYS = 30


def _merchant_out(merchant: Merchant) -> MerchantOut:
    return MerchantOut(id=merchant.id, email=merchant.email, tier=merchant.tier.value)


@router.post("/send-code", response_model=AuthCodeOut, response_model_by_alias=True)
async def send_code(payload: AuthCodeCreate, db: DbSession) -> AuthCodeOut:
    now = datetime.now(UTC)
    auth_code = AuthCode(
        email=payload.email,
        # 开发阶段固定验证码，后续接邮件服务时只替换这里的发送逻辑。
        code=DEV_CODE,
        expires_at=now + timedelta(seconds=CODE_EXPIRES_SECONDS),
    )
    db.add(auth_code)
    await db.commit()

    return AuthCodeOut(ok=True, expires_in=CODE_EXPIRES_SECONDS, dev_code=DEV_CODE)


@router.post("/login", response_model=AuthLoginOut)
async def login(payload: AuthLoginCreate, db: DbSession) -> AuthLoginOut:
    now = datetime.now(UTC)
    code_result = await db.execute(
        select(AuthCode)
        .where(
            AuthCode.email == payload.email,
            AuthCode.code == payload.code,
            AuthCode.used_at.is_(None),
            AuthCode.expires_at > now,
        )
        .order_by(AuthCode.created_at.desc())
        .limit(1)
    )
    auth_code = code_result.scalar_one_or_none()
    if auth_code is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

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

    auth_code.used_at = now
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
        tier=merchant.tier.value,
        session_expires_at=merchant_session.expires_at,
    )
