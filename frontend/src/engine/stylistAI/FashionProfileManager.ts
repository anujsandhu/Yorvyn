/**
 * YORVYN — Fashion Profile Manager (Phase 11)
 * Manages personal style preferences, favorite colors, budget limits,
 * disliked attributes, and saved outfits with persistent storage.
 */

import {
  PersonalFashionProfile,
  ClothingStyle,
  FitPreference,
  BudgetTier,
  FashionFeedbackRecord
} from './types';

const STORAGE_KEY = 'yorvyn_personal_fashion_profile';

export function createDefaultProfile(userId: string = 'default_user'): PersonalFashionProfile {
  return {
    userId,
    preferredStyles: ['casual', 'minimalist', 'quiet_luxury'],
    favoriteColors: ['#0f172a', '#1e293b', '#334155', '#ffffff', '#e2e8f0', '#0284c7'],
    preferredFits: ['regular', 'relaxed'],
    preferredCategories: ['top', 'bottom', 'outerwear', 'footwear'],
    preferredBrands: ['Yorvyn Studio', 'Quiet Luxury', 'COS', 'Common Projects'],
    budgetTier: 'mid_premium',
    maxPricePerItem: 25000,
    occasionPreferences: ['casual_day', 'college', 'work_office', 'weekend_brunch'],
    preferredFootwear: ['sneakers', 'loafers', 'boots'],
    accessoryPreferences: ['sunglasses', 'leather_belt', 'minimal_watch'],
    savedOutfitIds: [],
    dislikedStyles: [],
    dislikedColors: ['#ff00ff', '#00ff00'],
    feedbackHistory: [],
    updatedAt: new Date().toISOString()
  };
}

export const DEFAULT_FASHION_PROFILE: PersonalFashionProfile = createDefaultProfile();

export class FashionProfileManager {
  private profile: PersonalFashionProfile;
  private listeners: ((profile: PersonalFashionProfile) => void)[] = [];

  constructor(initialProfile?: Partial<PersonalFashionProfile>) {
    this.profile = this.loadProfile(initialProfile);
  }

  private loadProfile(initialOverride?: Partial<PersonalFashionProfile>): PersonalFashionProfile {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        const stored = window.localStorage.getItem(STORAGE_KEY);
        if (stored) {
          const parsed = JSON.parse(stored);
          return { ...createDefaultProfile(), ...parsed, ...initialOverride };
        }
      }
    } catch (e) {
      console.warn('[FashionProfileManager] Failed to read localStorage:', e);
    }
    return { ...createDefaultProfile(), ...initialOverride };
  }

  private saveProfile(): void {
    this.profile.updatedAt = new Date().toISOString();
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(this.profile));
      }
    } catch (e) {
      console.warn('[FashionProfileManager] Failed to write to localStorage:', e);
    }
    this.notifyListeners();
  }

  public getProfile(): PersonalFashionProfile {
    return {
      ...this.profile,
      preferredStyles: [...this.profile.preferredStyles],
      favoriteColors: [...this.profile.favoriteColors],
      preferredFits: [...this.profile.preferredFits],
      preferredCategories: [...this.profile.preferredCategories],
      preferredBrands: [...this.profile.preferredBrands],
      occasionPreferences: [...this.profile.occasionPreferences],
      preferredFootwear: [...this.profile.preferredFootwear],
      accessoryPreferences: [...this.profile.accessoryPreferences],
      savedOutfitIds: [...this.profile.savedOutfitIds],
      dislikedStyles: [...this.profile.dislikedStyles],
      dislikedColors: [...this.profile.dislikedColors],
      feedbackHistory: [...this.profile.feedbackHistory]
    };
  }

  public updateProfile(updates: Partial<PersonalFashionProfile>): PersonalFashionProfile {
    this.profile = {
      ...this.profile,
      ...updates
    };
    this.saveProfile();
    return this.getProfile();
  }

  public setPreferredStyles(styles: ClothingStyle[]): void {
    this.profile.preferredStyles = [...styles];
    this.saveProfile();
  }

  public setPreferredFits(fits: FitPreference[]): void {
    this.profile.preferredFits = [...fits];
    this.saveProfile();
  }

  public setFavoriteColors(colors: string[]): void {
    this.profile.favoriteColors = [...colors];
    this.saveProfile();
  }

  public setBudgetTier(tier: BudgetTier, maxPrice?: number): void {
    this.profile.budgetTier = tier;
    if (maxPrice !== undefined) {
      this.profile.maxPricePerItem = maxPrice;
    } else {
      this.profile.maxPricePerItem = tier === 'budget' ? 7500 : tier === 'mid_premium' ? 25000 : 75000;
    }
    this.saveProfile();
  }

  public toggleSavedOutfit(outfitId: string): boolean {
    const idx = this.profile.savedOutfitIds.indexOf(outfitId);
    let isSaved = false;
    if (idx >= 0) {
      this.profile.savedOutfitIds.splice(idx, 1);
    } else {
      this.profile.savedOutfitIds.push(outfitId);
      isSaved = true;
    }
    this.saveProfile();
    return isSaved;
  }

  public addFeedback(record: Omit<FashionFeedbackRecord, 'id' | 'timestamp'>): FashionFeedbackRecord {
    const newRecord: FashionFeedbackRecord = {
      ...record,
      id: `fb_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      timestamp: new Date().toISOString()
    };
    this.profile.feedbackHistory.push(newRecord);

    // Dynamic preference learning:
    if (record.action === 'dislike' && record.dislikeReason) {
      if (record.dislikeReason === 'too_formal') {
        this.profile.dislikedStyles.push('formal');
      } else if (record.dislikeReason === 'too_casual') {
        this.profile.dislikedStyles.push('streetwear');
      }
    }

    this.saveProfile();
    return newRecord;
  }

  public resetProfile(): PersonalFashionProfile {
    this.profile = createDefaultProfile(this.profile.userId);
    this.saveProfile();
    return this.getProfile();
  }

  public subscribe(listener: (profile: PersonalFashionProfile) => void): () => void {
    this.listeners.push(listener);
    listener(this.getProfile());
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  private notifyListeners(): void {
    for (const listener of this.listeners) {
      try {
        listener(this.getProfile());
      } catch (e) {
        console.error('[FashionProfileManager] Listener error:', e);
      }
    }
  }
}
