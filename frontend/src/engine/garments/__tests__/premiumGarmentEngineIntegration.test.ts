/**
 * YORVYN — Premium Garment Engine Integration Test Suite
 * Tests glTF Transform asset validation, three-mesh-bvh accelerated collision,
 * barycentric skinning transfer, and full virtual try-on lifecycle.
 */

import { describe, it, expect } from 'vitest';
import * as THREE from 'three';
import {
  GarmentFittingEngine,
  GarmentGltfValidator,
  GarmentCollisionResolver,
  GarmentSkinningAdapter,
  OutfitStateManager,
  BaseBodyController,
  GarmentResourceManager
} from '../index';

describe('YORVYN Premium Garment Engine Integration', () => {
  describe('1. glTF Transform Asset Validation (GarmentGltfValidator)', () => {
    it('should reject invalid or truncated binary data with explicit errors', async () => {
      const corruptData = new Uint8Array([0x00, 0x01, 0x02]);
      const report = await GarmentGltfValidator.validateGlb(corruptData);

      expect(report.isValid).toBe(false);
      expect(report.errors.length).toBeGreaterThan(0);
      expect(report.errors[0]).toContain('too small');
    });

    it('should reject binary files with incorrect magic number', async () => {
      const invalidMagic = new Uint8Array(20);
      const view = new DataView(invalidMagic.buffer);
      view.setUint32(0, 0x12345678, true); // Wrong magic
      view.setUint32(4, 2, true); // Version 2

      const report = await GarmentGltfValidator.validateGlb(invalidMagic);
      expect(report.isValid).toBe(false);
      expect(report.errors[0]).toContain('Invalid binary header magic');
    });

    it('should reject binary files with unsupported glTF version', async () => {
      const invalidVersion = new Uint8Array(20);
      const view = new DataView(invalidVersion.buffer);
      view.setUint32(0, 0x46546c67, true); // 'glTF'
      view.setUint32(4, 1, true); // Version 1.0 (unsupported)

      const report = await GarmentGltfValidator.validateGlb(invalidVersion);
      expect(report.isValid).toBe(false);
      expect(report.errors[0]).toContain('Unsupported glTF version 1');
    });
  });

  describe('2. three-mesh-bvh Spatial Collision Resolution', () => {
    it('should project penetrating garment vertices outward with guaranteed clearance', () => {
      // Create a body sphere of radius 1.0m
      const bodyGeo = new THREE.SphereGeometry(1.0, 16, 16);

      // Create garment vertices, one of which penetrates inside the sphere at r = 0.98m
      const garmentPositions = new Float32Array([
        0.98, 0.0, 0.0, // penetrating inside body by 20mm
        0.0, 1.05, 0.0, // outside body (clearance 50mm)
        0.0, 0.0, 1.002 // very close to surface (clearance 2mm, below 2.8mm threshold)
      ]);

      const result = GarmentCollisionResolver.resolveBodyCollisionsBVH(
        garmentPositions,
        bodyGeo,
        { minClearanceMeters: 0.0028, stiffness: 1.0 }
      );

      expect(result.penetrationCount).toBeGreaterThanOrEqual(1);

      // The penetrating vertex at index 0 should now be outside the body at r >= 1.0m
      const px = result.resolvedPositions[0];
      const py = result.resolvedPositions[1];
      const pz = result.resolvedPositions[2];
      const finalDist = Math.sqrt(px * px + py * py + pz * pz);

      expect(finalDist).toBeGreaterThan(1.0);
    });

    it('should preserve vertices that already satisfy clearance requirements', () => {
      const bodyGeo = new THREE.BoxGeometry(1.0, 1.0, 1.0);

      // Point at (0.8, 0, 0) is well outside the box face at x = 0.5
      const garmentPositions = new Float32Array([0.8, 0.0, 0.0]);

      const result = GarmentCollisionResolver.resolveBodyCollisionsBVH(
        garmentPositions,
        bodyGeo,
        { minClearanceMeters: 0.0028 }
      );

      expect(result.penetrationCount).toBe(0);
      expect(result.resolvedPositions[0]).toBeCloseTo(0.8, 4);
    });
  });

  describe('3. Barycentric Surface Skinning Weight Transfer', () => {
    it('should transfer continuous bone weights to unrigged garments using body BVH lookup', () => {
      // Create a simple rigged body plane
      const bodyGeo = new THREE.PlaneGeometry(1, 1, 2, 2);
      const vCount = bodyGeo.attributes.position.count;

      const skinIndices = new Uint16Array(vCount * 4);
      const skinWeights = new Float32Array(vCount * 4);

      // Rig body: Left side to Bone 1 (Chest), Right side to Bone 2 (Arm)
      for (let i = 0; i < vCount; i++) {
        const x = bodyGeo.attributes.position.getX(i);
        if (x < 0) {
          skinIndices[i * 4] = 1; // Chest bone
          skinWeights[i * 4] = 1.0;
        } else {
          skinIndices[i * 4] = 2; // Arm bone
          skinWeights[i * 4] = 1.0;
        }
      }

      bodyGeo.setAttribute('skinIndex', new THREE.BufferAttribute(skinIndices, 4));
      bodyGeo.setAttribute('skinWeight', new THREE.BufferAttribute(skinWeights, 4));

      // Unrigged garment vertex placed near the body plane at (-0.3, 0.0, 0.01)
      const garmentPositions = new Float32Array([
        -0.3, 0.0, 0.01,
        0.3, 0.0, 0.01
      ]);

      const skinning = GarmentSkinningAdapter.transferBodySkinWeightsBVH(
        garmentPositions,
        bodyGeo,
        4
      );

      expect(skinning.valid).toBe(true);

      // Vertex 0 (-0.3) should receive Bone 1 influence (smooth barycentric blending across triangle)
      expect(skinning.skinIndices[0]).toBe(1);
      expect(skinning.skinWeights[0]).toBeGreaterThan(0.5);

      // Vertex 1 (0.3) should receive Bone 2 influence
      expect(skinning.skinIndices[4]).toBe(2);
      expect(skinning.skinWeights[4]).toBeGreaterThan(0.5);

      // Sum of weights per vertex must strictly equal 1.0
      const sum0 = skinning.skinWeights[0] + skinning.skinWeights[1] + skinning.skinWeights[2] + skinning.skinWeights[3];
      const sum1 = skinning.skinWeights[4] + skinning.skinWeights[5] + skinning.skinWeights[6] + skinning.skinWeights[7];
      expect(sum0).toBeCloseTo(1.0, 4);
      expect(sum1).toBeCloseTo(1.0, 4);
    });
  });

  describe('4. Master Garment Fitting Engine Execution', () => {
    it('should complete the entire multi-stage pipeline with BVH and diagnostics', () => {
      const bodyGeo = new THREE.CylinderGeometry(0.2, 0.2, 1.0, 16);
      const bPositions = bodyGeo.attributes.position.array as Float32Array;
      const bNormals = bodyGeo.attributes.normal.array as Float32Array;

      // Garment cylinder
      const gGeo = new THREE.CylinderGeometry(0.201, 0.201, 0.8, 16);
      const gPositions = gGeo.attributes.position.array as Float32Array;
      const gIndices = gGeo.index!.array as Uint32Array;

      const result = GarmentFittingEngine.fitGarmentToAvatar({
        garmentId: 'test_trousers',
        positions: gPositions,
        indices: gIndices,
        skinCoords: bPositions,
        skinNormals: bNormals,
        bodyGeometry: bodyGeo,
        fabricType: 'denim',
        baseColor: '#2563eb'
      });

      expect(result.garmentId).toBe('test_trousers');
      expect(result.geometry.triangleCount).toBeGreaterThan(0);
      expect(result.collision.resolvedPositions.length).toBe(gPositions.length);
      expect(result.material.name).toBe('Twill Denim');
      expect(result.material.roughness).toBeGreaterThan(0.6);
      expect(result.diagnostics.status).toBe('passed');
      expect(result.diagnostics.isSkinProtected).toBe(true);
    });
  });

  describe('5. True Dressing, Undressing & Lifecycle Persistence', () => {
    it('should maintain persistent base body integrity when dressing and undressing', () => {
      const stateManager = new OutfitStateManager();
      const resourceManager = new GarmentResourceManager();

      // Verify baseline state has persistent body
      expect(stateManager.hasActiveGarment('top')).toBe(false);
      expect(stateManager.hasActiveGarment('bottom')).toBe(false);

      // 1. Dress top
      stateManager.dress({
        id: 'blazer_01',
        name: 'Wool Blazer',
        category: 'top',
        layerOrder: 2,
        visibleBodyRegions: ['head', 'neck', 'hands', 'legs', 'feet']
      });

      expect(stateManager.hasActiveGarment('top')).toBe(true);
      expect(stateManager.getGarment('top')?.id).toBe('blazer_01');

      // 2. Dress bottom (both top and bottom should coexist cleanly)
      stateManager.dress({
        id: 'trousers_01',
        name: 'Pleated Trousers',
        category: 'bottom',
        layerOrder: 1,
        visibleBodyRegions: ['head', 'neck', 'torso', 'arms', 'hands', 'feet']
      });

      expect(stateManager.hasActiveGarment('top')).toBe(true);
      expect(stateManager.hasActiveGarment('bottom')).toBe(true);

      // 3. Replace top: previous top removed, bottom remains intact
      stateManager.replace('top', {
        id: 'sweater_02',
        name: 'Cashmere Sweater',
        category: 'top',
        layerOrder: 2
      });

      expect(stateManager.getGarment('top')?.id).toBe('sweater_02');
      expect(stateManager.getGarment('bottom')?.id).toBe('trousers_01');

      // 4. Undress all: returns to clean base body without deleting body mesh
      const undressedState = stateManager.undressAll();
      expect(undressedState.top).toBeNull();
      expect(undressedState.bottom).toBeNull();
      expect(undressedState.underwear).not.toBeNull();
      expect(undressedState.underwear?.category).toBe('underwear');

      // Verify base body integrity report confirms 100% water-tightness
      const bodyCoords = new Float32Array([
        0, 1.70, 0, // head
        0, 1.48, 0, // neck
        0, 1.25, 0, // torso
        0.35, 1.20, 0, // arms
        0.55, 0.85, 0, // hands
        0.12, 0.50, 0, // legs
        0.12, 0.05, 0  // feet
      ]);
      const integrity = BaseBodyController.validateBaseBodyIntegrity(bodyCoords);
      expect(integrity.isContinuous).toBe(true);
      expect(integrity.missingBands.length).toBe(0);

      // 5. Clean up GPU resources safely
      resourceManager.dispose();
      expect(resourceManager.getAllocatedCount()).toBe(0);
    });
  });
});
