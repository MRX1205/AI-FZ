import { Bell, ChevronLeft } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, apiGet } from '../api/client'
import { MerchantTabBar } from '../components/MerchantTabBar'
import type { MerchantNotificationListResponse } from '../types/domain'
import {
  clearMerchantSession,
  getAuthHeaders,
  readMerchantSession,
  updateMerchantSessionMerchant,
} from './merchantAuthStorage'

function formatNoticeTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

export function MerchantNotificationsPage() {
  const navigate = useNavigate()
  const token = useMemo(() => readMerchantSession()?.token ?? '', [])
  const [data, setData] = useState<MerchantNotificationListResponse | null>(null)

  useEffect(() => {
    if (!token) {
      navigate('/merchant/auth', { replace: true })
      return
    }

    apiGet<MerchantNotificationListResponse>('/api/merchant/notifications', {
      headers: getAuthHeaders(token),
    })
      .then((response) => {
        setData(response)
        updateMerchantSessionMerchant(response.merchant)
      })
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) {
          clearMerchantSession()
          navigate('/merchant/auth', { replace: true })
        }
      })
  }, [navigate, token])

  return (
    <section className="merchant-notifications-page">
      <header className="profile-header">
        <button type="button" aria-label="返回商家后台" onClick={() => navigate('/merchant/dashboard')}>
          <ChevronLeft size={31} strokeWidth={2.4} />
        </button>
        <h1>系统通知</h1>
        <span aria-hidden="true" />
      </header>

      {!data ? (
        <div className="profile-loading">加载中...</div>
      ) : (
        <div className="notifications-scroll">
          <section className="notification-summary">
            <span aria-hidden="true">
              <Bell size={24} />
            </span>
            <div>
              <strong>{data.merchant.tier === 'vip' ? 'VIP系统通知' : '系统通知'}</strong>
              <small>{data.merchant.tier === 'vip' ? '新客资与会员到期提醒' : '新客资提醒'}</small>
            </div>
          </section>

          <ul className="notification-list">
            {data.notifications.map((notification) => (
              <li key={notification.id}>
                <time>{formatNoticeTime(notification.sentAt)}</time>
                <p>{notification.content}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      <MerchantTabBar />
    </section>
  )
}
