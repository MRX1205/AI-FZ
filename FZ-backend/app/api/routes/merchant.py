import shutil
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.auth import AuthCode, MerchantSession
from app.models.lead import MerchantLead, MerchantNotification
from app.models.merchant import Merchant, MerchantTier
from app.models.product import MerchantProduct
from app.schemas.auth import AuthCodeOut
from app.schemas.merchant import (
    DashboardLeadOut,
    DashboardMerchantOut,
    DashboardStatsOut,
    MerchantDashboardOut,
    MerchantEmailCodeCreate,
    MerchantEmailUpdate,
    MerchantLeadListOut,
    MerchantLeadOut,
    MerchantLeadStatusUpdate,
    MerchantNotificationListOut,
    MerchantNotificationOut,
    MerchantNotificationUpdate,
    MerchantProductCountsOut,
    MerchantProductListOut,
    MerchantProductOut,
    MerchantProductQuotaOut,
    MerchantProductStatusUpdate,
    MerchantProductUpdate,
    MerchantProfileOut,
    NotificationSettingsOut,
)

router = APIRouter(prefix="/merchant")
bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]
AuthCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]
DEV_CODE = "123456"
CODE_EXPIRES_SECONDS = 300
VIP_FALLBACK_START = datetime(2024, 5, 20, tzinfo=UTC)
VIP_FALLBACK_EXPIRES = datetime(2025, 5, 20, tzinfo=UTC)
UPLOAD_ROOT = Path(__file__).resolve().parents[3] / "uploads" / "products"


async def _get_current_merchant(
    credentials: AuthCredentials,
    db: AsyncSession,
) -> Merchant:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    result = await db.execute(
        select(MerchantSession, Merchant)
        .join(Merchant, Merchant.id == MerchantSession.merchant_id)
        .where(
            MerchantSession.token == credentials.credentials,
            MerchantSession.expires_at > datetime.now(UTC),
        )
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    return row[1]


def _profile_out(merchant: Merchant) -> MerchantProfileOut:
    vip_started_at = merchant.vip_started_at
    vip_expires_at = merchant.vip_expires_at
    if merchant.tier == MerchantTier.vip:
        vip_started_at = vip_started_at or VIP_FALLBACK_START
        vip_expires_at = vip_expires_at or VIP_FALLBACK_EXPIRES

    return MerchantProfileOut(
        id=merchant.id,
        email=merchant.email,
        tier=merchant.tier.value,
        vip_started_at=vip_started_at,
        vip_expires_at=vip_expires_at,
        notifications=NotificationSettingsOut(
            web_notification_enabled=True,
            email_notification_enabled=merchant.email_notification_enabled,
        ),
    )


def _dashboard_merchant_out(merchant: Merchant) -> DashboardMerchantOut:
    return DashboardMerchantOut(
        id=merchant.id,
        email=merchant.email,
        tier=merchant.tier.value,
    )


def _visible_buyer_email(merchant: Merchant, buyer_email: str) -> str:
    if merchant.tier == MerchantTier.vip:
        return buyer_email
    return "****@***.com"


def _lead_out(lead: MerchantLead, merchant: Merchant) -> MerchantLeadOut:
    return MerchantLeadOut(
        id=lead.id,
        submitted_at=lead.submitted_at,
        buyer_email=_visible_buyer_email(merchant, lead.buyer_email),
        message=lead.message,
        product_title=lead.product_title,
        product_price_cents=lead.product_price_cents,
        product_image_url=lead.product_image_url,
        status=lead.status,
        merchant_email=merchant.email,
    )


def _product_limit(merchant: Merchant) -> int:
    return 100 if merchant.tier == MerchantTier.vip else 2


def _product_out(product: MerchantProduct) -> MerchantProductOut:
    return MerchantProductOut(
        id=product.id,
        title=product.title,
        summary=product.summary,
        detail=product.detail,
        tags=product.tags,
        price_cents=product.price_cents,
        status=product.status,
        image_urls=product.image_urls,
        published_at=product.published_at,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


async def _get_merchant_product(
    product_id: UUID,
    merchant: Merchant,
    db: AsyncSession,
) -> MerchantProduct:
    result = await db.execute(
        select(MerchantProduct).where(
            MerchantProduct.id == product_id,
            MerchantProduct.merchant_id == merchant.id,
        )
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


async def _product_counts(
    merchant: Merchant,
    db: AsyncSession,
) -> tuple[MerchantProductCountsOut, MerchantProductQuotaOut]:
    result = await db.execute(
        select(MerchantProduct.status, func.count())
        .where(MerchantProduct.merchant_id == merchant.id)
        .group_by(MerchantProduct.status)
    )
    counts_by_status = {row[0]: row[1] for row in result.all()}
    listed_count = counts_by_status.get("listed", 0)
    product_limit = _product_limit(merchant)
    return (
        MerchantProductCountsOut(
            all=sum(counts_by_status.values()),
            listed=listed_count,
            draft=counts_by_status.get("draft", 0),
            unlisted=counts_by_status.get("unlisted", 0),
        ),
        MerchantProductQuotaOut(
            listed_count=listed_count,
            product_limit=product_limit,
            remaining=max(product_limit - listed_count, 0),
        ),
    )


async def _seed_products_if_empty(merchant: Merchant, db: AsyncSession) -> None:
    existing_result = await db.execute(
        select(MerchantProduct.id).where(MerchantProduct.merchant_id == merchant.id).limit(1)
    )
    if existing_result.scalar_one_or_none() is not None:
        return

    seed_products = [
        MerchantProduct(
            merchant_id=merchant.id,
            title="冰种晴底翡翠手镯",
            summary="冰种晴底，质地细腻通透，清新淡雅。",
            detail="本款冰种晴底翡翠手镯，种水达到冰种级别，质地细腻，底色清新淡雅，圈口55mm，佩戴舒适贴合。",
            tags=["冰种", "晴底色", "翡翠手镯", "正圈", "55圈口"],
            price_cents=4_800_000,
            status="listed",
            image_urls=["/mock-products/jade-1.png"],
            published_at=datetime(2026, 5, 20, 10, 30, tzinfo=UTC),
        ),
        MerchantProduct(
            merchant_id=merchant.id,
            title="冰种飘花翡翠吊坠",
            summary="冰种飘花，清爽耐看。",
            detail="冰种飘花翡翠吊坠，底子干净，飘花灵动，适合日常佩戴。",
            tags=["冰种", "飘花", "翡翠吊坠"],
            price_cents=3_200_000,
            status="draft",
            image_urls=["/mock-products/jade-3.png"],
            published_at=None,
        ),
        MerchantProduct(
            merchant_id=merchant.id,
            title="糯冰种翡翠手镯",
            summary="温润细腻，性价比高。",
            detail="糯冰种翡翠手镯，质地温润，底色柔和，适合日常佩戴。",
            tags=["糯冰种", "翡翠手镯", "收藏优选"],
            price_cents=1_880_000,
            status="unlisted",
            image_urls=["/mock-products/jade-1.png"],
            published_at=datetime(2026, 5, 15, 14, 30, tzinfo=UTC),
        ),
    ]
    if merchant.tier == MerchantTier.vip:
        for index in range(2, 11):
            seed_products.append(
                MerchantProduct(
                    merchant_id=merchant.id,
                    title=f"VIP精选翡翠货源{index}",
                    summary="高品质翡翠货源，适合平台展示。",
                    detail="VIP商家精选翡翠货源，图片清晰，种水表现稳定，可用于发布流程和后台管理联调。",
                    tags=["翡翠", "精选", "VIP货源"],
                    price_cents=2_800_000 + index * 100_000,
                    status="listed",
                    image_urls=[f"/mock-products/jade-{((index - 1) % 3) + 1}.png"],
                    published_at=datetime(2026, 5, min(28, 10 + index), 10, 0, tzinfo=UTC),
                )
            )
    db.add_all(seed_products)
    await db.commit()


async def _apply_product_update(
    product: MerchantProduct,
    payload: MerchantProductUpdate,
) -> None:
    product.title = payload.title
    product.summary = payload.summary
    product.detail = payload.detail
    product.tags = payload.tags
    product.price_cents = payload.price_cents


def _save_product_image(file: UploadFile) -> str:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image file required")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"

    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{suffix}"
    target = UPLOAD_ROOT / filename
    with target.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return f"/uploads/products/{filename}"


def _generated_product_fields(image_count: int) -> dict[str, object]:
    title = "冰种晴底翡翠手镯" if image_count == 1 else "多图冰种翡翠精品"
    summary = "AI根据图片生成，质地细腻通透，清新淡雅。"
    detail = (
        "该商品由AI根据上传图片生成初稿。整体观感清爽，翡翠种水表现自然，"
        "适合日常佩戴或送礼收藏。请商家发布前根据实物补充圈口、尺寸、证书等信息。"
    )
    tags = ["冰种", "翡翠", "AI生成", "清爽", "送礼佳品"]
    price_cents = 48_000 * 100
    return {
        "title": title,
        "summary": summary,
        "detail": detail,
        "tags": tags,
        "price_cents": price_cents,
    }


def _quota_exceeded_detail(merchant: Merchant) -> str:
    if merchant.tier == MerchantTier.vip:
        return "请下架部分商品后再发布"
    return "需升级VIP提升发布额度"


async def _assert_product_quota_available(
    merchant: Merchant,
    db: AsyncSession,
) -> None:
    _, quota = await _product_counts(merchant, db)
    if quota.remaining <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_quota_exceeded_detail(merchant),
        )


async def _seed_leads_if_empty(merchant: Merchant, db: AsyncSession) -> None:
    existing_result = await db.execute(
        select(MerchantLead.id).where(MerchantLead.merchant_id == merchant.id).limit(1)
    )
    if existing_result.scalar_one_or_none() is not None:
        return

    # 商品模块尚未开发，客资先保存商品快照；后续接真实商品表时替换这里。
    seed_leads = [
        MerchantLead(
            merchant_id=merchant.id,
            submitted_at=datetime(2026, 5, 20, 10, 30, tzinfo=UTC),
            buyer_email="buyer1@email.com",
            message="预算5万左右，冰种手镯，55圈口，不要纹裂，颜色要清爽一点",
            product_title="冰种晴底圆条手镯",
            product_price_cents=4_800_000,
            product_image_url="/mock-products/jade-1.png",
            status="pending",
        ),
        MerchantLead(
            merchant_id=merchant.id,
            submitted_at=datetime(2026, 5, 19, 15, 20, tzinfo=UTC),
            buyer_email="buyer2@email.com",
            message="送礼用，冰种飘绿吊坠，要求证书齐全",
            product_title="冰种飘花翡翠吊坠",
            product_price_cents=2_680_000,
            product_image_url="/mock-products/jade-2.png",
            status="contacted",
        ),
        MerchantLead(
            merchant_id=merchant.id,
            submitted_at=datetime(2026, 5, 18, 9, 10, tzinfo=UTC),
            buyer_email="buyer3@email.com",
            message="冰种平安扣，预算2万，无纹裂，日常佩戴",
            product_title="冰种平安扣",
            product_price_cents=1_980_000,
            product_image_url="/mock-products/jade-3.png",
            status="pending",
        ),
        MerchantLead(
            merchant_id=merchant.id,
            submitted_at=datetime(2026, 5, 17, 16, 40, tzinfo=UTC),
            buyer_email="buyer4@email.com",
            message="想要帝王绿挂件，越绿越好",
            product_title="帝王绿翡翠挂件",
            product_price_cents=8_800_000,
            product_image_url="/mock-products/jade-1.png",
            status="pending",
        ),
    ]
    db.add_all(seed_leads)
    await db.commit()


async def _seed_notifications_if_empty(merchant: Merchant, db: AsyncSession) -> None:
    existing_result = await db.execute(
        select(MerchantNotification.id)
        .where(MerchantNotification.merchant_id == merchant.id)
        .limit(1)
    )
    if existing_result.scalar_one_or_none() is not None:
        return

    notifications = [
        MerchantNotification(
            merchant_id=merchant.id,
            type="new_lead",
            content="有新客户对「冰种晴底圆条手镯」留下联系方式，请及时处理。",
            sent_at=datetime(2026, 5, 20, 10, 31, tzinfo=UTC),
        ),
        MerchantNotification(
            merchant_id=merchant.id,
            type="new_lead",
            content="有新客户对「冰种飘花翡翠吊坠」留下联系方式，请及时处理。",
            sent_at=datetime(2026, 5, 19, 15, 22, tzinfo=UTC),
        ),
    ]
    if merchant.tier == MerchantTier.vip:
        notifications.append(
            MerchantNotification(
                merchant_id=merchant.id,
                type="vip_expiring",
                content="您的VIP会员将在30天后到期，请联系运营续费。",
                sent_at=datetime(2026, 5, 18, 9, 0, tzinfo=UTC),
            )
        )

    db.add_all(notifications)
    await db.commit()


@router.get("/dashboard", response_model=MerchantDashboardOut, response_model_by_alias=True)
async def dashboard(credentials: AuthCredentials, db: DbSession) -> MerchantDashboardOut:
    merchant = await _get_current_merchant(credentials, db)
    is_vip = merchant.tier == MerchantTier.vip
    product_limit = 100 if is_vip else 2

    # 商品和客资模块的后台首页统计先保持原型额度展示。
    return MerchantDashboardOut(
        merchant=_dashboard_merchant_out(merchant),
        stats=DashboardStatsOut(
            listed_products=product_limit,
            product_limit=product_limit,
            today_leads=8,
            total_leads=128,
        ),
        recent_leads=[
            DashboardLeadOut(
                id="lead-1",
                submitted_at=datetime(2026, 5, 20, 10, 30, tzinfo=UTC),
                buyer_email="buyer1@email.com",
                message="预算5万左右，冰种手镯，55圈口，想看无纹无裂的货源",
                product_title="冰种晴底圆条手镯",
            ),
            DashboardLeadOut(
                id="lead-2",
                submitted_at=datetime(2026, 5, 19, 15, 20, tzinfo=UTC),
                buyer_email="buyer2@email.com",
                message="送礼用，冰种飘绿吊坠，要求证书齐全",
                product_title="冰种飘绿翡翠吊坠",
            ),
            DashboardLeadOut(
                id="lead-3",
                submitted_at=datetime(2026, 5, 18, 9, 10, tzinfo=UTC),
                buyer_email="buyer3@email.com",
                message="冰种平安扣，预算2万，无纹裂，日常佩戴",
                product_title="冰种平安扣",
            ),
        ],
    )


@router.get("/profile", response_model=MerchantProfileOut, response_model_by_alias=True)
async def profile(credentials: AuthCredentials, db: DbSession) -> MerchantProfileOut:
    merchant = await _get_current_merchant(credentials, db)
    return _profile_out(merchant)


@router.post("/profile/email-code", response_model=AuthCodeOut, response_model_by_alias=True)
async def send_profile_email_code(
    payload: MerchantEmailCodeCreate,
    credentials: AuthCredentials,
    db: DbSession,
) -> AuthCodeOut:
    await _get_current_merchant(credentials, db)
    auth_code = AuthCode(
        email=payload.email,
        # 开发阶段固定验证码，后续接真实邮件服务时替换发送逻辑。
        code=DEV_CODE,
        expires_at=datetime.now(UTC) + timedelta(seconds=CODE_EXPIRES_SECONDS),
    )
    db.add(auth_code)
    await db.commit()

    return AuthCodeOut(ok=True, expires_in=CODE_EXPIRES_SECONDS, dev_code=DEV_CODE)


@router.patch("/profile/email", response_model=MerchantProfileOut, response_model_by_alias=True)
async def update_profile_email(
    payload: MerchantEmailUpdate,
    credentials: AuthCredentials,
    db: DbSession,
) -> MerchantProfileOut:
    merchant = await _get_current_merchant(credentials, db)
    existing_result = await db.execute(
        select(Merchant).where(Merchant.email == payload.email, Merchant.id != merchant.id)
    )
    if existing_result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")

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

    auth_code.used_at = now
    merchant.email = payload.email
    await db.commit()
    await db.refresh(merchant)

    return _profile_out(merchant)


@router.patch(
    "/profile/notifications",
    response_model=NotificationSettingsOut,
    response_model_by_alias=True,
)
async def update_profile_notifications(
    payload: MerchantNotificationUpdate,
    credentials: AuthCredentials,
    db: DbSession,
) -> NotificationSettingsOut:
    merchant = await _get_current_merchant(credentials, db)
    merchant.web_notification_enabled = True
    merchant.email_notification_enabled = payload.email_notification_enabled
    await db.commit()
    await db.refresh(merchant)

    return NotificationSettingsOut(
        web_notification_enabled=True,
        email_notification_enabled=merchant.email_notification_enabled,
    )


@router.get("/products", response_model=MerchantProductListOut, response_model_by_alias=True)
async def products(
    credentials: AuthCredentials,
    db: DbSession,
    product_status: Annotated[
        str,
        Query(alias="status", pattern="^(all|listed|draft|unlisted)$"),
    ] = "all",
) -> MerchantProductListOut:
    merchant = await _get_current_merchant(credentials, db)
    await _seed_products_if_empty(merchant, db)

    statement = select(MerchantProduct).where(MerchantProduct.merchant_id == merchant.id)
    if product_status != "all":
        statement = statement.where(MerchantProduct.status == product_status)
    statement = statement.order_by(MerchantProduct.created_at.desc())
    result = await db.execute(statement)
    counts, quota = await _product_counts(merchant, db)

    return MerchantProductListOut(
        merchant=_dashboard_merchant_out(merchant),
        products=[_product_out(product) for product in result.scalars().all()],
        counts=counts,
        quota=quota,
    )


@router.post(
    "/products/drafts/generate",
    response_model=MerchantProductOut,
    response_model_by_alias=True,
)
async def generate_product_draft(
    credentials: AuthCredentials,
    db: DbSession,
    images: Annotated[list[UploadFile] | None, File()] = None,
) -> MerchantProductOut:
    merchant = await _get_current_merchant(credentials, db)
    await _seed_products_if_empty(merchant, db)

    if not images:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先上传商品图片")
    if len(images) > 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="最多上传6张图片")

    await _assert_product_quota_available(merchant, db)

    # 首版 AI 识别使用规则生成稳定字段，后续接多模态模型时只替换生成函数。
    image_urls = [_save_product_image(image) for image in images]
    generated_fields = _generated_product_fields(len(image_urls))
    product = MerchantProduct(
        merchant_id=merchant.id,
        title=str(generated_fields["title"]),
        summary=str(generated_fields["summary"]),
        detail=str(generated_fields["detail"]),
        tags=generated_fields["tags"],
        price_cents=int(generated_fields["price_cents"]),
        status="draft",
        image_urls=image_urls,
        published_at=None,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)

    return _product_out(product)


@router.get(
    "/products/{product_id}",
    response_model=MerchantProductOut,
    response_model_by_alias=True,
)
async def product_detail(
    product_id: UUID,
    credentials: AuthCredentials,
    db: DbSession,
) -> MerchantProductOut:
    merchant = await _get_current_merchant(credentials, db)
    await _seed_products_if_empty(merchant, db)
    product = await _get_merchant_product(product_id, merchant, db)

    return _product_out(product)


@router.patch(
    "/products/{product_id}/publish",
    response_model=MerchantProductOut,
    response_model_by_alias=True,
)
async def publish_product(
    product_id: UUID,
    payload: MerchantProductUpdate,
    credentials: AuthCredentials,
    db: DbSession,
) -> MerchantProductOut:
    merchant = await _get_current_merchant(credentials, db)
    product = await _get_merchant_product(product_id, merchant, db)
    await _apply_product_update(product, payload)

    if product.status != "listed":
        await _assert_product_quota_available(merchant, db)
    product.status = "listed"
    product.published_at = product.published_at or datetime.now(UTC)

    await db.commit()
    await db.refresh(product)

    return _product_out(product)


@router.patch(
    "/products/{product_id}",
    response_model=MerchantProductOut,
    response_model_by_alias=True,
)
async def update_product(
    product_id: UUID,
    payload: MerchantProductUpdate,
    credentials: AuthCredentials,
    db: DbSession,
) -> MerchantProductOut:
    merchant = await _get_current_merchant(credentials, db)
    product = await _get_merchant_product(product_id, merchant, db)
    await _apply_product_update(product, payload)
    await db.commit()
    await db.refresh(product)

    return _product_out(product)


@router.patch(
    "/products/{product_id}/status",
    response_model=MerchantProductOut,
    response_model_by_alias=True,
)
async def update_product_status(
    product_id: UUID,
    payload: MerchantProductStatusUpdate,
    credentials: AuthCredentials,
    db: DbSession,
) -> MerchantProductOut:
    merchant = await _get_current_merchant(credentials, db)
    product = await _get_merchant_product(product_id, merchant, db)

    if payload.status == "listed" and product.status != "listed":
        await _assert_product_quota_available(merchant, db)
        product.published_at = datetime.now(UTC)

    product.status = payload.status
    if payload.status != "listed" and product.published_at is None:
        product.published_at = None

    await db.commit()
    await db.refresh(product)

    return _product_out(product)


@router.delete("/products/{product_id}")
async def delete_product(
    product_id: UUID,
    credentials: AuthCredentials,
    db: DbSession,
) -> dict[str, bool]:
    merchant = await _get_current_merchant(credentials, db)
    product = await _get_merchant_product(product_id, merchant, db)
    await db.delete(product)
    await db.commit()

    return {"ok": True}


@router.post(
    "/products/{product_id}/images/replace",
    response_model=MerchantProductOut,
    response_model_by_alias=True,
)
async def replace_product_image(
    product_id: UUID,
    credentials: AuthCredentials,
    db: DbSession,
    file: Annotated[UploadFile, File(...)],
) -> MerchantProductOut:
    merchant = await _get_current_merchant(credentials, db)
    product = await _get_merchant_product(product_id, merchant, db)
    image_url = _save_product_image(file)
    product.image_urls = [image_url, *product.image_urls[1:]]
    await db.commit()
    await db.refresh(product)

    return _product_out(product)


@router.get("/leads", response_model=MerchantLeadListOut, response_model_by_alias=True)
async def leads(
    credentials: AuthCredentials,
    db: DbSession,
    lead_status: Annotated[
        str,
        Query(alias="status", pattern="^(all|pending|contacted)$"),
    ] = "all",
) -> MerchantLeadListOut:
    merchant = await _get_current_merchant(credentials, db)
    await _seed_leads_if_empty(merchant, db)

    statement = select(MerchantLead).where(MerchantLead.merchant_id == merchant.id)
    if lead_status != "all":
        statement = statement.where(MerchantLead.status == lead_status)
    statement = statement.order_by(MerchantLead.submitted_at.desc())

    result = await db.execute(statement)
    leads_out = [_lead_out(lead, merchant) for lead in result.scalars().all()]

    return MerchantLeadListOut(merchant=_dashboard_merchant_out(merchant), leads=leads_out)


@router.get("/leads/{lead_id}", response_model=MerchantLeadOut, response_model_by_alias=True)
async def lead_detail(
    lead_id: UUID,
    credentials: AuthCredentials,
    db: DbSession,
) -> MerchantLeadOut:
    merchant = await _get_current_merchant(credentials, db)
    await _seed_leads_if_empty(merchant, db)

    result = await db.execute(
        select(MerchantLead).where(
            MerchantLead.id == lead_id,
            MerchantLead.merchant_id == merchant.id,
        )
    )
    lead = result.scalar_one_or_none()
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    return _lead_out(lead, merchant)


@router.patch(
    "/leads/{lead_id}/status",
    response_model=MerchantLeadOut,
    response_model_by_alias=True,
)
async def update_lead_status(
    lead_id: UUID,
    payload: MerchantLeadStatusUpdate,
    credentials: AuthCredentials,
    db: DbSession,
) -> MerchantLeadOut:
    merchant = await _get_current_merchant(credentials, db)
    if merchant.tier != MerchantTier.vip:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="VIP required")

    result = await db.execute(
        select(MerchantLead).where(
            MerchantLead.id == lead_id,
            MerchantLead.merchant_id == merchant.id,
        )
    )
    lead = result.scalar_one_or_none()
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    lead.status = payload.status
    await db.commit()
    await db.refresh(lead)

    return _lead_out(lead, merchant)


@router.get(
    "/notifications",
    response_model=MerchantNotificationListOut,
    response_model_by_alias=True,
)
async def notifications(
    credentials: AuthCredentials,
    db: DbSession,
) -> MerchantNotificationListOut:
    merchant = await _get_current_merchant(credentials, db)
    await _seed_notifications_if_empty(merchant, db)

    allowed_types = (
        ["new_lead", "vip_expiring"] if merchant.tier == MerchantTier.vip else ["new_lead"]
    )
    result = await db.execute(
        select(MerchantNotification)
        .where(
            MerchantNotification.merchant_id == merchant.id,
            MerchantNotification.type.in_(allowed_types),
        )
        .order_by(MerchantNotification.sent_at.desc())
    )

    return MerchantNotificationListOut(
        merchant=_dashboard_merchant_out(merchant),
        notifications=[
            MerchantNotificationOut(
                id=notification.id,
                type=notification.type,
                content=notification.content,
                sent_at=notification.sent_at,
            )
            for notification in result.scalars().all()
        ],
    )
