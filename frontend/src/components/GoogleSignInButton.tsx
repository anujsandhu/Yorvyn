/**
 * Google Sign-In Button Component
 * 
 * Reusable button for Google Sign-In across the app
 */

import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import './GoogleSignInButton.css'

interface GoogleSignInButtonProps {
  variant?: 'primary' | 'secondary' | 'icon'
  size?: 'small' | 'medium' | 'large'
  fullWidth?: boolean
  disabled?: boolean
  className?: string
  /** Optional external click handler — if provided, the button won't call signInWithGoogle itself */
  onClick?: () => void | Promise<void>
  /** External loading state */
  loading?: boolean
}

export function GoogleSignInButton({
  variant = 'primary',
  size = 'medium',
  fullWidth = false,
  disabled = false,
  className = '',
  onClick: externalOnClick,
  loading: externalLoading,
}: GoogleSignInButtonProps) {
  const [internalLoading, setInternalLoading] = useState(false)
  const { signInWithGoogle } = useAuth()

  const loading = externalLoading ?? internalLoading

  const handleClick = async () => {
    if (externalOnClick) {
      await externalOnClick()
      return
    }
    try {
      setInternalLoading(true)
      await signInWithGoogle()
    } catch (error) {
      console.error('Sign-in error:', error)
      alert('Sign-in failed. Please try again.')
    } finally {
      setInternalLoading(false)
    }
  }

  const buttonClass = `google-signin-btn google-signin-${variant} google-signin-${size} ${
    fullWidth ? 'google-signin-full' : ''
  } ${loading ? 'google-signin-loading' : ''} ${className}`

  if (variant === 'icon') {
    return (
      <button
        className={buttonClass}
        onClick={handleClick}
        disabled={disabled || loading}
        type="button"
        aria-label="Sign in with Google"
        title="Sign in with Google"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            fill="#4285F4"
          />
          <path
            d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            fill="#34A853"
          />
          <path
            d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            fill="#FBBC05"
          />
          <path
            d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            fill="#EA4335"
          />
        </svg>
      </button>
    )
  }

  return (
    <button
      className={buttonClass}
      onClick={handleClick}
      disabled={disabled || loading}
      type="button"
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
          fill="currentColor"
        />
        <path
          d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
          fill="currentColor"
        />
        <path
          d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
          fill="currentColor"
        />
        <path
          d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
          fill="currentColor"
        />
      </svg>
      <span>{loading ? 'Signing in...' : 'Sign in with Google'}</span>
    </button>
  )
}
