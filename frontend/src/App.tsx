import { useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { MainView } from './components/MainView'
import { AppSideNav } from './components/AppSideNav'
import { SettingsModal } from './components/SettingsModal'
import { ProtectedRoute } from './components/ProtectedRoute'
import { LoginPage } from './pages/Login'
import { AuthProvider } from './context/AuthContext'
import { AppProvider } from './context/AppContext'
import { ErrorBoundary } from './components/ErrorBoundary'
import './App.css'

/**
 * AppShell renders the main application layout with the persistent
 * desktop Side Nav Bar and page routes.
 */
function AppShell() {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  return (
    <div className="app app-home-stage">
      <AppSideNav onOpenSettings={() => setIsSettingsOpen(true)} />
      <MainView />
      <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
    </div>
  )
}

/**
 * Main App Component
 */
function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <AuthProvider>
          <Routes>
            {/* Public Routes */}
            <Route path="/login" element={<LoginPage />} />

            {/* Protected Routes */}
            <Route
              path="/*"
              element={
                <ProtectedRoute>
                  <AppProvider>
                    <AppShell />
                  </AppProvider>
                </ProtectedRoute>
              }
            />
          </Routes>

          <Toaster
            position="bottom-right"
            toastOptions={{
              style: {
                fontFamily: 'var(--font-body)',
                fontSize: '0.85rem',
                background: '#fff',
                color: 'var(--text)',
                border: '1px solid var(--border)',
                boxShadow: 'var(--shadow-md)',
                borderRadius: 'var(--r-md)',
              },
            }}
          />
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  )
}

export default App
