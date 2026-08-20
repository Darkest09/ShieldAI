import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Toaster } from 'sonner'
import './index.css'
import App from './App.tsx'
import { CriticalAlertPoller } from '@/components/CriticalAlertPoller.tsx'
import { ThemeProvider } from './context/theme.tsx'
import Overview from './pages/Overview.tsx'
import ConfigPanel from './pages/ConfigPanel.tsx'
import SecurityLogs from './pages/SecurityLogs.tsx'
import Governance from './pages/Governance.tsx'
import Login from './pages/Login.tsx'
import Users from './pages/Users.tsx'
import SystemStatus from './pages/SystemStatus.tsx'
import { AuthProvider, useAuth } from './context/auth.tsx'

function ProtectedApp() {
  const { user, loading } = useAuth()
  if (loading) return <div className="p-8 text-sm text-zinc-500">Loading session…</div>
  if (!user) return <Navigate to="/login" replace />
  return <><CriticalAlertPoller /><App /></>
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <Toaster richColors closeButton theme="system" />
      <BrowserRouter basename={import.meta.env.BASE_URL}>
        <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<ProtectedApp />}>
            <Route index element={<Overview />} />
            <Route path="logs" element={<SecurityLogs />} />
            <Route path="governance" element={<Governance />} />
            <Route path="config" element={<ConfigPanel />} />
            <Route path="system" element={<SystemStatus />} />
            <Route path="users" element={<Users />} />
          </Route>
        </Routes>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  </StrictMode>,
)
