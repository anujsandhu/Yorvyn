import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { MainView } from './components/MainView'
import { AppSideNav } from './components/AppSideNav'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AppLoader } from './components/AppLoader'
import { AuthProvider } from './context/AuthContext'
import { AppProvider } from './context/AppContext'
import { ErrorBoundary } from './components/ErrorBoundary'
import './App.css'

const LoginPage = lazy(() => import('./pages/Login').then(m => ({ default: m.LoginPage })))
const OnboardingWizard = lazy(() => import('./features/onboarding/OnboardingWizard').then(m => ({ default: m.OnboardingWizard })))

/**
 * AppShell renders the main application layout with the persistent
 * desktop Side Nav Bar in crystal liquid glass and single-screen unified tray.
 */
function AppShell() {
  return (
    <div className="app app-home-stage">
      <AppSideNav />
      <MainView />
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
            <Route
              path="/login"
              element={
                <Suspense fallback={<AppLoader />}>
                  <LoginPage />
                </Suspense>
              }
            />

            {/* Onboarding Wizard Route */}
            <Route
              path="/onboarding"
              element={
                <ProtectedRoute checkOnboarding={false}>
                  <Suspense fallback={<AppLoader />}>
                    <OnboardingWizard />
                  </Suspense>
                </ProtectedRoute>
              }
            />

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

          {/* Luxury Apple-Grade Capsule Toaster (Centered Top) */}
          <Toaster
            position="top-center"
            containerStyle={{
              top: 22,
              zIndex: 999999,
            }}
            toastOptions={{
              className: 'yorvyn-capsule-toast',
              duration: 2200,
              style: {
                borderRadius: '9999px',
                background: '#ffffff',
                border: '1px solid rgba(226, 232, 240, 0.95)',
                boxShadow: '0 16px 40px -6px rgba(15, 23, 42, 0.14), 0 4px 14px -2px rgba(15, 23, 42, 0.05)',
                color: '#0f172a',
                padding: '8px 18px',
                minHeight: '40px',
                fontSize: '0.86rem',
                fontWeight: 500,
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Inter", sans-serif',
                letterSpacing: '-0.015em',
              },
              success: {
                duration: 2200,
                iconTheme: {
                  primary: '#0f172a',
                  secondary: '#ffffff',
                },
              },
              error: {
                duration: 3400,
                iconTheme: {
                  primary: '#ef4444',
                  secondary: '#ffffff',
                },
              },
              loading: {
                iconTheme: {
                  primary: '#0f172a',
                  secondary: '#e2e8f0',
                },
              },
            }}
          />
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  )
}

export default App
