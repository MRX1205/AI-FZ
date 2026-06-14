from datetime import UTC, datetime

from app.models.merchant import Merchant, MerchantTier


def effective_merchant_tier(merchant: Merchant | None) -> MerchantTier:
    if merchant is None:
        return MerchantTier.free
    if merchant.tier != MerchantTier.vip or merchant.vip_expires_at is None:
        return MerchantTier.free
    return MerchantTier.vip if merchant.vip_expires_at > datetime.now(UTC) else MerchantTier.free


def is_effective_vip(merchant: Merchant | None) -> bool:
    return effective_merchant_tier(merchant) == MerchantTier.vip


def effective_merchant_tier_value(merchant: Merchant | None) -> str:
    return effective_merchant_tier(merchant).value
