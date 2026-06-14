import calendar
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.merchant import Merchant, MerchantTier
from app.models.payment import MerchantVipOrder
from app.services.merchant_membership import is_effective_vip

VIP_PLAN_AMOUNTS = {
    6: 168_800,
    12: 299_900,
}


class VipOrderError(RuntimeError):
    pass


@dataclass(slots=True)
class VipPlan:
    title: str
    months: int
    amount_cents: int


def vip_plans() -> list[VipPlan]:
    return [
        VipPlan(title="VIP会员（12个月）", months=12, amount_cents=VIP_PLAN_AMOUNTS[12]),
        VipPlan(title="VIP会员（6个月）", months=6, amount_cents=VIP_PLAN_AMOUNTS[6]),
    ]


def vip_amount_cents(plan_months: int) -> int:
    if plan_months not in VIP_PLAN_AMOUNTS:
        raise VipOrderError("套餐不存在")
    return VIP_PLAN_AMOUNTS[plan_months]


def vip_order_no() -> str:
    return f"VIP{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:10].upper()}"


def amount_yuan_text(amount_cents: int) -> str:
    return f"{amount_cents / 100:.2f}"


def add_months(base: datetime, months: int) -> datetime:
    year = base.year + (base.month - 1 + months) // 12
    month = (base.month - 1 + months) % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return base.replace(year=year, month=month, day=day)


async def mark_vip_order_paid(
    db: AsyncSession,
    *,
    order_no: str,
    trade_status: str,
    alipay_trade_no: str,
    paid_at: datetime,
) -> MerchantVipOrder:
    result = await db.execute(
        select(MerchantVipOrder, Merchant)
        .join(Merchant, Merchant.id == MerchantVipOrder.merchant_id)
        .where(MerchantVipOrder.order_no == order_no)
        .with_for_update()
    )
    row = result.first()
    if row is None:
        raise VipOrderError("订单不存在")
    order, merchant = row
    if order.status == "paid":
        return order

    active_vip = is_effective_vip(merchant) and merchant.vip_expires_at is not None
    if active_vip and merchant.vip_expires_at and merchant.vip_expires_at > paid_at:
        grant_started_at = merchant.vip_expires_at
    else:
        grant_started_at = paid_at
        merchant.vip_started_at = paid_at

    merchant.tier = MerchantTier.vip
    merchant.vip_expires_at = add_months(grant_started_at, order.plan_months)

    order.status = "paid"
    order.trade_status = trade_status
    order.alipay_trade_no = alipay_trade_no
    order.paid_at = paid_at
    order.grant_started_at = grant_started_at
    order.grant_expires_at = merchant.vip_expires_at
    return order


async def mark_vip_order_closed(
    db: AsyncSession,
    *,
    order_no: str,
    trade_status: str,
) -> MerchantVipOrder | None:
    result = await db.execute(
        select(MerchantVipOrder)
        .where(MerchantVipOrder.order_no == order_no)
        .with_for_update()
    )
    order = result.scalar_one_or_none()
    if order is None:
        return None
    if order.status == "paid":
        return order
    order.status = "closed"
    order.trade_status = trade_status
    return order
