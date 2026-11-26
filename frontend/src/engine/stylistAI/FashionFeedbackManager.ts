/**
 * YORVYN — Fashion Feedback & Preference Learning Manager (Phase 11)
 * Tracks user likes, dislikes, reasons, and individual piece replacements
 * to dynamically optimize future outfit recommendations.
 */

import { FashionFeedbackRecord, DislikeReason, ClothingStyle } from './types';
import { FashionProfileManager } from './FashionProfileManager';

export class FashionFeedbackManager {
  private profileManager: FashionProfileManager;

  constructor(profileManager?: FashionProfileManager) {
    this.profileManager = profileManager || new FashionProfileManager();
  }

  public recordLike(outfitId: string, note?: string): FashionFeedbackRecord {
    return this.profileManager.addFeedback({
      outfitId,
      action: 'like',
      note
    });
  }

  public recordDislike(outfitId: string, reason: DislikeReason, note?: string): FashionFeedbackRecord {
    return this.profileManager.addFeedback({
      outfitId,
      action: 'dislike',
      dislikeReason: reason,
      note
    });
  }

  public recordSave(outfitId: string): FashionFeedbackRecord {
    this.profileManager.toggleSavedOutfit(outfitId);
    return this.profileManager.addFeedback({
      outfitId,
      action: 'save'
    });
  }

  public recordReplacement(
    outfitId: string,
    slot: 'top' | 'bottom' | 'outerwear' | 'footwear' | 'accessory',
    replacedWithItemId: string
  ): FashionFeedbackRecord {
    return this.profileManager.addFeedback({
      outfitId,
      action: 'replace_item',
      replacedItemSlot: slot,
      replacedWithItemId
    });
  }

  /**
   * Computes dynamic weighting multiplier for a given style based on user history.
   * Returns a multiplier between 0.4 (heavily disliked) and 1.3 (frequently liked/saved).
   */
  public getStyleWeightMultiplier(_style: ClothingStyle): number {
    const history = this.profileManager.getProfile().feedbackHistory;
    let likes = 0;
    let dislikes = 0;

    for (const record of history) {
      if (record.action === 'like' || record.action === 'save') {
        likes++;
      } else if (record.action === 'dislike') {
        dislikes++;
      }
    }

    if (dislikes > likes * 2 && dislikes > 2) return 0.55;
    if (likes > dislikes * 2 && likes > 2) return 1.25;
    return 1.0;
  }

  public getHistory(): FashionFeedbackRecord[] {
    return this.profileManager.getProfile().feedbackHistory;
  }

  public clearFeedback(): void {
    this.profileManager.updateProfile({ feedbackHistory: [] });
  }
}
