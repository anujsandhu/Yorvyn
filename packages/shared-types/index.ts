/**
 * Yorvyn Technology Library — Shared Types
 * Central contract declarations for 3D meshes, rigs, garments, and materials.
 */

export interface Vector3D {
  x: number;
  y: number;
  z: number;
}

export interface Quaternion4D {
  x: number;
  y: number;
  z: number;
  w: number;
}

export interface BoundingBox3D {
  min: Vector3D;
  max: Vector3D;
}

export interface RawMeshData {
  positions: Float32Array;
  normals: Float32Array;
  uvs?: Float32Array;
  indices: Uint32Array;
  jointIndices?: Uint16Array;
  jointWeights?: Float32Array;
}

export interface MaterialDef {
  id?: string;
  name: string;
  colorHex?: string;
  diffuseColorHex?: string;
  roughness: number;
  metalness: number;
  diffuseMapUrl?: string;
  normalMapUrl?: string;
  roughnessMapUrl?: string;
  doubleSided?: boolean;
  alphaMode?: 'opaque' | 'mask' | 'blend';
  opacity?: number;
}

export type GarmentCategoryType =
  | 'top'
  | 'bottom'
  | 'outerwear'
  | 'footwear'
  | 'accessory'
  | 'dress'
  | 't-shirt'
  | 'shirt'
  | 'pants'
  | 'jeans'
  | 'shorts'
  | 'skirt'
  | 'hoodie'
  | 'sweater'
  | 'jacket'
  | 'suit';

export interface GarmentMetadata {
  id: string;
  name: string;
  category: GarmentCategoryType;
  color?: string;
  fabricType?: string;
  tags?: string[];
  subcategory?: string;
  brand?: string;
  detectedColors?: string[];
  pattern?: string;
  necklineType?: string;
  sleeveLength?: string;
  fitType?: 'slim' | 'regular' | 'oversized';
  sourceModelVersion?: string;
  createdAt: string;
}

export interface SkeletalJointDef {
  name: string;
  parent?: string;
  position: Vector3D;
  rotation?: Quaternion4D;
}

export interface SkeletalRigDef {
  id?: string;
  name?: string;
  joints?: SkeletalJointDef[];
  canonicalHeight?: number; // in meters (e.g. 1.70)
  boneNames: string[];
  parentIndices: number[];
  restPositions: [number, number, number][];
}

export interface AnimationClipDef {
  name: string;
  loop?: boolean;
  isLooping?: boolean;
  durationSeconds: number;
  times?: Float32Array;
  boneTrackCount?: number;
  boneRotations?: Map<string, Float32Array>;
  boneTranslations?: Map<string, Float32Array>;
}

export interface JobProgressInfo {
  jobId: string;
  status?: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';
  stage?: string;
  stageLabel?: string;
  progressPercent: number;
  detailMessage?: string;
  errorMessage?: string;
}

/** Utility: Compute bounding box from 3D positions array or RawMeshData */
export function computeBoundingBox(input: Float32Array | RawMeshData): BoundingBox3D & { size: Vector3D } {
  const positions = (input instanceof Float32Array) ? input : input.positions;
  if (!positions || positions.length < 3) {
    return {
      min: { x: 0, y: 0, z: 0 },
      max: { x: 0, y: 0, z: 0 },
      size: { x: 0, y: 0, z: 0 }
    };
  }
  let minX = positions[0], maxX = positions[0];
  let minY = positions[1], maxY = positions[1];
  let minZ = positions[2], maxZ = positions[2];

  for (let i = 3; i < positions.length; i += 3) {
    const x = positions[i];
    const y = positions[i + 1];
    const z = positions[i + 2];
    if (x < minX) minX = x;
    if (x > maxX) maxX = x;
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
    if (z < minZ) minZ = z;
    if (z > maxZ) maxZ = z;
  }

  return {
    min: { x: minX, y: minY, z: minZ },
    max: { x: maxX, y: maxY, z: maxZ },
    size: { x: maxX - minX, y: maxY - minY, z: maxZ - minZ }
  };
}
