import { Bot, Gem, SendHorizontal, Sparkles, UserRound } from 'lucide-react'
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, apiAssetUrl, apiGet, apiPost } from '../api/client'
import type { ChatMessage, ChatMessagePairResponse, ChatSessionResponse, ProductCard } from '../types/domain'

const STORAGE_SESSION_ID = 'fz_home_chat_session_id_v1'
const STORAGE_MESSAGES = 'fz_home_chat_messages_v1'
const STORAGE_VISITOR_ID = 'fz_visitor_id_v1'
const STORAGE_MERCHANT_SESSION = 'fz_merchant_session_v1'
const STORAGE_VERSION = 'fz_home_chat_version_v1'
const CURRENT_STORAGE_VERSION = '2026-06-14-product-match-v1'
const MAX_INPUT_LENGTH = 300

const WELCOME_TEXT = '您好！\n请说出您的翡翠需求（预算、品类、尺寸、品相），我将为您精准匹配货源~'
const SUGGESTIONS = [
  '10万预算 帝王绿手镯',
  '冰种平安扣 预算2万 无纹无裂',
  '冰种翡翠吊坠 送礼自用均可',
]
const PRODUCT_NEED_TERMS = [
  '预算',
  '万',
  'w',
  'W',
  '手镯',
  '镯子',
  '吊坠',
  '挂件',
  '平安扣',
  '戒面',
  '蛋面',
  '珠串',
  '手串',
  '翡翠',
  '帝王绿',
  '阳绿',
  '冰种',
  '糯冰',
  '糯种',
  '飘花',
  '晴底',
  '紫罗兰',
  '无纹',
  '无裂',
  '证书',
]
const PRODUCT_NEED_INTENTS = ['找', '想要', '需要', '有没有', '推荐', '匹配', '预算', '买', '购买', '货源', '求']

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

function getVisitorId() {
  const existing = localStorage.getItem(STORAGE_VISITOR_ID)
  if (existing) return existing

  const visitorId = crypto.randomUUID()
  localStorage.setItem(STORAGE_VISITOR_ID, visitorId)
  return visitorId
}

function formatPrice(priceCents: number) {
  return `￥${Math.round(priceCents / 100).toLocaleString('zh-CN')}`
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

function looksLikeProductNeed(content: string) {
  const text = content.trim()
  if (!text) return false
  const termHits = PRODUCT_NEED_TERMS.reduce((count, term) => count + (text.includes(term) ? 1 : 0), 0)
  const hasBudget = /\d+\s*(万|w|W|千|k|K|元)|预算/.test(text)
  const hasCategory = /手镯|镯子|吊坠|挂件|平安扣|戒面|蛋面|珠串|手串/.test(text)
  const hasIntent = PRODUCT_NEED_INTENTS.some((term) => text.includes(term))
  return (hasBudget && termHits >= 1) || (hasCategory && (termHits >= 2 || hasIntent))
}

export function HomePage() {
  const navigate = useNavigate()
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const visitorId = useMemo(() => getVisitorId(), [])
  const [sessionId, setSessionId] = useState(() => {
    if (localStorage.getItem(STORAGE_VERSION) !== CURRENT_STORAGE_VERSION) {
      localStorage.removeItem(STORAGE_SESSION_ID)
      localStorage.removeItem(STORAGE_MESSAGES)
      localStorage.setItem(STORAGE_VERSION, CURRENT_STORAGE_VERSION)
      return null
    }
    return localStorage.getItem(STORAGE_SESSION_ID)
  })
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    if (localStorage.getItem(STORAGE_VERSION) !== CURRENT_STORAGE_VERSION) return []
    return readJson(STORAGE_MESSAGES, [])
  })
  const [inputValue, setInputValue] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [isComposing, setIsComposing] = useState(false)
  const [sendingMode, setSendingMode] = useState<'match' | 'chat'>('chat')

  const canSend = inputValue.trim().length > 0 && !isSending && !isComposing
  const hasMessages = messages.length > 0

  useEffect(() => {
    if (!sessionId) return

    apiGet<ChatSessionResponse>(`/api/chat/sessions/${sessionId}/messages`)
      .then((response) => {
        setMessages(response.messages)
      })
      .catch(() => {
        localStorage.removeItem(STORAGE_SESSION_ID)
        setSessionId(null)
      })
  }, [sessionId])

  useEffect(() => {
    // localStorage 让刷新后先恢复聊天，再由后端会话同步最新记录。
    localStorage.setItem(STORAGE_MESSAGES, JSON.stringify(messages))
  }, [messages])

  useLayoutEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: 'smooth',
    })
  }, [messages])

  useLayoutEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return

    // textarea 默认 2 行、最高约 6 行，按内容自动增高。
    textarea.style.height = 'auto'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 144)}px`
  }, [inputValue])

  async function createSession() {
    const response = await apiPost<ChatSessionResponse>('/api/chat/sessions', {
      visitorId,
      merchantId: null,
    })
    localStorage.setItem(STORAGE_SESSION_ID, response.sessionId)
    setSessionId(response.sessionId)
    return response.sessionId
  }

  async function ensureSession() {
    if (sessionId) return sessionId
    return createSession()
  }

  async function postChatMessage(activeSessionId: string, content: string, isProductNeed: boolean) {
    const path = isProductNeed
      ? `/api/chat/sessions/${activeSessionId}/matches`
      : `/api/chat/sessions/${activeSessionId}/messages`
    return apiPost<ChatMessagePairResponse>(path, {
      content,
    })
  }

  async function sendMessage(content: string) {
    const trimmedContent = content.trim()
    if (!trimmedContent || isSending) return

    const isProductNeed = looksLikeProductNeed(trimmedContent)
    setSendingMode(isProductNeed ? 'match' : 'chat')
    setIsSending(true)
    setInputValue('')

    try {
      const activeSessionId = await ensureSession()
      let response: ChatMessagePairResponse

      try {
        response = await postChatMessage(activeSessionId, trimmedContent, isProductNeed)
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 404) throw error

        localStorage.removeItem(STORAGE_SESSION_ID)
        const newSessionId = await createSession()
        response = await postChatMessage(newSessionId, trimmedContent, isProductNeed)
      }

      setMessages((current) => [...current, response.userMessage, response.assistantMessage])
    } finally {
      setIsSending(false)
    }
  }

  function handleMerchantEntry() {
    // 后续登录页写入 fz_merchant_session_v1；首页只按是否存在登录态做跳转。
    const merchantSession = localStorage.getItem(STORAGE_MERCHANT_SESSION)
    navigate(merchantSession ? '/merchant/dashboard' : '/merchant/auth')
  }

  return (
    <section className="home-page">
      <header className="home-header">
        <div className="home-brand">
          <span className="home-logo" aria-hidden="true">
            <Gem size={23} strokeWidth={2.5} />
          </span>
          <span>AI翡翠匹配</span>
        </div>
        <button className="merchant-entry" type="button" onClick={handleMerchantEntry}>
          商家入驻
        </button>
      </header>

      <div className="chat-scroll" ref={scrollRef}>
        {!hasMessages ? (
          <WelcomeBlock onSuggestionClick={sendMessage} />
        ) : (
          <div className="message-list" aria-live="polite">
            {messages.map((message) => (
              <ChatMessageItem key={message.id} message={message} />
            ))}
          </div>
        )}
      </div>

      <form
        className="composer-panel"
        onSubmit={(event) => {
          event.preventDefault()
          if (isComposing) return
          void sendMessage(inputValue)
        }}
      >
        <div className="composer-row">
          <textarea
            ref={textareaRef}
            value={inputValue}
            rows={2}
            className="composer-input"
            placeholder={'请输入您的翡翠需求...\n支持中文英文等多语言'}
            maxLength={MAX_INPUT_LENGTH}
            onCompositionStart={() => setIsComposing(true)}
            onCompositionEnd={(event) => {
              setIsComposing(false)
              setInputValue(event.currentTarget.value.slice(0, MAX_INPUT_LENGTH))
            }}
            onChange={(event) => setInputValue(event.target.value.slice(0, MAX_INPUT_LENGTH))}
          />
          <button className="send-button" type="submit" disabled={!canSend}>
            <SendHorizontal size={18} strokeWidth={2.4} />
            {isSending ? (sendingMode === 'match' ? '正在匹配货源...' : '正在回复...') : 'AI匹配'}
          </button>
        </div>
        <p className="composer-note">AI智能匹配，仅供参考，不做鉴定与交易</p>
      </form>
    </section>
  )
}

function WelcomeBlock({ onSuggestionClick }: { onSuggestionClick: (content: string) => Promise<void> }) {
  return (
    <div className="welcome-block">
      <div className="chat-row assistant-row">
        <AssistantAvatar />
        <div className="assistant-bubble welcome-bubble">
          <p>{WELCOME_TEXT}</p>
          <time>10:30</time>
        </div>
      </div>

      <div className="suggestion-list">
        {SUGGESTIONS.map((suggestion) => (
          <button
            className="suggestion-chip"
            type="button"
            key={suggestion}
            onClick={() => void onSuggestionClick(suggestion)}
          >
            <Sparkles size={17} />
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  )
}

function ChatMessageItem({ message }: { message: ChatMessage }) {
  if (message.role === 'user') {
    return (
      <div className="chat-row user-row">
        <div className="user-bubble">
          <p>{message.content}</p>
          <time>{formatTime(message.createdAt)}</time>
        </div>
        <UserAvatar />
      </div>
    )
  }

  return (
    <div className="assistant-message-group">
      <div className="chat-row assistant-row">
        <AssistantAvatar />
        <div className="assistant-bubble">
          <p>{message.content}</p>
          <time>{formatTime(message.createdAt)}</time>
        </div>
      </div>
      {message.matchedProducts?.length ? (
        <ProductMatches products={message.matchedProducts} createdAt={message.createdAt} />
      ) : null}
    </div>
  )
}

function ProductMatches({ products, createdAt }: { products: ProductCard[]; createdAt: string }) {
  const navigate = useNavigate()

  return (
    <section className="matches-panel" aria-label="翡翠货源匹配结果">
      <h2>为您找到以下优质货源</h2>
      <div className="product-card-row">
        {products.map((product) => (
          <button
            className="product-card"
            key={product.id}
            type="button"
            onClick={() => navigate(`/products/${product.id}`)}
          >
            <img src={apiAssetUrl(product.imageUrl)} alt={product.title} />
            <div className="product-card-body">
              <h3>{product.title}</h3>
              <div className="product-tags">
                {product.tags.slice(0, 3).map((tag) => (
                  <span key={tag}>{tag}</span>
                ))}
              </div>
              <div className="product-footer">
                <strong>{formatPrice(product.priceCents)}</strong>
                <span className={product.merchantTier === 'vip' ? 'tier-vip' : 'tier-free'}>
                  {product.merchantTier === 'vip' ? 'VIP' : '商家'}
                </span>
              </div>
            </div>
          </button>
        ))}
      </div>
      <time>{formatTime(createdAt)}</time>
    </section>
  )
}

function AssistantAvatar() {
  return (
    <span className="avatar assistant-avatar" aria-hidden="true">
      <Bot size={28} strokeWidth={2.2} />
    </span>
  )
}

function UserAvatar() {
  return (
    <span className="avatar user-avatar" aria-hidden="true">
      <UserRound size={24} strokeWidth={2.4} />
    </span>
  )
}
