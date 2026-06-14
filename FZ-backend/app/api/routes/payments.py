from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.payment import MerchantVipOrder
from app.services.alipay import (
    AlipayError,
    AlipayVerificationError,
    alipay_client,
)
from app.services.vip_orders import amount_yuan_text, mark_vip_order_closed, mark_vip_order_paid

router = APIRouter(prefix="/payments")

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post("/alipay/notify")
async def alipay_notify(request: Request, db: DbSession) -> PlainTextResponse:
    form = await request.form()
    raw_params = {key: str(value) for key, value in form.multi_items()}

    try:
        notification = alipay_client.verify_notification(raw_params)
    except AlipayVerificationError:
        return PlainTextResponse("failure", status_code=status.HTTP_400_BAD_REQUEST)
    except AlipayError:
        return PlainTextResponse("failure", status_code=status.HTTP_400_BAD_REQUEST)

    if notification.app_id != settings.alipay_app_id:
        return PlainTextResponse("failure", status_code=status.HTTP_400_BAD_REQUEST)
    if settings.alipay_seller_id and notification.seller_id != settings.alipay_seller_id:
        return PlainTextResponse("failure", status_code=status.HTTP_400_BAD_REQUEST)

    result = await db.execute(
        select(MerchantVipOrder).where(MerchantVipOrder.order_no == notification.out_trade_no)
    )
    order = result.scalar_one_or_none()
    if order is None:
        return PlainTextResponse("failure", status_code=status.HTTP_404_NOT_FOUND)
    if notification.total_amount != amount_yuan_text(order.amount_cents):
        return PlainTextResponse("failure", status_code=status.HTTP_400_BAD_REQUEST)

    if notification.trade_status == "TRADE_SUCCESS":
        await mark_vip_order_paid(
            db,
            order_no=order.order_no,
            trade_status=notification.trade_status,
            alipay_trade_no=notification.trade_no,
            paid_at=notification.notify_time or datetime.now(UTC),
        )
        await db.commit()
        return PlainTextResponse("success")

    if notification.trade_status == "TRADE_CLOSED":
        await mark_vip_order_closed(
            db,
            order_no=order.order_no,
            trade_status=notification.trade_status,
        )
        await db.commit()
        return PlainTextResponse("success")

    return PlainTextResponse("success")
