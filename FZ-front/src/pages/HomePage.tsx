import { Bot, Gem, SendHorizontal, Sparkles, UserRound } from 'lucide-react'
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { API_BASE_URL, ApiError, apiAssetUrl, apiGet, apiPost } from '../api/client'
import type {
  ChatMessage,
  ChatMessagePairResponse,
  ChatSessionResponse,
  MerchantAuthSession,
  ProductCard,
} from '../types/domain'
import {
  clearMerchantSession,
  getAuthHeaders,
  readMerchantSession,
  updateMerchantSessionMerchant,
} from './merchantAuthStorage'

const STORAGE_SESSION_ID = 'fz_home_chat_session_id_v1'
const STORAGE_MESSAGES = 'fz_home_chat_messages_v1'
const STORAGE_VISITOR_ID = 'fz_visitor_id_v1'
const STORAGE_VERSION = 'fz_home_chat_version_v1'
const CURRENT_STORAGE_VERSION = '2026-06-14-product-match-v1'
const MAX_INPUT_LENGTH = 300

const WELCOME_TEXT = '您好！\n请说出您的翡翠需求（预算、品类、尺寸、品相），我将为您精准匹配货源~'
const SUGGESTIONS = [
  '10万预算 帝王绿手镯',
  '冰种平安扣 预算2万 无纹无裂',
  '冰种翡翠吊坠 送礼自用均可',
]

type StreamEvent = {
  event: string
  data: unknown
}

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

function tempMessage(role: ChatMessage['role'], content: string): ChatMessage {
  return {
    id: `temp-${crypto.randomUUID()}`,
    role,
    content,
    createdAt: new Date().toISOString(),
  }
}

function parseStreamEvent(rawEvent: string): StreamEvent | null {
  const lines = rawEvent.split('\n')
  const eventLine = lines.find((line) => line.startsWith('event:'))
  const dataLines = lines.filter((line) => line.startsWith('data:'))
  if (!eventLine || dataLines.length === 0) return null

  const event = eventLine.replace(/^event:\s*/, '').trim()
  const dataText = dataLines.map((line) => line.replace(/^data:\s*/, '')).join('\n')
  try {
    return { event, data: JSON.parse(dataText) as unknown }
  } catch {
    return null
  }
}

async function postChatMessageStream({
  sessionId,
  content,
  onDelta,
  onResult,
}: {
  sessionId: string
  content: string
  onDelta: (content: string) => void
  onResult: (response: ChatMessagePairResponse) => void
}) {
  const response = await fetch(`${API_BASE_URL}/api/chat/sessions/${sessionId}/matches/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })

  if (!response.ok) {
    throw new ApiError(`POST /matches/stream failed with ${response.status}`, response.status)
  }
  if (!response.body) {
    throw new ApiError('当前浏览器不支持流式响应', response.status)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  function dispatch(rawEvent: string) {
    const parsed = parseStreamEvent(rawEvent.trim())
    if (!parsed) return
    if (parsed.event === 'message_delta') {
      const data = parsed.data as { content?: unknown }
      if (typeof data.content === 'string') onDelta(data.content)
      return
    }
    if (parsed.event === 'match_result') {
      onResult(parsed.data as ChatMessagePairResponse)
      return
    }
    if (parsed.event === 'error') {
      const data = parsed.data as { message?: unknown }
      throw new ApiError(typeof data.message === 'string' ? data.message : '匹配失败', 500)
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let separatorIndex = buffer.indexOf('\n\n')
    while (separatorIndex >= 0) {
      const rawEvent = buffer.slice(0, separatorIndex)
      buffer = buffer.slice(separatorIndex + 2)
      dispatch(rawEvent)
      separatorIndex = buffer.indexOf('\n\n')
    }
  }
  if (buffer.trim()) dispatch(buffer)
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

  const canSend = inputValue.trim().length > 0 && !isSending && !isComposing
  const hasMessages = messages.length > 0

  useEffect(() => {
    if (!sessionId) return

    apiGet<ChatSessionResponse>(`/api/chat/sessions/${sessionId}/messages`)
      .then((response) => {
        setMessages((current) => {
          if (response.messages.length === 0 && current.length > 0) {
            return current
          }
          return response.messages
        })
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

  async function sendMessage(content: string) {
    const trimmedContent = content.trim()
    if (!trimmedContent || isSending) return

    setIsSending(true)
    setInputValue('')

    const userPlaceholder = tempMessage('user', trimmedContent)
    const assistantPlaceholder = tempMessage('assistant', '')
    setMessages((current) => [...current, userPlaceholder, assistantPlaceholder])

    const appendDelta = (delta: string) => {
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantPlaceholder.id
            ? { ...message, content: `${message.content}${delta}` }
            : message,
        ),
      )
    }
    const replaceWithResult = (response: ChatMessagePairResponse) => {
      setMessages((current) =>
        current.map((message) => {
          if (message.id === userPlaceholder.id) return response.userMessage
          if (message.id === assistantPlaceholder.id) return response.assistantMessage
          return message
        }),
      )
    }

    try {
      const activeSessionId = await ensureSession()

      try {
        await postChatMessageStream({
          sessionId: activeSessionId,
          content: trimmedContent,
          onDelta: appendDelta,
          onResult: replaceWithResult,
        })
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 404) throw error

        localStorage.removeItem(STORAGE_SESSION_ID)
        const newSessionId = await createSession()
        await postChatMessageStream({
          sessionId: newSessionId,
          content: trimmedContent,
          onDelta: appendDelta,
          onResult: replaceWithResult,
        })
      }
    } catch (error) {
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantPlaceholder.id
            ? {
                ...message,
                content: error instanceof ApiError ? error.message : '匹配失败，请稍后再试。',
              }
            : message,
        ),
      )
    } finally {
      setIsSending(false)
    }
  }

  async function handleMerchantEntry() {
    const merchantSession = readMerchantSession()
    if (!merchantSession?.token) {
      navigate('/merchant/auth')
      return
    }

    try {
      const merchant = await apiGet<MerchantAuthSession['merchant']>('/api/auth/me', {
        headers: getAuthHeaders(merchantSession.token),
        cache: 'no-store',
      })
      updateMerchantSessionMerchant(merchant)
      navigate('/merchant/dashboard')
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearMerchantSession()
      }
      navigate('/merchant/auth')
    }
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
        <button className="merchant-entry" type="button" onClick={() => void handleMerchantEntry()}>
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
            {isSending ? '正在匹配货源...' : 'AI匹配'}
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
