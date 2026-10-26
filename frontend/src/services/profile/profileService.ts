/**
 * Profile & Avatar Persistence Service — Yorvyn
 * Interfaces with Supabase PostgreSQL and the FastAPI backend.
 * Provides resilient profile retrieval, updating, and onboarding completion.
 */

import { supabase, isSupabaseConfigured } from '../../utils/supabase';

export interface OnboardingProfileData {
  displayName: string;
  age: number;
  heightValue: number;
  heightUnit: 'cm' | 'ft';
  bodyType: string;
  skinToneId: string;
  skinToneHex: string;
  hairColourId: string;
  hairColourHex: string;
  avatarGenderPresentation: 'feminine' | 'masculine' | 'neutral';
  avatarConfiguration?: Record<string, any>;
  onboardingCompleted?: boolean;
}

export const DEFAULT_ONBOARDING_PROFILE: OnboardingProfileData = {
  displayName: 'Yorvyn Stylist',
  age: 26,
  heightValue: 175,
  heightUnit: 'cm',
  bodyType: 'athletic',
  skinToneId: 'medium',
  skinToneHex: '#f3c299',
  hairColourId: 'espresso',
  hairColourHex: '#3a2312',
  avatarGenderPresentation: 'neutral',
  avatarConfiguration: {
    gender: 0.5,
    height: 0.5,
    muscle: 0.6,
    weight: 0.5,
    skinTint: '#f3c299',
    hairColor: '#3a2312',
    hair: 'short01'
  },
  onboardingCompleted: false
};

class ProfileService {
  /**
   * Fetches the user profile from Supabase PostgreSQL (or falls back to backend / localStorage).
   */
  async getProfile(userId: string): Promise<OnboardingProfileData> {
    if (!userId) return { ...DEFAULT_ONBOARDING_PROFILE };

    // 1. Try Supabase directly
    if (isSupabaseConfigured) {
      try {
        const { data, error } = await supabase
          .from('yorvyn_profiles')
          .select('*')
          .eq('user_id', userId)
          .maybeSingle();

        if (!error && data) {
          return {
            displayName: data.display_name || data.name || DEFAULT_ONBOARDING_PROFILE.displayName,
            age: data.age || DEFAULT_ONBOARDING_PROFILE.age,
            heightValue: Number(data.height_value || data.height_cm || DEFAULT_ONBOARDING_PROFILE.heightValue),
            heightUnit: (data.height_unit as 'cm' | 'ft') || 'cm',
            bodyType: data.body_type || data.body_shape || DEFAULT_ONBOARDING_PROFILE.bodyType,
            skinToneId: data.skin_tone_id || DEFAULT_ONBOARDING_PROFILE.skinToneId,
            skinToneHex: data.skin_tone_hex || DEFAULT_ONBOARDING_PROFILE.skinToneHex,
            hairColourId: data.hair_colour_id || DEFAULT_ONBOARDING_PROFILE.hairColourId,
            hairColourHex: data.hair_colour_hex || DEFAULT_ONBOARDING_PROFILE.hairColourHex,
            avatarGenderPresentation: data.avatar_gender_presentation || DEFAULT_ONBOARDING_PROFILE.avatarGenderPresentation,
            avatarConfiguration: data.avatar_configuration || DEFAULT_ONBOARDING_PROFILE.avatarConfiguration,
            onboardingCompleted: Boolean(data.onboarding_completed)
          };
        }
      } catch (err) {
        console.warn('[ProfileService] Supabase profile fetch failed, trying local store:', err);
      }
    }

    // 2. Local storage fallback for offline / dev
    try {
      const local = localStorage.getItem(`yorvyn_profile_${userId}`);
      if (local) {
        return JSON.parse(local);
      }
    } catch {
      // ignore
    }

    return { ...DEFAULT_ONBOARDING_PROFILE };
  }

  /**
   * Saves or updates the user profile and avatar settings.
   */
  async saveProfile(userId: string, profile: Partial<OnboardingProfileData>): Promise<OnboardingProfileData> {
    const current = await this.getProfile(userId);
    const updated: OnboardingProfileData = {
      ...current,
      ...profile,
      avatarConfiguration: {
        ...(current.avatarConfiguration || {}),
        ...(profile.avatarConfiguration || {})
      }
    };

    // 1. Persist to Supabase if configured
    if (isSupabaseConfigured && userId) {
      try {
        const payload: Record<string, any> = {
          user_id: userId,
          display_name: updated.displayName,
          name: updated.displayName,
          age: updated.age,
          height_value: updated.heightValue,
          height_unit: updated.heightUnit,
          height_cm: updated.heightUnit === 'cm' ? Math.round(updated.heightValue) : Math.round(updated.heightValue * 30.48),
          body_type: updated.bodyType,
          body_shape: updated.bodyType,
          skin_tone_id: updated.skinToneId,
          skin_tone_hex: updated.skinToneHex,
          hair_colour_id: updated.hairColourId,
          hair_colour_hex: updated.hairColourHex,
          avatar_gender_presentation: updated.avatarGenderPresentation,
          avatar_configuration: updated.avatarConfiguration,
          onboarding_completed: Boolean(updated.onboardingCompleted),
          updated_at: new Date().toISOString()
        };

        const { error } = await supabase
          .from('yorvyn_profiles')
          .upsert(payload, { onConflict: 'user_id' });

        if (error) {
          console.warn('[ProfileService] Supabase upsert error:', error);
        }
      } catch (e) {
        console.warn('[ProfileService] Failed to upsert profile in Supabase:', e);
      }
    }

    // 2. Also save to local storage cache
    try {
      localStorage.setItem(`yorvyn_profile_${userId}`, JSON.stringify(updated));
      // Store avatar character for Ara engine / SettingsModal
      if (updated.avatarGenderPresentation === 'feminine') {
        localStorage.setItem('yorvyn_avatar_character', 'girl');
      } else if (updated.avatarGenderPresentation === 'masculine') {
        localStorage.setItem('yorvyn_avatar_character', 'boy');
      }
    } catch {
      // ignore
    }

    return updated;
  }

  /**
   * Completes the onboarding flow and marks onboarding_completed: true
   */
  async completeOnboarding(userId: string, data: OnboardingProfileData): Promise<OnboardingProfileData> {
    return this.saveProfile(userId, {
      ...data,
      onboardingCompleted: true
    });
  }
}

export const profileService = new ProfileService();
