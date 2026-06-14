import {
  Bell,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Info,
  LogOut,
  Mail,
  UserRound,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, apiGet, apiPatch, apiPost } from '../api/client'
import type { AuthCodeResponse, MerchantProfileResponse } from '../types/domain'
import {
  clearMerchantSession,
  getAuthHeaders,
  readMerchantSession,
  updateMerchantSessionMerchant,
} from './merchantAuthStorage'

function formatDate(value?: string | null) {
  if (!value) return '2025-05-20'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
    .format(new Date(value))
    .replaceAll('/', '-')
}

function isValidEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim())
}

export function MerchantProfilePage() {
  const navigate = useNavigate()
  const [profile, setProfile] = useState<MerchantProfileResponse | null>(null)
  const [activeSection, setActiveSection] = useState<string | null>(null)
  const [newEmail, setNewEmail] = useState('')
  const [emailCode, setEmailCode] = useState('')
  const [message, setMessage] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const token = useMemo(() => readMerchantSession()?.token ?? '', [])

  useEffect(() => {
    if (!token) {
      navigate('/merchant/auth', { replace: true })
      return
    }

    apiGet<MerchantProfileResponse>('/api/merchant/profile', {
      headers: getAuthHeaders(token),
      })
      .then((response) => {
        setProfile(response)
        setNewEmail(response.email)
        updateMerchantSessionMerchant(response)
      })
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) {
          clearMerchantSession()
          navigate('/merchant/auth', { replace: true })
        }
      })
  }, [navigate, token])

  if (!profile) {
    return (
      <section className="merchant-profile-page">
        <ProfileHeader title="个人中心" onBack={() => navigate('/merchant/dashboard')} />
        <div className="profile-loading">加载中...</div>
      </section>
    )
  }

  const isVip = profile.tier === 'vip'
  const expiresText = isVip ? `有效期至 ${formatDate(profile.vipExpiresAt)}` : '有效期至 永久'

  async function handleSendEmailCode() {
    if (!token || !isValidEmail(newEmail)) {
      setMessage('请输入正确的新邮箱')
      return
    }

    const response = await apiPost<AuthCodeResponse>(
      '/api/merchant/profile/email-code',
      {
        email: newEmail.trim().toLowerCase(),
      },
      {
        headers: getAuthHeaders(token),
      },
    )
    setMessage(`开发验证码：${response.devCode}`)
  }

  async function handleSaveEmail() {
    if (!token || !isValidEmail(newEmail) || !emailCode.trim()) {
      setMessage('请填写新邮箱和验证码')
      return
    }

    setIsSaving(true)
    try {
      const response = await apiPatch<MerchantProfileResponse>(
        '/api/merchant/profile/email',
        {
          email: newEmail.trim().toLowerCase(),
          code: emailCode.trim(),
        },
        { headers: getAuthHeaders(token) },
      )
      setProfile(response)
      updateMerchantSessionMerchant(response)
      setMessage('修改邮箱成功')
    } catch (error) {
      if (error instanceof ApiError && error.status === 400) {
        setMessage('验证码错误、过期或邮箱已存在')
      }
    } finally {
      setIsSaving(false)
    }
  }

  async function handleEmailNotificationChange(enabled: boolean) {
    if (!token) return
    const response = await apiPatch<MerchantProfileResponse['notifications']>(
      '/api/merchant/profile/notifications',
      { emailNotificationEnabled: enabled },
      { headers: getAuthHeaders(token) },
    )
    setProfile((current) => (current ? { ...current, notifications: response } : current))
  }

  async function handleLogout() {
    if (token) {
      try {
        await apiPost('/api/auth/logout', {}, { headers: getAuthHeaders(token) })
      } catch {
        // 本地退出优先，后端 token 已失效时也要清理前端登录态。
      }
    }
    clearMerchantSession()
    navigate('/')
  }

  function toggleSection(section: string) {
    setMessage('')
    setActiveSection((current) => (current === section ? null : section))
  }

  return (
    <section className="merchant-profile-page">
      <ProfileHeader title="个人中心" onBack={() => navigate('/merchant/dashboard')} />

      <div className="profile-scroll">
        <button className="seller-card" type="button" onClick={() => navigate('/merchant/account')}>
          <span className="seller-avatar" aria-hidden="true">
            <UserRound size={36} />
          </span>
          <span className="seller-meta">
            <strong>
              {profile.email}
              {isVip ? <em>VIP会员</em> : null}
            </strong>
            <small>{expiresText}</small>
          </span>
          <ChevronRight size={24} />
        </button>

        <div className="profile-list">
          <ProfileItem icon={<UserRound size={20} />} label="账户信息" onClick={() => toggleSection('account')} />
          {activeSection === 'account' ? (
            <div className="profile-expand">
              {isVip ? (
                <p>VIP起止日 {formatDate(profile.vipStartedAt)} ~ {formatDate(profile.vipExpiresAt)}</p>
              ) : (
                <p>普通会员 / 有效期至 永久</p>
              )}
            </div>
          ) : null}

          <ProfileItem icon={<Mail size={20} />} label="修改邮箱" onClick={() => toggleSection('email')} />
          {activeSection === 'email' ? (
            <div className="profile-expand">
              <p>当前邮箱 {profile.email}</p>
              <div className="inline-control">
                <input value={newEmail} placeholder="修改邮箱" onChange={(event) => setNewEmail(event.target.value)} />
                <button type="button" onClick={() => void handleSendEmailCode()}>
                  发送验证码
                </button>
              </div>
              <div className="inline-control">
                <input value={emailCode} placeholder="验证码" onChange={(event) => setEmailCode(event.target.value)} />
                <button type="button" disabled={isSaving} onClick={() => void handleSaveEmail()}>
                  保存
                </button>
              </div>
              {message ? <p className="profile-message">{message}</p> : null}
            </div>
          ) : null}

          <ProfileItem icon={<Bell size={20} />} label="通知设置" onClick={() => toggleSection('notifications')} />
          {activeSection === 'notifications' ? (
            <div className="profile-expand notification-options">
              <label>
                <input checked disabled type="checkbox" />
                有人感兴趣时网页内通知我
              </label>
              <label>
                <input
                  checked={profile.notifications.emailNotificationEnabled}
                  type="checkbox"
                  onChange={(event) => void handleEmailNotificationChange(event.target.checked)}
                />
                有人感兴趣时邮件通知我
              </label>
            </div>
          ) : null}

          <ProfileItem icon={<CircleHelp size={20} />} label="帮助中心" onClick={() => setMessage('帮助中心暂未开放')} />
          <ProfileItem icon={<Info size={20} />} label="关于我们" onClick={() => setMessage('关于我们暂未开放')} />
          <ProfileItem icon={<LogOut size={20} />} label="退出登录" onClick={() => void handleLogout()} />
        </div>

        {message && activeSection !== 'email' ? <p className="profile-toast">{message}</p> : null}
      </div>
    </section>
  )
}

function ProfileHeader({ title, onBack }: { title: string; onBack: () => void }) {
  return (
    <header className="profile-header">
      <button type="button" aria-label="返回" onClick={onBack}>
        <ChevronLeft size={31} strokeWidth={2.4} />
      </button>
      <h1>{title}</h1>
      <span aria-hidden="true" />
    </header>
  )
}

function ProfileItem({
  icon,
  label,
  onClick,
}: {
  icon: ReactNode
  label: string
  onClick: () => void
}) {
  return (
    <button className="profile-item" type="button" onClick={onClick}>
      <span className="profile-item-icon" aria-hidden="true">
        {icon}
      </span>
      <span>{label}</span>
      <ChevronRight size={22} />
    </button>
  )
}
