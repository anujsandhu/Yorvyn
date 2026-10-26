import {
  createContext, useContext, useEffect, useState, ReactNode, useCallback,
} from 'react'
import { Session, User as SupabaseUser } from '@supabase/supabase-js'
import { supabase, isSupabaseConfigured } from '../utils/supabase'
import { profileService, OnboardingProfileData, DEFAULT_ONBOARDING_PROFILE } from '../services/profile/profileService'

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
  profile: OnboardingProfileData | null
  onboardingCompleted: boolean
  refreshProfile: () => Promise<OnboardingProfileData>
  saveProfile: (updates: Partial<OnboardingProfileData>) => Promise<OnboardingProfileData>
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
  const [profile, setProfile] = useState<OnboardingProfileData | null>(null)
  const [onboardingCompleted, setOnboardingCompleted] = useState<boolean>(false)

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

  const loadUserProfile = useCallback(async (uid: string) => {
    try {
      const userProfile = await profileService.getProfile(uid)
      setProfile(userProfile)
      setOnboardingCompleted(Boolean(userProfile.onboardingCompleted))
      return userProfile
    } catch (e) {
      console.warn('Failed to load user profile:', e)
      setProfile(DEFAULT_ONBOARDING_PROFILE)
      setOnboardingCompleted(false)
      return DEFAULT_ONBOARDING_PROFILE
    }
  }, [])

  const refreshProfile = useCallback(async () => {
    if (user?.id) {
      return loadUserProfile(user.id)
    }
    return DEFAULT_ONBOARDING_PROFILE
  }, [user?.id, loadUserProfile])

  const saveProfile = useCallback(async (updates: Partial<OnboardingProfileData>) => {
    if (!user?.id) throw new Error('No authenticated user session')
    const updated = await profileService.saveProfile(user.id, updates)
    setProfile(updated)
    setOnboardingCompleted(Boolean(updated.onboardingCompleted))
    return updated
  }, [user?.id])

  useEffect(() => {
    // 1. Initial session check
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      setSession(session)
      const mappedUser = mapSupabaseUser(session?.user ?? null)
      setUser(mappedUser)
      if (mappedUser?.id) {
        await loadUserProfile(mappedUser.id)
      }
      setLoading(false)
    }).catch(err => {
      console.warn('Could not retrieve Supabase session:', err)
      setLoading(false)
    })

    // 2. Auth state change listener
    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, session) => {
      setSession(session)
      const mappedUser = mapSupabaseUser(session?.user ?? null)
      setUser(mappedUser)
      setLoading(false)

      if (event === 'SIGNED_IN' && mappedUser?.id) {
        syncInitialProfile(session?.user ?? null)
        await loadUserProfile(mappedUser.id)
      } else if (event === 'SIGNED_OUT') {
        setProfile(null)
        setOnboardingCompleted(false)
      }
    })

    return () => {
      subscription.unsubscribe()
    }
  }, [loadUserProfile])

  const syncInitialProfile = async (sbUser: SupabaseUser | null) => {
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
      console.warn('Initial profile sync warning:', e)
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
      const mapped = mapSupabaseUser(data.user)
      setUser(mapped)
      setSession(data.session)
      if (mapped?.id) {
        await loadUserProfile(mapped.id)
      }
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
      const mapped = mapSupabaseUser(data.user)
      setUser(mapped)
      setSession(data.session)
      // Seed default onboarding profile with display name
      if (mapped?.id) {
        await profileService.saveProfile(mapped.id, {
          displayName: displayName || mapped.displayName,
          onboardingCompleted: false
        })
        setOnboardingCompleted(false)
      }
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
    setProfile(null)
    setOnboardingCompleted(false)
  }

  return (
    <AuthCtx.Provider value={{
      user,
      session,
      loading,
      isNewUser,
      profile,
      onboardingCompleted,
      refreshProfile,
      saveProfile,
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
