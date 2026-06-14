from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.lead import MerchantLead, MerchantNotification
from app.models.merchant import Merchant, MerchantTier
from app.models.product import MerchantProduct, MerchantProductImage
from app.schemas.public_product import (
    PublicProductContactCreate,
    PublicProductContactOut,
    PublicProductOut,
)

router = APIRouter(prefix="/products")
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _product_image_urls(product: MerchantProduct, db: AsyncSession) -> list[str]:
    result = await db.execute(
        select(MerchantProductImage.public_url)
        .where(
            MerchantProductImage.product_id == product.id,
            MerchantProductImage.merchant_id == product.merchant_id,
        )
        .order_by(MerchantProductImage.sort_order.asc(), MerchantProductImage.created_at.asc())
    )
    uploaded_urls = list(result.scalars().all())
    return list(product.image_urls or []) or uploaded_urls or ["/mock-products/jade-1.png"]


async def _listed_product_or_404(product_id: UUID, db: AsyncSession) -> MerchantProduct:
    product = await db.get(MerchantProduct, product_id)
    if product is None or product.status != "listed":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在或未上架")
    return product


async def _public_product_out(product: MerchantProduct, db: AsyncSession) -> PublicProductOut:
    merchant = await db.get(Merchant, product.merchant_id)
    merchant_tier = merchant.tier.value if merchant else MerchantTier.free.value
    return PublicProductOut(
        id=product.id,
        title=product.title,
        summary=product.summary,
        detail=product.detail,
        tags=product.tags,
        price_cents=product.price_cents,
        image_urls=await _product_image_urls(product, db),
        merchant_tier=merchant_tier,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.get("/{product_id}", response_model=PublicProductOut, response_model_by_alias=True)
async def product_detail(product_id: UUID, db: DbSession) -> PublicProductOut:
    product = await _listed_product_or_404(product_id, db)
    return await _public_product_out(product, db)


@router.post(
    "/{product_id}/contact",
    response_model=PublicProductContactOut,
    response_model_by_alias=True,
)
async def contact_product_seller(
    product_id: UUID,
    payload: PublicProductContactCreate,
    db: DbSession,
) -> PublicProductContactOut:
    product = await _listed_product_or_404(product_id, db)
    existing_result = await db.execute(
        select(MerchantLead).where(
            MerchantLead.product_id == product.id,
            MerchantLead.buyer_email == payload.buyer_email,
        )
    )
    existing_lead = existing_result.scalar_one_or_none()
    if existing_lead is not None:
        return PublicProductContactOut(
            ok=False,
            message="已提交过联系意向，卖家会尽快联系您。",
            lead_id=existing_lead.id,
        )

    now = datetime.now(UTC)
    image_urls = await _product_image_urls(product, db)
    lead = MerchantLead(
        merchant_id=product.merchant_id,
        product_id=product.id,
        submitted_at=now,
        buyer_email=payload.buyer_email,
        message=f"用户对「{product.title}」提交联系卖家意向",
        product_title=product.title,
        product_price_cents=product.price_cents,
        product_image_url=image_urls[0],
        status="pending",
    )
    notification = MerchantNotification(
        merchant_id=product.merchant_id,
        type="new_lead",
        content=f"有新客户对「{product.title}」留下联系方式，请及时处理。",
        sent_at=now,
    )
    db.add_all([lead, notification])
    await db.commit()
    await db.refresh(lead)

    return PublicProductContactOut(
        ok=True,
        message="提交成功，卖家会尽快联系您。",
        lead_id=lead.id,
    )
