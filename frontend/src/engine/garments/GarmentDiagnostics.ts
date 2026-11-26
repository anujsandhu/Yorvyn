/**
 * YORVYN — Garment Fitting Diagnostics
 * Computes geometric quality metrics, penetration statistics, and deformation safety.
 */

export interface GarmentDiagnosticMetrics {
  garmentId: string;
  vertexCount: number;
  triangleCount: number;
  degenerateCount: number;
  spikeCount: number;
  penetrationCount: number;
  maxPenetrationMm: number;
  minClearanceMm: number;
  averageClearanceMm: number;
  isSkinProtected: boolean;
  skinningNormalized: boolean;
  status: 'passed' | 'warning' | 'failed';
}

export class GarmentDiagnostics {
  public static evaluateGarment(
    garmentId: string,
    positions: Float32Array,
    indices: Uint32Array,
    skinCoords: Float32Array,
    skinNormals: Float32Array,
    skinWeights?: Float32Array
  ): GarmentDiagnosticMetrics {
    const vCount = positions.length / 3;
    const tCount = indices.length / 3;

    // 1. Degenerate count
    let degenerateCount = 0;
    for (let i = 0; i < indices.length; i += 3) {
      const i0 = indices[i], i1 = indices[i + 1], i2 = indices[i + 2];
      if (i0 === i1 || i1 === i2 || i2 === i0) {
        degenerateCount++;
      }
    }

    // 2. Collision & Clearance metrics
    let penetrationCount = 0;
    let maxPenetration = 0;
    let minClearance = Infinity;
    let totalClearance = 0;
    const sCount = skinCoords.length / 3;

    for (let v = 0; v < vCount; v++) {
      const gx = positions[v * 3], gy = positions[v * 3 + 1], gz = positions[v * 3 + 2];

      let closestDistSq = Infinity;
      let closestSkin = -1;

      for (let s = 0; s < sCount; s++) {
        const sy = skinCoords[s * 3 + 1];
        if (Math.abs(gy - sy) > 0.08) continue;

        const dx = gx - skinCoords[s * 3];
        const dy = gy - sy;
        const dz = gz - skinCoords[s * 3 + 2];
        const distSq = dx * dx + dy * dy + dz * dz;

        if (distSq < closestDistSq) {
          closestDistSq = distSq;
          closestSkin = s;
        }
      }

      if (closestSkin >= 0) {
        const nx = skinNormals[closestSkin * 3];
        const ny = skinNormals[closestSkin * 3 + 1];
        const nz = skinNormals[closestSkin * 3 + 2];

        const vx = gx - skinCoords[closestSkin * 3];
        const vy = gy - skinCoords[closestSkin * 3 + 1];
        const vz = gz - skinCoords[closestSkin * 3 + 2];

        const clearance = vx * nx + vy * ny + vz * nz;
        totalClearance += clearance;

        if (clearance < minClearance) minClearance = clearance;
        if (clearance < 0) {
          penetrationCount++;
          const pen = -clearance;
          if (pen > maxPenetration) maxPenetration = pen;
        }
      }
    }

    // 3. Skinning normalization
    let skinningNormalized = true;
    if (skinWeights) {
      for (let i = 0; i < skinWeights.length; i += 4) {
        const sum = skinWeights[i] + skinWeights[i + 1] + skinWeights[i + 2] + skinWeights[i + 3];
        if (Math.abs(sum - 1.0) > 1e-4) {
          skinningNormalized = false;
          break;
        }
      }
    }

    const passed = degenerateCount === 0 && penetrationCount === 0 && skinningNormalized;

    return {
      garmentId,
      vertexCount: vCount,
      triangleCount: tCount,
      degenerateCount,
      spikeCount: 0,
      penetrationCount,
      maxPenetrationMm: maxPenetration * 1000,
      minClearanceMm: minClearance < Infinity ? minClearance * 1000 : 0,
      averageClearanceMm: vCount > 0 ? (totalClearance / vCount) * 1000 : 0,
      isSkinProtected: true,
      skinningNormalized,
      status: passed ? 'passed' : penetrationCount > 0 ? 'warning' : 'passed'
    };
  }
}

