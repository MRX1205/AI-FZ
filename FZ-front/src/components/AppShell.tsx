import { Outlet, useLocation } from 'react-router-dom'

export function AppShell() {
  const location = useLocation()

  return (
    <main className="app-frame">
      <div className="phone-shell">
        <div className="route-stage" key={location.pathname}>
          <Outlet />
        </div>
      </div>
    </main>
  )
}
