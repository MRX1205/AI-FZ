import { CheckCircle2, ChevronLeft, ImagePlus, Loader2, Plus } from 'lucide-react'
import { type ChangeEvent, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, apiGet, apiUpload } from '../api/client'
import type { MerchantProductDraftGenerateResponse, MerchantProductListResponse } from '../types/domain'
import { clearMerchantSession, getAuthHeaders, readMerchantSession } from './merchantAuthStorage'

type UploadPreview = {
  id: string
  file: File
  url: string
}

const steps = [
  {
    title: '上传商品图片',
    description: '上传清晰的翡翠图片，AI将为您自动生成商品文案',
  },
  {
    title: 'AI智能生成',
    description: '正在识别图片特征，生成商品信息...',
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
  const previewsRef = useRef<UploadPreview[]>([])
  const [data, setData] = useState<MerchantProductListResponse | null>(null)
  const [previews, setPreviews] = useState<UploadPreview[]>([])
  const [toast, setToast] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)

  useEffect(() => {
    if (!token) {
      navigate('/merchant/auth', { replace: true })
      return
    }

    apiGet<MerchantProductListResponse>('/api/merchant/products?status=all', {
      headers: getAuthHeaders(token),
    })
      .then(setData)
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) {
          clearMerchantSession()
          navigate('/merchant/auth', { replace: true })
        }
      })
  }, [navigate, token])

  useEffect(() => {
    previewsRef.current = previews
  }, [previews])

  useEffect(() => () => previewsRef.current.forEach((preview) => URL.revokeObjectURL(preview.url)), [])

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
    const remaining = 6 - previews.length
    if (remaining <= 0) {
      showToast('最多上传6张图片')
      return
    }
    if (imageFiles.length > remaining) {
      showToast('最多上传6张图片')
    }

    const nextPreviews = imageFiles.slice(0, remaining).map((file) => ({
      id: `${file.name}-${file.lastModified}-${crypto.randomUUID()}`,
      file,
      url: URL.createObjectURL(file),
    }))
    setPreviews((current) => [...current, ...nextPreviews])
  }

  function removePreview(id: string) {
    setPreviews((current) => {
      const target = current.find((preview) => preview.id === id)
      if (target) URL.revokeObjectURL(target.url)
      return current.filter((preview) => preview.id !== id)
    })
  }

  async function handleGenerate() {
    if (!data || !token || isGenerating) return
    if (data.quota.remaining <= 0) {
      showToast(data.merchant.tier === 'vip' ? '请下架部分商品后再发布' : '需升级VIP提升发布额度')
      return
    }
    if (previews.length === 0) {
      showToast('请先上传商品图片')
      return
    }

    setIsGenerating(true)
    const formData = new FormData()
    previews.forEach((preview) => formData.append('images', preview.file))

    try {
      const product = await apiUpload<MerchantProductDraftGenerateResponse>(
        '/api/merchant/products/drafts/generate',
        formData,
        { headers: getAuthHeaders(token) },
      )
      navigate(`/merchant/publish/edit/${product.id}`)
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearMerchantSession()
        navigate('/merchant/auth', { replace: true })
        return
      }
      showToast(error instanceof ApiError && error.status === 400 ? '生成失败，请检查图片和发布额度' : '生成失败，请稍后重试')
    } finally {
      setIsGenerating(false)
    }
  }

  const isVip = data?.merchant.tier === 'vip'
  const quota = data?.quota ?? { listedCount: 0, productLimit: isVip ? 100 : 2, remaining: 0 }
  const disabledByQuota = data ? quota.remaining <= 0 : false
  const quotaText = isVip ? '商家最多发布' : '免费商家最多发布'

  return (
    <section className="merchant-publish-page">
      <header className="profile-header publish-header">
        <button type="button" aria-label="返回商家后台" onClick={() => navigate('/merchant/dashboard')}>
          <ChevronLeft size={31} strokeWidth={2.4} />
        </button>
        <h1>发布商品</h1>
        <span>{isGenerating ? 'AI生成中' : ''}</span>
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
                    {previews.map((preview) => (
                      <button
                        className="publish-image-tile"
                        key={preview.id}
                        type="button"
                        aria-label="移除已上传图片"
                        onClick={() => removePreview(preview.id)}
                      >
                        <img src={preview.url} alt="已上传商品图片" />
                        <small>移除</small>
                      </button>
                    ))}
                    {previews.length < 6 ? (
                      <button
                        className="publish-add-tile"
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                      >
                        <Plus size={34} />
                        <span>添加图片</span>
                      </button>
                    ) : null}
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
          className={disabledByQuota || previews.length === 0 ? 'is-quota-disabled' : ''}
          type="button"
          disabled={!data || isGenerating}
          onClick={() => void handleGenerate()}
        >
          {isGenerating ? (
            <>
              <Loader2 className="is-spinning" size={20} />
              AI生成中
            </>
          ) : (
            'AI生成'
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
    </section>
  )
}
