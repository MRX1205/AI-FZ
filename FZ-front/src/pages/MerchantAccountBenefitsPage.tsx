import { ChevronLeft, Crown, Gem, Mail, Package } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, apiGet } from '../api/client'
import type { MerchantAccountResponse } from '../types/domain'
import {
  clearMerchantSession,
  getAuthHeaders,
  readMerchantSession,
  updateMerchantSessionMerchant,
} from './merchantAuthStorage'

function formatDate(value?: string | null) {
  if (!value) return '永久'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
    .format(new Date(value))
    .replaceAll('/', '-')
}

export function MerchantAccountBenefitsPage() {
  const navigate = useNavigate()
  const token = useMemo(() => readMerchantSession()?.token ?? '', [])
  const [account, setAccount] = useState<MerchantAccountResponse | null>(null)

  useEffect(() => {
    if (!token) {
      navigate('/merchant/auth', { replace: true })
      return
    }

    apiGet<MerchantAccountResponse>('/api/merchant/account', {
      headers: getAuthHeaders(token),
    })
      .then((response) => {
        setAccount(response)
        updateMerchantSessionMerchant(response.merchant)
      })
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) {
          clearMerchantSession()
          navigate('/merchant/auth', { replace: true })
        }
      })
  }, [navigate, token])

  if (!account) {
    return (
      <section className="merchant-account-page">
        <header className="profile-header">
          <button type="button" aria-label="返回账户权限" onClick={() => navigate('/merchant/account')}>
            <ChevronLeft size={31} strokeWidth={2.4} />
          </button>
          <h1>VIP权益</h1>
          <span aria-hidden="true" />
        </header>
        <div className="profile-loading">加载中...</div>
      </section>
    )
  }

  return (
    <section className="merchant-account-page">
      <header className="profile-header">
        <button type="button" aria-label="返回账户权限" onClick={() => navigate('/merchant/account')}>
          <ChevronLeft size={31} strokeWidth={2.4} />
        </button>
        <h1>VIP权益</h1>
        <span>{account.merchant.tier === 'vip' ? <em className="account-vip-tag">VIP</em> : null}</span>
      </header>

      <div className="account-scroll">
        <section className="membership-card is-vip">
          <span className="membership-icon" aria-hidden="true">
            <Crown size={27} />
          </span>
          <div>
            <h2>VIP会员</h2>
            <p>{`有效期至 ${formatDate(account.vipExpiresAt)}`}</p>
          </div>
        </section>

        <section className="benefit-grid">
          <article>
            <span>
              <Package size={18} />
            </span>
            <strong>{`${account.productLimit}件商品发布上限`}</strong>
            <p>{`当前已上架 ${account.listedCount} 件，今日新增 ${account.todayPublished} 件。`}</p>
          </article>
          <article>
            <span>
              <Mail size={18} />
            </span>
            <strong>{account.leadAccess}</strong>
            <p>支持查看完整客资联系方式，便于快速跟进成交。</p>
          </article>
          <article>
            <span>
              <Gem size={18} />
            </span>
            <strong>{`优先展示权重 ${account.priority}`}</strong>
            <p>在推荐展示和匹配排序中享受更高曝光机会。</p>
          </article>
        </section>
      </div>
    </section>
  )
}
