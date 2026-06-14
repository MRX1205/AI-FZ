import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { HomePage } from './pages/HomePage'
import { MerchantAccountPage } from './pages/MerchantAccountPage'
import { MerchantAccountBenefitsPage } from './pages/MerchantAccountBenefitsPage'
import { MerchantAccountPaymentResultPage } from './pages/MerchantAccountPaymentResultPage'
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
import { MerchantPublishResultPage } from './pages/MerchantPublishResultPage'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { ProductDetailPage } from './pages/ProductDetailPage'
import { routeGroups } from './routes'

const implementedRoutes = new Set([
  '/',
  '/products/:id',
  '/merchant/account',
  '/merchant/account/benefits',
  '/merchant/account/payment-result',
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
  '/merchant/publish/result',
  '/merchant/publish/result/:id',
])

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/products/:id" element={<ProductDetailPage />} />
        <Route path="/merchant/account" element={<MerchantAccountPage />} />
        <Route path="/merchant/account/benefits" element={<MerchantAccountBenefitsPage />} />
        <Route path="/merchant/account/payment-result" element={<MerchantAccountPaymentResultPage />} />
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
        <Route path="/merchant/publish/result" element={<Navigate to="/merchant/publish" replace />} />
        <Route path="/merchant/publish/result/:id" element={<MerchantPublishResultPage />} />
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
