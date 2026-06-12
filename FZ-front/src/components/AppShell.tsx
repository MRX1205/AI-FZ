import { Outlet } from 'react-router-dom'

export function AppShell() {
  return (
    <main className="app-frame">
      <div className="phone-shell">
        <Outlet />
      </div>
    </main>
  )
}
