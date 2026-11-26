/**
 * Supabase Client Initialization for Yorvyn.
 * Provides authentication, session persistence, and Row-Level Security client.
 */

import { createClient, SupabaseClient } from '@supabase/supabase-js';

const SUPABASE_URL = 
  import.meta.env.VITE_SUPABASE_URL || 
  import.meta.env.NEXT_PUBLIC_SUPABASE_URL || 
  'https://demo-project.supabase.co';

const SUPABASE_ANON_KEY = 
  import.meta.env.VITE_SUPABASE_ANON_KEY || 
  import.meta.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || 
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.demo-key';

const isValidKey = (key: string) => 
  typeof key === 'string' && (
    (key.startsWith('eyJ') && key.split('.').length === 3) ||
    key.startsWith('sb_publishable_')
  );

export const isSupabaseConfigured = Boolean(
  (import.meta.env.VITE_SUPABASE_URL || import.meta.env.NEXT_PUBLIC_SUPABASE_URL) && 
  (import.meta.env.VITE_SUPABASE_ANON_KEY || import.meta.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY) &&
  !String(import.meta.env.VITE_SUPABASE_URL || import.meta.env.NEXT_PUBLIC_SUPABASE_URL).includes('demo-project') &&
  isValidKey(import.meta.env.VITE_SUPABASE_ANON_KEY || import.meta.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY)
);

/**
 * Checks whether remote Supabase database tables (e.g. yorvyn_profiles) are available.
 * If tables have not been created or are missing in PostgREST schema cache, direct
 * queries trigger browser 404 console errors. In that scenario, Yorvyn seamlessly
 * uses the FastAPI backend (/api/fashion/profile) and localStorage for persistence.
 */
export const isSupabaseDatabaseAvailable = (): boolean => {
  if (typeof window === 'undefined') return false;
  if (!isSupabaseConfigured) return false;
  if (localStorage.getItem('yorvyn_supabase_db_disabled') === 'true') return false;
  // Require explicit flag or proven remote table presence to prevent 404 console errors
  return import.meta.env.VITE_ENABLE_SUPABASE_PROFILES_TABLE === 'true';
};

export const markSupabaseDatabaseUnavailable = (): void => {
  if (typeof window !== 'undefined') {
    localStorage.setItem('yorvyn_supabase_db_disabled', 'true');
    localStorage.removeItem('yorvyn_supabase_db_available');
  }
};

export const supabase: SupabaseClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
    storage: typeof window !== 'undefined' ? window.localStorage : undefined,
  },
});
