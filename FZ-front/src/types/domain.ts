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

export type VisitorNeedTag = {
  name: string
  score: number
}

export type VisitorNeedParam = {
  category: string
  value: string
}

export type VisitorNeedProfile = {
  id: string
  sourceType: 'direct' | 'rewritten'
  originalQuestion: string
  normalizedQuestion: string
  title: string
  summary: string
  detail: string
  tags: VisitorNeedTag[]
  params: VisitorNeedParam[]
}

export type PublicProduct = {
  id: string
  title: string
  summary: string
  detail: string
  tags: string[]
  priceCents: number
  imageUrls: string[]
  merchantTier: MerchantTier
  createdAt: string
  updatedAt: string
}

export type PublicProductContactPayload = {
  buyerEmail: string
}

export type PublicProductContactResponse = {
  ok: boolean
  message: string
  leadId?: string | null
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
  needProfile?: VisitorNeedProfile | null
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
  devCode?: string
}

export type MerchantDashboardLead = {
  id: string
  submittedAt: string
  buyerEmail: string
  message: string
  productTitle: string
}

export type MerchantDashboardResponse = {
  merchant: MerchantAuthSession['merchant']
  stats: {
    listedProducts: number
    productLimit: number
    todayLeads: number
    totalLeads: number
  }
  recentLeads: MerchantDashboardLead[]
}

export type MerchantNotificationSettings = {
  webNotificationEnabled: boolean
  emailNotificationEnabled: boolean
}

export type MerchantProfileResponse = MerchantAuthSession['merchant'] & {
  vipStartedAt?: string | null
  vipExpiresAt?: string | null
  notifications: MerchantNotificationSettings
}

export type MerchantLeadStatus = 'pending' | 'contacted'

export type MerchantLead = {
  id: string
  productId?: string | null
  submittedAt: string
  buyerEmail: string
  message: string
  productTitle: string
  productPriceCents: number
  productImageUrl: string
  status: MerchantLeadStatus
  merchantEmail: string
}

export type MerchantLeadListResponse = {
  merchant: MerchantAuthSession['merchant']
  leads: MerchantLead[]
}

export type MerchantSystemNotification = {
  id: string
  type: 'new_lead' | 'vip_expiring'
  content: string
  sentAt: string
}

export type MerchantNotificationListResponse = {
  merchant: MerchantAuthSession['merchant']
  notifications: MerchantSystemNotification[]
}

export type MerchantProductStatus = 'draft' | 'listed' | 'unlisted'

export type MerchantProduct = {
  id: string
  title: string
  summary: string
  detail: string
  tags: string[]
  priceCents: number
  status: MerchantProductStatus
  imageUrls: string[]
  publishedAt?: string | null
  createdAt: string
  updatedAt: string
}

export type MerchantProductListResponse = {
  merchant: MerchantAuthSession['merchant']
  products: MerchantProduct[]
  counts: {
    all: number
    listed: number
    draft: number
    unlisted: number
  }
  quota: {
    listedCount: number
    productLimit: number
    remaining: number
  }
}

export type MerchantProductCurrentDraftResponse = {
  merchant: MerchantAuthSession['merchant']
  product: MerchantProduct | null
  quota: MerchantProductListResponse['quota']
}

export type MerchantProductUpdatePayload = {
  title: string
  summary: string
  detail: string
  tags: string[]
  priceCents: number
}

export type MerchantProductDraftGenerateResponse = MerchantProduct

export type MerchantProductPublishPayload = MerchantProductUpdatePayload
