type ProductShareInfo = {
  id: string
  title: string
  summary: string
  priceCents: number
}

export type ProductShareResult = 'shared' | 'copied' | 'cancelled'

export function createProductShareData(product: ProductShareInfo) {
  const url = `${window.location.origin}/products/${product.id}`
  const price = `￥${Math.round(product.priceCents / 100).toLocaleString('zh-CN')}`
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

  await navigator.clipboard.writeText(`${shareData.text}\n${shareData.url}`)
  return 'copied'
}
