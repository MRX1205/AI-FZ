import { ChevronLeft, Edit3, Share2, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, apiDelete, apiGet } from '../api/client'
import type { MerchantProduct, MerchantProductListResponse, MerchantProductStatus } from '../types/domain'
import { clearMerchantSession, getAuthHeaders, readMerchantSession } from './merchantAuthStorage'

type ProductTab = 'all' | MerchantProductStatus

const productTabs: Array<{ key: ProductTab; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'listed', label: '已上架' },
  { key: 'draft', label: '草稿' },
  { key: 'unlisted', label: '已下架' },
]

function formatPrice(cents: number) {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
    maximumFractionDigits: 0,
  }).format(cents / 100)
}

function formatProductTime(product: MerchantProduct) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(product.publishedAt ?? product.createdAt))
}

function statusText(status: MerchantProductStatus) {
  if (status === 'listed') return '已上架'
  if (status === 'unlisted') return '已下架'
  return '草稿'
}

export function MerchantProductsPage() {
  const navigate = useNavigate()
  const token = useMemo(() => readMerchantSession()?.token ?? '', [])
  const [activeTab, setActiveTab] = useState<ProductTab>('all')
  const [data, setData] = useState<MerchantProductListResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [shareMessage, setShareMessage] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<MerchantProduct | null>(null)

  useEffect(() => {
    if (!token) {
      navigate('/merchant/auth', { replace: true })
      return
    }

    apiGet<MerchantProductListResponse>(`/api/merchant/products?status=${activeTab}`, {
      headers: getAuthHeaders(token),
    })
      .then(setData)
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) {
          clearMerchantSession()
          navigate('/merchant/auth', { replace: true })
        }
      })
      .finally(() => setIsLoading(false))
  }, [activeTab, navigate, token])

  async function refreshProducts() {
    if (!token) return
    const response = await apiGet<MerchantProductListResponse>(`/api/merchant/products?status=${activeTab}`, {
      headers: getAuthHeaders(token),
    })
    setData(response)
  }

  async function handleDelete() {
    if (!deleteTarget || !token) return
    await apiDelete<{ ok: boolean }>(`/api/merchant/products/${deleteTarget.id}`, {
      headers: getAuthHeaders(token),
    })
    setDeleteTarget(null)
    await refreshProducts()
  }

  const counts = data?.counts ?? { all: 0, listed: 0, draft: 0, unlisted: 0 }
  const isVip = data?.merchant.tier === 'vip'
  const hasRemaining = (data?.quota.remaining ?? 0) > 0
  const publishText = hasRemaining ? '+ 发布新商品' : isVip ? '请下架部分商品后再发布' : '升级VIP发布更多商品'

  return (
    <section className="merchant-products-page">
      <header className="profile-header">
        <button type="button" aria-label="返回商家后台" onClick={() => navigate('/merchant/dashboard')}>
          <ChevronLeft size={31} strokeWidth={2.4} />
        </button>
        <h1>商品管理</h1>
        <span>
          <button
            type="button"
            aria-label="分享商品管理"
            onClick={() => setShareMessage('分享功能暂未接入')}
          >
            <Share2 size={23} />
          </button>
        </span>
      </header>

      <nav className="products-tabs" aria-label="商品状态筛选">
        {productTabs.map((tab) => (
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
            {tab.label}({counts[tab.key]})
          </button>
        ))}
      </nav>

      <div className="products-scroll">
        {isLoading || !data ? (
          <div className="profile-loading">加载中...</div>
        ) : (
          <ul className="product-list">
            {data.products.map((product) => (
              <li key={product.id}>
                <img src={product.imageUrls[0] ?? '/mock-products/jade-1.png'} alt={product.title} />
                <div className="product-list-main">
                  <strong>{product.title}</strong>
                  <em>{formatPrice(product.priceCents)}</em>
                  <time>{formatProductTime(product)}</time>
                </div>
                <div className="product-list-side">
                  <span className={`product-status product-status-${product.status}`}>
                    {statusText(product.status)}
                  </span>
                  <button type="button" onClick={() => navigate(`/merchant/products/${product.id}/edit`)}>
                    <Edit3 size={17} />
                    编辑
                  </button>
                  <button className="is-danger" type="button" onClick={() => setDeleteTarget(product)}>
                    <Trash2 size={17} />
                    删除
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="product-publish-bar">
        <button type="button" disabled={!hasRemaining} onClick={() => navigate('/merchant/publish')}>
          {publishText}
        </button>
      </div>

      {shareMessage ? <p className="product-toast">{shareMessage}</p> : null}
      {deleteTarget ? (
        <ConfirmDialog
          title="确认删除商品"
          message={`删除后将无法恢复「${deleteTarget.title}」`}
          confirmText="删除"
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => void handleDelete()}
        />
      ) : null}
    </section>
  )
}

function ConfirmDialog({
  title,
  message,
  confirmText,
  onCancel,
  onConfirm,
}: {
  title: string
  message: string
  confirmText: string
  onCancel: () => void
  onConfirm: () => void
}) {
  return (
    <div className="product-dialog-backdrop" role="presentation">
      <div className="product-dialog" role="dialog" aria-modal="true" aria-label={title}>
        <h2>{title}</h2>
        <p>{message}</p>
        <div>
          <button type="button" onClick={onCancel}>
            取消
          </button>
          <button className="is-danger" type="button" onClick={onConfirm}>
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
