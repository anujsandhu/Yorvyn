/**
 * YORVYN — Master Garment Fitting Engine
 * Orchestrates glTF validation, geometry repair, BVH-accelerated collision resolution,
 * skeletal skinning transfer, and PBR fabric shading.
 */

import * as THREE from 'three';
import { GarmentGltfValidator, GltfValidationReport } from './GarmentGltfValidator';
import { GarmentGeometryValidator, GeometryValidationResult } from './GarmentGeometryValidator';
import { GarmentCollisionResolver, CollisionResolutionResult } from './GarmentCollisionResolver';
import { GarmentSkinningAdapter, SkinningAdaptationResult } from './GarmentSkinningAdapter';
import { GarmentLayerManager } from './GarmentLayerManager';
import { GarmentDiagnostics, GarmentDiagnosticMetrics } from './GarmentDiagnostics';
import { GarmentMaterialSystem, FabricType, FabricMaterialConfig } from './GarmentMaterialSystem';

export interface GarmentFitPipelineInput {
  garmentId: string;
  positions: Float32Array;
  indices: Uint32Array;
  skinCoords: Float32Array;
  skinNormals: Float32Array;
  bodyGeometry?: THREE.BufferGeometry;
  skinIndices?: Uint16Array;
  skinWeights?: Float32Array;
  numBones?: number;
  fabricType?: FabricType;
  baseColor?: string;
}

export interface GarmentFitPipelineResult {
  garmentId: string;
  geometry: GeometryValidationResult;
  collision: CollisionResolutionResult;
  skinning?: SkinningAdaptationResult;
  material: FabricMaterialConfig;
  diagnostics: GarmentDiagnosticMetrics;
  gltfValidation?: GltfValidationReport;
}

export class GarmentFittingEngine {
  /**
   * Validates a source GLB/glTF garment binary asset using glTF Transform.
   * Rejects corrupted or invalid files with explicit diagnostic messages.
   */
  public static async validateSourceAsset(glbBytes: Uint8Array): Promise<GltfValidationReport> {
    const report = await GarmentGltfValidator.validateGlb(glbBytes);
    if (!report.isValid) {
      throw new Error(`[GarmentFittingEngine] Asset validation failed: ${report.errors.join('; ')}`);
    }
    return report;
  }

  /**
   * Executes the complete robust 4-stage virtual try-on fitting pipeline:
   * 1. Geometry Validation & Degenerate Repair
   * 2. BVH-Accelerated Spatial Body Collision Resolution
   * 3. Skeletal Skin Weight Normalization / Barycentric Transfer
   * 4. PBR Fabric Shading & Diagnostics
   */
  public static fitGarmentToAvatar(input: GarmentFitPipelineInput): GarmentFitPipelineResult {
    // Stage 1: Geometry Sanity & Repair
    const geometry = GarmentGeometryValidator.validateAndRepair(
      input.positions,
      input.indices
    );

    // Stage 2: Spatial Collision Resolution with Skin (BVH or vertex normals)
    let collision: CollisionResolutionResult;
    if (input.bodyGeometry) {
      collision = GarmentCollisionResolver.resolveBodyCollisionsBVH(
        geometry.positions,
        input.bodyGeometry,
        { minClearanceMeters: 0.0028, stiffness: 1.0 }
      );
    } else {
      collision = GarmentCollisionResolver.resolveBodyCollisions(
        geometry.positions,
        input.skinCoords,
        input.skinNormals,
        { minClearanceMeters: 0.0028, stiffness: 1.0 }
      );
    }

    // Stage 3: Skeletal Skin Weight Normalization or Barycentric Transfer
    let skinning: SkinningAdaptationResult | undefined;
    if (input.skinIndices && input.skinWeights && input.numBones) {
      skinning = GarmentSkinningAdapter.normalizeAndValidateWeights(
        input.skinIndices,
        input.skinWeights,
        input.numBones,
        4
      );
    } else if (input.bodyGeometry) {
      // Unrigged garment: Transfer skin weights from avatar body using BVH surface correspondence
      skinning = GarmentSkinningAdapter.transferBodySkinWeightsBVH(
        geometry.positions,
        input.bodyGeometry,
        4
      );
    }

    // Stage 4: Fabric Material Profile
    const material = GarmentMaterialSystem.getFabricProfile(
      input.fabricType || 'cotton',
      input.baseColor || '#ffffff'
    );

    // Diagnostics
    const diagnostics = GarmentDiagnostics.evaluateGarment(
      input.garmentId,
      collision.resolvedPositions,
      geometry.indices,
      input.skinCoords,
      input.skinNormals,
      skinning?.skinWeights
    );

    return {
      garmentId: input.garmentId,
      geometry,
      collision,
      skinning,
      material,
      diagnostics
    };
  }
}

export {
  GarmentGltfValidator,
  GarmentGeometryValidator,
  GarmentCollisionResolver,
  GarmentSkinningAdapter,
  GarmentLayerManager,
  GarmentDiagnostics,
  GarmentMaterialSystem
};
