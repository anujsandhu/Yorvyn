import {
  createContext, useContext, useEffect, useState, ReactNode, useCallback,
} from 'react'
import { Session, User as SupabaseUser } from '@supabase/supabase-js'
import { supabase, isSupabaseConfigured, isSupabaseDatabaseAvailable, markSupabaseDatabaseUnavailable } from '../utils/supabase'
import { profileService, OnboardingProfileData, DEFAULT_ONBOARDING_PROFILE } from '../services/profile/profileService'
import { invalidateApiCache } from '../services/fashionApi'
import { studio3DAssetManager } from '../engine/ara/Studio3DAssetManager'

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
  deleteAccount: () => Promise<{ success?: boolean; error?: any }>
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
      if (mappedUser) {
        setUser(mappedUser)
        if (mappedUser?.id) {
          await loadUserProfile(mappedUser.id)
        }
      } else {
        const urlParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null
        const isSignedOut = typeof window !== 'undefined' && localStorage.getItem('yorvyn_signed_out') === 'true'
        const isDemo = urlParams?.get('demo') === 'true' || Boolean(typeof window !== 'undefined' && localStorage.getItem('yorvyn_dev_user')) || (import.meta.env.DEV && !isSignedOut)
        if (isDemo && import.meta.env.DEV) {
          const mockUser: YorvynUser = {
            id: 'dev_user_1',
            uid: 'dev_user_1',
            email: 'anujsandhu747@gmail.com',
            displayName: 'Anuj Sandhu',
            photoURL: '',
            provider: 'email'
          }
          setUser(mockUser)
          setOnboardingCompleted(true)
        } else {
          setUser(null)
        }
      }
      setLoading(false)
    }).catch(err => {
      console.warn('Could not retrieve Supabase session:', err)
      setUser(null)
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
    if (!sbUser || !isSupabaseDatabaseAvailable()) return
    try {
      const { error } = await supabase.from('yorvyn_profiles').upsert({
        user_id: sbUser.id,
        email: sbUser.email,
        display_name: sbUser.user_metadata?.full_name || sbUser.email?.split('@')[0],
        avatar_url: sbUser.user_metadata?.avatar_url || '',
        last_seen_at: new Date().toISOString()
      }, { onConflict: 'user_id' })
      if (error && (error.code === 'PGRST205' || (error as any).status === 404)) {
        markSupabaseDatabaseUnavailable()
      }
    } catch (e) {
      markSupabaseDatabaseUnavailable()
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
    if (typeof window !== 'undefined') {
      localStorage.removeItem('yorvyn_guest_session')
      localStorage.setItem('yorvyn_signed_out', 'true')
    }
    invalidateApiCache()
    studio3DAssetManager.clearPrivateAssets()
    await supabase.auth.signOut()
    setUser(null)
    setSession(null)
    setProfile(null)
    setOnboardingCompleted(false)
  }

  const deleteAccount = async () => {
    if (!user?.id) return { error: 'No user session found' }
    try {
      if (isSupabaseConfigured) {
        // Delete related user feedback and profile records in Supabase
        await supabase.from('avatar_feedback').delete().eq('user_id', user.id)
        await supabase.from('user_profiles').delete().eq('user_id', user.id)
      }
      // Clear all local caches
      if (typeof window !== 'undefined') {
        localStorage.removeItem('yorvyn_avatar_cache')
        localStorage.removeItem('yorvyn_avatar_feedback_cache')
        localStorage.removeItem('yorvyn_avatar_character')
        localStorage.removeItem('yorvyn_local_profile')
      }
      // Sign out
      invalidateApiCache()
    studio3DAssetManager.clearPrivateAssets()
    await supabase.auth.signOut()
      setUser(null)
      setSession(null)
      setProfile(null)
      setOnboardingCompleted(false)
      return { success: true }
    } catch (err: any) {
      console.warn('Error deleting account:', err)
      return { error: err.message || 'Failed to delete account' }
    }
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
      signOut,
      deleteAccount
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

export function useOptionalAuth() {
  return useContext(AuthCtx)
}
