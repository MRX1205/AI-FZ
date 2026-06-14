import { ChevronLeft, ChevronRight, Plus, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError, apiAssetUrl, apiGet, apiPatch } from '../api/client'
import type { MerchantProduct, MerchantProductPublishPayload } from '../types/domain'
import { clearMerchantSession, getAuthHeaders, readMerchantSession } from './merchantAuthStorage'

function yuanFromCents(cents: number) {
  return String(Math.round(cents / 100))
}

function centsFromYuan(value: string) {
  const numeric = Number(value.replace(/[^\d.]/g, ''))
  if (!Number.isFinite(numeric) || numeric <= 0) return 0
  return Math.round(numeric * 100)
}

function normalizeTags(tags: string[]) {
  return tags.map((tag) => tag.trim()).filter(Boolean).slice(0, 10)
}

function sameTags(left: string[], right: string[]) {
  if (left.length !== right.length) return false
  return left.every((tag, index) => tag === right[index])
}

export function MerchantPublishEditPage() {
  const navigate = useNavigate()
  const { id } = useParams()
  const token = useMemo(() => readMerchantSession()?.token ?? '', [])
  const [product, setProduct] = useState<MerchantProduct | null>(null)
  const [activeImage, setActiveImage] = useState(0)
  const [title, setTitle] = useState('')
  const [summary, setSummary] = useState('')
  const [detail, setDetail] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [editingTagIndex, setEditingTagIndex] = useState<number | null>(null)
  const [price, setPrice] = useState('')
  const [message, setMessage] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    if (!token) {
      navigate('/merchant/auth', { replace: true })
      return
    }
    if (!id) return

    apiGet<MerchantProduct>(`/api/merchant/products/${id}`, {
      headers: getAuthHeaders(token),
    })
      .then((response) => {
        setProduct(response)
        setTitle(response.title)
        setSummary(response.summary)
        setDetail(response.detail)
        setTags(response.tags)
        setPrice(yuanFromCents(response.priceCents))
        setActiveImage(0)
      })
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) {
          clearMerchantSession()
          navigate('/merchant/auth', { replace: true })
          return
        }
        navigate('/merchant/publish', { replace: true })
      })
  }, [id, navigate, token])

  const buildPayload = useCallback((showValidation = true): MerchantProductPublishPayload | null => {
    const payload = {
      title: title.trim(),
      summary: summary.trim(),
      detail: detail.trim(),
      tags: normalizeTags(tags),
      priceCents: centsFromYuan(price),
    }
    if (!payload.title || !payload.summary || !payload.detail || payload.priceCents <= 0) {
      if (showValidation) setMessage('请完整填写商品信息和价格')
      return null
    }
    return payload
  }, [detail, price, summary, tags, title])

  function hasChanged(payload: MerchantProductPublishPayload) {
    if (!product) return false
    return (
      payload.title !== product.title ||
      payload.summary !== product.summary ||
      payload.detail !== product.detail ||
      payload.priceCents !== product.priceCents ||
      !sameTags(payload.tags, product.tags)
    )
  }

  async function handleSave() {
    if (!product || !token || isSaving) return
    const payload = buildPayload()
    if (!payload) return
    if (!hasChanged(payload)) {
      navigate('/merchant/publish')
      return
    }

    setIsSaving(true)
    try {
      await apiPatch<MerchantProduct>(`/api/merchant/products/${product.id}`, payload, {
        headers: getAuthHeaders(token),
      })
      navigate('/merchant/publish')
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearMerchantSession()
        navigate('/merchant/auth', { replace: true })
        return
      }
      setMessage(error instanceof ApiError ? error.message : '保存失败，请稍后重试')
    } finally {
      setIsSaving(false)
    }
  }

  function updateTag(index: number, value: string) {
    setTags((current) => current.map((tag, tagIndex) => (tagIndex === index ? value : tag)))
  }

  function removeTag(index: number) {
    setTags((current) => current.filter((_, tagIndex) => tagIndex !== index))
    setEditingTagIndex(null)
  }

  function addTag() {
    if (tags.length >= 10) {
      setMessage('最多添加10个标签')
      return
    }
    setTags((current) => [...current, '新标签'])
    setEditingTagIndex(tags.length)
  }

  const imageUrls = product?.imageUrls.length ? product.imageUrls : ['/mock-products/jade-1.png']
  const imageCount = imageUrls.length

  return (
    <section className="merchant-publish-edit-page">
      <header className="profile-header publish-edit-header">
        <button type="button" aria-label="返回发布商品" onClick={() => navigate('/merchant/publish')}>
          <ChevronLeft size={31} strokeWidth={2.4} />
        </button>
        <h1>编辑商品信息</h1>
        <button type="button" disabled={isSaving} onClick={() => void handleSave()}>
          保存
        </button>
      </header>

      {!product ? (
        <div className="profile-loading">加载中...</div>
      ) : (
        <>
          <div className="publish-edit-scroll">
            <section className="publish-carousel" aria-label="商品图片预览">
              <img src={apiAssetUrl(imageUrls[activeImage])} alt={product.title || '商品图片'} />
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

            <section className="product-edit-form publish-form">
              <label>
                商品标题 <small>（10字以内）</small>
                <input value={title} maxLength={10} onChange={(event) => setTitle(event.target.value)} />
              </label>
              <label>
                商品简介 <small>（50字以内）</small>
                <input value={summary} maxLength={50} onChange={(event) => setSummary(event.target.value)} />
              </label>
              <label>
                详情 <small>（300字以内）</small>
                <textarea value={detail} maxLength={300} onChange={(event) => setDetail(event.target.value)} />
              </label>

              <div className="publish-tag-section">
                <strong>
                  商品标签 <small>（最多10个）</small>
                </strong>
                <div className="publish-tag-list">
                  {tags.map((tag, index) => (
                    <span className="publish-tag" key={`publish-tag-${index}`}>
                      {editingTagIndex === index ? (
                        <input
                          autoFocus
                          value={tag}
                          onBlur={() => setEditingTagIndex(null)}
                          onChange={(event) => updateTag(index, event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter') setEditingTagIndex(null)
                          }}
                        />
                      ) : (
                        <button type="button" onClick={() => setEditingTagIndex(index)}>
                          {tag}
                        </button>
                      )}
                      <button type="button" aria-label="删除标签" onClick={() => removeTag(index)}>
                        <X size={14} />
                      </button>
                    </span>
                  ))}
                  <button className="publish-add-tag" type="button" onClick={addTag}>
                    <Plus size={16} />
                    添加标签
                  </button>
                </div>
              </div>

              <label>
                预估售价 <small>（元）</small>
                <input inputMode="decimal" value={price} onChange={(event) => setPrice(event.target.value)} />
              </label>
            </section>
            {message ? <p className="product-edit-message">{message}</p> : null}
          </div>

          <div className="publish-confirm-bar">
            <button type="button" disabled={isSaving} onClick={() => void handleSave()}>
              {isSaving ? '保存中...' : '保存'}
            </button>
          </div>
        </>
      )}
    </section>
  )
}
