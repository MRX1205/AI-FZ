import { Home, LayoutDashboard, Package, UserRound } from 'lucide-react'
import type { ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

type MerchantTabKey = 'home' | 'products' | 'dashboard' | 'profile'

function activeMerchantTab(pathname: string): MerchantTabKey {
  if (pathname === '/') return 'home'
  if (pathname.startsWith('/merchant/products') || pathname.startsWith('/merchant/publish')) {
    return 'products'
  }
  if (pathname.startsWith('/merchant/profile') || pathname.startsWith('/merchant/account')) {
    return 'profile'
  }
  return 'dashboard'
}

export function MerchantTabBar() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const activeTab = activeMerchantTab(pathname)
  const items: Array<{ key: MerchantTabKey; label: string; path: string; icon: ReactNode }> = [
    { key: 'home', label: '首页', path: '/', icon: <Home size={27} /> },
    { key: 'products', label: '商品', path: '/merchant/products', icon: <Package size={27} /> },
    {
      key: 'dashboard',
      label: '管理后台',
      path: '/merchant/dashboard',
      icon: <LayoutDashboard size={27} />,
    },
    { key: 'profile', label: '我的', path: '/merchant/profile', icon: <UserRound size={27} /> },
  ]

  return (
    <nav className="dashboard-tabbar" aria-label="商家导航">
      {items.map((item) => (
        <button
          className={activeTab === item.key ? 'is-active' : ''}
          key={item.key}
          type="button"
          onClick={() => navigate(item.path)}
        >
          {item.icon}
          <span>{item.label}</span>
        </button>
      ))}
    </nav>
  )
}
