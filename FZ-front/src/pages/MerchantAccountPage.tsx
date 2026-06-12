import { BriefcaseBusiness, ChevronLeft, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, apiGet } from '../api/client'
import type { MerchantAuthSession, MerchantProfileResponse } from '../types/domain'

const MERCHANT_SESSION_KEY = 'fz_merchant_session_v1'

function readMerchantSession(): MerchantAuthSession | null {
  try {
    const raw = localStorage.getItem(MERCHANT_SESSION_KEY)
    return raw ? (JSON.parse(raw) as MerchantAuthSession) : null
  } catch {
    return null
  }
}

function formatDate(value?: string | null) {
  if (!value) return '2025-05-20'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
    .format(new Date(value))
    .replaceAll('/', '-')
}

export function MerchantAccountPage() {
  const navigate = useNavigate()
  const token = useMemo(() => readMerchantSession()?.token ?? '', [])
  const [profile, setProfile] = useState<MerchantProfileResponse | null>(null)
  const [isDialogOpen, setIsDialogOpen] = useState(false)

  useEffect(() => {
    if (!token) {
      navigate('/merchant/auth', { replace: true })
      return
    }

    apiGet<MerchantProfileResponse>('/api/merchant/profile', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(setProfile)
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) {
          localStorage.removeItem(MERCHANT_SESSION_KEY)
          navigate('/merchant/auth', { replace: true })
        }
      })
  }, [navigate, token])

  if (!profile) {
    return (
      <section className="merchant-account-page">
        <AccountHeader isVip={false} onBack={() => navigate('/merchant/profile')} />
        <div className="profile-loading">加载中...</div>
      </section>
    )
  }

  const isVip = profile.tier === 'vip'
  const limits = isVip
    ? {
        productLimit: '100件',
        todayPublished: '36件',
        leadAccess: '无限查看全部',
        priority: '高',
        buttonText: '联系运营续费',
      }
    : {
        productLimit: '2件',
        todayPublished: '0件',
        leadAccess: '无查看权限',
        priority: '低',
        buttonText: '联系运营升级',
      }

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
            <p>{isVip ? `有效期至 ${formatDate(profile.vipExpiresAt)}` : '有效期至 永久'}</p>
          </div>
          {isVip ? <button type="button">查看权益</button> : null}
        </section>

        <section className="account-section">
          <h2>当前权限</h2>
          <dl className="permission-table">
            <div>
              <dt>商品发布上限</dt>
              <dd>{limits.productLimit}</dd>
            </div>
            <div>
              <dt>今日已发布</dt>
              <dd>{limits.todayPublished}</dd>
            </div>
            <div>
              <dt>客资查看权限</dt>
              <dd>{limits.leadAccess}</dd>
            </div>
            <div>
              <dt>优先展示权重</dt>
              <dd>{limits.priority}</dd>
            </div>
          </dl>
        </section>

        <section className="account-section">
          <h2>升级/续费</h2>
          <div className="plan-list">
            <div>
              <span>VIP会员（12个月）</span>
              <strong>￥2999</strong>
            </div>
            <div>
              <span>VIP会员（6个月）</span>
              <strong>￥1688</strong>
            </div>
          </div>
        </section>

        <button className="account-action" type="button" onClick={() => setIsDialogOpen(true)}>
          {limits.buttonText}
        </button>
      </div>

      {isDialogOpen ? (
        <div className="account-dialog-backdrop" role="presentation">
          <div className="account-dialog" role="dialog" aria-modal="true" aria-label="联系运营">
            <button type="button" aria-label="关闭" onClick={() => setIsDialogOpen(false)}>
              <X size={20} />
            </button>
            <h2>{limits.buttonText}</h2>
            <p>请联系运营开通/续费VIP</p>
            <button className="account-dialog-confirm" type="button" onClick={() => setIsDialogOpen(false)}>
              确定
            </button>
          </div>
        </div>
      ) : null}
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
