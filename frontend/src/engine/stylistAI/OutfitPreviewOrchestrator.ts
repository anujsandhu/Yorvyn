/**
 * YORVYN — Outfit Preview Orchestrator (Phase 11)
 * Bridges AI outfit proposals with the persistent 3D avatar fitting system.
 * Converts outfit recommendations into executable HumanParams,
 * supports individual piece replacement, and manages non-destructive staging.
 */

import { OutfitRecommendation } from './types';
import { HumanParams } from '../ara/core/params';
import { FashionCatalogItem } from '../../data/fashionCatalogData';
import { Garment } from '../../types/fashion';

export interface StagedOutfitPreview {
  outfit: OutfitRecommendation;
  baselineParams: HumanParams;
  stagedParams: HumanParams;
  custom3DGarment?: Garment | null;
  timestamp: string;
}

export class OutfitPreviewOrchestrator {
  private currentStaged: StagedOutfitPreview | null = null;
  private listeners: ((staged: StagedOutfitPreview | null) => void)[] = [];

  /**
   * Stages an outfit recommendation onto the persistent 3D avatar without destroying avatar DNA.
   */
  public stageOutfit(
    outfit: OutfitRecommendation,
    baselineParams: HumanParams
  ): StagedOutfitPreview {
    const stagedParams: HumanParams = { ...baselineParams };
    let custom3D: Garment | null = null;

    // Check if top is a custom 3D reconstructed piece
    if ('is_custom_3d' in outfit.top && (outfit.top.is_custom_3d || outfit.top.glb_url)) {
      custom3D = outfit.top as Garment;
      stagedParams.outfit = 'none';
      stagedParams.top = 'none';
    } else if ('appliedParams' in outfit.top) {
      Object.assign(stagedParams, (outfit.top as FashionCatalogItem).appliedParams);
    } else {
      stagedParams.top = 'tshirt';
    }

    // Apply bottoms
    if ('appliedParams' in outfit.bottom) {
      const p = (outfit.bottom as FashionCatalogItem).appliedParams;
      if (p.bottom) stagedParams.bottom = p.bottom;
      if (p.outfit && stagedParams.outfit === 'none') stagedParams.outfit = p.outfit;
    } else {
      stagedParams.bottom = 'trousers';
    }

    // Apply shoes
    if ('appliedParams' in outfit.footwear) {
      const p = (outfit.footwear as FashionCatalogItem).appliedParams;
      if (p.shoes) stagedParams.shoes = p.shoes;
    } else if ('araShoesId' in outfit.footwear && (outfit.footwear as any).araShoesId) {
      stagedParams.shoes = (outfit.footwear as any).araShoesId as string;
    } else {
      stagedParams.shoes = 'shoes01';
    }

    // Absolute identity preservation guarantee: Avatar skin, hair, facial hair, and expressions are NEVER modified
    stagedParams.skin = baselineParams.skin;
    stagedParams.skinTint = baselineParams.skinTint;
    stagedParams.hair = baselineParams.hair;
    stagedParams.hairColor = baselineParams.hairColor;
    stagedParams.hairTint = baselineParams.hairTint;
    stagedParams.facialHair = baselineParams.facialHair;
    stagedParams.expression = baselineParams.expression;
    stagedParams.height = baselineParams.height;
    stagedParams.weight = baselineParams.weight;
    stagedParams.muscle = baselineParams.muscle;
    stagedParams.proportions = baselineParams.proportions;

    this.currentStaged = {
      outfit,
      baselineParams: { ...baselineParams },
      stagedParams,
      custom3DGarment: custom3D,
      timestamp: new Date().toISOString()
    };

    this.notifyListeners();
    return this.currentStaged;
  }

  /**
   * Replaces an individual garment in the staged outfit (e.g. swap shirt, swap shoes).
   */
  public replacePiece(
    slot: 'top' | 'bottom' | 'footwear' | 'outerwear',
    newItem: FashionCatalogItem | Garment
  ): StagedOutfitPreview | null {
    if (!this.currentStaged) return null;

    const updatedOutfit = { ...this.currentStaged.outfit };
    if (slot === 'top') updatedOutfit.top = newItem;
    else if (slot === 'bottom') updatedOutfit.bottom = newItem;
    else if (slot === 'footwear') updatedOutfit.footwear = newItem;
    else if (slot === 'outerwear') updatedOutfit.outerwear = newItem;

    return this.stageOutfit(updatedOutfit, this.currentStaged.baselineParams);
  }

  public getStaged(): StagedOutfitPreview | null {
    return this.currentStaged ? { ...this.currentStaged } : null;
  }

  public revert(): HumanParams | null {
    if (!this.currentStaged) return null;
    const original = { ...this.currentStaged.baselineParams };
    this.currentStaged = null;
    this.notifyListeners();
    return original;
  }

  public commit(): HumanParams | null {
    if (!this.currentStaged) return null;
    const finalParams = { ...this.currentStaged.stagedParams };
    this.currentStaged = null;
    this.notifyListeners();
    return finalParams;
  }

  public subscribe(listener: (staged: StagedOutfitPreview | null) => void): () => void {
    this.listeners.push(listener);
    listener(this.getStaged());
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  private notifyListeners(): void {
    for (const listener of this.listeners) {
      try {
        listener(this.getStaged());
      } catch (e) {
        console.error('[OutfitPreviewOrchestrator] Listener error:', e);
      }
    }
  }
}
