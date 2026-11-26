/**
 * YORVYN — Garment Fitting, Reconstruction & Simulation Test Suite (Phase 4)
 * Verifies geometry repair, collision resolution, skin weight normalization, and layer management.
 */

import { describe, it, expect } from 'vitest';
import {
  GarmentGeometryValidator,
  GarmentCollisionResolver,
  GarmentSkinningAdapter,
  GarmentLayerManager,
  GarmentFittingEngine,
  GarmentMaterialSystem
} from '../index';

describe('GarmentGeometryValidator', () => {
  it('should detect and remove degenerate triangles and out-of-bound indices', () => {
    // 4 vertices forming a square: 2 valid triangles + 1 degenerate (duplicate indices)
    const positions = new Float32Array([
      0, 0, 0,
      1, 0, 0,
      1, 1, 0,
      0, 1, 0
    ]);
    const indices = new Uint32Array([
      0, 1, 2, // Valid triangle 1
      0, 2, 3, // Valid triangle 2
      1, 1, 2, // Degenerate (duplicate index)
      0, 1, 99 // Out-of-bound index
    ]);

    const res = GarmentGeometryValidator.validateAndRepair(positions, indices);
    expect(res.triangleCount).toBe(2);
    expect(res.degenerateTriangleCount).toBe(2);
    expect(res.repaired).toBe(true);
    expect(res.indices.length).toBe(6);
  });

  it('should clean up NaN and infinite vertex coordinates', () => {
    const positions = new Float32Array([
      0, NaN, 0,
      1, 0, Infinity,
      0, 1, 0
    ]);
    const indices = new Uint32Array([0, 1, 2]);

    const res = GarmentGeometryValidator.validateAndRepair(positions, indices);
    expect(res.nanVertexCount).toBe(2);
    expect(isNaN(res.positions[1])).toBe(false);
    expect(isFinite(res.positions[5])).toBe(true);
  });

  it('should generate valid normalized vertex normals', () => {
    const positions = new Float32Array([
      0, 0, 0,
      1, 0, 0,
      0, 1, 0
    ]);
    const indices = new Uint32Array([0, 1, 2]);

    const res = GarmentGeometryValidator.validateAndRepair(positions, indices);
    expect(res.normals.length).toBe(9);
    // Face normal for (1,0,0) x (0,1,0) should point along +Z [0, 0, 1]
    expect(res.normals[2]).toBeCloseTo(1.0, 3);
    expect(res.normals[5]).toBeCloseTo(1.0, 3);
    expect(res.normals[8]).toBeCloseTo(1.0, 3);
  });
});

describe('GarmentCollisionResolver', () => {
  it('should push penetrating garment vertices outside body surface along normals', () => {
    // Body skin vertex at origin with outward normal +Z
    const bodyCoords = new Float32Array([0, 1.0, 0]);
    const bodyNormals = new Float32Array([0, 0, 1]);

    // Garment vertex placed inside/behind the skin at Z = -0.005 (5mm penetration)
    const garmentPositions = new Float32Array([0, 1.0, -0.005]);

    const res = GarmentCollisionResolver.resolveBodyCollisions(
      garmentPositions,
      bodyCoords,
      bodyNormals,
      { minClearanceMeters: 0.003 }
    );

    expect(res.penetrationCount).toBe(1);
    expect(res.maxPenetrationMeters).toBeCloseTo(0.008, 4);
    // After resolution, Z position should be at body Z (0) + minClearance (0.003) = 0.003
    expect(res.resolvedPositions[2]).toBeCloseTo(0.003, 3);
  });

  it('should preserve vertices that already have sufficient clearance', () => {
    const bodyCoords = new Float32Array([0, 1.0, 0]);
    const bodyNormals = new Float32Array([0, 0, 1]);
    const garmentPositions = new Float32Array([0, 1.0, 0.010]); // 10mm clearance

    const res = GarmentCollisionResolver.resolveBodyCollisions(
      garmentPositions,
      bodyCoords,
      bodyNormals,
      { minClearanceMeters: 0.003 }
    );

    expect(res.penetrationCount).toBe(0);
    expect(res.resolvedPositions[2]).toBeCloseTo(0.010, 4);
  });
});

describe('GarmentSkinningAdapter', () => {
  it('should strictly normalize bone weights to sum to 1.0', () => {
    const indices = new Uint16Array([0, 1, 2, 3]);
    const rawWeights = new Float32Array([0.4, 0.3, 0.1, 0.0]); // Sums to 0.8

    const res = GarmentSkinningAdapter.normalizeAndValidateWeights(indices, rawWeights, 10, 4);
    expect(res.normalizedCount).toBe(1);

    const sum = res.skinWeights[0] + res.skinWeights[1] + res.skinWeights[2] + res.skinWeights[3];
    expect(sum).toBeCloseTo(1.0, 5);
  });

  it('should clamp out-of-bound bone indices and prune trivial weights', () => {
    const indices = new Uint16Array([0, 999, 2, 3]); // Index 999 >= numBones (10)
    const rawWeights = new Float32Array([0.8, 0.2, 0.002, 0.0]); // 0.002 is trivial

    const res = GarmentSkinningAdapter.normalizeAndValidateWeights(indices, rawWeights, 10, 4);
    expect(res.prunedCount).toBe(1);
    expect(res.skinIndices[1]).toBe(0);
    expect(res.skinWeights[0]).toBeCloseTo(1.0, 5);
  });
});

describe('GarmentLayerManager', () => {
  it('should replace separate top and bottom when a full outfit is equipped', () => {
    let state = GarmentLayerManager.undressToMannequin(true);
    expect(state.underwear?.id).toBe('briefs');
    expect(state.underwear?.hidesSkin).toBe(false);

    // Equip top and bottom
    state = GarmentLayerManager.applyGarment(state, {
      id: 'tee',
      name: 'Crewneck Tee',
      layerType: 'top',
      layerIndex: 2,
      hidesSkin: false
    });
    state = GarmentLayerManager.applyGarment(state, {
      id: 'jeans',
      name: 'Denim Jeans',
      layerType: 'bottom',
      layerIndex: 1,
      hidesSkin: false
    });

    expect(state.top?.id).toBe('tee');
    expect(state.bottom?.id).toBe('jeans');

    // Equip full outfit
    state = GarmentLayerManager.applyGarment(state, {
      id: 'suit',
      name: 'Tailored Suit',
      layerType: 'outfit',
      layerIndex: 3,
      hidesSkin: true
    });

    expect(state.outfit?.id).toBe('suit');
    expect(state.top).toBeUndefined();
    expect(state.bottom).toBeUndefined();
  });

  it('should clear full outfit when equipping a separate bottom layer', () => {
    let state = GarmentLayerManager.applyGarment({ accessories: [] }, {
      id: 'suit',
      name: 'Tailored Suit',
      layerType: 'outfit',
      layerIndex: 3,
      hidesSkin: true
    });
    expect(state.outfit?.id).toBe('suit');

    state = GarmentLayerManager.applyGarment(state, {
      id: 'trousers',
      name: 'Pleated Trousers',
      layerType: 'bottom',
      layerIndex: 1,
      hidesSkin: false
    });

    expect(state.outfit).toBeUndefined();
    expect(state.bottom?.id).toBe('trousers');
  });

  it('should ensure underwear never hides skin', () => {
    const isHidden = GarmentLayerManager.shouldHideSkin({
      id: 'briefs',
      name: 'Briefs',
      layerType: 'underwear',
      layerIndex: 0,
      hidesSkin: true // requested true, but rule enforces false
    });
    expect(isHidden).toBe(false);
  });
});

describe('GarmentMaterialSystem', () => {
  it('should configure PBR fabric profiles with double-sided rendering', () => {
    const denim = GarmentMaterialSystem.getFabricProfile('denim', '#1e3a8a');
    expect(denim.doubleSided).toBe(true);
    expect(denim.roughness).toBe(0.65);
    expect(denim.metalness).toBe(0.02);
    expect(denim.color).toBe('#1e3a8a');

    const leather = GarmentMaterialSystem.getFabricProfile('leather', '#000000');
    expect(leather.clearcoat).toBeGreaterThan(0.3);
  });
});

describe('GarmentFittingEngine (End-to-End Pipeline)', () => {
  it('should successfully run the complete virtual try-on fitting pipeline', () => {
    const positions = new Float32Array([
      0, 1.0, 0.001, // Penetrating slightly
      0.1, 1.0, 0.005,
      0, 1.1, 0.005
    ]);
    const indices = new Uint32Array([0, 1, 2]);

    const skinCoords = new Float32Array([0, 1.0, 0]);
    const skinNormals = new Float32Array([0, 0, 1]);

    const result = GarmentFittingEngine.fitGarmentToAvatar({
      garmentId: 'sig-polo',
      positions,
      indices,
      skinCoords,
      skinNormals,
      fabricType: 'cotton',
      baseColor: '#ffffff'
    });

    expect(result.geometry.valid).toBe(true);
    expect(result.collision.resolvedPositions[2]).toBeCloseTo(0.0028, 4);
    expect(result.material.name).toBe('Cotton Jersey');
    expect(result.diagnostics.status).toBe('passed');
  });
});
