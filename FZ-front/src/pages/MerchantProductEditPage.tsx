import { Camera, ChevronLeft, Trash2 } from 'lucide-react'
import { type ChangeEvent, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError, apiDelete, apiGet, apiPatch, apiUpload } from '../api/client'
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

function tagsText(tags: string[]) {
  return tags.join(' ')
}

function parseTags(value: string) {
  return value
    .split(/[\s,，、]+/)
    .map((tag) => tag.trim())
    .filter(Boolean)
    .slice(0, 10)
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
  const [tags, setTags] = useState('')
  const [price, setPrice] = useState('')
  const [message, setMessage] = useState('')
  const [deleteOpen, setDeleteOpen] = useState(false)

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
        setTags(tagsText(response.tags))
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
      tags: parseTags(tags),
      priceCents: centsFromYuan(price),
    }
  }

  async function saveProduct() {
    if (!product || !token) return null
    const payload = buildPayload()
    if (!payload.title || !payload.summary || !payload.detail || payload.priceCents <= 0) {
      setMessage('请完整填写商品信息和价格')
      return null
    }

    const response = await apiPatch<MerchantProduct>(`/api/merchant/products/${product.id}`, payload, {
      headers: getAuthHeaders(token),
    })
    setProduct(response)
    return response
  }

  async function handleSaveAndBack() {
    const response = await saveProduct()
    if (response) navigate('/merchant/products')
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
      navigate('/merchant/products')
    } catch (error) {
      if (error instanceof ApiError && error.status === 400) {
        setMessage('发布余额不足，请先下架部分商品')
      }
    }
  }

  async function handleDelete() {
    if (!product || !token) return
    await apiDelete<{ ok: boolean }>(`/api/merchant/products/${product.id}`, {
      headers: getAuthHeaders(token),
    })
    navigate('/merchant/products')
  }

  async function handleImageChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file || !product || !token) return

    const formData = new FormData()
    formData.append('file', file)
    const response = await apiUpload<MerchantProduct>(
      `/api/merchant/products/${product.id}/images/replace`,
      formData,
      { headers: getAuthHeaders(token) },
    )
    setProduct(response)
    setMessage('图片已替换')
  }

  const nextStatus: MerchantProductStatus = product?.status === 'listed' ? 'unlisted' : 'listed'
  const statusButtonText = product?.status === 'listed' ? '下架商品' : '上架商品'

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
          <button type="button" onClick={() => void handleSaveAndBack()}>
            保存
          </button>
        </span>
      </header>

      {!product ? (
        <div className="profile-loading">加载中...</div>
      ) : (
        <>
          <div className="product-edit-scroll">
            <section className="product-image-preview">
              <img src={product.imageUrls[0] ?? '/mock-products/jade-1.png'} alt={product.title} />
              <button type="button" onClick={() => fileInputRef.current?.click()}>
                <Camera size={18} />
                替换图片
              </button>
              <span>1/{Math.max(product.imageUrls.length, 1)}</span>
              <input ref={fileInputRef} accept="image/*" type="file" onChange={(event) => void handleImageChange(event)} />
            </section>

            <section className="product-edit-form">
              <label>
                商品标题 <small>（10字以内）</small>
                <input value={title} maxLength={40} onChange={(event) => setTitle(event.target.value)} />
              </label>
              <label>
                商品简介 <small>（50字以内）</small>
                <input value={summary} maxLength={80} onChange={(event) => setSummary(event.target.value)} />
              </label>
              <label>
                商品详情 <small>（300字以内）</small>
                <textarea value={detail} maxLength={500} onChange={(event) => setDetail(event.target.value)} />
              </label>
              <label>
                商品标签 <small>（最多10个）</small>
                <textarea
                  className="tag-input"
                  value={tags}
                  placeholder="用空格分隔标签"
                  onChange={(event) => setTags(event.target.value)}
                />
              </label>
              <label>
                预估售价 <small>（元）</small>
                <input inputMode="decimal" value={price} onChange={(event) => setPrice(event.target.value)} />
              </label>
            </section>
            {message ? <p className="product-edit-message">{message}</p> : null}
          </div>

          <div className="product-edit-actions">
            <button type="button" onClick={() => void handleStatusChange(nextStatus)}>
              {statusButtonText}
            </button>
            <button type="button" onClick={() => void handleSaveAndBack()}>
              保存修改
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
