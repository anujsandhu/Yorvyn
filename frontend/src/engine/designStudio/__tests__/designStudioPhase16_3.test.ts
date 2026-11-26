import { describe, it, expect } from 'vitest';
import * as THREE from 'three';
import {
  DesignStateEngine,
  createInitialDesignState,
  validatePatternPolygon2D,
} from '../DesignStateEngine';
import { RealtimeMeshEditor } from '../RealtimeMeshEditor';
import { detectGraphicsCapabilities } from '../GraphicsCapabilityService';

describe('Phase 16.3 Real-Time Garment Design Engine', () => {
  it('validates geometry bounds, propagates 3D edits to 2D patterns, and supports undo/redo', () => {
    const engine = new DesignStateEngine(createInitialDesignState({ garmentId: 'g_1', category: 'jacket' }));
    const initLen = engine.getState().measurements.garmentLengthM;
    const initFrontArea = engine.getState().patternPieces.front_body.area_m2;

    expect(engine.applyGeometryEdit({ torsoLengthScale: 3.0 }).ok).toBe(false);

    const res = engine.applyGeometryEdit({ torsoLengthScale: 0.85, torsoWidthScale: 1.1 });
    expect(res.ok).toBe(true);
    expect(engine.getState().measurements.garmentLengthM).toBeLessThan(initLen);
    expect(engine.getState().patternPieces.front_body.area_m2).not.toBe(initFrontArea);
    expect(engine.canUndo()).toBe(true);

    // Undo restores exact measurements & pattern pieces
    expect(engine.undo()).toBe(true);
    expect(engine.getState().measurements.garmentLengthM).toBe(initLen);
    expect(engine.canRedo()).toBe(true);

    // Redo reapplies delta
    expect(engine.redo()).toBe(true);
    expect(engine.getState().measurements.garmentLengthM).toBeLessThan(initLen);
  });

  it('rejects self-intersecting 2D pattern polygons and syncs valid 2D edits back to 3D measurements', () => {
    const engine = new DesignStateEngine(createInitialDesignState({ garmentId: 'g_2', category: 'tops' }));
    const bowtieErrors = validatePatternPolygon2D([
      { x: 0, y: 0 },
      { x: 0.5, y: 0.5 },
      { x: 0.5, y: 0 },
      { x: 0, y: 0.5 },
    ]);
    expect(bowtieErrors.some((e) => e.toLowerCase().includes('self-intersection'))).toBe(true);

    const invalidRes = engine.applyPatternVertexEdit('front_body', 2, { x: -0.2, y: -0.2 });
    expect(invalidRes.ok).toBe(false);
    expect(engine.getState().patternValidationErrors.length).toBeGreaterThan(0);

    const beforeChest = engine.getState().measurements.chestWidthM;
    const pt = engine.getState().patternPieces.front_body.boundary_polygon[2];
    const okRes = engine.applyPatternVertexEdit('front_body', 2, { x: pt.x + 0.08, y: pt.y });
    expect(okRes.ok).toBe(true);
    expect(engine.getState().measurements.chestWidthM).toBeGreaterThan(beforeChest);
  });

  it('rejects stale design versions without silent overwrite and distinguishes visual presets', () => {
    const engine = new DesignStateEngine(createInitialDesignState({ garmentId: 'g_3', category: 'shirt' }));
    expect(engine.applyGeometryEdit({ torsoWidthScale: 1.05 }).ok).toBe(true);
    // Stale expectedVersion=1 when current is 2 must fail
    const conflict = engine.applyGeometryEdit({ torsoWidthScale: 1.15 }, 'studio', 1);
    expect(conflict.ok).toBe(false);
    expect(engine.getState().syncStatus).toBe('CONSTRUCTION_CONFLICT');

    engine.applyMaterialEdit({ preset: 'leather', baseColor: '#1f1714' });
    expect(engine.getState().material.preset).toBe('leather');
    expect(engine.getState().material.isPhysicallyVerified).toBe(false);
  });

  it('mutates Three.js BufferGeometry in place, calculates live metrics, and disposes resources', () => {
    const group = new THREE.Group();
    const torsoMesh = new THREE.Mesh(
      new THREE.BoxGeometry(0.5, 0.7, 0.2, 4, 4, 4),
      new THREE.MeshStandardMaterial({ color: '#ffffff' })
    );
    torsoMesh.name = 'torso';
    torsoMesh.userData = { component_id: 'torso', semantic_type: 'torso' };
    const sleeveMesh = new THREE.Mesh(
      new THREE.CylinderGeometry(0.08, 0.06, 0.5, 8, 2),
      new THREE.MeshStandardMaterial({ color: '#ffffff' })
    );
    sleeveMesh.name = 'left_sleeve';
    sleeveMesh.userData = { component_id: 'left_sleeve', semantic_type: 'sleeve' };
    sleeveMesh.position.set(-0.35, 0.1, 0);
    group.add(torsoMesh, sleeveMesh);

    const editor = new RealtimeMeshEditor();
    const state = createInitialDesignState({ garmentId: 'g_mesh', category: 'jacket' });
    const baseMetrics = editor.applyGeometryParameters(group, state.geometryParams);

    const deformedMetrics = editor.applyGeometryParameters(group, {
      ...state.geometryParams,
      torsoWidthScale: 1.25,
      sleeveWidthScale: 1.30,
    });
    expect(deformedMetrics.widthCm).toBeGreaterThan(baseMetrics.widthCm);
    expect(deformedMetrics.triangleCount).toBe(baseMetrics.triangleCount);

    editor.applyMaterialAndInspectionModes(
      group,
      { ...state.material, stitchVisible: true },
      { ...state.viewModes, wireframe: true, showSeams: true, showMeasurements: true },
      'torso',
      null
    );
    expect((torsoMesh.material as THREE.MeshStandardMaterial).wireframe).toBe(true);
    editor.dispose();
  });

  it('probes WebGL2/WebGPU capabilities safely in headless environment without crashing', async () => {
    const caps = await detectGraphicsCapabilities({ probeWebGPUAdapter: false });
    expect(caps.threeWebgpuModuleBundled).toBe(true);
    expect(['webgl2', 'software_fallback']).toContain(caps.preferredBackend);
  });
});
