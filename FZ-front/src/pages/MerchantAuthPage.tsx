import { Check, ChevronLeft, Gem, Lock, Mail, ShieldCheck, Zap } from 'lucide-react'
import type { FormEvent, ReactNode } from 'react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiPost } from '../api/client'
import type { AuthCodeResponse, MerchantAuthSession } from '../types/domain'
import { saveMerchantSession } from './merchantAuthStorage'

function isValidEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim())
}

export function MerchantAuthPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [countdown, setCountdown] = useState(0)
  const [isSendingCode, setIsSendingCode] = useState(false)
  const [isLoggingIn, setIsLoggingIn] = useState(false)
  const [message, setMessage] = useState('')

  const normalizedEmail = useMemo(() => email.trim().toLowerCase(), [email])
  const canRequestCode = isValidEmail(normalizedEmail) && countdown === 0 && !isSendingCode
  const canLogin = isValidEmail(normalizedEmail) && code.trim().length > 0 && !isLoggingIn

  useEffect(() => {
    if (countdown <= 0) return

    // 倒计时组件卸载时清理定时器，避免返回首页后仍继续更新状态。
    const timer = window.setTimeout(() => {
      setCountdown((current) => Math.max(current - 1, 0))
    }, 1000)

    return () => window.clearTimeout(timer)
  }, [countdown])

  async function handleSendCode() {
    if (!canRequestCode) return

    setIsSendingCode(true)
    setMessage('')

    try {
      const response = await apiPost<AuthCodeResponse>('/api/auth/send-code', {
        email: normalizedEmail,
      })
      setCountdown(60)
      setMessage(`开发验证码：${response.devCode}`)
    } catch {
      setMessage('验证码获取失败，请检查邮箱后重试')
    } finally {
      setIsSendingCode(false)
    }
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canLogin) return

    setIsLoggingIn(true)
    setMessage('')

    try {
      const session = await apiPost<MerchantAuthSession>('/api/auth/login', {
        email: normalizedEmail,
        code: code.trim(),
      })
      // 首页和后续后台页都通过这个本地登录态判断商家是否已登录。
      saveMerchantSession(session)
      navigate('/merchant/dashboard')
    } catch {
      setMessage('验证码错误或已过期，请重新获取')
    } finally {
      setIsLoggingIn(false)
    }
  }

  return (
    <section className="merchant-auth-page">
      <button className="auth-back" type="button" aria-label="返回首页" onClick={() => navigate('/')}>
        <ChevronLeft size={32} strokeWidth={2.4} />
      </button>

      <div className="auth-content">
        <header className="auth-heading">
          <span className="auth-logo" aria-hidden="true">
            <Gem size={48} strokeWidth={2.1} />
          </span>
          <h1>商家入驻</h1>
          <p>加入高翠网 · 获取精准买家线索</p>
        </header>

        <form className="auth-form" onSubmit={handleLogin}>
          <label className="auth-field">
            <Mail size={27} strokeWidth={1.8} />
            <input
              type="email"
              inputMode="email"
              autoComplete="email"
              value={email}
              placeholder="请输入您的邮箱地址"
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>

          <button
            className="auth-primary-button"
            type="button"
            disabled={!canRequestCode}
            onClick={handleSendCode}
          >
            {isSendingCode ? '获取中...' : '获取验证码'}
          </button>

          <label className="auth-field">
            <ShieldCheck size={27} strokeWidth={1.8} />
            <input
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              value={code}
              placeholder="请输入验证码"
              onChange={(event) => setCode(event.target.value)}
            />
            <span className="auth-countdown">{countdown > 0 ? `${countdown}s` : ''}</span>
          </label>

          <button className="auth-primary-button" type="submit" disabled={!canLogin}>
            {isLoggingIn ? '登录中...' : '登录 / 注册'}
          </button>

          {message ? <p className="auth-message">{message}</p> : null}
        </form>

        <footer className="auth-footer">
          <div className="auth-benefits" aria-label="商家入驻说明">
            <Benefit icon={<Mail size={22} />} label="仅需邮箱" />
            <Benefit icon={<Lock size={22} />} label="验证码登录" />
            <Benefit icon={<Zap size={22} />} label="快速入驻" />
            <Benefit icon={<Check size={23} />} label="免费试用" />
          </div>

          <p className="auth-agreement">
            登录即表示同意<span>《平台服务协议》</span> 与 <span>《隐私政策》</span>
          </p>
        </footer>
      </div>
    </section>
  )
}

function Benefit({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <div className="auth-benefit">
      <span className="auth-benefit-icon" aria-hidden="true">
        {icon}
      </span>
      <span>{label}</span>
    </div>
  )
}
