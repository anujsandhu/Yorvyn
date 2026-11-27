/**
 * YORVYN — Garment Size and Ease Intelligence Engine (Phase 5)
 * Evaluates garment ease relative to avatar measurements and computes
 * non-uniform segment scaling curves for proportional virtual try-on.
 */

import { AvatarBodyMeasurements } from './AvatarBodyMeasurementEngine';

export interface GarmentEaseResult {
  fitClassification: 'compression' | 'slim' | 'regular' | 'relaxed' | 'oversized';
  chestEaseCm: number;
  waistEaseCm: number;
  hipEaseCm: number;
  shoulderEaseCm: number;
  inseamEaseCm: number;
  isNegativeEase: boolean;
  segmentScales: {
    shoulder: number;
    chest: number;
    waist: number;
    hip: number;
    height: number;
  };
}

export class GarmentEaseEngine {
  public static calculateEase(
    category: string,
    subcategory: string,
    measurements: AvatarBodyMeasurements,
    targetFit?: string
  ): GarmentEaseResult {
    const isBottom = category.includes('bottom') || category.includes('pant') || category.includes('jean');

    // Default canonical base garment circumferences (1.75m standard human)
    let gChest = 102.0; // +6cm ease
    let gWaist = 84.0;  // +6cm ease
    let gHip = 104.0;   // +6cm ease
    let gShoulder = 45.0; // +1.5cm ease
    let gInseam = 78.0;

    const fitOffsets: Record<string, number> = {
      compression: -3.0,
      slim: -2.0,
      regular: 0.0,
      relaxed: 5.0,
      oversized: 10.0
    };
    const offset = targetFit && fitOffsets[targetFit.toLowerCase()] !== undefined ? fitOffsets[targetFit.toLowerCase()] : 0.0;

    if (subcategory === 'hoodie' || subcategory === 'jacket') {
      gChest = 110.0 + offset;
      gWaist = 90.0 + offset;
      gShoulder = 47.5 + offset * 0.25;
    } else if (subcategory === 'formal_shirt') {
      gChest = 100.0 + offset;
      gWaist = 82.0 + offset;
    } else if (isBottom) {
      gWaist = 82.0 + offset;
      gHip = 104.0 + offset;
    } else if (category.includes('dress')) {
      gChest = 98.0 + offset;
      gWaist = 80.0 + offset;
      gHip = 110.0 + offset;
    }

    const chestEase = Math.round((gChest - measurements.chestCircumferenceCm) * 10) / 10;
    const waistEase = Math.round((gWaist - measurements.waistCircumferenceCm) * 10) / 10;
    const hipEase = Math.round((gHip - measurements.hipCircumferenceCm) * 10) / 10;
    const shoulderEase = Math.round((gShoulder - measurements.shoulderWidthCm) * 10) / 10;
    const inseamEase = Math.round((gInseam - measurements.inseamCm) * 10) / 10;

    const refEase = isBottom ? hipEase : chestEase;
    let classification: 'compression' | 'slim' | 'regular' | 'relaxed' | 'oversized' = 'regular';
    if (refEase < 0.0) {
      classification = 'compression';
    } else if (refEase < 4.0) {
      classification = 'slim';
    } else if (refEase < 9.0) {
      classification = 'regular';
    } else if (refEase < 15.0) {
      classification = 'relaxed';
    } else {
      classification = 'oversized';
    }

    // Proportional anatomical scaling multipliers relative to canonical Ara 3D 1.75m body
    const sShoulder = Math.max(0.75, Math.min(1.40, (measurements.shoulderWidthCm + shoulderEase) / 45.0));
    const sChest = Math.max(0.70, Math.min(1.45, (measurements.chestCircumferenceCm + chestEase) / 102.0));
    const sWaist = Math.max(0.70, Math.min(1.45, (measurements.waistCircumferenceCm + waistEase) / 84.0));
    const sHip = Math.max(0.70, Math.min(1.45, (measurements.hipCircumferenceCm + hipEase) / 104.0));
    const sHeight = Math.max(0.75, Math.min(1.35, measurements.heightCm / 175.0));

    return {
      fitClassification: classification,
      chestEaseCm: chestEase,
      waistEaseCm: waistEase,
      hipEaseCm: hipEase,
      shoulderEaseCm: shoulderEase,
      inseamEaseCm: inseamEase,
      isNegativeEase: refEase < 0.0,
      segmentScales: {
        shoulder: Math.round(sShoulder * 1000) / 1000,
        chest: Math.round(sChest * 1000) / 1000,
        waist: Math.round(sWaist * 1000) / 1000,
        hip: Math.round(sHip * 1000) / 1000,
        height: Math.round(sHeight * 1000) / 1000
      }
    };
  }
}

