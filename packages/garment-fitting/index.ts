/**
 * Yorvyn Technology Library — Garment Fitting
 * Body-relative scaling, alignment, dynamic occlusion masking, and collision mitigation.
 */

import { Garment3DAsset } from '../garment-core';
import { AvatarCharacterModel } from '../avatar-core';

export interface FittingResult {
  garment: Garment3DAsset;
  appliedScale: [number, number, number];
  appliedOffset: [number, number, number];
  maskedBodyMaterialIds: string[]; // Materials hidden to eliminate poke-through
  clippingScore: number;          // 0.0 (no clipping) .. 1.0 (severe clipping)
}

export interface IGarmentFitter {
  /** Fit and scale garment to the target character's proportions */
  fitToAvatar(
    garment: Garment3DAsset,
    avatar: AvatarCharacterModel
  ): Promise<FittingResult>;

  /** Calculate occlusion mask list to eliminate internal mesh poke-through */
  computeOcclusionMask(
    garmentCategory: string,
    avatar: AvatarCharacterModel
  ): string[];
}
