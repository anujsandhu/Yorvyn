/**
 * Yorvyn Technology Library — Garment Core
 * Garment category taxonomy, 3D manifold geometry requirements, and boundary loop definitions.
 */

import type { RawMeshData, MaterialDef, GarmentMetadata } from '../shared-types/index.ts';

export interface BoundaryLoop {
  name: 'neck' | 'left_cuff' | 'right_cuff' | 'waist' | 'left_ankle' | 'right_ankle' | 'hem';
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

export const GARMENT_CATEGORIES = [
  't-shirt',
  'shirt',
  'jacket',
  'hoodie',
  'sweater',
  'pants',
  'jeans',
  'shorts',
  'skirt',
  'dress',
  'suit'
] as const;

export class StandardGarmentValidator implements IGarmentValidator {
  public validateManifold(
    mesh: RawMeshData,
    category: string
  ): {
    isValid: boolean;
    issues: string[];
    triangleCount: number;
    vertexCount: number;
  } {
    const issues: string[] = [];
    const vertexCount = mesh.positions.length / 3;
    const triangleCount = mesh.indices.length / 3;

    if (vertexCount < 3) {
      issues.push(`Insufficient vertices: found ${vertexCount}, minimum 3 required`);
    }

    if (triangleCount < 1) {
      issues.push(`Insufficient triangles: found ${triangleCount}, minimum 1 required`);
    }

    // Check index bounds
    for (let i = 0; i < mesh.indices.length; i++) {
      const idx = mesh.indices[i];
      if (idx < 0 || idx >= vertexCount) {
        issues.push(`Index out of bounds at position ${i}: ${idx} exceeds vertexCount ${vertexCount}`);
        break;
      }
    }

    // Check for NaN or non-finite coordinates
    let hasNonFinite = false;
    for (let i = 0; i < mesh.positions.length; i++) {
      if (!Number.isFinite(mesh.positions[i])) {
        hasNonFinite = true;
        break;
      }
    }
    if (hasNonFinite) {
      issues.push('Mesh positions contain NaN or non-finite floating point coordinates');
    }

    // Check bounding box volume
    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;
    let minZ = Infinity, maxZ = -Infinity;

    for (let i = 0; i < vertexCount; i++) {
      const x = mesh.positions[i * 3];
      const y = mesh.positions[i * 3 + 1];
      const z = mesh.positions[i * 3 + 2];
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
      if (z < minZ) minZ = z;
      if (z > maxZ) maxZ = z;
    }

    const extentY = maxY - minY;
    if (extentY < 0.05) {
      issues.push(`Garment vertical dimension too flat (${extentY.toFixed(3)}m) for category '${category}'`);
    }

    return {
      isValid: issues.length === 0,
      issues,
      triangleCount,
      vertexCount
    };
  }
}

export function extractBoundaryLoops(mesh: RawMeshData, category: string): BoundaryLoop[] {
  const loops: BoundaryLoop[] = [];
  const vertexCount = mesh.positions.length / 3;
  if (vertexCount === 0) return loops;

  let minY = Infinity, maxY = -Infinity;
  for (let i = 0; i < vertexCount; i++) {
    const y = mesh.positions[i * 3 + 1];
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
  }

  // Upper boundary opening (neck / waist)
  const topIndices: number[] = [];
  const topThreshold = maxY - (maxY - minY) * 0.1;
  let topCenterX = 0, topCenterY = 0, topCenterZ = 0;

  for (let i = 0; i < vertexCount; i++) {
    const y = mesh.positions[i * 3 + 1];
    if (y >= topThreshold) {
      topIndices.push(i);
      topCenterX += mesh.positions[i * 3];
      topCenterY += y;
      topCenterZ += mesh.positions[i * 3 + 2];
    }
  }

  if (topIndices.length > 0) {
    const count = topIndices.length;
    loops.push({
      name: category === 'pants' || category === 'shorts' ? 'waist' : 'neck',
      vertexIndices: topIndices,
      center: [topCenterX / count, topCenterY / count, topCenterZ / count],
      radius: 0.12
    });
  }

  // Lower boundary opening (hem / ankles)
  const bottomIndices: number[] = [];
  const bottomThreshold = minY + (maxY - minY) * 0.1;
  let botCenterX = 0, botCenterY = 0, botCenterZ = 0;

  for (let i = 0; i < vertexCount; i++) {
    const y = mesh.positions[i * 3 + 1];
    if (y <= bottomThreshold) {
      bottomIndices.push(i);
      botCenterX += mesh.positions[i * 3];
      botCenterY += y;
      botCenterZ += mesh.positions[i * 3 + 2];
    }
  }

  if (bottomIndices.length > 0) {
    const count = bottomIndices.length;
    loops.push({
      name: category === 'pants' ? 'left_ankle' : 'hem',
      vertexIndices: bottomIndices,
      center: [botCenterX / count, botCenterY / count, botCenterZ / count],
      radius: 0.22
    });
  }

  return loops;
}
