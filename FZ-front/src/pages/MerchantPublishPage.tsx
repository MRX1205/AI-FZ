import { CheckCircle2, ChevronLeft, Edit3, ImagePlus, Loader2, Plus, X } from 'lucide-react'
import { type ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, apiAssetUrl, apiDelete, apiGet, apiPatch, apiUpload } from '../api/client'
import { ImagePreview } from '../components/ImagePreview'
import type {
  MerchantProduct,
  MerchantProductCurrentDraftResponse,
  MerchantProductDraftGenerateResponse,
  MerchantProductPublishPayload,
} from '../types/domain'
import {
  clearMerchantSession,
  getAuthHeaders,
  readMerchantSession,
  updateMerchantSessionMerchant,
} from './merchantAuthStorage'

const steps = [
  {
    title: '上传商品图片',
    description: '上传清晰的翡翠图片，AI将为您自动生成商品文案',
  },
  {
    title: 'AI智能生成',
    description: 'AI识别图片特征，生成商品信息',
  },
  {
    title: '编辑商品信息',
    description: '可修改AI生成的标题、描述、标签和价格',
  },
  {
    title: '提交发布',
    description: '发布后商品将在平台展示给买家',
  },
]

export function MerchantPublishPage() {
  const navigate = useNavigate()
  const token = useMemo(() => readMerchantSession()?.token ?? '', [])
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [draftData, setDraftData] = useState<MerchantProductCurrentDraftResponse | null>(null)
  const [toast, setToast] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [isPublishing, setIsPublishing] = useState(false)
  const [hasGenerated, setHasGenerated] = useState(false)
  const [previewIndex, setPreviewIndex] = useState<number | null>(null)

  const loadDraft = useCallback(async () => {
    const response = await apiGet<MerchantProductCurrentDraftResponse>(
      `/api/merchant/products/current-draft?_ts=${Date.now()}`,
      {
        headers: getAuthHeaders(token),
        cache: 'no-store',
      },
    )
    setDraftData(response)
    updateMerchantSessionMerchant(response.merchant)
    setHasGenerated(Boolean(response.product?.title || response.product?.summary || response.product?.detail))
    return response
  }, [token])

  useEffect(() => {
    if (!token) {
      navigate('/merchant/auth', { replace: true })
      return
    }

    void Promise.resolve().then(async () => {
      try {
        await loadDraft()
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          clearMerchantSession()
          navigate('/merchant/auth', { replace: true })
        }
      }
    })
  }, [loadDraft, navigate, token])

  function showToast(message: string) {
    setToast(message)
    window.setTimeout(() => setToast(''), 1800)
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? [])
    event.target.value = ''
    if (files.length === 0) return

    const imageFiles = files.filter((file) => file.type.startsWith('image/'))
    if (imageFiles.length !== files.length) {
      showToast('请上传图片文件')
    }
    if (imageFiles.length === 0) return
    const currentCount = draftData?.product?.imageUrls.length ?? 0
    const remaining = 6 - currentCount
    if (remaining <= 0) {
      showToast('最多上传6张图片')
      return
    }
    if (imageFiles.length > remaining) {
      showToast('最多上传6张图片')
    }

    const formData = new FormData()
    imageFiles.slice(0, remaining).forEach((file) => formData.append('images', file))
    setIsUploading(true)
    apiUpload<MerchantProduct>('/api/merchant/products/drafts/images', formData, {
      headers: getAuthHeaders(token),
    })
      .then(async () => {
        await loadDraft()
        setHasGenerated(false)
      })
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) {
          clearMerchantSession()
          navigate('/merchant/auth', { replace: true })
          return
        }
        showToast(error instanceof ApiError ? error.message : '图片上传失败')
      })
      .finally(() => setIsUploading(false))
  }

  async function removeImage(index: number) {
    if (!draftData?.product || !token) return
    try {
      const product = await apiDelete<MerchantProduct>(
        `/api/merchant/products/${draftData.product.id}/images/${index}`,
        { headers: getAuthHeaders(token) },
      )
      await loadDraft()
      setHasGenerated(Boolean(product.imageUrls.length > 0 && (product.title || product.summary || product.detail)))
    } catch (error) {
      showToast(error instanceof ApiError ? error.message : '图片删除失败')
    }
  }

  async function handleGenerate() {
    const product = draftData?.product
    if (!draftData || !token || isGenerating || isUploading) return
    if (!product || product.imageUrls.length === 0) {
      showToast('请先上传商品图片')
      return
    }

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
        showToast('生成结果异常，请稍后重试')
        return
      }
      setDraftData((current) => (current ? { ...current, product: generatedProduct } : current))
      setHasGenerated(true)
      showToast('AI生成完成')
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearMerchantSession()
        navigate('/merchant/auth', { replace: true })
        return
      }
      showToast(error instanceof ApiError ? error.message : '生成失败，请稍后重试')
    } finally {
      setIsGenerating(false)
    }
  }

  async function handlePublish() {
    const product = draftData?.product
    if (!product || !token || isPublishing) return
    const payload: MerchantProductPublishPayload = {
      title: product.title,
      summary: product.summary,
      detail: product.detail,
      tags: product.tags,
      priceCents: product.priceCents,
    }
    setIsPublishing(true)
    try {
      await apiPatch<MerchantProduct>(`/api/merchant/products/${product.id}/publish`, payload, {
        headers: getAuthHeaders(token),
      })
      navigate('/merchant/products', { state: { refreshAt: Date.now(), message: '发布成功' } })
    } catch (error) {
      showToast(error instanceof ApiError ? error.message : '发布失败，请稍后重试')
    } finally {
      setIsPublishing(false)
    }
  }

  const isVip = draftData?.merchant.tier === 'vip'
  const quota = draftData?.quota ?? { listedCount: 0, productLimit: isVip ? 100 : 2, remaining: 0 }
  const product = draftData?.product
  const imageUrls = product?.imageUrls ?? []
  const resolvedImageUrls = imageUrls.map(apiAssetUrl)
  const disabledByQuota = draftData ? quota.remaining <= 0 : false
  const quotaText = isVip ? '商家最多发布' : '免费商家最多发布'
  const hasProductInfo = Boolean(
    product?.title.trim() && product.summary.trim() && product.detail.trim() && product.priceCents > 0,
  )
  const canGenerate = Boolean(draftData && imageUrls.length > 0 && !isGenerating && !isUploading)
  const canPublish = Boolean(draftData && product && imageUrls.length > 0 && !disabledByQuota && !isPublishing)
  const canConfirmPublish = Boolean(canPublish && hasProductInfo)

  return (
    <section className="merchant-publish-page">
      <header className="profile-header publish-header">
        <button type="button" aria-label="返回商家后台" onClick={() => navigate('/merchant/dashboard')}>
          <ChevronLeft size={31} strokeWidth={2.4} />
        </button>
        <h1>发布商品</h1>
        <span aria-hidden="true" />
      </header>

      <div className="publish-scroll">
        <ol className="publish-steps">
          {steps.map((step, index) => (
            <li className={index === 0 ? 'is-current' : ''} key={step.title}>
              <span className="publish-step-dot">
                {index === 0 ? <ImagePlus size={15} /> : <CheckCircle2 size={18} />}
              </span>
              <div>
                <h2>
                  {index + 1}. {step.title}
                </h2>
                <p>{step.description}</p>
                {index === 0 ? (
                  <div className="publish-upload-grid">
                    {imageUrls.map((imageUrl, imageIndex) => (
                      <div className="publish-image-tile" key={`${imageUrl}-${imageIndex}`}>
                        <button
                          className="publish-image-preview-button"
                          type="button"
                          aria-label={`预览第${imageIndex + 1}张商品图片`}
                          onClick={() => setPreviewIndex(imageIndex)}
                        >
                          <img src={resolvedImageUrls[imageIndex]} alt="已上传商品图片" />
                        </button>
                        <button
                          className="publish-image-remove-button"
                          type="button"
                          aria-label="移除已上传图片"
                          onClick={() => void removeImage(imageIndex)}
                        >
                          <X size={15} />
                        </button>
                      </div>
                    ))}
                    {imageUrls.length < 6 ? (
                      <button
                        className="publish-add-tile"
                        type="button"
                        disabled={isUploading}
                        onClick={() => fileInputRef.current?.click()}
                      >
                        <Plus size={34} />
                        <span>添加图片</span>
                      </button>
                    ) : null}
                  </div>
                ) : null}
                {index === 1 ? (
                  <div className="publish-step-action is-column">
                    <button type="button" disabled={!canGenerate} onClick={() => void handleGenerate()}>
                      <Loader2
                        className={isGenerating ? 'is-spinning publish-generate-spinner' : 'publish-generate-spinner'}
                        size={16}
                      />
                      <span>
                        {isGenerating
                          ? 'AI识别图片特征，生成商品信息'
                          : hasGenerated
                            ? '重新生成'
                            : 'AI生成'}
                      </span>
                    </button>
                    {hasGenerated && product ? (
                      <button
                        className="publish-result-entry"
                        type="button"
                        onClick={() => navigate(`/merchant/publish/result/${product.id}`)}
                      >
                        查看AI生成结果
                      </button>
                    ) : null}
                  </div>
                ) : null}
                {index === 2 ? (
                  <div className="publish-step-action">
                    <button
                      type="button"
                      disabled={!product || !hasGenerated}
                      onClick={() => product && navigate(`/merchant/publish/edit/${product.id}`)}
                    >
                      <Edit3 size={16} />
                      编辑商品信息
                    </button>
                  </div>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      </div>

      <div className="publish-bottom">
        <p>
          {quotaText}
          <em> {quota.productLimit} </em>件商品，当前已发布
          <em> {quota.listedCount}/{quota.productLimit} </em>件
        </p>
        <button
          className={!canConfirmPublish ? 'is-quota-disabled' : ''}
          type="button"
          disabled={!draftData || isGenerating || isUploading || isPublishing}
          onClick={() => {
            if (disabledByQuota) {
              showToast(isVip ? '请下架部分商品后再发布' : '需升级VIP提升发布额度')
              return
            }
            if (imageUrls.length === 0) {
              showToast('请先上传商品图片')
              return
            }
            if (!hasGenerated || !hasProductInfo) {
              showToast('请先生成并完善商品信息')
              return
            }
            if (!canPublish) return
            void handlePublish()
          }}
        >
          {isPublishing ? (
            <>
              <Loader2 className="is-spinning" size={20} />
              发布中...
            </>
          ) : (
            '确认发布'
          )}
        </button>
      </div>

      <input
        ref={fileInputRef}
        accept="image/*"
        multiple
        type="file"
        className="publish-file-input"
        onChange={(event) => handleFileChange(event)}
      />
      {toast ? <p className="product-toast">{toast}</p> : null}
      {previewIndex !== null ? (
        <ImagePreview
          images={resolvedImageUrls}
          initialIndex={previewIndex}
          alt="已上传商品图片"
          onClose={() => setPreviewIndex(null)}
        />
      ) : null}
    </section>
  )
}
