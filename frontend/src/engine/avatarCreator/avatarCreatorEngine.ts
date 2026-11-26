/**
 * YORVYN — PHASE 7: Centralized Avatar Customization Engine
 * 
 * Orchestrates:
 * 1. Immediate reactive updates to AvatarProfile
 * 2. Multi-level Undo / Redo history stack (up to 50 states)
 * 3. Side-by-side comparison mechanism (Initial vs Current)
 * 4. Granular per-category resets (reset only face/body without wiping other work)
 * 5. Full character reset with confirmation safety
 * 6. Cloud Supabase & local persistence sync
 */

import { 
  AvatarProfile, 
  DEFAULT_AVATAR_PROFILE, 
  DEFAULT_AVATAR_PROPORTIONS_MASCULINE,
  DEFAULT_AVATAR_PROPORTIONS_FEMININE,
  migrateAvatarProfile
} from '../../types/avatarProfile';
import { 
  AvatarCreatorCategory, 
  AvatarActionSnapshot, 
  AvatarCreatorHistory 
} from './avatarCreatorTypes';
import { profileService } from '../../services/profile/profileService';

export type AvatarChangeListener = (
  profile: AvatarProfile, 
  history: AvatarCreatorHistory,
  isComparing: boolean
) => void;

export class AvatarCreatorEngine {
  private currentProfile: AvatarProfile;
  private comparisonProfile: AvatarProfile;
  private isComparing: boolean = false;

  private undoStack: AvatarActionSnapshot[] = [];
  private redoStack: AvatarActionSnapshot[] = [];
  private readonly MAX_HISTORY = 50;

  private listeners: Set<AvatarChangeListener> = new Set();

  constructor(initialProfile?: Partial<AvatarProfile>) {
    const base = initialProfile ? migrateAvatarProfile(initialProfile) : { ...DEFAULT_AVATAR_PROFILE };
    this.currentProfile = JSON.parse(JSON.stringify(base));
    this.comparisonProfile = JSON.parse(JSON.stringify(base));
  }

  /**
   * Returns current active AvatarProfile (or comparison profile if comparison mode is active).
   */
  getProfile(): AvatarProfile {
    return this.isComparing ? this.comparisonProfile : this.currentProfile;
  }

  /**
   * Returns the canonical, working profile regardless of comparison mode.
   */
  getWorkingProfile(): AvatarProfile {
    return this.currentProfile;
  }

  /**
   * Returns the original comparison baseline snapshot.
   */
  getComparisonSnapshot(): AvatarProfile {
    return this.comparisonProfile;
  }

  /**
   * Sets or synchronizes a new profile (e.g. from cloud or parent page).
   */
  setProfile(profile: AvatarProfile, resetHistory: boolean = false): void {
    this.currentProfile = JSON.parse(JSON.stringify(profile));
    if (resetHistory) {
      this.comparisonProfile = JSON.parse(JSON.stringify(profile));
      this.undoStack = [];
      this.redoStack = [];
    }
    this.notify();
  }

  /**
   * Applies a partial update with undo tracking.
   */
  updateProfile(
    patch: Partial<AvatarProfile>, 
    category: AvatarCreatorCategory = 'body',
    description: string = 'Updated character'
  ): void {
    // Record current state in undo stack
    this.undoStack.push({
      timestamp: Date.now(),
      description,
      category,
      profile: JSON.parse(JSON.stringify(this.currentProfile))
    });

    if (this.undoStack.length > this.MAX_HISTORY) {
      this.undoStack.shift();
    }

    // Clear redo on new action
    this.redoStack = [];

    // Deep merge patch
    this.currentProfile = {
      ...this.currentProfile,
      ...patch,
      updatedAt: new Date().toISOString(),
      proportions: {
        ...this.currentProfile.proportions,
        ...(patch.proportions || {})
      },
      face: {
        ...this.currentProfile.face,
        ...(patch.face || {})
      },
      appearance: {
        ...this.currentProfile.appearance,
        ...(patch.appearance || {}),
        skinDetails: {
          ...this.currentProfile.appearance.skinDetails,
          ...(patch.appearance?.skinDetails || {})
        },
        makeup: {
          ...this.currentProfile.appearance.makeup,
          ...(patch.appearance?.makeup || {})
        }
      },
      wardrobe: {
        ...this.currentProfile.wardrobe,
        ...(patch.wardrobe || {})
      }
    };

    this.notify();
  }

  /**
   * Undo the last change.
   */
  undo(): boolean {
    if (this.undoStack.length === 0) return false;

    const previous = this.undoStack.pop()!;
    this.redoStack.push({
      timestamp: Date.now(),
      description: 'Before undo',
      category: previous.category,
      profile: JSON.parse(JSON.stringify(this.currentProfile))
    });

    this.currentProfile = previous.profile;
    this.notify();
    return true;
  }

  /**
   * Redo the undone change.
   */
  redo(): boolean {
    if (this.redoStack.length === 0) return false;

    const next = this.redoStack.pop()!;
    this.undoStack.push({
      timestamp: Date.now(),
      description: next.description,
      category: next.category,
      profile: JSON.parse(JSON.stringify(this.currentProfile))
    });

    this.currentProfile = next.profile;
    this.notify();
    return true;
  }

  /**
   * Hold or toggle comparison between customized character and original snapshot.
   */
  setComparing(comparing: boolean): void {
    if (this.isComparing !== comparing) {
      this.isComparing = comparing;
      this.notify();
    }
  }

  isComparisonActive(): boolean {
    return this.isComparing;
  }

  /**
   * Resets only the specified category to defaults, leaving other categories intact.
   */
  resetCategory(category: AvatarCreatorCategory): void {
    const isMasc = this.currentProfile.genderPresentation !== 'feminine';
    const defaultProps = isMasc ? DEFAULT_AVATAR_PROPORTIONS_MASCULINE : DEFAULT_AVATAR_PROPORTIONS_FEMININE;

    let patch: Partial<AvatarProfile> = {};

    switch (category) {
      case 'body':
        patch = { proportions: { ...defaultProps } };
        break;
      case 'face':
        patch = {
          face: {
            ...this.currentProfile.face,
            headShape: 0.0,
            faceWidth: 0.0,
            faceHeight: 0.0,
            foreheadHeight: 0.0,
            jawWidth: isMasc ? 0.05 : -0.05,
            jawAngle: 0.0,
            chinWidth: 0.0,
            chinShape: 0.0,
            chinProjection: 0.0,
            cheekFullness: 0.0,
            cheekboneProminence: 0.0,
            facialSymmetry: 0.0,
            faceShapePreset: 'default'
          }
        };
        break;
      case 'eyes':
        patch = {
          face: {
            ...this.currentProfile.face,
            eyeSize: 0.0,
            eyeSpacing: 0.0,
            eyePosition: 0.0,
            eyeAngle: 0.0,
            eyelidShape: 0.0,
            eyeHighlights: 0.85
          },
          appearance: {
            ...this.currentProfile.appearance,
            eyeColorId: 'brownlight'
          }
        };
        break;
      case 'eyebrows':
        patch = {
          face: {
            ...this.currentProfile.face,
            eyebrowShapeId: isMasc ? 'eyebrow001' : 'eyebrow010',
            eyebrowThickness: 0.0,
            eyebrowPosition: 0.0,
            eyebrowArch: 0.0
          },
          appearance: {
            ...this.currentProfile.appearance,
            eyebrowStyleId: isMasc ? 'eyebrow001' : 'eyebrow010'
          }
        };
        break;
      case 'nose':
        patch = {
          face: {
            ...this.currentProfile.face,
            noseWidth: 0.0,
            noseLength: 0.0,
            noseBridgeWidth: 0.0,
            noseTipShape: 0.0,
            nostrilWidth: 0.0,
            nostrilShape: 0.0,
            noseAngle: 0.0
          }
        };
        break;
      case 'mouth':
        patch = {
          face: {
            ...this.currentProfile.face,
            upperLipFullness: 0.0,
            lowerLipFullness: 0.0,
            mouthWidth: 0.0,
            mouthPosition: 0.0
          }
        };
        break;
      case 'ears':
        patch = {
          face: {
            ...this.currentProfile.face,
            earSize: 0.0,
            earPosition: 0.0,
            earShape: 0.0,
            earlobeVariation: 0.0,
            piercingStyleId: 'none'
          }
        };
        break;
      case 'hair':
        patch = {
          appearance: {
            ...this.currentProfile.appearance,
            hairStyleId: isMasc ? 'short02' : 'bob01',
            hairColorHex: '#1e293b',
            hairLength: 0.0,
            hairVolume: 0.0,
            hairline: 0.0
          }
        };
        break;
      case 'facial_hair':
        patch = {
          appearance: {
            ...this.currentProfile.appearance,
            facialHairId: 'none',
            facialHairDensity: 0.5,
            facialHairLength: 0.5
          }
        };
        break;
      case 'skin':
        patch = {
          appearance: {
            ...this.currentProfile.appearance,
            skinToneId: 'amber',
            skinToneHex: '#f3c299',
            skinUndertone: 'neutral',
            skinDetails: {
              freckles: 0,
              beautyMarks: false,
              moles: false,
              scars: 'none'
            },
            makeup: {
              lipColor: undefined,
              blushColor: undefined,
              blushIntensity: 0
            }
          }
        };
        break;
      case 'clothing':
        patch = {
          wardrobe: {
            ...this.currentProfile.wardrobe,
            isBareMannequin: false,
            outfitId: isMasc ? 'male_elegantsuit01' : 'female_elegantsuit01',
            topId: 'none',
            bottomId: 'none',
            shoesId: 'shoes01',
            outerwearId: 'none'
          }
        };
        break;
      case 'accessories':
        patch = {
          wardrobe: {
            ...this.currentProfile.wardrobe,
            accessories: [],
            sunglasses: false
          }
        };
        break;
      case 'expressions':
        patch = {
          face: {
            ...this.currentProfile.face,
            restingExpression: 'neutral'
          }
        };
        break;
    }

    this.updateProfile(patch, category, `Reset ${category}`);
  }

  /**
   * Resets entire character back to default with confirmation.
   */
  resetEntireCharacter(): void {
    const isMasc = this.currentProfile.genderPresentation !== 'feminine';
    const defaultProfile = isMasc
      ? { ...DEFAULT_AVATAR_PROFILE, genderPresentation: 'masculine' as const, proportions: DEFAULT_AVATAR_PROPORTIONS_MASCULINE }
      : { ...DEFAULT_AVATAR_PROFILE, genderPresentation: 'feminine' as const, proportions: DEFAULT_AVATAR_PROPORTIONS_FEMININE };

    this.updateProfile(defaultProfile, 'body', 'Reset entire character');
  }

  /**
   * Persists to ProfileService / Supabase and localStorage.
   */
  async save(userId: string = ''): Promise<AvatarProfile> {
    try {
      const saved = await profileService.saveAvatarProfile(userId, this.currentProfile);
      // Update comparison baseline to saved state
      this.comparisonProfile = JSON.parse(JSON.stringify(saved));
      this.notify();
      return saved;
    } catch (err) {
      // Local storage fallback
      localStorage.setItem('yorvyn_avatar_profile_v3', JSON.stringify(this.currentProfile));
      localStorage.setItem('yorvyn_avatar_character', this.currentProfile.genderPresentation === 'feminine' ? 'elena' : 'aarav');
      this.comparisonProfile = JSON.parse(JSON.stringify(this.currentProfile));
      this.notify();
      return this.currentProfile;
    }
  }

  /**
   * History metadata.
   */
  getHistory(): AvatarCreatorHistory {
    return {
      canUndo: this.undoStack.length > 0,
      canRedo: this.redoStack.length > 0,
      historyLength: this.undoStack.length,
      currentIndex: this.undoStack.length
    };
  }

  subscribe(listener: AvatarChangeListener): () => void {
    this.listeners.add(listener);
    listener(this.getProfile(), this.getHistory(), this.isComparing);
    return () => this.listeners.delete(listener);
  }

  private notify(): void {
    const profile = this.getProfile();
    const history = this.getHistory();
    this.listeners.forEach(l => l(profile, history, this.isComparing));
  }
}

