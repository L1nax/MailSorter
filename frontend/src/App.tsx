import { Routes, Route } from 'react-router-dom'
import Layout from '@/components/layout/Layout'
import Dashboard from '@/pages/Dashboard'
import Rules from '@/pages/Rules'
import Logs from '@/pages/Logs'
import SettingsPage from '@/pages/SettingsPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="rules" element={<Rules />} />
        <Route path="logs" element={<Logs />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  )
}
