import { ChevronLeft, Edit3, Share2, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ApiError, apiAssetUrl, apiDelete, apiGet } from '../api/client'
import { ImagePreview } from '../components/ImagePreview'
import type { MerchantProduct, MerchantProductListResponse, MerchantProductStatus } from '../types/domain'
import {
  clearMerchantSession,
  getAuthHeaders,
  readMerchantSession,
  updateMerchantSessionMerchant,
} from './merchantAuthStorage'

type ProductTab = 'all' | MerchantProductStatus

const productTabs: Array<{ key: ProductTab; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'listed', label: '已上架' },
  { key: 'draft', label: '草稿' },
  { key: 'unlisted', label: '已下架' },
]

function formatPrice(cents: number) {
  return `${Math.round(cents / 100).toLocaleString('zh-CN')}元`
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
  const location = useLocation()
  const token = useMemo(() => readMerchantSession()?.token ?? '', [])
  const locationMessage = (location.state as { message?: string } | null)?.message ?? ''
  const [activeTab, setActiveTab] = useState<ProductTab>('all')
  const [data, setData] = useState<MerchantProductListResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [shareMessage, setShareMessage] = useState(locationMessage)
  const [deleteTarget, setDeleteTarget] = useState<MerchantProduct | null>(null)
  const [previewProduct, setPreviewProduct] = useState<MerchantProduct | null>(null)
  const hasLoadedRef = useRef(false)
  const activeTabRef = useRef<ProductTab>('all')

  const refreshProducts = useCallback(async (status: ProductTab = activeTabRef.current) => {
    if (!token) return
    if (!hasLoadedRef.current) setIsLoading(true)
    setLoadError('')
    try {
      const response = await apiGet<MerchantProductListResponse>(
        `/api/merchant/products?status=${status}&_ts=${Date.now()}`,
        {
          headers: getAuthHeaders(token),
          cache: 'no-store',
        },
      )
      hasLoadedRef.current = true
      setData(response)
      updateMerchantSessionMerchant(response.merchant)
    } catch (error) {
      if (error instanceof ApiError) {
        setLoadError(error.message)
      } else {
        setLoadError('商品数据加载失败')
      }
      throw error
    } finally {
      setIsLoading(false)
    }
  }, [token])

  useEffect(() => {
    if (!token) {
      navigate('/merchant/auth', { replace: true })
      return
    }

    activeTabRef.current = 'all'
    void Promise.resolve()
      .then(() => {
        setActiveTab('all')
        return refreshProducts('all')
      })
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) {
          clearMerchantSession()
          navigate('/merchant/auth', { replace: true })
        }
      })
  }, [location.key, navigate, refreshProducts, token])

  useEffect(() => {
    if (!token) return
    const handleFocus = () => {
      void refreshProducts(activeTabRef.current)
    }
    window.addEventListener('focus', handleFocus)
    return () => window.removeEventListener('focus', handleFocus)
  }, [refreshProducts, token])

  useEffect(() => {
    if (!locationMessage) return
    const timer = window.setTimeout(() => {
      setShareMessage(locationMessage)
      navigate(location.pathname, { replace: true, state: null })
    }, 0)
    return () => window.clearTimeout(timer)
  }, [location.pathname, locationMessage, navigate])

  useEffect(() => {
    if (!shareMessage) return
    const timer = window.setTimeout(() => setShareMessage(''), 1800)
    return () => window.clearTimeout(timer)
  }, [shareMessage])

  async function handleDelete() {
    if (!deleteTarget || !token) return
    await apiDelete<{ ok: boolean }>(`/api/merchant/products/${deleteTarget.id}`, {
      headers: getAuthHeaders(token),
    })
    setDeleteTarget(null)
    await refreshProducts()
  }

  const isVip = data?.merchant.tier === 'vip'
  const hasRemaining = (data?.quota.remaining ?? 0) > 0
  const publishText = hasRemaining ? '+ 发布新商品' : isVip ? '请下架部分商品后再发布' : '升级VIP发布更多商品'

  function handlePublishClick() {
    if (hasRemaining) {
      navigate('/merchant/publish')
      return
    }
    setShareMessage(isVip ? '请下架部分商品后再发布' : '需升级VIP提升发布额度')
  }

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
            onClick={() => setShareMessage('请选择已上架商品进入编辑页分享')}
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
              activeTabRef.current = tab.key
              setActiveTab(tab.key)
              void refreshProducts(tab.key)
            }}
          >
            {data ? `${tab.label}(${data.counts[tab.key]})` : tab.label}
          </button>
        ))}
      </nav>

      <div className="products-scroll">
        {loadError ? (
          <div className="product-empty">
            <strong>商品数据加载失败</strong>
            <span>{loadError}</span>
            <button type="button" onClick={() => void refreshProducts()}>
              重新加载
            </button>
          </div>
        ) : isLoading || !data ? (
          <div className="profile-loading">加载中...</div>
        ) : (
          <>
            {data.products.length === 0 ? (
              <div className="product-empty">
                <strong>暂无商品</strong>
                <span>点击底部按钮发布新的翡翠商品</span>
              </div>
            ) : (
              <ul className="product-list">
                {data.products.map((product) => (
                  <li key={product.id}>
                    <button
                      className="product-list-image-button"
                      type="button"
                      aria-label={`预览${product.title}图片`}
                      onClick={() => setPreviewProduct(product)}
                    >
                      <img src={apiAssetUrl(product.imageUrls[0] ?? '/mock-products/jade-1.png')} alt={product.title} />
                    </button>
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
          </>
        )}
      </div>

      <div className="product-publish-bar">
        <button className={!hasRemaining ? 'is-disabled' : ''} type="button" onClick={handlePublishClick}>
          {publishText}
        </button>
      </div>

      {shareMessage ? <p className="product-toast">{shareMessage}</p> : null}
      {previewProduct ? (
        <ImagePreview
          images={(previewProduct.imageUrls.length ? previewProduct.imageUrls : ['/mock-products/jade-1.png']).map(
            apiAssetUrl,
          )}
          initialIndex={0}
          alt={previewProduct.title}
          onClose={() => setPreviewProduct(null)}
        />
      ) : null}
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
