/**
 * YORVYN — PHASE 8: Avatar Preview Orchestrator
 * 
 * Coordinates:
 * 1. Safe staging and previewing of AI customization proposals without mutating baseline state.
 * 2. Instant Before/After visual comparison toggling.
 * 3. Multi-option alternative proposals switching.
 * 4. User acceptance (committing patch into AvatarCreatorEngine) or rejection (reverting to baseline).
 */

import { AvatarProfile } from '../../types/avatarProfile';
import { AvatarCustomizationProposal } from './avatarAITypes';
import { AvatarCreatorEngine } from '../avatarCreator/avatarCreatorEngine';

export interface AvatarPreviewState {
  isPreviewActive: boolean;
  activeProposal: AvatarCustomizationProposal | null;
  baselineProfile: AvatarProfile | null;
  previewProfile: AvatarProfile | null;
  isShowingOriginal: boolean;
  activeAlternativeIndex: number; // -1 for main proposal, 0..N for alternatives
}

export type AvatarPreviewListener = (state: AvatarPreviewState) => void;

export class AvatarPreviewOrchestrator {
  private state: AvatarPreviewState = {
    isPreviewActive: false,
    activeProposal: null,
    baselineProfile: null,
    previewProfile: null,
    isShowingOriginal: false,
    activeAlternativeIndex: -1
  };

  private listeners: Set<AvatarPreviewListener> = new Set();
  private creatorEngine: AvatarCreatorEngine | null = null;

  constructor(creatorEngine?: AvatarCreatorEngine) {
    if (creatorEngine) {
      this.creatorEngine = creatorEngine;
    }
  }

  public setCreatorEngine(engine: AvatarCreatorEngine): void {
    this.creatorEngine = engine;
  }

  public getState(): AvatarPreviewState {
    return { ...this.state };
  }

  public isPreviewing(): boolean {
    return this.state.isPreviewActive;
  }

  public getEffectiveProfile(): AvatarProfile | null {
    if (!this.state.isPreviewActive) {
      return this.creatorEngine ? this.creatorEngine.getProfile() : null;
    }
    return this.state.isShowingOriginal 
      ? this.state.baselineProfile 
      : this.state.previewProfile;
  }

  /**
   * Start previewing a proposed customization.
   */
  public startPreview(
    proposal: AvatarCustomizationProposal,
    baselineProfile?: AvatarProfile
  ): AvatarProfile {
    const baseline = baselineProfile 
      ? JSON.parse(JSON.stringify(baselineProfile))
      : this.creatorEngine 
        ? JSON.parse(JSON.stringify(this.creatorEngine.getProfile()))
        : null;

    if (!baseline) {
      throw new Error('AvatarPreviewOrchestrator: No baseline profile available to preview against.');
    }

    proposal.status = 'previewing';

    // Merge baseline with proposal patch (deep copy to avoid unintended mutations)
    const previewProfile = this.applyPatch(baseline, proposal.profilePatch);

    this.state = {
      isPreviewActive: true,
      activeProposal: proposal,
      baselineProfile: baseline,
      previewProfile: previewProfile,
      isShowingOriginal: false,
      activeAlternativeIndex: -1
    };

    this.notify();
    return previewProfile;
  }

  /**
   * Switch between the primary proposal and alternative options (e.g. 3 hairstyles).
   */
  public selectAlternative(alternativeIndex: number): AvatarProfile | null {
    if (!this.state.isPreviewActive || !this.state.activeProposal || !this.state.baselineProfile) {
      return null;
    }

    if (alternativeIndex === -1) {
      // Return to main proposal
      const preview = this.applyPatch(this.state.baselineProfile, this.state.activeProposal.profilePatch);
      this.state.previewProfile = preview;
      this.state.activeAlternativeIndex = -1;
      this.notify();
      return preview;
    }

    const alts = this.state.activeProposal.alternatives;
    if (!alts || !alts[alternativeIndex]) {
      return null;
    }

    const selectedAlt = alts[alternativeIndex];
    const preview = this.applyPatch(this.state.baselineProfile, selectedAlt.profilePatch);
    this.state.previewProfile = preview;
    this.state.activeAlternativeIndex = alternativeIndex;
    this.notify();
    return preview;
  }

  /**
   * Toggle Before/After comparison view.
   */
  public toggleBeforeAfter(showOriginal?: boolean): boolean {
    if (!this.state.isPreviewActive) return false;

    this.state.isShowingOriginal = showOriginal !== undefined 
      ? showOriginal 
      : !this.state.isShowingOriginal;

    this.notify();
    return this.state.isShowingOriginal;
  }

  /**
   * Commit accepted proposal changes into AvatarCreatorEngine.
   */
  public acceptPreview(): AvatarProfile | null {
    if (!this.state.isPreviewActive || !this.state.activeProposal) {
      return null;
    }

    const currentProposal = this.getActiveProposalOrAlternative();
    if (!currentProposal) return null;

    currentProposal.status = 'accepted';

    // Commit to engine if available
    if (this.creatorEngine && currentProposal.profilePatch) {
      this.creatorEngine.updateProfile(
        currentProposal.profilePatch,
        currentProposal.category,
        `AI: ${currentProposal.title}`
      );
    }

    const finalProfile = this.state.previewProfile;

    // Reset preview state
    this.state = {
      isPreviewActive: false,
      activeProposal: null,
      baselineProfile: null,
      previewProfile: null,
      isShowingOriginal: false,
      activeAlternativeIndex: -1
    };

    this.notify();
    return finalProfile;
  }

  /**
   * Reject the proposed preview and revert to original baseline profile.
   */
  public rejectPreview(): AvatarProfile | null {
    if (!this.state.isPreviewActive) return null;

    if (this.state.activeProposal) {
      this.state.activeProposal.status = 'rejected';
    }

    const revertedProfile = this.state.baselineProfile;

    // Reset preview state
    this.state = {
      isPreviewActive: false,
      activeProposal: null,
      baselineProfile: null,
      previewProfile: null,
      isShowingOriginal: false,
      activeAlternativeIndex: -1
    };

    this.notify();
    return revertedProfile;
  }

  public getActiveProposalOrAlternative(): AvatarCustomizationProposal | null {
    if (!this.state.activeProposal) return null;
    if (this.state.activeAlternativeIndex >= 0 && this.state.activeProposal.alternatives) {
      return this.state.activeProposal.alternatives[this.state.activeAlternativeIndex] || this.state.activeProposal;
    }
    return this.state.activeProposal;
  }

  public subscribe(listener: AvatarPreviewListener): () => void {
    this.listeners.add(listener);
    listener(this.getState());
    return () => this.listeners.delete(listener);
  }

  private notify(): void {
    const snapshot = this.getState();
    this.listeners.forEach(fn => fn(snapshot));
  }

  /**
   * Safe deep merge of profile patch onto baseline.
   */
  private applyPatch(base: AvatarProfile, patch: Partial<AvatarProfile>): AvatarProfile {
    const result = JSON.parse(JSON.stringify(base)) as AvatarProfile;

    for (const [key, value] of Object.entries(patch)) {
      if (value !== undefined && value !== null) {
        if (typeof value === 'object' && !Array.isArray(value)) {
          (result as any)[key] = {
            ...((result as any)[key] || {}),
            ...value
          };
        } else {
          (result as any)[key] = value;
        }
      }
    }

    return result;
  }
}

export const avatarPreviewOrchestrator = new AvatarPreviewOrchestrator();
