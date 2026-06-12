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

export type ProductCard = {
  id: string
  title: string
  tags: string[]
  priceCents: number
  imageUrl: string
  merchantTier: MerchantTier
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
  matchedProducts?: ProductCard[] | null
  createdAt: string
}

export type ChatSessionResponse = {
  sessionId: string
  messages: ChatMessage[]
}

export type ChatMessagePairResponse = {
  userMessage: ChatMessage
  assistantMessage: ChatMessage
}

export type MerchantAuthSession = {
  token: string
  merchant: {
    id: string
    email: string
    tier: MerchantTier
  }
}

export type AuthCodeResponse = {
  ok: boolean
  expiresIn: number
  devCode: string
}
