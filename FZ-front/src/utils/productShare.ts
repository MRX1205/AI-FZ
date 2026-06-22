type ProductShareInfo = {
  id: string
  title: string
  summary: string
  priceCents: number
}

export type ProductShareResult = 'shared' | 'copied' | 'cancelled'

export function createProductShareData(product: ProductShareInfo) {
  const url = `${window.location.origin}/products/${product.id}`
  const price = `￥${Math.round(product.priceCents / 100)}`
  return {
    title: product.title,
    text: `${product.title}｜${price}\n${product.summary}`,
    url,
  }
}

export async function shareProduct(product: ProductShareInfo): Promise<ProductShareResult> {
  const shareData = createProductShareData(product)

  if (navigator.share) {
    try {
      await navigator.share(shareData)
      return 'shared'
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return 'cancelled'
    }
  }

  const shareText = `${shareData.text}\n${shareData.url}`
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(shareText)
      return 'copied'
    } catch {
      // 回退到 document.execCommand，兼容部分移动 WebView 与分享受限环境。
    }
  }

  const textarea = document.createElement('textarea')
  textarea.value = shareText
  textarea.setAttribute('readonly', 'true')
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  textarea.style.pointerEvents = 'none'
  document.body.appendChild(textarea)
  textarea.select()
  textarea.setSelectionRange(0, textarea.value.length)
  document.execCommand('copy')
  document.body.removeChild(textarea)
  return 'copied'
}
