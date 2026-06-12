import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { HomePage } from './pages/HomePage'
import { MerchantAccountPage } from './pages/MerchantAccountPage'
import { MerchantAuthPage } from './pages/MerchantAuthPage'
import { MerchantDashboardPage } from './pages/MerchantDashboardPage'
import { MerchantLeadDetailPage } from './pages/MerchantLeadDetailPage'
import { MerchantLeadsPage } from './pages/MerchantLeadsPage'
import { MerchantNotificationsPage } from './pages/MerchantNotificationsPage'
import { MerchantProductEditPage } from './pages/MerchantProductEditPage'
import { MerchantProductsPage } from './pages/MerchantProductsPage'
import { MerchantProfilePage } from './pages/MerchantProfilePage'
import { MerchantPublishEditPage } from './pages/MerchantPublishEditPage'
import { MerchantPublishPage } from './pages/MerchantPublishPage'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { routeGroups } from './routes'

const implementedRoutes = new Set([
  '/',
  '/merchant/account',
  '/merchant/auth',
  '/merchant/dashboard',
  '/merchant/leads',
  '/merchant/leads/:id',
  '/merchant/notifications',
  '/merchant/products',
  '/merchant/products/:id/edit',
  '/merchant/profile',
  '/merchant/publish',
  '/merchant/publish/edit/:id',
])

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/merchant/account" element={<MerchantAccountPage />} />
        <Route path="/merchant/auth" element={<MerchantAuthPage />} />
        <Route path="/merchant/dashboard" element={<MerchantDashboardPage />} />
        <Route path="/merchant/leads" element={<MerchantLeadsPage />} />
        <Route path="/merchant/leads/:id" element={<MerchantLeadDetailPage />} />
        <Route path="/merchant/notifications" element={<MerchantNotificationsPage />} />
        <Route path="/merchant/products" element={<MerchantProductsPage />} />
        <Route path="/merchant/products/:id/edit" element={<MerchantProductEditPage />} />
        <Route path="/merchant/profile" element={<MerchantProfilePage />} />
        <Route path="/merchant/publish" element={<MerchantPublishPage />} />
        <Route path="/merchant/publish/edit/:id" element={<MerchantPublishEditPage />} />
        {routeGroups.flatMap((group) =>
          group.routes.filter((route) => !implementedRoutes.has(route.path)).map((route) => (
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
