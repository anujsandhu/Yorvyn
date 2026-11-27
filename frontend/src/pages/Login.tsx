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
import { motion, AnimatePresence } from 'framer-motion'
import { EnvelopeSimple, LockKey, User as UserIcon, Eye, EyeSlash } from '../components/icons'
import toast from 'react-hot-toast'
import { useAuth } from '../context/AuthContext'
import { AtmosphereBackground } from '../components/AtmosphereBackground'
import yorvynLogo from '../assets/yorvyn-logo.png'
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
      {/* ── 1. Dynamic Atmosphere Sky Background ── */}
      <AtmosphereBackground 
        lowlightColor={0x93c5fd}
        highlightColor={0xffffff}
        midtoneColor={0xbfdbfe}
        baseColor={0xe0f2fe}
        blurFactor={0.5}
        speed={0.45}
      />

      {/* ── 2. Floating Frosted Glass Card with Smooth Spring Animation ── */}
      <motion.div 
        className="yorvyn-auth-card"
        initial={{ opacity: 0, y: 24, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        {/* Top Brand Logo */}
        <div className="auth-brand-badge" aria-label="Yorvyn">
          <img src={yorvynLogo} alt="Yorvyn" className="auth-brand-logo-img" />
        </div>

        {/* Header Typography with Smooth Fade Transitions */}
        <AnimatePresence mode="wait">
          <motion.div
            key={authMode}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
          >
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
          </motion.div>
        </AnimatePresence>

        {/* ── 3. Input Form ── */}
        <form onSubmit={handleSubmit} className="auth-pill-form" noValidate>
          {authMode === 'signup' && (
            <div className="auth-pill-input-wrap">
              <span className="auth-pill-left-icon">
                <UserIcon size={16} />
              </span>
              <input
                type="text"
                placeholder="Full Name (e.g. Aarav Sharma)"
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
              <EnvelopeSimple size={16} />
            </span>
            <input
              type="email"
              placeholder="Email (e.g. aarav@example.in)"
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
                <LockKey size={16} />
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
                {showPassword ? <EyeSlash size={16} /> : <Eye size={16} />}
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

        {/* ── 5. Social Google Sign-In ── */}
        <div className="auth-social-row">
          <motion.button
            type="button"
            className="auth-google-pill-btn"
            onClick={handleGoogleSignIn}
            disabled={isSubmitting}
            title="Sign in with Google"
            aria-label="Sign in with Google"
            whileHover={{ scale: 1.012 }}
            whileTap={{ scale: 0.985 }}
            transition={{ duration: 0.18 }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className="auth-google-icon">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
            </svg>
            <span className="auth-google-text">Sign in with Google</span>
          </motion.button>
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
      </motion.div>
    </div>
  )
}
