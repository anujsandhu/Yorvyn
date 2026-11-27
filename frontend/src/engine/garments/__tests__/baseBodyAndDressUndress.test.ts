/**
 * YORVYN — Phase 5 Test Suite: Base Avatar Body, True Dress/Undress System & Garment Replacement
 * Verifies persistent base body integrity, clothing state transitions, atomic replacements,
 * and clean GPU resource management.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import * as THREE from 'three';
import {
  BaseBodyController,
  OutfitStateManager,
  GarmentResourceManager,
  GarmentVisibilityManager,
  GarmentCompatibilityValidator,
  PersistentOutfitState
} from '../index';
import { LiveMannequinEngine } from '../../mannequin/LiveMannequinEngine';
import { DEFAULT_PARAMS } from '../../ara/core/params';

describe('BaseBodyController', () => {
  it('should verify complete anatomical integrity across all body regions', () => {
    // Construct synthetic continuous human body positions spanning 0 to 1.78m
    const verts: number[] = [];
    const tris: number[] = [];

    // Head (1.50 - 1.78m)
    for (let i = 0; i < 60; i++) verts.push(0, 1.65, 0);
    // Neck (1.38 - 1.50m)
    for (let i = 0; i < 30; i++) verts.push(0, 1.44, 0);
    // Torso (0.85 - 1.38m, x within 0.22m)
    for (let i = 0; i < 150; i++) verts.push(0.05, 1.10, 0);
    // Arms & Hands (0.85 - 1.38m, x > 0.22m)
    for (let i = 0; i < 80; i++) verts.push(0.35, 1.10, 0);
    // Legs (0.12 - 0.85m)
    for (let i = 0; i < 150; i++) verts.push(0.10, 0.50, 0);
    // Feet (< 0.12m)
    for (let i = 0; i < 30; i++) verts.push(0.10, 0.05, 0);

    for (let i = 0; i < (verts.length / 3) - 2; i++) {
      tris.push(i, i + 1, i + 2);
    }

    const pos = new Float32Array(verts);
    const idx = new Uint32Array(tris);

    const report = BaseBodyController.verifyIntegrity(pos, idx);
    expect(report.isComplete).toBe(true);
    expect(report.hasHead).toBe(true);
    expect(report.hasNeck).toBe(true);
    expect(report.hasTorso).toBe(true);
    expect(report.hasArms).toBe(true);
    expect(report.hasHands).toBe(true);
    expect(report.hasLegs).toBe(true);
    expect(report.hasFeet).toBe(true);
    expect(report.minY).toBeLessThan(0.10);
    expect(report.maxY).toBeGreaterThan(1.60);
  });

  it('should generate valid neutral modesty underwear specifications', () => {
    const spec = BaseBodyController.getModestyUnderwearSpec(0.9);
    expect(spec.id).toBe('briefs');
    expect(spec.hidesSkin).toBe(false);
    expect(spec.offsetMeters).toBeGreaterThan(0.003);
    expect(spec.waistbandOffsetMeters).toBeGreaterThan(spec.offsetMeters);
  });
});

describe('OutfitStateManager', () => {
  let manager: OutfitStateManager;

  beforeEach(() => {
    manager = new OutfitStateManager({ userId: 'usr_test_123' });
  });

  it('should initialize with neutral modesty underwear and clean base body state', () => {
    const state = manager.getState();
    expect(state.underwear?.id).toBe('briefs');
    expect(state.underwear?.hidesSkin).toBe(false);
    expect(state.top).toBeNull();
    expect(state.bottom).toBeNull();
    expect(state.outfit).toBeNull();
  });

  it('should dress a top and preserve existing compatible garments', () => {
    // Equip bottom
    manager.dress({
      id: 'jeans_01',
      name: 'Denim Jeans',
      category: 'bottom'
    });
    // Equip top
    const state = manager.dress({
      id: 'tee_01',
      name: 'Classic White Tee',
      category: 'top'
    });

    expect(state.top?.id).toBe('tee_01');
    expect(state.bottom?.id).toBe('jeans_01');
    expect(state.outfit).toBeNull();
  });

  it('should clear separate top and bottom when a full outfit is equipped', () => {
    manager.dress({ id: 'tee', name: 'Tee', category: 'top' });
    manager.dress({ id: 'jeans', name: 'Jeans', category: 'bottom' });

    const state = manager.dress({
      id: 'suit_01',
      name: 'Tailored Tuxedo Suit',
      category: 'outfit'
    });

    expect(state.outfit?.id).toBe('suit_01');
    expect(state.top).toBeNull();
    expect(state.bottom).toBeNull();
  });

  it('should undress a single garment without affecting other categories', () => {
    manager.dress({ id: 'tee', name: 'Tee', category: 'top' });
    manager.dress({ id: 'jeans', name: 'Jeans', category: 'bottom' });
    manager.dress({ id: 'sneakers', name: 'Sneakers', category: 'shoes' });

    // Undress top only
    const state = manager.undress('top');
    expect(state.top).toBeNull();
    expect(state.bottom?.id).toBe('jeans');
    expect(state.shoes?.id).toBe('sneakers');
  });

  it('should perform undressAll cleanly back to bare modesty base', () => {
    manager.dress({ id: 'suit', name: 'Suit', category: 'outfit' });
    manager.dress({ id: 'boots', name: 'Boots', category: 'shoes' });

    const state = manager.undressAll(true);
    expect(state.outfit).toBeNull();
    expect(state.top).toBeNull();
    expect(state.bottom).toBeNull();
    expect(state.shoes).toBeNull();
    expect(state.underwear?.id).toBe('briefs');
    expect(state.underwear?.hidesSkin).toBe(false);
  });

  it('should atomically replace garments in the same slot', () => {
    manager.dress({ id: 'tee_v1', name: 'Tee V1', category: 'top' });
    const state = manager.replace({ id: 'tee_v2', name: 'Tee V2', category: 'top' });
    expect(state.top?.id).toBe('tee_v2');
  });

  it('should rollback to previous valid state if an operation fails', () => {
    manager.dress({ id: 'valid_look', name: 'Valid Look', category: 'top' });
    manager.dress({ id: 'faulty_look', name: 'Faulty Look', category: 'top' });

    const rolledBack = manager.rollback();
    expect(rolledBack?.top?.id).toBe('valid_look');
  });

  it('should restore a saved persistent outfit state accurately', () => {
    const saved: PersistentOutfitState = {
      version: 1,
      userId: 'usr_saved',
      underwear: { id: 'briefs', name: 'Briefs', category: 'underwear' },
      bottom: { id: 'chinos', name: 'Chino Trousers', category: 'bottom' },
      top: { id: 'polo', name: 'Signature Polo', category: 'top' },
      outfit: null,
      outerwear: null,
      shoes: { id: 'loafers', name: 'Leather Loafers', category: 'shoes' },
      accessories: [],
      updatedAt: '2026-10-29T20:00:00.000Z'
    };

    const restored = manager.restore(saved);
    expect(restored.top?.id).toBe('polo');
    expect(restored.bottom?.id).toBe('chinos');
    expect(restored.shoes?.id).toBe('loafers');
  });
});

describe('GarmentResourceManager', () => {
  let resManager: GarmentResourceManager;
  let scene: THREE.Scene;

  beforeEach(() => {
    resManager = new GarmentResourceManager();
    scene = new THREE.Scene();
  });

  it('should register a garment and track its geometries and materials', () => {
    const geo = new THREE.BoxGeometry(0.5, 0.5, 0.5);
    const mat = new THREE.MeshStandardMaterial({ color: 0xff0000 });
    const mesh = new THREE.Mesh(geo, mat);
    scene.add(mesh);

    const binding = resManager.register('garment_tee', 'top', mesh);
    expect(binding.garmentId).toBe('garment_tee');
    expect(binding.geometries.length).toBe(1);
    expect(binding.materials.length).toBe(1);
    expect(resManager.hasActiveCategory('top')).toBe(true);
  });

  it('should dispose resources cleanly and remove object from scene upon category replacement', () => {
    const geo1 = new THREE.BoxGeometry(0.5, 0.5, 0.5);
    const mat1 = new THREE.MeshStandardMaterial({ color: 0xff0000 });
    const mesh1 = new THREE.Mesh(geo1, mat1);
    scene.add(mesh1);
    resManager.register('tee_v1', 'top', mesh1);

    // Register tee_v2 in same category (should auto-dispose tee_v1)
    const geo2 = new THREE.SphereGeometry(0.3);
    const mat2 = new THREE.MeshStandardMaterial({ color: 0x00ff00 });
    const mesh2 = new THREE.Mesh(geo2, mat2);
    scene.add(mesh2);
    resManager.register('tee_v2', 'top', mesh2);

    expect(mesh1.parent).toBeNull(); // Unlinked from scene
    expect(resManager.getBinding('top')?.garmentId).toBe('tee_v2');
  });

  it('should dispose all resources when requested', () => {
    const mesh1 = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshStandardMaterial());
    const mesh2 = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshStandardMaterial());
    scene.add(mesh1);
    scene.add(mesh2);

    resManager.register('t1', 'top', mesh1);
    resManager.register('b1', 'bottom', mesh2);

    resManager.disposeAll();
    expect(resManager.hasActiveCategory('top')).toBe(false);
    expect(resManager.hasActiveCategory('bottom')).toBe(false);
  });
});

describe('GarmentCompatibilityValidator', () => {
  it('should accept garments with valid scale and Y-up orientation', () => {
    const positions = new Float32Array([
      -0.2, 0.9, 0,
       0.2, 0.9, 0,
       0.0, 1.4, 0
    ]);
    const res = GarmentCompatibilityValidator.validateCompatibility(positions, 1.78);
    expect(res.isCompatible).toBe(true);
    expect(res.isYUp).toBe(true);
    expect(res.scaleFactor).toBe(1.0);
  });

  it('should auto-detect millimeter scale and provide correction factor', () => {
    // 500mm high garment
    const positions = new Float32Array([
      0, 0, 0,
      100, 500, 0,
      0, 500, 100
    ]);
    const res = GarmentCompatibilityValidator.validateCompatibility(positions, 1.78);
    expect(res.scaleFactor).toBe(0.001); // 1/1000 correction
  });
});

describe('GarmentVisibilityManager', () => {
  it('should keep avatar skin, eyes, and hair visible under all circumstances', () => {
    const model = new THREE.Group();

    const skinMesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshStandardMaterial({ name: 'Skin' }));
    const hairMesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshStandardMaterial({ name: 'Hair' }));
    const topMesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshStandardMaterial({ name: 'Top' }));
    model.add(skinMesh, hairMesh, topMesh);

    const outfitState: PersistentOutfitState = {
      version: 1,
      underwear: null,
      top: null, // Top is undressed
      bottom: null,
      outfit: null,
      outerwear: null,
      shoes: null,
      accessories: [],
      updatedAt: ''
    };

    GarmentVisibilityManager.syncMeshVisibility(model, outfitState);

    expect(skinMesh.visible).toBe(true);
    expect(hairMesh.visible).toBe(true);
    expect(topMesh.visible).toBe(false); // Top hidden because outfitState.top is null
  });

  it('should show top mesh when top is equipped in outfit state', () => {
    const model = new THREE.Group();
    const topMesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshStandardMaterial({ name: 'Top' }));
    model.add(topMesh);

    const outfitState: PersistentOutfitState = {
      version: 1,
      underwear: null,
      top: { id: 'tee', name: 'Tee', category: 'top' },
      bottom: null,
      outfit: null,
      outerwear: null,
      shoes: null,
      accessories: [],
      updatedAt: ''
    };

    GarmentVisibilityManager.syncMeshVisibility(model, outfitState);
    expect(topMesh.visible).toBe(true);
  });

  it('should show full outfit mesh and shoes when equipped in HumanParams', () => {
    const model = new THREE.Group();
    const skinMesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshStandardMaterial({ name: 'Skin' }));
    const outfitMesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshStandardMaterial({ name: 'Outfit' }));
    const shoesMesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshStandardMaterial({ name: 'Shoes' }));
    model.add(skinMesh, outfitMesh, shoesMesh);

    const engine = new LiveMannequinEngine();
    engine.init(model, [], {
      ...DEFAULT_PARAMS,
      outfit: 'male_elegantsuit01',
      shoes: 'shoes01',
      top: 'none',
      bottom: 'none'
    });

    expect(skinMesh.visible).toBe(true);
    expect(outfitMesh.visible).toBe(true);
    expect(shoesMesh.visible).toBe(true);
  });

  it('should show separates (top, bottom, shoes) when equipped in HumanParams', () => {
    const model = new THREE.Group();
    const topMesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshStandardMaterial({ name: 'Uniform shirt' }));
    const bottomMesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshStandardMaterial({ name: 'Trousers' }));
    const shoesMesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshStandardMaterial({ name: 'Shoes' }));
    const outfitMesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshStandardMaterial({ name: 'Outfit' }));
    model.add(topMesh, bottomMesh, shoesMesh, outfitMesh);

    const engine = new LiveMannequinEngine();
    engine.init(model, [], {
      ...DEFAULT_PARAMS,
      outfit: 'none',
      top: 'uniform_shirt',
      bottom: 'trousers',
      shoes: 'shoes01'
    });

    expect(topMesh.visible).toBe(true);
    expect(bottomMesh.visible).toBe(true);
    expect(shoesMesh.visible).toBe(true);
    expect(outfitMesh.visible).toBe(false);
  });

  it('should correctly hide garments and reveal modesty briefs when undressed to bare mannequin', () => {
    const model = new THREE.Group();
    const skinMesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshStandardMaterial({ name: 'Skin' }));
    const briefsMesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshStandardMaterial({ name: 'Briefs' }));
    const topMesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshStandardMaterial({ name: 'Top' }));
    const outfitMesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshStandardMaterial({ name: 'Outfit' }));
    model.add(skinMesh, briefsMesh, topMesh, outfitMesh);

    const engine = new LiveMannequinEngine();
    engine.init(model, [], {
      ...DEFAULT_PARAMS,
      outfit: 'none',
      top: 'none',
      bottom: 'none',
      underwear: true
    });

    expect(skinMesh.visible).toBe(true);
    expect(briefsMesh.visible).toBe(true);
    expect(topMesh.visible).toBe(false);
    expect(outfitMesh.visible).toBe(false);
  });
});

