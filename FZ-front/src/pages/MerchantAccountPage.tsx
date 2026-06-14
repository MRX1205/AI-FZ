import { BriefcaseBusiness, Check, ChevronLeft } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, apiGet, apiPost } from '../api/client'
import type {
  MerchantAccountResponse,
  MerchantVipOrder,
  MerchantVipOrderCreatePayload,
} from '../types/domain'
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

function formatPrice(amountCents: number) {
  return `￥${Math.round(amountCents / 100).toLocaleString('zh-CN')}`
}

function detectPayChannel(): 'wap' | 'page' {
  if (typeof navigator === 'undefined') return 'page'
  return /android/i.test(navigator.userAgent) ? 'wap' : 'page'
}

export function MerchantAccountPage() {
  const navigate = useNavigate()
  const token = useMemo(() => readMerchantSession()?.token ?? '', [])
  const [account, setAccount] = useState<MerchantAccountResponse | null>(null)
  const [selectedMonths, setSelectedMonths] = useState<number | null>(null)
  const [message, setMessage] = useState('')
  const [isPaying, setIsPaying] = useState(false)

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
          return
        }
        setMessage('账户信息加载失败，请稍后重试')
      })
  }, [navigate, token])

  async function handlePay() {
    if (!token || !account) return
    if (!selectedMonths) {
      setMessage('请选择充值套餐')
      return
    }

    setIsPaying(true)
    setMessage('')

    try {
      const payload: MerchantVipOrderCreatePayload = {
        planMonths: selectedMonths,
        payChannel: detectPayChannel(),
      }
      const response = await apiPost<MerchantVipOrder>(
        '/api/merchant/account/vip-orders',
        payload,
        { headers: getAuthHeaders(token) },
      )
      if (!response.payUrl) {
        setMessage('支付链接生成失败，请稍后重试')
        setIsPaying(false)
        return
      }
      window.location.assign(response.payUrl)
    } catch (error) {
      setIsPaying(false)
      setMessage(error instanceof ApiError ? error.message : '发起支付失败，请稍后重试')
    }
  }

  if (!account) {
    return (
      <section className="merchant-account-page">
        <AccountHeader isVip={false} onBack={() => navigate('/merchant/profile')} />
        <div className="profile-loading">加载中...</div>
      </section>
    )
  }

  const isVip = account.merchant.tier === 'vip'

  return (
    <section className="merchant-account-page">
      <AccountHeader isVip={isVip} onBack={() => navigate('/merchant/profile')} />

      <div className="account-scroll">
        <section className={`membership-card ${isVip ? 'is-vip' : 'is-free'}`}>
          <span className="membership-icon" aria-hidden="true">
            <BriefcaseBusiness size={27} />
          </span>
          <div>
            <h2>{isVip ? 'VIP会员' : '普通会员'}</h2>
            <p>{`有效期至 ${formatDate(account.vipExpiresAt)}`}</p>
          </div>
          {isVip ? (
            <button type="button" onClick={() => navigate('/merchant/account/benefits')}>
              查看权益
            </button>
          ) : null}
        </section>

        <section className="account-section">
          <h2>当前权限</h2>
          <dl className="permission-table">
            <div>
              <dt>商品发布上限</dt>
              <dd>{`${account.listedCount} / ${account.productLimit} 件`}</dd>
            </div>
            <div>
              <dt>今日已发布</dt>
              <dd>{`${account.todayPublished} 件`}</dd>
            </div>
            <div>
              <dt>客资查看权限</dt>
              <dd>{account.leadAccess}</dd>
            </div>
            <div>
              <dt>优先展示权重</dt>
              <dd>{account.priority}</dd>
            </div>
          </dl>
        </section>

        <section className="account-section">
          <h2>升级/续费</h2>
          <div className="plan-list">
            {account.plans.map((plan) => {
              const isSelected = selectedMonths === plan.months
              return (
                <button
                  className={`plan-row ${isSelected ? 'is-selected' : ''}`}
                  key={plan.months}
                  type="button"
                  onClick={() => setSelectedMonths(plan.months)}
                >
                  <span>{plan.title}</span>
                  <strong>{formatPrice(plan.amountCents)}</strong>
                  {isSelected ? (
                    <em>
                      <Check size={15} />
                    </em>
                  ) : null}
                </button>
              )
            })}
          </div>
        </section>

        {message ? <p className="account-message">{message}</p> : null}

        <button className="account-action" disabled={isPaying} type="button" onClick={() => void handlePay()}>
          {isPaying ? '正在跳转支付...' : isVip ? '续费VIP' : '升级为VIP'}
        </button>
      </div>
    </section>
  )
}

function AccountHeader({ isVip, onBack }: { isVip: boolean; onBack: () => void }) {
  return (
    <header className="profile-header">
      <button type="button" aria-label="返回个人中心" onClick={onBack}>
        <ChevronLeft size={31} strokeWidth={2.4} />
      </button>
      <h1>账户权限</h1>
      <span>{isVip ? <em className="account-vip-tag">VIP</em> : null}</span>
    </header>
  )
}
