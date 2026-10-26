import {
  createContext, useContext, useEffect, useState, ReactNode,
} from 'react'
import { Session, User as SupabaseUser } from '@supabase/supabase-js'
import { supabase, isSupabaseConfigured } from '../utils/supabase'

export interface YorvynUser {
  id: string
  uid: string // Backward-compatible alias for existing code referencing user.uid
  email?: string
  displayName?: string
  photoURL?: string
  provider?: string
}

interface AuthContextValue {
  user: YorvynUser | null
  session: Session | null
  loading: boolean
  isNewUser: boolean
  signInWithGoogle: () => Promise<void>
  signInWithEmail: (email: string, password: string) => Promise<{ error: any }>
  signUpWithEmail: (email: string, password: string, displayName?: string) => Promise<{ error: any }>
  resetPassword: (email: string) => Promise<{ error: any }>
  signOut: () => Promise<void>
}

const AuthCtx = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<YorvynUser | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [isNewUser, setIsNewUser] = useState(false)

  // Map Supabase User into YorvynUser
  const mapSupabaseUser = (sbUser: SupabaseUser | null): YorvynUser | null => {
    if (!sbUser) return null
    return {
      id: sbUser.id,
      uid: sbUser.id,
      email: sbUser.email,
      displayName: sbUser.user_metadata?.full_name || sbUser.user_metadata?.name || sbUser.email?.split('@')[0] || 'Yorvyn Member',
      photoURL: sbUser.user_metadata?.avatar_url || sbUser.user_metadata?.picture || '',
      provider: sbUser.app_metadata?.provider || 'supabase'
    }
  }

  useEffect(() => {
    // 1. Initial session check
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setUser(mapSupabaseUser(session?.user ?? null))
      setLoading(false)
    }).catch(err => {
      console.warn('Could not retrieve Supabase session:', err)
      setLoading(false)
    })

    // 2. Auth state change listener
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      setSession(session)
      setUser(mapSupabaseUser(session?.user ?? null))
      setLoading(false)

      if (event === 'SIGNED_IN') {
        // Sync profile to database if configured
        syncProfile(session?.user ?? null)
      }
    })

    return () => {
      subscription.unsubscribe()
    }
  }, [])

  const syncProfile = async (sbUser: SupabaseUser | null) => {
    if (!sbUser || !isSupabaseConfigured) return
    try {
      await supabase.from('yorvyn_profiles').upsert({
        user_id: sbUser.id,
        email: sbUser.email,
        display_name: sbUser.user_metadata?.full_name || sbUser.email?.split('@')[0],
        avatar_url: sbUser.user_metadata?.avatar_url || '',
        last_seen_at: new Date().toISOString()
      }, { onConflict: 'user_id' })
    } catch (e) {
      console.warn('Profile sync notification:', e)
    }
  }

  const signInWithGoogle = async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: window.location.origin
      }
    })
    if (error) throw error
  }

  const signInWithEmail = async (email: string, password: string) => {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password
    })
    if (!error && data.user) {
      setUser(mapSupabaseUser(data.user))
      setSession(data.session)
    }
    return { error }
  }

  const signUpWithEmail = async (email: string, password: string, displayName?: string) => {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          full_name: displayName || email.split('@')[0]
        }
      }
    })
    if (!error && data.user) {
      setIsNewUser(true)
      setUser(mapSupabaseUser(data.user))
      setSession(data.session)
    }
    return { error }
  }

  const resetPassword = async (email: string) => {
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password`
    })
    return { error }
  }

  const signOut = async () => {
    setIsNewUser(false)
    await supabase.auth.signOut()
    setUser(null)
    setSession(null)
  }

  return (
    <AuthCtx.Provider value={{
      user,
      session,
      loading,
      isNewUser,
      signInWithGoogle,
      signInWithEmail,
      signUpWithEmail,
      resetPassword,
      signOut
    }}>
      {children}
    </AuthCtx.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthCtx)
  if (!ctx) throw new Error('useAuth must be inside AuthProvider')
  return ctx
}
