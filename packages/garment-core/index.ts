/**
 * Yorvyn Technology Library — Garment Core
 * Garment category taxonomy, 3D manifold geometry requirements, and boundary loop definitions.
 */

import { RawMeshData, MaterialDef, GarmentMetadata } from '../shared-types';

export interface BoundaryLoop {
  name: 'neck' | 'left_cuff' | 'right_cuff' | 'waist' | 'left_ankle' | 'right_ankle';
  vertexIndices: number[];
  center: [number, number, number];
  radius: number;
}

export interface Garment3DAsset {
  metadata: GarmentMetadata;
  mesh: RawMeshData;
  materials: MaterialDef[];
  boundaryLoops: BoundaryLoop[];
  isSeparableGarment: true; // Distinguishes from fused human+clothing meshes
}

export interface IGarmentValidator {
  /** Verify that geometry is a 2-manifold separate garment with required openings */
  validateManifold(mesh: RawMeshData, category: string): {
    isValid: boolean;
    issues: string[];
    triangleCount: number;
    vertexCount: number;
  };
}
