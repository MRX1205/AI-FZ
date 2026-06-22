import { ChevronLeft, ChevronRight, Mail, Share2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError, apiAssetUrl, apiGet, apiPost } from '../api/client'
import { ImagePreview } from '../components/ImagePreview'
import type {
  PublicProduct,
  PublicProductContactPayload,
  PublicProductContactResponse,
} from '../types/domain'
import { shareProduct } from '../utils/productShare'

function formatPrice(priceCents: number) {
  return `￥${Math.round(priceCents / 100)}`
}

function isValidEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim())
}

export function ProductDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [product, setProduct] = useState<PublicProduct | null>(null)
  const [activeImage, setActiveImage] = useState(0)
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [previewIndex, setPreviewIndex] = useState<number | null>(null)

  const imageUrls = useMemo(() => {
    const urls = product?.imageUrls?.length ? product.imageUrls : ['/mock-products/jade-1.png']
    return urls.map(apiAssetUrl)
  }, [product])
  const visibleTags = product?.tags.slice(0, 10) ?? []
  const heroImage = imageUrls[Math.min(activeImage, imageUrls.length - 1)] ?? '/mock-products/jade-1.png'

  useEffect(() => {
    if (!id) return
    apiGet<PublicProduct>(`/api/products/${id}`)
      .then((response) => {
        setProduct(response)
        setActiveImage(0)
      })
      .catch((error) => {
        setLoadError(error instanceof ApiError ? error.message : '商品加载失败')
      })
  }, [id])

  async function handleContactSubmit() {
    if (!id || !product || isSubmitting) return
    const nextEmail = email.trim()
    if (!isValidEmail(nextEmail)) {
      setMessage('请输入正确的联系邮箱')
      return
    }

    setIsSubmitting(true)
    setMessage('')
    try {
      const response = await apiPost<PublicProductContactResponse>(
        `/api/products/${id}/contact`,
        { buyerEmail: nextEmail } satisfies PublicProductContactPayload,
      )
      setMessage(response.message)
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : '提交失败，请稍后再试')
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleShare() {
    if (!product) return
    try {
      const result = await shareProduct(product)
      if (result === 'copied') setMessage('商品链接已复制')
      if (result === 'shared') setMessage('已打开系统分享')
    } catch {
      setMessage('分享失败，请稍后再试')
    }
  }

  return (
    <section className="public-product-page">
      <header className="public-product-header">
        <button type="button" aria-label="返回" onClick={() => navigate(-1)}>
          <ChevronLeft size={32} strokeWidth={2.4} />
        </button>
        <h1>商品详情</h1>
        <button type="button" aria-label="分享商品" onClick={() => void handleShare()}>
          <Share2 size={25} strokeWidth={2.3} />
        </button>
      </header>

      {!product ? (
        <div className="public-product-state">
          {loadError ? (
            <>
              <strong>商品加载失败</strong>
              <span>{loadError}</span>
            </>
          ) : (
            <span>加载中...</span>
          )}
        </div>
      ) : (
        <div className="public-product-scroll">
          <section className="public-product-gallery">
            <button
              className="public-product-image-button"
              type="button"
              aria-label="预览商品图片"
              onClick={() => setPreviewIndex(activeImage)}
            >
              <img src={heroImage} alt={product.title} />
            </button>
            {imageUrls.length > 1 ? (
              <>
                <button
                  className="public-product-nav public-product-prev"
                  type="button"
                  aria-label="上一张图片"
                  onClick={() => setActiveImage((current) => (current - 1 + imageUrls.length) % imageUrls.length)}
                >
                  <ChevronLeft size={24} />
                </button>
                <button
                  className="public-product-nav public-product-next"
                  type="button"
                  aria-label="下一张图片"
                  onClick={() => setActiveImage((current) => (current + 1) % imageUrls.length)}
                >
                  <ChevronRight size={24} />
                </button>
              </>
            ) : null}
            <span className="public-product-count">
              {activeImage + 1}/{imageUrls.length}
            </span>
            <div className="public-product-dots" aria-label="商品图片轮播">
              {imageUrls.map((imageUrl, index) => (
                <button
                  className={activeImage === index ? 'is-active' : ''}
                  key={`${imageUrl}-${index}`}
                  type="button"
                  aria-label={`查看第${index + 1}张图片`}
                  onClick={() => setActiveImage(index)}
                />
              ))}
            </div>
          </section>

          <section className="public-product-main">
            <h2>{product.title}</h2>
            <div className="public-product-price-row">
              <strong>{formatPrice(product.priceCents)}</strong>
              <span>预估价</span>
              <em className={product.merchantTier === 'vip' ? 'tier-vip' : 'tier-free'}>
                {product.merchantTier === 'vip' ? 'VIP' : '商家'}
              </em>
            </div>
            <div className="public-product-tags">
              {visibleTags.slice(0, 6).map((tag) => (
                <span key={tag}>{tag}</span>
              ))}
              {visibleTags.length > 6 ? <span>...</span> : null}
            </div>
          </section>

          <section className="public-product-copy">
            <h3>AI简介（50字）</h3>
            <p>{product.summary}</p>
            <h3>AI详情（300字）</h3>
            <p>{product.detail}</p>
          </section>

          <section className="public-product-copy">
            <h3>商品标签（10个）</h3>
            <div className="public-product-tags is-wrap">
              {visibleTags.map((tag) => (
                <span key={tag}>{tag}</span>
              ))}
            </div>
          </section>

          <section className="public-contact-panel">
            <h3>
              联系卖家 <small>（留下邮箱，卖家将主动联系您）</small>
            </h3>
            <label className="public-contact-input">
              <Mail size={22} />
              <input
                value={email}
                inputMode="email"
                type="email"
                placeholder="请输入您的联系邮箱"
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <button type="button" disabled={isSubmitting} onClick={() => void handleContactSubmit()}>
              {isSubmitting ? '提交中...' : '提交意向，等待卖家联系'}
            </button>
            {message ? <p>{message}</p> : null}
            <small>我们尊重您的隐私，仅用于卖家联系您</small>
          </section>
        </div>
      )}
      {previewIndex !== null ? (
        <ImagePreview
          images={imageUrls}
          initialIndex={previewIndex}
          alt={product?.title ?? '商品图片'}
          onClose={() => setPreviewIndex(null)}
        />
      ) : null}
    </section>
  )
}
