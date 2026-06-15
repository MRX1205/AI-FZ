import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError, apiAssetUrl, apiGet, apiUpload } from '../api/client'
import { ImagePreview } from '../components/ImagePreview'
import { MerchantTabBar } from '../components/MerchantTabBar'
import type { MerchantProduct, MerchantProductDraftGenerateResponse } from '../types/domain'
import { clearMerchantSession, getAuthHeaders, readMerchantSession } from './merchantAuthStorage'

function formatPrice(cents: number) {
  if (cents <= 0) return '待确认'
  return `${Math.round(cents / 100).toLocaleString('zh-CN')}元`
}

export function MerchantPublishResultPage() {
  const navigate = useNavigate()
  const { id } = useParams()
  const token = useMemo(() => readMerchantSession()?.token ?? '', [])
  const [product, setProduct] = useState<MerchantProduct | null>(null)
  const [activeImage, setActiveImage] = useState(0)
  const [message, setMessage] = useState('')
  const [loadError, setLoadError] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [previewIndex, setPreviewIndex] = useState<number | null>(null)

  const hydrateProduct = useCallback((response: MerchantProduct) => {
    setProduct(response)
    setActiveImage(0)
    setLoadError('')
  }, [])

  useEffect(() => {
    if (!token) {
      navigate('/merchant/auth', { replace: true })
      return
    }
    if (!id) {
      navigate('/merchant/publish', { replace: true })
      return
    }

    apiGet<MerchantProduct>(`/api/merchant/products/${id}`, {
      headers: getAuthHeaders(token),
      cache: 'no-store',
    })
      .then(hydrateProduct)
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) {
          clearMerchantSession()
          navigate('/merchant/auth', { replace: true })
          return
        }
        setLoadError(error instanceof ApiError ? error.message : 'AI生成结果加载失败')
      })
  }, [hydrateProduct, id, navigate, token])

  async function handleRegenerate() {
    if (!product || !token || isGenerating) return
    setMessage('')
    setIsGenerating(true)
    const formData = new FormData()
    formData.append('productId', product.id)

    try {
      const generatedProduct = await apiUpload<MerchantProductDraftGenerateResponse>(
        '/api/merchant/products/drafts/generate',
        formData,
        { headers: getAuthHeaders(token) },
      )
      if (!generatedProduct?.id) {
        setMessage('生成结果异常，请稍后重试')
        return
      }
      hydrateProduct(generatedProduct)
      setMessage('已重新生成')
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearMerchantSession()
        navigate('/merchant/auth', { replace: true })
        return
      }
      setMessage(error instanceof ApiError ? error.message : '重新生成失败，请稍后重试')
    } finally {
      setIsGenerating(false)
    }
  }

  const imageUrls = product?.imageUrls?.length ? product.imageUrls : ['/mock-products/jade-1.png']
  const resolvedImageUrls = imageUrls.map(apiAssetUrl)
  const imageCount = imageUrls.length

  return (
    <section className="merchant-publish-result-page">
      <header className="profile-header publish-result-header">
        <button type="button" aria-label="返回发布商品" onClick={() => navigate('/merchant/publish')}>
          <ChevronLeft size={31} strokeWidth={2.4} />
        </button>
        <h1>AI智能生成结果</h1>
        <button
          className="publish-result-regenerate"
          type="button"
          disabled={!product || isGenerating}
          onClick={() => void handleRegenerate()}
        >
          {isGenerating ? '生成中...' : '重新生成'}
        </button>
      </header>

      {loadError ? (
        <div className="profile-loading publish-result-error">
          <strong>{loadError}</strong>
          <button type="button" onClick={() => navigate('/merchant/publish')}>
            返回发布页
          </button>
        </div>
      ) : !product ? (
        <div className="profile-loading">加载中...</div>
      ) : (
        <div className="publish-result-scroll">
          <section className="publish-carousel publish-result-carousel" aria-label="商品图片预览">
            <img
              src={resolvedImageUrls[activeImage]}
              alt={product.title || '商品图片'}
              role="button"
              tabIndex={0}
              onClick={() => setPreviewIndex(activeImage)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') setPreviewIndex(activeImage)
              }}
            />
            {imageCount > 1 ? (
              <>
                <button
                  className="publish-carousel-prev"
                  type="button"
                  aria-label="上一张图片"
                  onClick={() => setActiveImage((current) => (current - 1 + imageCount) % imageCount)}
                >
                  <ChevronLeft size={23} />
                </button>
                <button
                  className="publish-carousel-next"
                  type="button"
                  aria-label="下一张图片"
                  onClick={() => setActiveImage((current) => (current + 1) % imageCount)}
                >
                  <ChevronRight size={23} />
                </button>
              </>
            ) : null}
            <div className="publish-carousel-dots" aria-hidden="true">
              {imageUrls.map((imageUrl, index) => (
                <span className={activeImage === index ? 'is-active' : ''} key={`${imageUrl}-${index}`} />
              ))}
            </div>
            <em>
              {activeImage + 1}/{imageCount}
            </em>
          </section>

          <section className="publish-result-content">
            <ResultField label="商品标题" hint="（10字以内）" value={product.title} />
            <ResultField label="商品简介" hint="（50字以内）" value={product.summary} />
            <ResultField label="商品详情" hint="（300字以内）" value={product.detail} multiline />

            <div className="publish-result-field">
              <strong>
                商品标签 <small>（10个）</small>
              </strong>
              <div className="publish-tag-list">
                {(product.tags ?? []).map((tag) => (
                  <span className="publish-tag publish-result-tag" key={tag}>
                    {tag}
                  </span>
                ))}
              </div>
            </div>

            <div className="publish-result-price">
              <strong>
                预估售价 <small>（元）</small>
              </strong>
              <em>{formatPrice(product.priceCents)}</em>
            </div>
          </section>
          {message ? <p className="product-edit-message">{message}</p> : null}
        </div>
      )}
      <MerchantTabBar />
      {previewIndex !== null ? (
        <ImagePreview
          images={resolvedImageUrls}
          initialIndex={previewIndex}
          alt={product?.title || '商品图片'}
          onClose={() => setPreviewIndex(null)}
        />
      ) : null}
    </section>
  )
}

function ResultField({
  label,
  hint,
  value,
  multiline = false,
}: {
  label: string
  hint: string
  value: string
  multiline?: boolean
}) {
  return (
    <div className="publish-result-field">
      <strong>
        {label} <small>{hint}</small>
      </strong>
      <p className={multiline ? 'is-multiline' : ''}>{value || '待补充'}</p>
    </div>
  )
}
