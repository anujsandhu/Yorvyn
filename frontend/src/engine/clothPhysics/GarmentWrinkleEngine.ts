/**
 * YORVYN — Dynamic Garment Wrinkle and Fold Engine (Phase 6)
 * Analyzes local strain tensors (compression vs tension) under avatar movement,
 * generates physically plausible folds and creases, and simulates viscoelastic wrinkle recovery.
 */

import * as THREE from 'three';

export interface WrinkleMetrics {
  compressionRatio: number;
  tensionRatio: number;
  maxStrain: number;
  minStrain: number;
  foldCount: number;
  isStrainBalanced: boolean;
}

export class GarmentWrinkleEngine {
  private static readonly CRITICAL_BUCKLING_STRAIN = -0.015;

  /**
   * Evaluates local compressive strain and modulates mesh vertices and normals to produce realistic dynamic folds.
   */
  public static applyWrinkleDeformation(
    geometry: THREE.BufferGeometry,
    restPositions: Float32Array,
    fabricType: string = 'cotton',
    recoveryFactor: number = 0.95
  ): WrinkleMetrics {
    const posAttr = geometry.attributes.position as THREE.BufferAttribute;
    const normAttr = geometry.attributes.normal as THREE.BufferAttribute;

    if (!posAttr || !restPositions || posAttr.count === 0) {
      return {
        compressionRatio: 0,
        tensionRatio: 0,
        maxStrain: 0,
        minStrain: 0,
        foldCount: 0,
        isStrainBalanced: true
      };
    }

    const vCount = posAttr.count;
    const currentPos = posAttr.array as Float32Array;
    const currentNorm = normAttr ? (normAttr.array as Float32Array) : null;

    // Fabric characteristic fold properties
    const fabricFoldProfiles: Record<string, { wavelengthM: number; maxAmpM: number; recovery: number }> = {
      cotton: { wavelengthM: 0.024, maxAmpM: 0.0038, recovery: 0.92 },
      denim: { wavelengthM: 0.038, maxAmpM: 0.0055, recovery: 0.88 },
      silk: { wavelengthM: 0.012, maxAmpM: 0.0018, recovery: 0.98 },
      wool: { wavelengthM: 0.028, maxAmpM: 0.0042, recovery: 0.94 },
      leather: { wavelengthM: 0.045, maxAmpM: 0.0060, recovery: 0.84 },
      knitted: { wavelengthM: 0.020, maxAmpM: 0.0025, recovery: 0.96 },
      knitwear: { wavelengthM: 0.020, maxAmpM: 0.0025, recovery: 0.96 },
      synthetic: { wavelengthM: 0.016, maxAmpM: 0.0022, recovery: 0.97 },
      linen: { wavelengthM: 0.032, maxAmpM: 0.0048, recovery: 0.85 }
    };

    const normFabric = fabricType.toLowerCase().trim();
    const profile = fabricFoldProfiles[normFabric] || fabricFoldProfiles.cotton;
    const wavelength = profile.wavelengthM;
    const maxAmp = profile.maxAmpM;
    const effRecovery = profile.recovery * recoveryFactor;

    // Approximate vertex strain by measuring displacement relative to rest configuration
    let compressionCount = 0;
    let tensionCount = 0;
    let foldCount = 0;
    let maxStrain = 0;
    let minStrain = 0;

    for (let i = 0; i < vCount; i++) {
      const idx = i * 3;
      const rx = restPositions[idx];
      const ry = restPositions[idx + 1];
      const rz = restPositions[idx + 2];

      const cx = currentPos[idx];
      const cy = currentPos[idx + 1];
      const cz = currentPos[idx + 2];

      const dRestSq = rx * rx + ry * ry + rz * rz;
      const dCurrSq = cx * cx + cy * cy + cz * cz;
      const dRest = Math.sqrt(Math.max(1e-6, dRestSq));
      const dCurr = Math.sqrt(Math.max(1e-6, dCurrSq));

      // Local compression/tension indicator
      const strain = (dCurr - dRest) / dRest;
      if (strain > maxStrain) maxStrain = strain;
      if (strain < minStrain) minStrain = strain;

      if (strain < this.CRITICAL_BUCKLING_STRAIN && currentNorm) {
        compressionCount++;
        const compMag = Math.sqrt(Math.min(0.5, Math.abs(strain)));
        const spatialPhase = (cx * 1.5 + cy * 2.5 + cz * 1.0) / Math.max(0.005, wavelength);
        const wave = Math.sin(spatialPhase * 2.0 * Math.PI);

        if (Math.abs(wave) > 0.65) {
          foldCount++;
        }

        // Apply out-of-plane buckling displacement along vertex normal
        const disp = wave * maxAmp * compMag * (1.0 - effRecovery * 0.45);
        currentPos[idx] += currentNorm[idx] * disp;
        currentPos[idx + 1] += currentNorm[idx + 1] * disp;
        currentPos[idx + 2] += currentNorm[idx + 2] * disp;
      } else if (strain > 0.02) {
        tensionCount++;
      }
    }

    posAttr.needsUpdate = true;
    if (normAttr) {
      geometry.computeVertexNormals();
      normAttr.needsUpdate = true;
    }

    return {
      compressionRatio: Number((compressionCount / Math.max(1, vCount)).toFixed(4)),
      tensionRatio: Number((tensionCount / Math.max(1, vCount)).toFixed(4)),
      maxStrain: Number(maxStrain.toFixed(4)),
      minStrain: Number(minStrain.toFixed(4)),
      foldCount,
      isStrainBalanced: compressionCount / Math.max(1, vCount) < 0.65
    };
  }
}
