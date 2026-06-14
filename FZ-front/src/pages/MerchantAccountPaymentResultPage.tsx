import { CheckCircle2, ChevronLeft, CircleAlert, LoaderCircle } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ApiError, apiGet, apiPost } from '../api/client'
import type { MerchantVipOrder, MerchantVipOrderSyncResponse } from '../types/domain'
import {
  clearMerchantSession,
  getAuthHeaders,
  readMerchantSession,
  updateMerchantSessionMerchant,
} from './merchantAuthStorage'

type ResultState = 'loading' | 'success' | 'failed'

export function MerchantAccountPaymentResultPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = useMemo(() => readMerchantSession()?.token ?? '', [])
  const orderId = searchParams.get('order_id') ?? searchParams.get('orderId')
  const [state, setState] = useState<ResultState>(orderId ? 'loading' : 'failed')
  const [message, setMessage] = useState(
    orderId ? '正在确认支付结果...' : '未找到支付订单，请返回账户权限页查看',
  )
  const [order, setOrder] = useState<MerchantVipOrder | null>(null)

  useEffect(() => {
    if (!token) {
      navigate('/merchant/auth', { replace: true })
      return
    }
    if (!orderId) {
      return
    }

    let cancelled = false

    async function refreshMerchant() {
      const merchant = await apiGet<{ id: string; email: string; tier: 'free' | 'vip' }>('/api/auth/me', {
        headers: getAuthHeaders(token),
      })
      updateMerchantSessionMerchant(merchant)
    }

    async function syncOrder() {
      try {
        const currentOrder = await apiGet<MerchantVipOrder>(`/api/merchant/account/vip-orders/${orderId}`, {
          headers: getAuthHeaders(token),
        })
        if (cancelled) return
        setOrder(currentOrder)
        if (currentOrder.status === 'paid') {
          await refreshMerchant()
          if (cancelled) return
          setState('success')
          setMessage('VIP开通成功，权益已生效')
          return
        }
        if (currentOrder.status === 'closed') {
          setState('failed')
          setMessage('该订单已关闭，请重新发起支付')
          return
        }

        for (let attempt = 0; attempt < 4; attempt += 1) {
          const syncResponse = await apiPost<MerchantVipOrderSyncResponse>(
            `/api/merchant/account/vip-orders/${orderId}/sync`,
            {},
            { headers: getAuthHeaders(token) },
          )
          if (cancelled) return
          setOrder(syncResponse.order)
          if (syncResponse.order.status === 'paid') {
            await refreshMerchant()
            if (cancelled) return
            setState('success')
            setMessage('VIP开通成功，权益已生效')
            return
          }
          if (syncResponse.order.status === 'closed') {
            setState('failed')
            setMessage('该订单已关闭，请重新发起支付')
            return
          }
          await new Promise((resolve) => window.setTimeout(resolve, 1200))
        }

        setState('failed')
        setMessage('支付结果还未同步完成，请稍后回到账户权限页刷新查看')
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          clearMerchantSession()
          navigate('/merchant/auth', { replace: true })
          return
        }
        setState('failed')
        setMessage(error instanceof ApiError ? error.message : '支付结果查询失败，请稍后重试')
      }
    }

    void syncOrder()

    return () => {
      cancelled = true
    }
  }, [navigate, orderId, token])

  return (
    <section className="merchant-account-page">
      <header className="profile-header">
        <button type="button" aria-label="返回账户权限" onClick={() => navigate('/merchant/account')}>
          <ChevronLeft size={31} strokeWidth={2.4} />
        </button>
        <h1>支付结果</h1>
        <span aria-hidden="true" />
      </header>

      <div className="account-scroll">
        <section className={`payment-result-card is-${state}`}>
          <span aria-hidden="true">
            {state === 'loading' ? (
              <LoaderCircle className="is-spinning" size={28} />
            ) : state === 'success' ? (
              <CheckCircle2 size={28} />
            ) : (
              <CircleAlert size={28} />
            )}
          </span>
          <strong>{state === 'loading' ? '支付确认中' : state === 'success' ? '支付成功' : '支付未完成'}</strong>
          <p>{message}</p>
          {order ? <small>{`订单号 ${order.orderNo}`}</small> : null}
        </section>

        <button className="account-action" type="button" onClick={() => navigate('/merchant/account')}>
          返回账户权限
        </button>
      </div>
    </section>
  )
}
