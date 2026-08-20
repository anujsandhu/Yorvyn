import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { TopNav } from './components/TopNav'
import { Sidebar } from './components/Sidebar'
import { MainView } from './components/MainView'
import { ProtectedRoute } from './components/ProtectedRoute'
import { LoginPage } from './pages/Login'
import { AuthProvider } from './context/AuthContext'
import { AppProvider } from './context/AppContext'
import { ErrorBoundary } from './components/ErrorBoundary'
import './App.css'

/**
 * Main App Component
 * 
 * Initializes Firebase, sets up authentication, and routing.
 * - /login - Public login page
 * - /* - Protected app pages (requires authentication)
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
                    <div className="app">
                      <TopNav />
                      <div className="app-body">
                        <Sidebar />
                        <Routes>
                          <Route path="/*" element={<MainView />} />
                        </Routes>
                      </div>
                    </div>
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
