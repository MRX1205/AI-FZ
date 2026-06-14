import { ChevronLeft } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError, apiAssetUrl, apiGet, apiPatch } from '../api/client'
import { ImagePreview } from '../components/ImagePreview'
import type { MerchantAuthSession, MerchantLead } from '../types/domain'
import {
  clearMerchantSession,
  getAuthHeaders,
  readMerchantSession,
  updateMerchantSessionMerchant,
} from './merchantAuthStorage'

function formatFullTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
    .format(new Date(value))
    .replaceAll('/', '-')
}

function formatPrice(cents: number) {
  return `${Math.round(cents / 100).toLocaleString('zh-CN')}元`
}

export function MerchantLeadDetailPage() {
  const navigate = useNavigate()
  const { id } = useParams()
  const session = useMemo(() => readMerchantSession(), [])
  const token = session?.token ?? ''
  const [merchant, setMerchant] = useState<MerchantAuthSession['merchant'] | null>(session?.merchant ?? null)
  const [lead, setLead] = useState<MerchantLead | null>(null)
  const [message, setMessage] = useState('')
  const [isPreviewOpen, setIsPreviewOpen] = useState(false)

  useEffect(() => {
    if (!token) {
      navigate('/merchant/auth', { replace: true })
      return
    }
    if (!id) return

    Promise.all([
      apiGet<MerchantAuthSession['merchant']>('/api/auth/me', {
        headers: getAuthHeaders(token),
      }),
      apiGet<MerchantLead>(`/api/merchant/leads/${id}`, {
        headers: getAuthHeaders(token),
      }),
    ])
      .then(([nextMerchant, nextLead]) => {
        setMerchant(nextMerchant)
        updateMerchantSessionMerchant(nextMerchant)
        setLead(nextLead)
      })
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) {
          clearMerchantSession()
          navigate('/merchant/auth', { replace: true })
          return
        }
        navigate('/merchant/leads', { replace: true })
      })
  }, [id, navigate, token])

  async function handleCopyEmail() {
    if (!lead) return
    await navigator.clipboard.writeText(lead.buyerEmail)
    setMessage('邮箱已复制')
  }

  async function handleMarkContacted() {
    if (!lead || !token) return
    const response = await apiPatch<MerchantLead>(
      `/api/merchant/leads/${lead.id}/status`,
      { status: 'contacted' },
      { headers: getAuthHeaders(token) },
    )
    setLead(response)
    setMessage('已标记为已联系')
  }

  const isVip = merchant?.tier === 'vip'

  return (
    <section className="merchant-lead-detail-page">
      <header className="profile-header lead-detail-header">
        <button type="button" aria-label="返回客资列表" onClick={() => navigate('/merchant/leads')}>
          <ChevronLeft size={31} strokeWidth={2.4} />
        </button>
        <h1>客资详情</h1>
        <span>
          {isVip && lead ? (
            <button type="button" onClick={() => void handleMarkContacted()}>
              标记已联系
            </button>
          ) : null}
        </span>
      </header>

      {!lead ? (
        <div className="profile-loading">加载中...</div>
      ) : (
        <>
          <div className="lead-detail-scroll">
            <section className="lead-detail-fields">
              <DetailRow label="留言时间" value={formatFullTime(lead.submittedAt)} />
              <DetailRow label="用户需求原文" value={lead.message} isMultiline />
              <div className="lead-detail-row">
                <strong>关联商品</strong>
                <div className="lead-product-mini">
                  <button type="button" aria-label="预览关联商品图片" onClick={() => setIsPreviewOpen(true)}>
                    <img alt="" src={apiAssetUrl(lead.productImageUrl)} />
                  </button>
                  <span>
                    <em>{lead.productTitle}</em>
                    <small>{formatPrice(lead.productPriceCents)}</small>
                  </span>
                </div>
              </div>
              <div className="lead-detail-row">
                <strong>用户邮箱</strong>
                <span>
                  {lead.buyerEmail}
                  <small>{isVip ? '（VIP可见完整邮箱）' : '（升级VIP可见完整邮箱）'}</small>
                </span>
              </div>
              <DetailRow label="商家账号" value={lead.merchantEmail} />
            </section>
            {message ? <p className="lead-detail-message">{message}</p> : null}
          </div>

          {isVip ? (
            <div className="lead-detail-actions is-vip">
              <button type="button" onClick={() => void handleCopyEmail()}>
                复制邮箱
              </button>
              <button type="button" onClick={() => void handleMarkContacted()}>
                标记已联系
              </button>
            </div>
          ) : (
            <div className="lead-detail-actions">
              <button type="button" onClick={() => navigate('/merchant/account')}>
                升级VIP，查看完整联系方式
              </button>
            </div>
          )}
          {isPreviewOpen ? (
            <ImagePreview
              images={[apiAssetUrl(lead.productImageUrl)]}
              initialIndex={0}
              alt={lead.productTitle}
              onClose={() => setIsPreviewOpen(false)}
            />
          ) : null}
        </>
      )}
    </section>
  )
}

function DetailRow({
  label,
  value,
  isMultiline,
}: {
  label: string
  value: string
  isMultiline?: boolean
}) {
  return (
    <div className={`lead-detail-row ${isMultiline ? 'is-multiline' : ''}`}>
      <strong>{label}</strong>
      <span>{value}</span>
    </div>
  )
}
