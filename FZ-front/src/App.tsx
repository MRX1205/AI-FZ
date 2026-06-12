import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { routeGroups } from './routes'

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        {routeGroups.flatMap((group) =>
          group.routes.map((route) => (
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
