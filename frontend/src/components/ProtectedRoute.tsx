import { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { AppLoader } from './AppLoader'

interface ProtectedRouteProps {
  children: ReactNode
  checkOnboarding?: boolean
}

export function ProtectedRoute({ children, checkOnboarding = true }: ProtectedRouteProps) {
  const { user, loading, onboardingCompleted } = useAuth()
  const location = useLocation()

  if (loading) return <AppLoader />
  if (!user)   return <Navigate to="/login" replace />

  // If user has not completed onboarding and is trying to access protected main app,
  // redirect to /onboarding
  if (checkOnboarding && !onboardingCompleted && location.pathname !== '/onboarding') {
    return <Navigate to="/onboarding" replace />
  }

  // If user completed onboarding and tries to visit /onboarding, redirect to home /
  if (!checkOnboarding && onboardingCompleted && location.pathname === '/onboarding') {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
