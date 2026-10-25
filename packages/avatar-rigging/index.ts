/**
 * Yorvyn Technology Library — Avatar Rigging
 * Humanoid skeletal topology, joint landmarks, and vertex skinning calculation.
 */

import { SkeletalRigDef, RawMeshData } from '../shared-types';

export interface SkinningWeightsResult {
  jointIndices: Uint16Array;  // (N, 4) joint references
  jointWeights: Float32Array; // (N, 4) normalized weight floats (sum to 1.0)
}

export interface IAvatarRiggingService {
  /** Create standard 65-bone humanoid skeleton matching character height */
  generateRig(characterHeightMeters: number): SkeletalRigDef;

  /** Compute smooth heat-diffusion / distance bone weights for arbitrary manifold mesh */
  computeSkinningWeights(
    mesh: RawMeshData,
    rig: SkeletalRigDef,
    maxInfluencesPerVertex?: number
  ): SkinningWeightsResult;
}
