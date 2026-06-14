import { Camera, ChevronLeft, ChevronRight, Plus, Trash2, X } from 'lucide-react'
import { type ChangeEvent, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError, apiAssetUrl, apiDelete, apiGet, apiPatch, apiUpload } from '../api/client'
import type {
  MerchantProduct,
  MerchantProductStatus,
  MerchantProductUpdatePayload,
} from '../types/domain'
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

export function MerchantProductEditPage() {
  const navigate = useNavigate()
  const { id } = useParams()
  const token = useMemo(() => readMerchantSession()?.token ?? '', [])
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [product, setProduct] = useState<MerchantProduct | null>(null)
  const [title, setTitle] = useState('')
  const [summary, setSummary] = useState('')
  const [detail, setDetail] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [editingTagIndex, setEditingTagIndex] = useState<number | null>(null)
  const [price, setPrice] = useState('')
  const [message, setMessage] = useState('')
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [activeImage, setActiveImage] = useState(0)
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
      })
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) {
          clearMerchantSession()
          navigate('/merchant/auth', { replace: true })
          return
        }
        navigate('/merchant/products', { replace: true })
      })
  }, [id, navigate, token])

  function buildPayload(): MerchantProductUpdatePayload {
    return {
      title: title.trim(),
      summary: summary.trim(),
      detail: detail.trim(),
      tags: normalizeTags(tags),
      priceCents: centsFromYuan(price),
    }
  }

  function hasChanged(payload: MerchantProductUpdatePayload) {
    if (!product) return false
    return (
      payload.title !== product.title ||
      payload.summary !== product.summary ||
      payload.detail !== product.detail ||
      payload.priceCents !== product.priceCents ||
      !sameTags(payload.tags, product.tags)
    )
  }

  function hydrateProduct(nextProduct: MerchantProduct) {
    setProduct(nextProduct)
    setTitle(nextProduct.title)
    setSummary(nextProduct.summary)
    setDetail(nextProduct.detail)
    setTags(nextProduct.tags)
    setPrice(yuanFromCents(nextProduct.priceCents))
  }

  async function saveProduct() {
    if (!product || !token) return null
    const payload = buildPayload()
    if (!payload.title || !payload.summary || !payload.detail || payload.priceCents <= 0) {
      setMessage('请完整填写商品信息和价格')
      return null
    }
    if (!hasChanged(payload)) {
      setMessage('暂无修改')
      return product
    }

    setIsSaving(true)
    try {
      const savedProduct = await apiPatch<MerchantProduct>(`/api/merchant/products/${product.id}`, payload, {
        headers: getAuthHeaders(token),
      })
      hydrateProduct(savedProduct)
      setMessage('已保存')
      return savedProduct
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearMerchantSession()
        navigate('/merchant/auth', { replace: true })
        return null
      }
      setMessage(error instanceof ApiError ? error.message : '保存失败，请稍后重试')
      return null
    } finally {
      setIsSaving(false)
    }
  }

  async function handleSaveAndBack() {
    const response = await saveProduct()
    if (response) navigate('/merchant/products', { state: { refreshAt: Date.now() } })
  }

  async function handleStatusChange(nextStatus: MerchantProductStatus) {
    const saved = await saveProduct()
    if (!saved || !token) return
    try {
      await apiPatch<MerchantProduct>(
        `/api/merchant/products/${saved.id}/status`,
        { status: nextStatus },
        { headers: getAuthHeaders(token) },
      )
      navigate('/merchant/products', { state: { refreshAt: Date.now() } })
    } catch (error) {
      if (error instanceof ApiError && error.status === 400) {
        setMessage(error.message)
      }
    }
  }

  async function handleDelete() {
    if (!product || !token) return
    await apiDelete<{ ok: boolean }>(`/api/merchant/products/${product.id}`, {
      headers: getAuthHeaders(token),
    })
    navigate('/merchant/products', { state: { refreshAt: Date.now() } })
  }

  async function handleImageChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file || !product || !token) return

    const formData = new FormData()
    formData.append('file', file)
    formData.append('imageIndex', String(activeImage))
    const response = await apiUpload<MerchantProduct>(
      `/api/merchant/products/${product.id}/images/replace`,
      formData,
      { headers: getAuthHeaders(token) },
    )
    setProduct(response)
    setActiveImage((current) => Math.min(current, Math.max(response.imageUrls.length - 1, 0)))
    setMessage('图片已替换')
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

  const nextStatus: MerchantProductStatus = product?.status === 'listed' ? 'unlisted' : 'listed'
  const statusButtonText = product?.status === 'listed' ? '下架商品' : '上架商品'
  const imageUrls = product?.imageUrls.length ? product.imageUrls : ['/mock-products/jade-1.png']
  const imageCount = imageUrls.length

  return (
    <section className="merchant-product-edit-page">
      <header className="profile-header product-edit-header">
        <button type="button" aria-label="返回商品管理" onClick={() => navigate('/merchant/products')}>
          <ChevronLeft size={31} strokeWidth={2.4} />
        </button>
        <h1>编辑商品</h1>
        <span className="product-edit-top-actions">
          <button className="is-danger" type="button" onClick={() => setDeleteOpen(true)}>
            删除
          </button>
          <i aria-hidden="true" />
          <button type="button" disabled={isSaving} onClick={() => void handleSaveAndBack()}>
            {isSaving ? '保存中' : '保存'}
          </button>
        </span>
      </header>

      {!product ? (
        <div className="profile-loading">加载中...</div>
      ) : (
        <>
          <div className="product-edit-scroll">
            <section className="product-image-preview">
              <img src={apiAssetUrl(imageUrls[activeImage])} alt={product.title} />
              {imageCount > 1 ? (
                <>
                  <button
                    className="product-image-nav product-image-prev"
                    type="button"
                    aria-label="上一张图片"
                    onClick={() => setActiveImage((current) => (current - 1 + imageCount) % imageCount)}
                  >
                    <ChevronLeft size={23} />
                  </button>
                  <button
                    className="product-image-nav product-image-next"
                    type="button"
                    aria-label="下一张图片"
                    onClick={() => setActiveImage((current) => (current + 1) % imageCount)}
                  >
                    <ChevronRight size={23} />
                  </button>
                </>
              ) : null}
              <button type="button" onClick={() => fileInputRef.current?.click()}>
                <Camera size={18} />
                替换图片
              </button>
              <div className="product-image-dots" aria-hidden="true">
                {imageUrls.map((imageUrl, index) => (
                  <i className={activeImage === index ? 'is-active' : ''} key={`${imageUrl}-${index}`} />
                ))}
              </div>
              <span>
                {activeImage + 1}/{imageCount}
              </span>
              <input ref={fileInputRef} accept="image/*" type="file" onChange={(event) => void handleImageChange(event)} />
            </section>

            <section className="product-edit-form">
              <label>
                商品标题 <small>（10字以内）</small>
                <input value={title} maxLength={10} onChange={(event) => setTitle(event.target.value)} />
              </label>
              <label>
                商品简介 <small>（50字以内）</small>
                <input value={summary} maxLength={50} onChange={(event) => setSummary(event.target.value)} />
              </label>
              <label>
                商品详情 <small>（300字以内）</small>
                <textarea value={detail} maxLength={300} onChange={(event) => setDetail(event.target.value)} />
              </label>
              <div className="publish-tag-section">
                <strong>
                  商品标签 <small>（最多10个）</small>
                </strong>
                <div className="publish-tag-list">
                  {tags.map((tag, index) => (
                    <span className="publish-tag" key={`edit-tag-${index}`}>
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

          <div className="product-edit-actions">
            <button type="button" disabled={isSaving} onClick={() => void handleStatusChange(nextStatus)}>
              {statusButtonText}
            </button>
            <button type="button" disabled={isSaving} onClick={() => void handleSaveAndBack()}>
              {isSaving ? '保存中...' : '保存修改'}
            </button>
          </div>
        </>
      )}

      {deleteOpen && product ? (
        <div className="product-dialog-backdrop" role="presentation">
          <div className="product-dialog" role="dialog" aria-modal="true" aria-label="确认删除商品">
            <Trash2 size={30} />
            <h2>确认删除商品</h2>
            <p>删除后将无法恢复「{product.title}」</p>
            <div>
              <button type="button" onClick={() => setDeleteOpen(false)}>
                取消
              </button>
              <button className="is-danger" type="button" onClick={() => void handleDelete()}>
                删除
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  )
}
