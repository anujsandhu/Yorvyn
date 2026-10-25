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
  id: string;
  name: string;
  colorHex: string;
  roughness: number;
  metalness: number;
  diffuseMapUrl?: string;
  normalMapUrl?: string;
  roughnessMapUrl?: string;
  doubleSided?: boolean;
  alphaMode?: 'opaque' | 'mask' | 'blend';
  opacity?: number;
}

export type GarmentCategoryType = 'top' | 'bottom' | 'outerwear' | 'footwear' | 'accessory' | 'dress';

export interface GarmentMetadata {
  id: string;
  name: string;
  category: GarmentCategoryType;
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
  id: string;
  name: string;
  joints: SkeletalJointDef[];
  canonicalHeight: number; // in meters (e.g. 1.70)
}

export interface AnimationClipDef {
  name: string;
  loop: boolean;
  durationSeconds: number;
  times: Float32Array;
  boneRotations?: Map<string, Float32Array>;
  boneTranslations?: Map<string, Float32Array>;
}

export interface JobProgressInfo {
  jobId: string;
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';
  progressPercent: number;
  stageLabel: string;
  errorMessage?: string;
}
