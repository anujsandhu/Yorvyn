/**
 * Yorvyn Technology Library — Avatar Core
 * Core anthropometry representation, coordinate conventions, and body definitions.
 */

import type { RawMeshData, MaterialDef, SkeletalRigDef, BoundingBox3D } from '../shared-types/index.ts';

export interface AvatarAnthropometry {
  gender: number; // 0.0 (female) .. 1.0 (male)
  age: number;    // 0.0 (young) .. 1.0 (mature)
  muscle: number; // 0.0 (lean) .. 1.0 (athletic)
  weight: number; // 0.0 (slim) .. 1.0 (heavy)
  height: number; // in meters (canonical baseline: 1.70m, range: 1.45m - 2.15m)
  breastSize?: number;
  chestCircumferenceCm?: number;
  waistCircumferenceCm?: number;
  hipCircumferenceCm?: number;
  shoulderWidthCm?: number;
  inseamLengthCm?: number;
}

export interface AvatarCharacterModel {
  id: string;
  name: string;
  parameters: AvatarAnthropometry;
  mesh: RawMeshData;
  materials: MaterialDef[];
  rig?: SkeletalRigDef;
  bounds: BoundingBox3D;
  metadata?: Record<string, unknown>;
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

/** Creates canonical default anthropometry matching a regular 1.70m avatar */
export function createDefaultAnthropometry(): AvatarAnthropometry {
  return {
    gender: 0.5,
    age: 0.35,
    muscle: 0.5,
    weight: 0.5,
    height: 1.70,
    breastSize: 0.5,
    chestCircumferenceCm: 96,
    waistCircumferenceCm: 80,
    hipCircumferenceCm: 98,
    shoulderWidthCm: 44,
    inseamLengthCm: 78
  };
}

/** Normalizes and clamps anthropometry parameters to valid bounds */
export function normalizeAnthropometry(raw: Partial<AvatarAnthropometry>): AvatarAnthropometry {
  const clamp = (val: number | undefined, min: number, max: number, fallback: number) => {
    if (val === undefined || isNaN(val)) return fallback;
    return Math.max(min, Math.min(max, val));
  };

  const height = clamp(raw.height, 1.40, 2.15, 1.70);
  const heightRatio = height / 1.70;

  return {
    gender: clamp(raw.gender, 0.0, 1.0, 0.5),
    age: clamp(raw.age, 0.0, 1.0, 0.35),
    muscle: clamp(raw.muscle, 0.0, 1.0, 0.5),
    weight: clamp(raw.weight, 0.0, 1.0, 0.5),
    height,
    breastSize: clamp(raw.breastSize, 0.0, 1.0, 0.5),
    chestCircumferenceCm: clamp(raw.chestCircumferenceCm, 60, 150, 96 * heightRatio),
    waistCircumferenceCm: clamp(raw.waistCircumferenceCm, 50, 140, 80 * heightRatio),
    hipCircumferenceCm: clamp(raw.hipCircumferenceCm, 60, 150, 98 * heightRatio),
    shoulderWidthCm: clamp(raw.shoulderWidthCm, 30, 65, 44 * heightRatio),
    inseamLengthCm: clamp(raw.inseamLengthCm, 50, 110, 78 * heightRatio)
  };
}

/** Calculates anatomical landmark heights in world meters */
export function calculateAnatomicalHeights(anthropometry: AvatarAnthropometry | number) {
  const h = typeof anthropometry === 'number'
    ? Math.max(1.0, anthropometry)
    : Math.max(1.0, anthropometry.height);

  return {
    headTop: h,
    eyes: h * AVATAR_COORDINATE_CONVENTIONS.headHeightRatio,
    neck: h * AVATAR_COORDINATE_CONVENTIONS.neckHeightRatio,
    chest: h * AVATAR_COORDINATE_CONVENTIONS.chestHeightRatio,
    waist: h * AVATAR_COORDINATE_CONVENTIONS.waistHeightRatio,
    hips: h * AVATAR_COORDINATE_CONVENTIONS.hipHeightRatio,
    crotch: h * 0.48,
    knees: h * AVATAR_COORDINATE_CONVENTIONS.kneeHeightRatio,
    ankles: h * AVATAR_COORDINATE_CONVENTIONS.ankleHeightRatio
  };
}
