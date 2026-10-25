/**
 * Yorvyn Technology Library — Avatar Core
 * Core anthropometry representation, coordinate conventions, and body definitions.
 */

import { RawMeshData, MaterialDef, SkeletalRigDef, BoundingBox3D } from '../shared-types';

export interface AvatarAnthropometry {
  gender: number; // 0.0 (female) .. 1.0 (male)
  age: number;    // 0.0 (young) .. 1.0 (mature)
  muscle: number; // 0.0 (lean) .. 1.0 (athletic)
  weight: number; // 0.0 (slim) .. 1.0 (heavy)
  height: number; // in meters (canonical baseline: 1.70m, range: 1.45m - 2.05m)
  breastSize?: number;
}

export interface AvatarCharacterModel {
  id: string;
  name: string;
  parameters: AvatarAnthropometry;
  mesh: RawMeshData;
  materials: MaterialDef[];
  rig?: SkeletalRigDef;
  bounds: BoundingBox3D;
}

/**
 * Standard Yorvyn Coordinate System Conventions:
 * - Metric scale: Units in meters (Three.js world units)
 * - Coordinate handedness: Right-handed (Three.js standard)
 * - Up vector: +Y is vertical up
 * - Facing direction: +Z is forward facing
 * - Origin: (0, 0, 0) is situated at ground contact between the feet
 */
export const AVATAR_COORDINATE_CONVENTIONS = {
  axisUp: '+Y',
  axisFront: '+Z',
  scaleUnit: 'meter',
  canonicalHeightMeters: 1.70,
  headHeightRatio: 0.925,
  neckHeightRatio: 0.835,
  chestHeightRatio: 0.770,
  waistHeightRatio: 0.620,
  hipHeightRatio: 0.550,
  kneeHeightRatio: 0.290,
  ankleHeightRatio: 0.050
} as const;
