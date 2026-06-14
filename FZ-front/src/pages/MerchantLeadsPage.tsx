import { ChevronLeft } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, apiGet } from '../api/client'
import type { MerchantLeadListResponse, MerchantLeadStatus } from '../types/domain'
import {
  clearMerchantSession,
  getAuthHeaders,
  readMerchantSession,
  updateMerchantSessionMerchant,
} from './merchantAuthStorage'

type LeadTab = 'all' | MerchantLeadStatus

const tabs: Array<{ key: LeadTab; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'pending', label: '待联系' },
  { key: 'contacted', label: '已联系' },
]

function formatLeadTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

function statusText(status: MerchantLeadStatus) {
  return status === 'contacted' ? '已联系' : '待联系'
}

export function MerchantLeadsPage() {
  const navigate = useNavigate()
  const token = useMemo(() => readMerchantSession()?.token ?? '', [])
  const [activeTab, setActiveTab] = useState<LeadTab>('all')
  const [data, setData] = useState<MerchantLeadListResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!token) {
      navigate('/merchant/auth', { replace: true })
      return
    }

    apiGet<MerchantLeadListResponse>(`/api/merchant/leads?status=${activeTab}`, {
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
      .finally(() => setIsLoading(false))
  }, [activeTab, navigate, token])

  const isVip = data?.merchant.tier === 'vip'

  return (
    <section className="merchant-leads-page">
      <header className="profile-header">
        <button type="button" aria-label="返回商家后台" onClick={() => navigate('/merchant/dashboard')}>
          <ChevronLeft size={31} strokeWidth={2.4} />
        </button>
        <h1>客资列表</h1>
        <span aria-hidden="true" />
      </header>

      <nav className="leads-tabs" aria-label="客资状态筛选">
        {tabs.map((tab) => (
          <button
            className={activeTab === tab.key ? 'is-active' : ''}
            key={tab.key}
            type="button"
            onClick={() => {
              if (activeTab === tab.key) return
              setIsLoading(true)
              setActiveTab(tab.key)
            }}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div className={`leads-scroll ${isVip ? '' : 'has-upgrade-bar'}`}>
        {isLoading || !data ? (
          <div className="profile-loading">加载中...</div>
        ) : (
          <ul className="lead-list">
            {data.leads.map((lead) => (
              <li key={lead.id}>
                <button type="button" onClick={() => navigate(`/merchant/leads/${lead.id}`)}>
                  <time>{formatLeadTime(lead.submittedAt)}</time>
                  <span className="lead-row-main">
                    <strong>{lead.message}</strong>
                    <small>{lead.productTitle}</small>
                  </span>
                  <span className="lead-row-side">
                    <em className={lead.status === 'contacted' ? 'is-contacted' : ''}>
                      {statusText(lead.status)}
                    </em>
                    <small>{lead.buyerEmail}</small>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {!isVip ? (
        <div className="lead-upgrade-bar">
          <p>免费商家仅显示部分邮箱，升级VIP查看全部</p>
          <button type="button" onClick={() => navigate('/merchant/account')}>
            升级VIP，查看全部联系方式
          </button>
        </div>
      ) : null}
    </section>
  )
}
