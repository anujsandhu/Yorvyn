/**
 * Profile & Avatar Persistence Service — Yorvyn
 * Interfaces with Supabase PostgreSQL and the FastAPI backend.
 * Provides resilient profile retrieval, updating, and onboarding completion.
 */

import { 
  supabase, 
  isSupabaseDatabaseAvailable, 
  markSupabaseDatabaseUnavailable 
} from '../../utils/supabase';
import { fashionApi } from '../fashionApi';
import { 
  AvatarProfile, 
  DEFAULT_AVATAR_PROFILE, 
  migrateAvatarProfile 
} from '../../types/avatarProfile';

export interface OnboardingProfileData {
  displayName: string;
  age: number;
  gender?: 'female' | 'male' | 'non-binary' | string;
  phoneNumber?: string;
  location?: string;
  heightValue: number;
  heightUnit: 'cm' | 'ft';
  weightValue?: number;
  weightUnit?: 'kg' | 'lbs';
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
  gender: 'female',
  phoneNumber: '',
  location: '',
  heightValue: 175,
  heightUnit: 'cm',
  weightValue: 65,
  weightUnit: 'kg',
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

    // 1. Try Supabase directly only if remote database tables are confirmed available
    if (isSupabaseDatabaseAvailable()) {
      try {
        const { data, error } = await supabase
          .from('yorvyn_profiles')
          .select('*')
          .eq('user_id', userId)
          .maybeSingle();

        if (error) {
          if (error.code === 'PGRST205' || (error as any).status === 404) {
            markSupabaseDatabaseUnavailable();
          }
        } else if (data) {
          return {
            displayName: data.display_name || data.name || DEFAULT_ONBOARDING_PROFILE.displayName,
            age: data.age || DEFAULT_ONBOARDING_PROFILE.age,
            gender: data.gender || DEFAULT_ONBOARDING_PROFILE.gender,
            phoneNumber: data.phone_number || data.phone || DEFAULT_ONBOARDING_PROFILE.phoneNumber,
            location: data.location || data.city || DEFAULT_ONBOARDING_PROFILE.location,
            heightValue: Number(data.height_value || data.height_cm || DEFAULT_ONBOARDING_PROFILE.heightValue),
            heightUnit: (data.height_unit as 'cm' | 'ft') || 'cm',
            weightValue: Number(data.weight_value || DEFAULT_ONBOARDING_PROFILE.weightValue),
            weightUnit: (data.weight_unit as 'kg' | 'lbs') || (DEFAULT_ONBOARDING_PROFILE.weightUnit as 'kg' | 'lbs'),
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
        markSupabaseDatabaseUnavailable();
      }
    }

    // 2. Local storage fallback for offline / dev / fast hydration
    try {
      const local = localStorage.getItem(`yorvyn_profile_${userId}`);
      if (local) {
        return JSON.parse(local);
      }
    } catch {
      // ignore
    }

    // 3. Try FastAPI backend (/api/fashion/profile)
    try {
      const backendProfile = await fashionApi.getProfile(userId);
      if (backendProfile && (backendProfile.name || backendProfile.body_shape)) {
        return {
          displayName: backendProfile.name || DEFAULT_ONBOARDING_PROFILE.displayName,
          age: DEFAULT_ONBOARDING_PROFILE.age,
          gender: DEFAULT_ONBOARDING_PROFILE.gender,
          phoneNumber: '',
          location: '',
          heightValue: backendProfile.height_cm || DEFAULT_ONBOARDING_PROFILE.heightValue,
          heightUnit: 'cm',
          weightValue: DEFAULT_ONBOARDING_PROFILE.weightValue,
          weightUnit: 'kg',
          bodyType: backendProfile.body_shape || DEFAULT_ONBOARDING_PROFILE.bodyType,
          skinToneId: backendProfile.color_season || DEFAULT_ONBOARDING_PROFILE.skinToneId,
          skinToneHex: DEFAULT_ONBOARDING_PROFILE.skinToneHex,
          hairColourId: DEFAULT_ONBOARDING_PROFILE.hairColourId,
          hairColourHex: DEFAULT_ONBOARDING_PROFILE.hairColourHex,
          avatarGenderPresentation: DEFAULT_ONBOARDING_PROFILE.avatarGenderPresentation,
          avatarConfiguration: DEFAULT_ONBOARDING_PROFILE.avatarConfiguration,
          onboardingCompleted: true
        };
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

    // 1. Persist to Supabase if database tables are available
    if (isSupabaseDatabaseAvailable() && userId) {
      try {
        const payload: Record<string, any> = {
          user_id: userId,
          display_name: updated.displayName,
          name: updated.displayName,
          age: updated.age,
          gender: updated.gender,
          phone_number: updated.phoneNumber,
          location: updated.location,
          height_value: updated.heightValue,
          height_unit: updated.heightUnit,
          height_cm: updated.heightUnit === 'cm' ? Math.round(updated.heightValue) : Math.round(updated.heightValue * 30.48),
          weight_value: updated.weightValue,
          weight_unit: updated.weightUnit,
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

        if (error && (error.code === 'PGRST205' || (error as any).status === 404)) {
          markSupabaseDatabaseUnavailable();
        }
      } catch (e) {
        markSupabaseDatabaseUnavailable();
      }
    }

    // 2. Persist to FastAPI backend
    try {
      if (userId) {
        await fashionApi.updateProfile({
          name: updated.displayName,
          height_cm: updated.heightUnit === 'cm' ? Math.round(updated.heightValue) : Math.round(updated.heightValue * 30.48),
          body_shape: updated.bodyType as any
        }, userId);
      }
    } catch {
      // ignore
    }

    // 3. Also save to local storage cache
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

  /**
   * Fetches the strongly typed, versioned AvatarProfile (Schema v3).
   */
  async getAvatarProfile(userId: string): Promise<AvatarProfile> {
    if (!userId) {
      try {
        const cached = localStorage.getItem('yorvyn_avatar_profile_v3');
        if (cached) return migrateAvatarProfile(JSON.parse(cached));
      } catch {}
      return { ...DEFAULT_AVATAR_PROFILE };
    }

    // Try Supabase first only if remote database tables are confirmed available
    if (isSupabaseDatabaseAvailable()) {
      try {
        const { data, error } = await supabase
          .from('yorvyn_profiles')
          .select('avatar_profile_v3, avatar_configuration, height_cm, weight_value, body_type, skin_tone_id, skin_tone_hex, hair_colour_id, hair_colour_hex, avatar_gender_presentation')
          .eq('user_id', userId)
          .maybeSingle();

        if (error && (error.code === 'PGRST205' || (error as any).status === 404)) {
          markSupabaseDatabaseUnavailable();
        } else if (data) {
          if (data.avatar_profile_v3) {
            return migrateAvatarProfile(data.avatar_profile_v3, userId);
          }
          // Migrate from legacy fields
          return migrateAvatarProfile(data, userId);
        }
      } catch (err) {
        markSupabaseDatabaseUnavailable();
      }
    }

    // Fallback to localStorage
    try {
      const cached = localStorage.getItem(`yorvyn_avatar_profile_v3_${userId}`) || localStorage.getItem('yorvyn_avatar_profile_v3');
      if (cached) {
        return migrateAvatarProfile(JSON.parse(cached), userId);
      }
    } catch {}

    const legacyProfile = await this.getProfile(userId);
    return migrateAvatarProfile(legacyProfile, userId);
  }

  /**
   * Persists the AvatarProfile (Schema v3) to Supabase and cache.
   */
  async saveAvatarProfile(userId: string, profile: Partial<AvatarProfile>): Promise<AvatarProfile> {
    const current = await this.getAvatarProfile(userId);
    const updated: AvatarProfile = {
      ...current,
      ...profile,
      userId: userId || current.userId,
      updatedAt: new Date().toISOString(),
      proportions: {
        ...current.proportions,
        ...(profile.proportions || {})
      },
      face: {
        ...current.face,
        ...(profile.face || {})
      },
      appearance: {
        ...current.appearance,
        ...(profile.appearance || {})
      },
      wardrobe: {
        ...current.wardrobe,
        ...(profile.wardrobe || {})
      }
    };

    // Save to local cache
    try {
      const serialized = JSON.stringify(updated);
      localStorage.setItem('yorvyn_avatar_profile_v3', serialized);
      if (userId) {
        localStorage.setItem(`yorvyn_avatar_profile_v3_${userId}`, serialized);
      }
      if (updated.genderPresentation === 'feminine') {
        localStorage.setItem('yorvyn_avatar_character', 'girl');
      } else if (updated.genderPresentation === 'masculine') {
        localStorage.setItem('yorvyn_avatar_character', 'boy');
      }
    } catch {}

    // Persist to Supabase if database table is available
    if (isSupabaseDatabaseAvailable() && userId) {
      try {
        const { error } = await supabase
          .from('yorvyn_profiles')
          .upsert({
            user_id: userId,
            avatar_profile_v3: updated,
            avatar_configuration: {
              gender: updated.genderPresentation === 'feminine' ? 0.05 : 0.95,
              height: Math.max(0, Math.min(1, (updated.proportions.heightCm - 155) / 40)),
              weight: Math.max(0, Math.min(1, (updated.proportions.weightKg - 45) / 55)),
              muscle: updated.proportions.muscleDefinition,
              skinTint: updated.appearance.skinToneHex,
              hairColor: updated.appearance.hairColorHex,
              hair: updated.appearance.hairStyleId,
              outfit: updated.wardrobe.outfitId
            },
            height_cm: updated.proportions.heightCm,
            weight_value: updated.proportions.weightKg,
            body_type: updated.proportions.silhouette,
            skin_tone_id: updated.appearance.skinToneId,
            skin_tone_hex: updated.appearance.skinToneHex,
            hair_colour_id: updated.appearance.hairStyleId,
            hair_colour_hex: updated.appearance.hairColorHex,
            avatar_gender_presentation: updated.genderPresentation,
            updated_at: new Date().toISOString()
          }, { onConflict: 'user_id' });

        if (error && (error.code === 'PGRST205' || (error as any).status === 404)) {
          markSupabaseDatabaseUnavailable();
        }
      } catch (err) {
        markSupabaseDatabaseUnavailable();
      }
    }

    // Also sync to FastAPI Fashion DNA
    try {
      if (userId) {
        await fashionApi.syncAvatarDna(updated, userId);
      }
    } catch {
      // ignore
    }

    return updated;
  }
}

export const profileService = new ProfileService();
