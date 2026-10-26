/**
 * Login & Registration Page — Yorvyn
 *
 * Professional sign-in page supporting:
 * - Supabase Email & Password Authentication (Sign In & Sign Up)
 * - Google Sign-In with OAuth
 * - Password Reset & Recovery
 * - Yorvyn aesthetic styling
 */

import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, Heart, Bot, Star, Mail, Lock, User as UserIcon, ArrowRight } from 'lucide-react'
import toast from 'react-hot-toast'
import { useAuth } from '../context/AuthContext'
import { GoogleSignInButton } from '../components/GoogleSignInButton'
import { Logo } from '../components/Logo'
import { AppLoader } from '../components/AppLoader'
import './Login.css'

const NEW_USER_MESSAGES = [
  { headline: 'Discover Your Signature Style', sub: 'Tell us your mood, occasion, and preferences — our AI styles the perfect outfit for you.' },
  { headline: 'Your Fashion Journey Starts Here', sub: 'Explore curated haute-couture wardrobes matched to your personal color season and body geometry.' },
  { headline: 'Tailored Outfits You\'ll Love', sub: 'Personalized recommendations powered by machine learning and your digital wardrobe.' },
]

export function LoginPage() {
  const navigate = useNavigate()
  const { user, loading, signInWithGoogle, signInWithEmail, signUpWithEmail, resetPassword } = useAuth()
  const [msgIdx] = useState(() => Math.floor(Math.random() * NEW_USER_MESSAGES.length))
  
  // Tab state: 'login' | 'signup' | 'forgot'
  const [authTab, setAuthTab] = useState<'login' | 'signup' | 'forgot'>('login')
  
  // Form fields
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    if (user && !loading) {
      navigate('/', { replace: true })
    }
  }, [user, loading, navigate])

  const handleGoogleSignIn = async () => {
    setIsSubmitting(true)
    try {
      await signInWithGoogle()
    } catch (err: any) {
      toast.error(err?.message || 'Google sign-in failed. Please try email login.')
      setIsSubmitting(false)
    }
  }

  const handleEmailAuth = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || (!password && authTab !== 'forgot')) {
      toast.error('Please enter all required fields.')
      return
    }

    setIsSubmitting(true)
    try {
      if (authTab === 'login') {
        const { error } = await signInWithEmail(email, password)
        if (error) {
          toast.error(error.message || 'Invalid email or password.')
        } else {
          toast.success('Welcome back to Yorvyn.')
          navigate('/')
        }
      } else if (authTab === 'signup') {
        const { error } = await signUpWithEmail(email, password, name)
        if (error) {
          toast.error(error.message || 'Registration failed. Please try again.')
        } else {
          toast.success('Account created successfully! Welcome to Yorvyn.')
          navigate('/')
        }
      } else if (authTab === 'forgot') {
        const { error } = await resetPassword(email)
        if (error) {
          toast.error(error.message || 'Could not send recovery email.')
        } else {
          toast.success('Password recovery link sent! Check your inbox.')
          setAuthTab('login')
        }
      }
    } catch (err: any) {
      toast.error(err?.message || 'Authentication error encountered.')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (loading) {
    return <AppLoader />
  }

  const msg = NEW_USER_MESSAGES[msgIdx]

  return (
    <div className="lp-root">
      {/* Ambient background blobs */}
      <div className="lp-blob lp-blob-1" aria-hidden="true" />
      <div className="lp-blob lp-blob-2" aria-hidden="true" />

      <div className="lp-card">
        {/* ── Logo ── */}
        <div className="lp-logo-wrap">
          <Logo size="lg" />
        </div>

        {/* ── Headline ── */}
        <div className="lp-hero">
          <h1 className="lp-headline">{msg.headline}</h1>
          <p className="lp-sub">{msg.sub}</p>
        </div>

        {/* ── Feature pills ── */}
        <div className="lp-features">
          <div className="lp-feature">
            <span className="lp-feature-icon"><Sparkles size={15} /></span>
            <span>AI Stylist</span>
          </div>
          <div className="lp-feature">
            <span className="lp-feature-icon"><Star size={15} /></span>
            <span>3D Avatar Try-On</span>
          </div>
          <div className="lp-feature">
            <span className="lp-feature-icon"><Heart size={15} /></span>
            <span>Digital Wardrobe</span>
          </div>
          <div className="lp-feature">
            <span className="lp-feature-icon"><Bot size={15} /></span>
            <span>Voice & Text Chat</span>
          </div>
        </div>

        {/* ── Auth Tabs ── */}
        <div className="auth-tab-bar">
          <button 
            type="button"
            className={`auth-tab-btn ${authTab === 'login' ? 'active' : ''}`}
            onClick={() => setAuthTab('login')}
          >
            Sign In
          </button>
          <button 
            type="button"
            className={`auth-tab-btn ${authTab === 'signup' ? 'active' : ''}`}
            onClick={() => setAuthTab('signup')}
          >
            Create Account
          </button>
        </div>

        {/* ── Email & Password Form ── */}
        <form onSubmit={handleEmailAuth} className="auth-form-wrap">
          {authTab === 'signup' && (
            <div className="auth-input-group">
              <UserIcon size={16} className="auth-input-icon" />
              <input 
                type="text" 
                placeholder="Full Name"
                className="auth-text-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={isSubmitting}
                required
              />
            </div>
          )}

          <div className="auth-input-group">
            <Mail size={16} className="auth-input-icon" />
            <input 
              type="email" 
              placeholder="Email address"
              className="auth-text-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isSubmitting}
              required
            />
          </div>

          {authTab !== 'forgot' && (
            <div className="auth-input-group">
              <Lock size={16} className="auth-input-icon" />
              <input 
                type="password" 
                placeholder="Password"
                className="auth-text-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isSubmitting}
                required
                minLength={6}
              />
            </div>
          )}

          {authTab === 'login' && (
            <div style={{ textAlign: 'right', marginTop: '-4px' }}>
              <button 
                type="button" 
                className="forgot-password-link"
                onClick={() => setAuthTab('forgot')}
              >
                Forgot password?
              </button>
            </div>
          )}

          <button 
            type="submit" 
            className="auth-submit-btn"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              'Processing...'
            ) : (
              <>
                {authTab === 'login' ? 'Sign In' : authTab === 'signup' ? 'Create Account' : 'Send Recovery Link'}
                <ArrowRight size={16} style={{ display: 'inline', marginLeft: '6px' }} />
              </>
            )}
          </button>

          {authTab === 'forgot' && (
            <div style={{ textAlign: 'center', marginTop: '6px' }}>
              <button 
                type="button" 
                className="forgot-password-link"
                onClick={() => setAuthTab('login')}
              >
                ← Back to Sign In
              </button>
            </div>
          )}
        </form>

        {/* ── Divider ── */}
        <div className="lp-divider">
          <span>or continue with</span>
        </div>

        {/* ── Google Sign-in ── */}
        <div className="lp-signin-wrap">
          <GoogleSignInButton
            fullWidth
            variant="primary"
            size="large"
            onClick={handleGoogleSignIn}
            loading={isSubmitting}
          />
          <p className="lp-note">
            Your preferences, measurements, and digital wardrobe are private and encrypted.
          </p>
        </div>

        {/* ── Footer ── */}
        <p className="lp-footer">
          By signing in you agree to Yorvyn's Terms of Service and Privacy Policy.
        </p>
      </div>
    </div>
  )
}
