export type MerchantTier = 'free' | 'vip'

export type ProductStatus = 'draft' | 'listed' | 'unlisted'

export type LeadStatus = 'pending' | 'contacted'

export type Product = {
  id: string
  merchantId: string
  title: string
  summary: string
  detail: string
  priceCents: number
  status: ProductStatus
  tags: string[]
  imageUrls: string[]
}

export type Lead = {
  id: string
  productId: string
  merchantId: string
  buyerEmail: string
  buyerMessage: string
  status: LeadStatus
  createdAt: string
}

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  matchedProducts?: Product[]
  createdAt: string
}
