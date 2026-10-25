/**
 * Yorvyn Technology Library — Garment Reconstruction
 * Modular Stage A & B reconstruction contracts for image understanding & separable mesh creation.
 */

import { Garment3DAsset } from '../garment-core';
import { JobProgressInfo } from '../shared-types';

export interface TemporaryGarmentInput {
  jobId: string;
  frontImageBytes: Uint8Array;
  backImageBytes?: Uint8Array;
  hintCategory?: string;
  imageMimeType: string;
}

export interface GarmentUnderstandingResult {
  category: string;
  subcategory: string;
  confidence: number;
  dominantColorHex: string;
  detectedPalette: string[];
  patternType: 'solid' | 'striped' | 'graphic' | 'patterned';
  necklineType: 'crewneck' | 'v_neck' | 'collar' | 'scoop';
  sleeveLength: 'sleeveless' | 'short' | 'three_quarter' | 'long';
  qualityScore: number; // 0.0 - 1.0
}

export interface IGarmentReconstructionEngine {
  readonly engineId: string;
  readonly engineName: string;
  readonly requiresGpu: boolean;

  /** Stage A: Understand silhouette, contours, and colors from temporary photo */
  analyzeGarmentPhoto(input: TemporaryGarmentInput): Promise<GarmentUnderstandingResult>;

  /** Stage B: Reconstruct separable 3D garment mesh and materials */
  reconstructGarment(
    input: TemporaryGarmentInput,
    analysis: GarmentUnderstandingResult,
    onProgress?: (progress: JobProgressInfo) => void
  ): Promise<Garment3DAsset>;
}
