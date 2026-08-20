/**
 * Login Page — Yorvyn
 *
 * Professional sign-in page with:
 * - Yorvyn logo
 * - "Welcome back" for returning users, warm greeting for new users
 * - Google Sign-In
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, Heart, Bot, Star } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { GoogleSignInButton } from '../components/GoogleSignInButton'
import { Logo } from '../components/Logo'
import { AppLoader } from '../components/AppLoader'
import './Login.css'

const NEW_USER_MESSAGES = [
  { headline: 'Discover Your Signature Scent', sub: 'Tell us your mood, occasion, and style — our AI finds the perfect fragrance for you.' },
  { headline: 'Your Scent Journey Starts Here', sub: 'Explore 73,000+ fragrances curated by AI, matched to your unique personality.' },
  { headline: 'Find Fragrances You\'ll Love', sub: 'Personalized recommendations powered by machine learning and your preferences.' },
]

export function LoginPage() {
  const navigate = useNavigate()
  const { user, loading, signInWithGoogle } = useAuth()
  const [msgIdx] = useState(() => Math.floor(Math.random() * NEW_USER_MESSAGES.length))
  const [signingIn, setSigningIn] = useState(false)

  useEffect(() => {
    if (user && !loading) {
      navigate('/', { replace: true })
    }
  }, [user, loading, navigate])

  const handleSignIn = async () => {
    setSigningIn(true)
    try {
      await signInWithGoogle()
    } catch {
      setSigningIn(false)
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
            <span>AI-Powered</span>
          </div>
          <div className="lp-feature">
            <span className="lp-feature-icon"><Star size={15} /></span>
            <span>73K+ Fragrances</span>
          </div>
          <div className="lp-feature">
            <span className="lp-feature-icon"><Heart size={15} /></span>
            <span>Save Favourites</span>
          </div>
          <div className="lp-feature">
            <span className="lp-feature-icon"><Bot size={15} /></span>
            <span>Chat Advisor</span>
          </div>
        </div>

        {/* ── Divider ── */}
        <div className="lp-divider">
          <span>Sign in to continue</span>
        </div>

        {/* ── Sign-in ── */}
        <div className="lp-signin-wrap">
          <GoogleSignInButton
            fullWidth
            variant="primary"
            size="large"
            onClick={handleSignIn}
            loading={signingIn}
          />
          <p className="lp-note">
            We never share your data. Your preferences are private and secure.
          </p>
        </div>

        {/* ── Footer ── */}
        <p className="lp-footer">
          By signing in you agree to our Terms of Service and Privacy Policy.
        </p>
      </div>
    </div>
  )
}
