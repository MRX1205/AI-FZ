import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { HomePage } from './pages/HomePage'
import { MerchantAuthPage } from './pages/MerchantAuthPage'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { routeGroups } from './routes'

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/merchant/auth" element={<MerchantAuthPage />} />
        {routeGroups.flatMap((group) =>
          group.routes.filter((route) => route.path !== '/' && route.path !== '/merchant/auth').map((route) => (
            <Route
              key={route.path}
              path={route.path}
              element={<PlaceholderPage route={route} groupTitle={group.title} />}
            />
          )),
        )}
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
