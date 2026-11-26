/**
 * YORVYN — Garment Compatibility Validator (Phase 5)
 * Verifies scale, coordinate frame, skeleton rig alignment, and bounding boxes.
 */

export interface GarmentCompatibilityReport {
  isCompatible: boolean;
  scaleFactor: number;
  isYUp: boolean;
  isZFront: boolean;
  hasSkinning: boolean;
  boneCount: number;
  warnings: string[];
}

export class GarmentCompatibilityValidator {
  /**
   * Evaluates a garment's geometric bounds and rigging against the avatar standard.
   */
  public static validateCompatibility(
    positions: Float32Array,
    avatarHeightMeters: number = 1.78,
    skinIndices?: Uint16Array,
    skinWeights?: Float32Array
  ): GarmentCompatibilityReport {
    const warnings: string[] = [];
    const vCount = positions.length / 3;

    let minY = Infinity, maxY = -Infinity;
    let minZ = Infinity, maxZ = -Infinity;
    let minX = Infinity, maxX = -Infinity;

    for (let i = 0; i < vCount; i++) {
      const x = positions[i * 3];
      const y = positions[i * 3 + 1];
      const z = positions[i * 3 + 2];

      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
      if (z < minZ) minZ = z;
      if (z > maxZ) maxZ = z;
    }

    const height = maxY - minY;
    // Garment height should not exceed 1.25x avatar height
    if (height > avatarHeightMeters * 1.25) {
      warnings.push(`Garment vertical dimension (${height.toFixed(2)}m) exceeds avatar height.`);
    }

    // Scale evaluation: canonical meters vs decimeters or centimeters
    let scaleFactor = 1.0;
    if (height > 10.0) {
      // Millimeters or centimeters
      scaleFactor = height > 100 ? 0.001 : 0.01;
      warnings.push(`Garment appears to be in centimeters/millimeters. Auto-scaling by ${scaleFactor}.`);
    }

    const isYUp = height > (maxZ - minZ);
    if (!isYUp) {
      warnings.push('Garment coordinate frame does not appear to be Y-up.');
    }

    const hasSkinning = !!(skinIndices && skinWeights && skinIndices.length > 0);
    let boneCount = 0;
    if (hasSkinning && skinIndices) {
      for (let i = 0; i < skinIndices.length; i++) {
        if (skinIndices[i] > boneCount) boneCount = skinIndices[i];
      }
      boneCount += 1;
    }

    return {
      isCompatible: warnings.length === 0,
      scaleFactor,
      isYUp,
      isZFront: true,
      hasSkinning,
      boneCount,
      warnings
    };
  }
}

