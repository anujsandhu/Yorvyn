/**
 * Yorvyn Technology Library — Garment Fitting
 * Body-relative scaling, alignment, dynamic occlusion masking, and collision mitigation.
 */

import type { Garment3DAsset } from '../garment-core/index.ts';
import type { AvatarCharacterModel } from '../avatar-core/index.ts';

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

export class StandardGarmentFitter implements IGarmentFitter {
  public async fitToAvatar(
    garment: Garment3DAsset,
    avatar: AvatarCharacterModel
  ): Promise<FittingResult> {
    const anthropometry = avatar.parameters;
    const charHeight = anthropometry.height ?? 1.70;
    const baseHeight = 1.70;
    const heightScale = charHeight / baseHeight;

    const chestCirc = anthropometry.chestCircumferenceCm ?? 96.0;
    const waistCirc = anthropometry.waistCircumferenceCm ?? 80.0;
    const hipCirc = anthropometry.hipCircumferenceCm ?? 98.0;

    const chestRatio = chestCirc / 96.0;
    const waistRatio = waistCirc / 80.0;
    const hipRatio = hipCirc / 98.0;

    const isBottom =
      garment.metadata.category === 'pants' ||
      garment.metadata.category === 'shorts' ||
      garment.metadata.category === 'jeans';

    let widthScale = 1.0;
    let depthScale = 1.0;

    if (isBottom) {
      widthScale = Math.max(0.85, Math.min(1.4, hipRatio));
      depthScale = Math.max(0.85, Math.min(1.4, (waistRatio + hipRatio) / 2));
    } else {
      widthScale = Math.max(0.85, Math.min(1.4, (chestRatio * 0.7 + waistRatio * 0.3)));
      depthScale = Math.max(0.85, Math.min(1.4, (chestRatio * 0.6 + waistRatio * 0.4)));
    }

    const appliedScale: [number, number, number] = [
      widthScale,
      heightScale,
      depthScale
    ];

    const appliedOffset: [number, number, number] = [0, 0, 0];
    const maskedBodyMaterialIds = this.computeOcclusionMask(garment.metadata.category, avatar);

    // Bounding collision estimation
    const clippingScore = Math.max(0.01, 0.05 * Math.abs(1.0 - widthScale));

    return {
      garment,
      appliedScale,
      appliedOffset,
      maskedBodyMaterialIds,
      clippingScore
    };
  }

  public computeOcclusionMask(
    garmentCategory: string,
    _avatar: AvatarCharacterModel
  ): string[] {
    const cat = garmentCategory.toLowerCase();
    switch (cat) {
      case 't-shirt':
      case 'shirt':
      case 'sweater':
      case 'hoodie':
      case 'jacket':
        return ['Body_Chest', 'Body_Torso_Upper', 'Body_UpperArm_Inner'];
      case 'pants':
      case 'jeans':
      case 'trousers':
        return ['Body_Pelvis', 'Body_Thigh_Upper', 'Body_Thigh_Inner'];
      case 'dress':
      case 'suit':
        return ['Body_Chest', 'Body_Torso_Upper', 'Body_Pelvis', 'Body_Thigh_Upper'];
      case 'shorts':
      case 'skirt':
        return ['Body_Pelvis', 'Body_Thigh_Upper'];
      default:
        return ['Body_Torso_Upper'];
    }
  }
}
