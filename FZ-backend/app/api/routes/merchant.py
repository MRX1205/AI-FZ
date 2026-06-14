import shutil
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.auth import AuthCode, MerchantSession
from app.models.lead import MerchantLead, MerchantNotification
from app.models.merchant import Merchant, MerchantTier
from app.models.product import MerchantProduct, MerchantProductEmbedding, MerchantProductImage
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
    MerchantProductCurrentDraftOut,
    MerchantProductDraftUpdate,
    MerchantProductImageOut,
    MerchantProductListOut,
    MerchantProductOut,
    MerchantProductQuotaOut,
    MerchantProductStatusUpdate,
    MerchantProfileOut,
    NotificationSettingsOut,
)
from app.services.embeddings import ProductEmbeddingError, embedding_client
from app.services.product_image_recognition_agent import (
    ProductImageRecognitionError,
    product_image_recognition_agent,
)
from app.services.product_search import (
    product_search_content_hash,
    refresh_product_search_text,
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
        product_id=lead.product_id,
        submitted_at=lead.submitted_at,
        buyer_email=_visible_buyer_email(merchant, lead.buyer_email),
        message=lead.message,
        product_title=lead.product_title,
        product_price_cents=lead.product_price_cents,
        product_image_url=lead.product_image_url,
        status=lead.status,
        merchant_email=merchant.email,
    )


async def _product_embedding(
    product: MerchantProduct,
    db: AsyncSession,
) -> MerchantProductEmbedding | None:
    result = await db.execute(
        select(MerchantProductEmbedding).where(
            MerchantProductEmbedding.product_id == product.id,
            MerchantProductEmbedding.merchant_id == product.merchant_id,
        )
    )
    return result.scalar_one_or_none()


async def _refresh_product_embedding(
    product: MerchantProduct,
    db: AsyncSession,
) -> None:
    refresh_product_search_text(product)
    content_hash = product_search_content_hash(product)
    existing = await _product_embedding(product, db)
    if existing and existing.content_hash == content_hash:
        return

    try:
        result = await embedding_client.embed_document(product.search_text)
    except ProductEmbeddingError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error

    if existing is None:
        db.add(
            MerchantProductEmbedding(
                merchant_id=product.merchant_id,
                product_id=product.id,
                provider=result.provider,
                model=result.model,
                dimensions=result.dimensions,
                content_hash=content_hash,
                embedding=result.embedding,
            )
        )
        return

    existing.provider = result.provider
    existing.model = result.model
    existing.dimensions = result.dimensions
    existing.content_hash = content_hash
    existing.embedding = result.embedding


def _product_limit(merchant: Merchant) -> int:
    return 100 if merchant.tier == MerchantTier.vip else 2


async def _product_images(
    product: MerchantProduct,
    db: AsyncSession,
) -> list[MerchantProductImage]:
    result = await db.execute(
        select(MerchantProductImage)
        .where(
            MerchantProductImage.product_id == product.id,
            MerchantProductImage.merchant_id == product.merchant_id,
        )
        .order_by(MerchantProductImage.sort_order.asc(), MerchantProductImage.created_at.asc())
    )
    return list(result.scalars().all())


def _product_image_out(image: MerchantProductImage) -> MerchantProductImageOut:
    return MerchantProductImageOut(
        id=image.id,
        merchant_id=image.merchant_id,
        product_id=image.product_id,
        storage_key=image.storage_key,
        public_url=image.public_url,
        sort_order=image.sort_order,
        created_at=image.created_at,
    )


async def _product_out(product: MerchantProduct, db: AsyncSession) -> MerchantProductOut:
    images = await _product_images(product, db)
    image_urls = list(product.image_urls or []) or [image.public_url for image in images]
    return MerchantProductOut(
        id=product.id,
        title=product.title,
        summary=product.summary,
        detail=product.detail,
        tags=product.tags,
        price_cents=product.price_cents,
        status=product.status,
        image_urls=image_urls,
        images=[_product_image_out(image) for image in images],
        published_at=product.published_at,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


async def _current_product_image_urls(
    product: MerchantProduct,
    db: AsyncSession,
) -> list[str]:
    images = await _product_images(product, db)
    return list(product.image_urls or []) or [image.public_url for image in images]


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


async def _is_publish_flow_draft(
    product: MerchantProduct,
    db: AsyncSession,
) -> bool:
    image_urls = await _current_product_image_urls(product, db)
    has_uploaded_image = any(image_url.startswith("/uploads/") for image_url in image_urls)
    is_empty_upload_draft = (
        not product.title
        and not product.summary
        and not product.detail
        and not product.tags
        and product.price_cents == 0
    )
    return has_uploaded_image or is_empty_upload_draft


async def _get_latest_publish_flow_draft(
    merchant: Merchant,
    db: AsyncSession,
) -> MerchantProduct | None:
    result = await db.execute(
        select(MerchantProduct)
        .where(
            MerchantProduct.merchant_id == merchant.id,
            MerchantProduct.status == "draft",
        )
        .order_by(MerchantProduct.updated_at.desc(), MerchantProduct.created_at.desc())
    )
    for product in result.scalars():
        if await _is_publish_flow_draft(product, db):
            return product
    return None


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
            image_urls=[
                "/mock-products/jade-1.png",
                "/mock-products/jade-2.png",
                "/mock-products/jade-3.png",
            ],
            published_at=datetime(2026, 5, 20, 10, 30, tzinfo=UTC),
            created_at=datetime(2026, 5, 20, 10, 30, tzinfo=UTC),
            updated_at=datetime(2026, 5, 20, 10, 30, tzinfo=UTC),
        ),
        MerchantProduct(
            merchant_id=merchant.id,
            title="冰种飘花翡翠吊坠",
            summary="冰种飘花，清爽耐看。",
            detail="冰种飘花翡翠吊坠，底子干净，飘花灵动，适合日常佩戴。",
            tags=["冰种", "飘花", "翡翠吊坠"],
            price_cents=3_200_000,
            status="draft",
            image_urls=["/mock-products/jade-2.png", "/mock-products/jade-3.png"],
            published_at=None,
            created_at=datetime(2026, 5, 18, 10, 30, tzinfo=UTC),
            updated_at=datetime(2026, 5, 18, 10, 30, tzinfo=UTC),
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
            created_at=datetime(2026, 5, 15, 14, 30, tzinfo=UTC),
            updated_at=datetime(2026, 5, 15, 14, 30, tzinfo=UTC),
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
                    created_at=datetime(2026, 5, min(28, 10 + index), 10, 0, tzinfo=UTC),
                    updated_at=datetime(2026, 5, min(28, 10 + index), 10, 0, tzinfo=UTC),
                )
            )
    db.add_all(seed_products)
    await db.commit()


async def _apply_product_draft_update(
    product: MerchantProduct,
    payload: MerchantProductDraftUpdate,
) -> None:
    product.title = payload.title
    product.summary = payload.summary
    product.detail = payload.detail
    product.tags = payload.tags
    product.price_cents = payload.price_cents
    refresh_product_search_text(product)


async def _assert_product_ready_to_publish(
    product: MerchantProduct,
    db: AsyncSession,
) -> None:
    image_urls = await _current_product_image_urls(product, db)
    if not image_urls:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先上传商品图片")
    if not product.title.strip() or not product.summary.strip() or not product.detail.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请完整填写商品信息")
    if product.price_cents <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请填写商品价格")


def _save_merchant_product_image(
    file: UploadFile,
    merchant: Merchant,
    product: MerchantProduct,
    image_id: UUID,
) -> tuple[str, str]:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image file required")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"

    storage_key = (
        f"merchants/{merchant.id}/products/{product.id}/{image_id}{suffix}"
    )
    target = UPLOAD_ROOT.parent / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return storage_key, f"/uploads/{storage_key}"


def _remove_uploaded_file(image_url: str) -> None:
    if not image_url.startswith("/uploads/"):
        return
    image_path = UPLOAD_ROOT.parent / image_url.removeprefix("/uploads/")
    image_path.unlink(missing_ok=True)


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
    products_out = [await _product_out(product, db) for product in result.scalars().all()]
    counts, quota = await _product_counts(merchant, db)

    return MerchantProductListOut(
        merchant=_dashboard_merchant_out(merchant),
        products=products_out,
        counts=counts,
        quota=quota,
    )


@router.get(
    "/products/current-draft",
    response_model=MerchantProductCurrentDraftOut,
    response_model_by_alias=True,
)
async def current_product_draft(
    credentials: AuthCredentials,
    db: DbSession,
) -> MerchantProductCurrentDraftOut:
    merchant = await _get_current_merchant(credentials, db)
    await _seed_products_if_empty(merchant, db)
    draft = await _get_latest_publish_flow_draft(merchant, db)
    _, quota = await _product_counts(merchant, db)

    return MerchantProductCurrentDraftOut(
        merchant=_dashboard_merchant_out(merchant),
        product=await _product_out(draft, db) if draft else None,
        quota=quota,
    )


@router.post(
    "/products/drafts/images",
    response_model=MerchantProductOut,
    response_model_by_alias=True,
)
async def append_product_draft_images(
    credentials: AuthCredentials,
    db: DbSession,
    images: Annotated[list[UploadFile] | None, File()] = None,
) -> MerchantProductOut:
    merchant = await _get_current_merchant(credentials, db)
    await _seed_products_if_empty(merchant, db)

    if not images:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先上传商品图片")

    draft = await _get_latest_publish_flow_draft(merchant, db)
    current_image_urls = await _current_product_image_urls(draft, db) if draft else []
    if len(current_image_urls) + len(images) > 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="最多上传6张图片")

    if draft is None:
        draft = MerchantProduct(
            merchant_id=merchant.id,
            title="",
            summary="",
            detail="",
            tags=[],
            price_cents=0,
            status="draft",
            image_urls=[],
            published_at=None,
        )
        db.add(draft)
        await db.flush()
    else:
        draft.title = ""
        draft.summary = ""
        draft.detail = ""
        draft.tags = []
        draft.price_cents = 0

    image_urls: list[str] = []
    for offset, image in enumerate(images):
        image_id = uuid.uuid4()
        storage_key, public_url = _save_merchant_product_image(image, merchant, draft, image_id)
        db.add(
            MerchantProductImage(
                id=image_id,
                merchant_id=merchant.id,
                product_id=draft.id,
                storage_key=storage_key,
                public_url=public_url,
                sort_order=len(current_image_urls) + offset,
            )
        )
        image_urls.append(public_url)
    draft.image_urls = current_image_urls + image_urls

    await db.commit()
    await db.refresh(draft)

    return await _product_out(draft, db)


@router.post(
    "/products/drafts/generate",
    response_model=MerchantProductOut,
    response_model_by_alias=True,
)
async def generate_product_draft(
    credentials: AuthCredentials,
    db: DbSession,
    product_id: Annotated[UUID | None, Form(alias="productId")] = None,
    images: Annotated[list[UploadFile] | None, File()] = None,
) -> MerchantProductOut:
    merchant = await _get_current_merchant(credentials, db)
    await _seed_products_if_empty(merchant, db)

    draft = await _get_merchant_product(product_id, merchant, db) if product_id else None
    current_image_urls = await _current_product_image_urls(draft, db) if draft else []

    if not images and not current_image_urls:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先上传商品图片")
    if images and len(images) + len(current_image_urls) > 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="最多上传6张图片")

    product = draft
    if product is None:
        product = MerchantProduct(
            merchant_id=merchant.id,
            title="",
            summary="",
            detail="",
            tags=[],
            price_cents=0,
            status="draft",
            image_urls=[],
            published_at=None,
        )
        db.add(product)
        await db.flush()

    uploaded_image_urls: list[str] = []
    if images:
        for offset, image in enumerate(images):
            image_id = uuid.uuid4()
            storage_key, public_url = _save_merchant_product_image(
                image,
                merchant,
                product,
                image_id,
            )
            db.add(
                MerchantProductImage(
                    id=image_id,
                    merchant_id=merchant.id,
                    product_id=product.id,
                    storage_key=storage_key,
                    public_url=public_url,
                    sort_order=len(current_image_urls) + offset,
                )
            )
            uploaded_image_urls.append(public_url)

    image_urls = current_image_urls + uploaded_image_urls
    try:
        product = await product_image_recognition_agent.recognize_and_save_product(
            product=product,
            image_urls=image_urls,
            db=db,
        )
    except ProductImageRecognitionError as error:
        for image_url in uploaded_image_urls:
            _remove_uploaded_file(image_url)
        await db.rollback()
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error

    return await _product_out(product, db)


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

    return await _product_out(product, db)


@router.patch(
    "/products/{product_id}/publish",
    response_model=MerchantProductOut,
    response_model_by_alias=True,
)
async def publish_product(
    product_id: UUID,
    payload: MerchantProductDraftUpdate,
    credentials: AuthCredentials,
    db: DbSession,
) -> MerchantProductOut:
    merchant = await _get_current_merchant(credentials, db)
    product = await _get_merchant_product(product_id, merchant, db)
    await _apply_product_draft_update(product, payload)
    await _assert_product_ready_to_publish(product, db)

    if product.status != "listed":
        await _assert_product_quota_available(merchant, db)
    product.status = "listed"
    product.published_at = product.published_at or datetime.now(UTC)
    await _refresh_product_embedding(product, db)

    await db.commit()
    await db.refresh(product)

    return await _product_out(product, db)


@router.patch(
    "/products/{product_id}",
    response_model=MerchantProductOut,
    response_model_by_alias=True,
)
async def update_product(
    product_id: UUID,
    payload: MerchantProductDraftUpdate,
    credentials: AuthCredentials,
    db: DbSession,
) -> MerchantProductOut:
    merchant = await _get_current_merchant(credentials, db)
    product = await _get_merchant_product(product_id, merchant, db)
    await _apply_product_draft_update(product, payload)
    if product.status == "listed":
        await _refresh_product_embedding(product, db)
    await db.commit()
    await db.refresh(product)

    return await _product_out(product, db)


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
    if payload.status == "listed":
        await _refresh_product_embedding(product, db)
    if payload.status != "listed" and product.published_at is None:
        product.published_at = None

    await db.commit()
    await db.refresh(product)

    return await _product_out(product, db)


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


@router.delete(
    "/products/{product_id}/images/{image_index}",
    response_model=MerchantProductOut,
    response_model_by_alias=True,
)
async def delete_product_image(
    product_id: UUID,
    image_index: int,
    credentials: AuthCredentials,
    db: DbSession,
) -> MerchantProductOut:
    merchant = await _get_current_merchant(credentials, db)
    product = await _get_merchant_product(product_id, merchant, db)
    images = await _product_images(product, db)
    image_urls = await _current_product_image_urls(product, db)
    if image_index < 0 or image_index >= len(image_urls):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    removed_image = next((image for image in images if image.sort_order == image_index), None)
    if removed_image is not None:
        _remove_uploaded_file(removed_image.public_url)
        await db.delete(removed_image)
    else:
        _remove_uploaded_file(image_urls[image_index])
    for image in images:
        if image.sort_order > image_index:
            image.sort_order -= 1

    product.image_urls = [
        image_url for index, image_url in enumerate(image_urls) if index != image_index
    ]
    product.title = ""
    product.summary = ""
    product.detail = ""
    product.tags = []
    product.price_cents = 0
    await db.commit()
    await db.refresh(product)

    return await _product_out(product, db)


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
    image_index: Annotated[int, Form(alias="imageIndex")] = 0,
) -> MerchantProductOut:
    merchant = await _get_current_merchant(credentials, db)
    product = await _get_merchant_product(product_id, merchant, db)
    images = await _product_images(product, db)
    image_urls = await _current_product_image_urls(product, db)
    image_id = uuid.uuid4()
    storage_key, public_url = _save_merchant_product_image(file, merchant, product, image_id)

    safe_index = min(max(image_index, 0), max(len(image_urls) - 1, 0))
    image = next(
        (product_image for product_image in images if product_image.sort_order == safe_index),
        None,
    )

    if image is not None:
        _remove_uploaded_file(image.public_url)
        image.storage_key = storage_key
        image.public_url = public_url
        image_urls[safe_index] = public_url
    elif not image_urls:
        db.add(
            MerchantProductImage(
                id=image_id,
                merchant_id=merchant.id,
                product_id=product.id,
                storage_key=storage_key,
                public_url=public_url,
                sort_order=0,
            )
        )
        image_urls = [public_url]
    else:
        _remove_uploaded_file(image_urls[safe_index])
        db.add(
            MerchantProductImage(
                id=image_id,
                merchant_id=merchant.id,
                product_id=product.id,
                storage_key=storage_key,
                public_url=public_url,
                sort_order=safe_index,
            )
        )
        image_urls[safe_index] = public_url
    product.image_urls = image_urls
    await db.commit()
    await db.refresh(product)

    return await _product_out(product, db)


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
