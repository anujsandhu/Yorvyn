/**
 * Login & Registration Page — Yorvyn
 *
 * Polished, high-fashion aesthetic authentication page matching the reference design:
 * - Floating glassmorphic card with frosted backdrop blur
 * - Ambient sky-blue atmospheric background with dynamic fog and subtle orbit arcs
 * - Centered sign-in doorway icon badge
 * - Pill-shaped input fields with icons and show/hide password toggle
 * - Dark charcoal primary action button ("Get Started" / "Sign In")
 * - "Or sign in with" divider with 3 social buttons (Google, Facebook, Apple)
 * - Seamless switching between Sign In, Create Account, and Password Recovery
 */

import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Mail, Lock, User as UserIcon, Eye, EyeOff } from 'lucide-react'
import toast from 'react-hot-toast'
import { useAuth } from '../context/AuthContext'
import { AtmosphereBackground } from '../components/AtmosphereBackground'
import './Login.css'

export function LoginPage() {
  const navigate = useNavigate()
  const { user, loading, onboardingCompleted, signInWithGoogle, signInWithEmail, signUpWithEmail, resetPassword } = useAuth()
  
  // Auth view mode: 'login' | 'signup' | 'forgot'
  const [authMode, setAuthMode] = useState<'login' | 'signup' | 'forgot'>('login')
  
  // Form fields
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Redirect if already authenticated
  useEffect(() => {
    if (user && !loading) {
      if (onboardingCompleted) {
        navigate('/', { replace: true })
      } else {
        navigate('/onboarding', { replace: true })
      }
    }
  }, [user, loading, onboardingCompleted, navigate])

  const handleGoogleSignIn = async () => {
    setIsSubmitting(true)
    try {
      await signInWithGoogle()
    } catch (err: any) {
      toast.error(err?.message || 'Google sign-in failed. Please try email login.')
      setIsSubmitting(false)
    }
  }

  const handleFacebookSignIn = () => {
    toast('Facebook authentication will be enabled in production.', {
      icon: 'ℹ️'
    })
  }

  const handleAppleSignIn = () => {
    toast('Apple Sign-In will be enabled in production.', {
      icon: 'ℹ️'
    })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || (!password && authMode !== 'forgot')) {
      toast.error('Please enter all required fields.')
      return
    }

    setIsSubmitting(true)
    try {
      if (authMode === 'login') {
        const { error } = await signInWithEmail(email, password)
        if (error) {
          toast.error(error.message || 'Invalid email or password.')
        } else {
          toast.success('Welcome back to Yorvyn.')
          // AuthContext will determine if onboarding is completed or needed
        }
      } else if (authMode === 'signup') {
        const { error } = await signUpWithEmail(email, password, name)
        if (error) {
          toast.error(error.message || 'Registration failed. Please try again.')
        } else {
          toast.success('Account created! Welcome to your digital atelier.')
          navigate('/onboarding')
        }
      } else if (authMode === 'forgot') {
        const { error } = await resetPassword(email)
        if (error) {
          toast.error(error.message || 'Could not send recovery email.')
        } else {
          toast.success('Password recovery link sent! Check your inbox.')
          setAuthMode('login')
        }
      }
    } catch (err: any) {
      toast.error(err?.message || 'Authentication error encountered.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="yorvyn-login-page">
      {/* ── 1. Dynamic Atmosphere & Concentric Sky Arcs ── */}
      <AtmosphereBackground 
        lowlightColor={0x93c5fd}
        highlightColor={0xffffff}
        midtoneColor={0xbfdbfe}
        baseColor={0xe0f2fe}
        blurFactor={0.5}
        speed={0.45}
      />

      <div className="sky-ambient-overlay" aria-hidden="true">
        {/* Subtle geometric orbital arcs as in design reference */}
        <svg className="sky-concentric-arcs" viewBox="0 0 1200 800" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="600" cy="400" r="280" stroke="rgba(255, 255, 255, 0.45)" strokeWidth="1.2" />
          <circle cx="600" cy="400" r="420" stroke="rgba(255, 255, 255, 0.3)" strokeWidth="1" strokeDasharray="6 6" />
          <circle cx="600" cy="400" r="580" stroke="rgba(255, 255, 255, 0.2)" strokeWidth="1" />
        </svg>
      </div>

      {/* ── 2. Floating Frosted Glass Card ── */}
      <div className="yorvyn-auth-card">
        {/* Top Badge Icon */}
        <div className="auth-badge-icon" aria-hidden="true">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#1e2025" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
            <polyline points="10 17 15 12 10 7" />
            <line x1="15" y1="12" x2="3" y2="12" />
          </svg>
        </div>

        {/* Header Typography */}
        <h1 className="auth-card-title">
          {authMode === 'login' && 'Sign in with email'}
          {authMode === 'signup' && 'Create your account'}
          {authMode === 'forgot' && 'Reset your password'}
        </h1>
        <p className="auth-card-subtitle">
          {authMode === 'login' && 'Experience personalized fashion, digital wardrobe, and real 3D avatar styling. For free'}
          {authMode === 'signup' && 'Join Yorvyn to configure your personalized 3D avatar and digital styling atelier.'}
          {authMode === 'forgot' && 'Enter your verified account email to receive a secure password reset link.'}
        </p>

        {/* ── 3. Input Form ── */}
        <form onSubmit={handleSubmit} className="auth-pill-form" noValidate>
          {authMode === 'signup' && (
            <div className="auth-pill-input-wrap">
              <span className="auth-pill-left-icon">
                <UserIcon size={16} />
              </span>
              <input
                type="text"
                placeholder="Full Name"
                className="auth-pill-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={isSubmitting}
                required
                autoComplete="name"
              />
            </div>
          )}

          <div className="auth-pill-input-wrap">
            <span className="auth-pill-left-icon">
              <Mail size={16} />
            </span>
            <input
              type="email"
              placeholder="Email"
              className="auth-pill-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isSubmitting}
              required
              autoComplete="email"
            />
          </div>

          {authMode !== 'forgot' && (
            <div className="auth-pill-input-wrap">
              <span className="auth-pill-left-icon">
                <Lock size={16} />
              </span>
              <input
                type={showPassword ? 'text' : 'password'}
                placeholder="Password"
                className="auth-pill-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isSubmitting}
                required
                minLength={6}
                autoComplete={authMode === 'signup' ? 'new-password' : 'current-password'}
              />
              <button
                type="button"
                className="auth-pill-eye-btn"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          )}

          {authMode === 'login' && (
            <div className="auth-forgot-row">
              <button
                type="button"
                className="auth-forgot-link"
                onClick={() => setAuthMode('forgot')}
              >
                Forgot password?
              </button>
            </div>
          )}

          {/* Primary Action Button */}
          <button
            type="submit"
            className="auth-dark-cta-btn"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              'Please wait...'
            ) : authMode === 'login' ? (
              'Get Started'
            ) : authMode === 'signup' ? (
              'Create Account'
            ) : (
              'Send Reset Link'
            )}
          </button>
        </form>

        {/* ── 4. Social Divider ── */}
        <div className="auth-dotted-divider">
          <span>Or sign in with</span>
        </div>

        {/* ── 5. Social Icon Row (Google, Facebook, Apple) ── */}
        <div className="auth-social-row">
          {/* Google Button */}
          <button
            type="button"
            className="auth-social-pill"
            onClick={handleGoogleSignIn}
            disabled={isSubmitting}
            title="Sign in with Google"
            aria-label="Sign in with Google"
          >
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
            </svg>
          </button>

          {/* Facebook Button */}
          <button
            type="button"
            className="auth-social-pill"
            onClick={handleFacebookSignIn}
            disabled={isSubmitting}
            title="Sign in with Facebook"
            aria-label="Sign in with Facebook"
          >
            <svg width="19" height="19" viewBox="0 0 24 24" fill="#1877F2">
              <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
            </svg>
          </button>

          {/* Apple Button */}
          <button
            type="button"
            className="auth-social-pill"
            onClick={handleAppleSignIn}
            disabled={isSubmitting}
            title="Sign in with Apple"
            aria-label="Sign in with Apple"
          >
            <svg width="19" height="19" viewBox="0 0 24 24" fill="#000000">
              <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M15.97 6.37c.62-.75 1.04-1.8 0.93-2.85-.9.04-1.99.6-2.63 1.35-.57.66-.99 1.72-.88 2.74 1.01.08 2.04-.54 2.58-1.24z" />
            </svg>
          </button>
        </div>

        {/* ── 6. Bottom Switcher Link ── */}
        <div className="auth-switch-wrap">
          {authMode === 'login' ? (
            <p className="auth-switch-text">
              Don't have an account?{' '}
              <button
                type="button"
                className="auth-switch-link"
                onClick={() => setAuthMode('signup')}
              >
                Create one
              </button>
            </p>
          ) : authMode === 'signup' ? (
            <p className="auth-switch-text">
              Already have an account?{' '}
              <button
                type="button"
                className="auth-switch-link"
                onClick={() => setAuthMode('login')}
              >
                Sign in
              </button>
            </p>
          ) : (
            <p className="auth-switch-text">
              Remember your password?{' '}
              <button
                type="button"
                className="auth-switch-link"
                onClick={() => setAuthMode('login')}
              >
                Sign in
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
