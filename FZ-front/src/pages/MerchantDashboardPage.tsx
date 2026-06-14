import {
  Bell,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Crown,
  Home,
  LayoutDashboard,
  Package,
  Plus,
  UserRound,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, apiGet } from '../api/client'
import type { MerchantDashboardResponse, MerchantTier } from '../types/domain'
import {
  clearMerchantSession,
  readMerchantSession,
  updateMerchantSessionMerchant,
} from './merchantAuthStorage'

function formatLeadTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

export function MerchantDashboardPage() {
  const navigate = useNavigate()
  const [dashboard, setDashboard] = useState<MerchantDashboardResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const session = readMerchantSession()
    if (!session?.token) {
      navigate('/merchant/auth', { replace: true })
      return
    }

    apiGet<MerchantDashboardResponse>('/api/merchant/dashboard', {
      headers: {
        Authorization: `Bearer ${session.token}`,
      },
    })
      .then((response) => {
        setDashboard(response)
        updateMerchantSessionMerchant(response.merchant)
      })
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) {
          clearMerchantSession()
          navigate('/merchant/auth', { replace: true })
          return
        }
      })
      .finally(() => {
        setIsLoading(false)
      })
  }, [navigate])

  const tier = dashboard?.merchant.tier ?? 'free'
  const isVip = tier === 'vip'

  return (
    <section className="merchant-dashboard-page">
      <header className="dashboard-header">
        <button className="dashboard-icon-button" type="button" aria-label="返回首页" onClick={() => navigate('/')}>
          <ChevronLeft size={29} strokeWidth={2.4} />
        </button>
        <div className="dashboard-title-wrap">
          <h1>商家后台</h1>
          {isVip ? <span className="dashboard-vip-badge">VIP</span> : null}
        </div>
        <button
          className="dashboard-icon-button"
          type="button"
          aria-label="系统通知"
          onClick={() => navigate('/merchant/notifications')}
        >
          <Bell size={25} strokeWidth={2.2} />
        </button>
      </header>

      <div className="dashboard-scroll">
        {isLoading || !dashboard ? (
          <div className="dashboard-loading">加载中...</div>
        ) : (
          <>
            <StatsPanel stats={dashboard.stats} />
            <ShortcutGrid />
            <RecentLeads leads={dashboard.recentLeads} />
            <LeadPromo />
          </>
        )}
      </div>

      <DashboardTabBar tier={tier} />
    </section>
  )
}

function StatsPanel({ stats }: { stats: MerchantDashboardResponse['stats'] }) {
  return (
    <section className="dashboard-stats" aria-label="商家数据">
      <div>
        <span>商品数量</span>
        <strong>
          {stats.listedProducts}
          <small> / {stats.productLimit}</small>
        </strong>
        <em>已上架 / 上限</em>
      </div>
      <div>
        <span>今日客资</span>
        <strong>
          {stats.todayLeads}
          <small> 条</small>
        </strong>
      </div>
      <div>
        <span>累计客资</span>
        <strong>
          {stats.totalLeads}
          <small> 条</small>
        </strong>
      </div>
    </section>
  )
}

function ShortcutGrid() {
  const navigate = useNavigate()
  const items = [
    { label: '发布商品', path: '/merchant/publish', icon: <Plus size={31} />, tone: 'green' },
    { label: '商品管理', path: '/merchant/products', icon: <Package size={28} />, tone: 'blue' },
    { label: '客资列表', path: '/merchant/leads', icon: <UserRound size={29} />, tone: 'orange' },
    { label: '账户权限', path: '/merchant/account', icon: <Crown size={29} />, tone: 'purple' },
  ]

  return (
    <nav className="dashboard-shortcuts" aria-label="商家后台功能">
      {items.map((item) => (
        <button type="button" key={item.label} onClick={() => navigate(item.path)}>
          <span className={`shortcut-icon shortcut-${item.tone}`}>{item.icon}</span>
          <span>{item.label}</span>
        </button>
      ))}
    </nav>
  )
}

function RecentLeads({ leads }: { leads: MerchantDashboardResponse['recentLeads'] }) {
  const navigate = useNavigate()

  return (
    <section className="recent-leads-panel">
      <header>
        <h2>最近客资</h2>
        <button type="button" onClick={() => navigate('/merchant/leads')}>
          全部
          <ChevronRight size={18} />
        </button>
      </header>
      <ul>
        {leads.map((lead) => (
          <li key={lead.id}>
            <time>
              <Clock3 size={15} />
              {formatLeadTime(lead.submittedAt)}
            </time>
            <div className="lead-copy">
              <p>{lead.message}</p>
              <span>{lead.productTitle}</span>
            </div>
            <a className="lead-email" href={`mailto:${lead.buyerEmail}`}>
              {lead.buyerEmail}
            </a>
          </li>
        ))}
      </ul>
    </section>
  )
}

function LeadPromo() {
  return (
    <section className="lead-promo" aria-label="客源匹配说明">
      <strong>极速匹配客源</strong>
      <span>AI智能分发，成交快人一步</span>
    </section>
  )
}

function DashboardTabBar({ tier }: { tier: MerchantTier }) {
  const navigate = useNavigate()
  const items = [
    { label: '首页', path: '/', icon: <Home size={27} /> },
    { label: '商品', path: '/merchant/products', icon: <Package size={27} /> },
    { label: '管理后台', path: '/merchant/dashboard', icon: <LayoutDashboard size={27} />, active: true },
    { label: '我的', path: '/merchant/profile', icon: <UserRound size={27} /> },
  ]

  return (
    <nav className="dashboard-tabbar" aria-label={`${tier === 'vip' ? 'VIP' : '免费'}商家导航`}>
      {items.map((item) => (
        <TabButton
          key={item.label}
          active={item.active}
          icon={item.icon}
          label={item.label}
          onClick={() => navigate(item.path)}
        />
      ))}
    </nav>
  )
}

function TabButton({
  active,
  icon,
  label,
  onClick,
}: {
  active?: boolean
  icon: ReactNode
  label: string
  onClick: () => void
}) {
  return (
    <button className={active ? 'is-active' : ''} type="button" onClick={onClick}>
      {icon}
      <span>{label}</span>
    </button>
  )
}
