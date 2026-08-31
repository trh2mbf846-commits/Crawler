import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Escalations } from './pages/Escalations'
import { Overview } from './pages/Overview'
import { PortalStatus } from './pages/PortalStatus'
import { SearchProfiles } from './pages/SearchProfiles'
import { TenderDetailPage } from './pages/TenderDetailPage'

function NotFound() {
  return (
    <div className="rounded-lg border border-dashed border-line bg-surface px-6 py-14 text-center">
      <p className="text-sm font-semibold text-ink">Seite nicht gefunden</p>
    </div>
  )
}

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/tenders/:id" element={<TenderDetailPage />} />
        <Route path="/profiles" element={<SearchProfiles />} />
        <Route path="/portals" element={<PortalStatus />} />
        <Route path="/escalations" element={<Escalations />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Layout>
  )
}

export default App
