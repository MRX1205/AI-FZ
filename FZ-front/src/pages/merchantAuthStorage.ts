import type { MerchantAuthSession } from '../types/domain'

export const MERCHANT_SESSION_KEY = 'fz_merchant_session_v1'

export function readMerchantSession(): MerchantAuthSession | null {
  try {
    const raw = localStorage.getItem(MERCHANT_SESSION_KEY)
    return raw ? (JSON.parse(raw) as MerchantAuthSession) : null
  } catch {
    return null
  }
}

export function clearMerchantSession() {
  localStorage.removeItem(MERCHANT_SESSION_KEY)
}

export function saveMerchantSession(session: MerchantAuthSession) {
  localStorage.setItem(MERCHANT_SESSION_KEY, JSON.stringify(session))
}

export function getAuthHeaders(token: string) {
  return { Authorization: `Bearer ${token}` }
}

export function updateMerchantSessionMerchant(merchant: MerchantAuthSession['merchant']) {
  const current = readMerchantSession()
  if (!current) return
  localStorage.setItem(
    MERCHANT_SESSION_KEY,
    JSON.stringify({
      ...current,
      merchant,
    }),
  )
}
