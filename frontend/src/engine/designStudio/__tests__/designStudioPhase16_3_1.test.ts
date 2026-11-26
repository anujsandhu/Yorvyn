import { describe, it, expect } from 'vitest';
import * as THREE from 'three';
import {
  DesignStateEngine,
  createInitialDesignState,
} from '../DesignStateEngine';
import {
  applyPanelEaseToChest,
  halfChestToCircumferenceM,
  panelWidthToHalfChestM,
  validateMappingTopology,
} from '../SemanticCorrespondenceEngine';
import { RealtimeMeshEditor } from '../RealtimeMeshEditor';

describe('Phase 16.3.1 Semantic Correspondence, Dimensional Contract & Transactional Integrity', () => {
  it('computes explicit scoped measurements and avoids ambiguous half-panel scaling distortion', () => {
    expect(panelWidthToHalfChestM(0.216, 'PATTERN_PANEL_HALF', 2)).toBe(0.432);
    expect(halfChestToCircumferenceM(0.432)).toBe(0.864);

    const conv = applyPanelEaseToChest({
      panelWidthM: 0.216,
      panelScope: 'PATTERN_PANEL_HALF',
      easeDeltaM: 0.03,
      applySymmetrically: true,
    });
    expect(conv.panelWidth.valueCm).toBe(24.6);
    expect(conv.halfGarmentFlat.valueCm).toBe(49.2);
    expect(conv.finishedGarmentCircumference.valueCm).toBe(98.4);

    // Asymmetric single-panel +3cm ease adds +3cm to half-flat & circumference (not +6/+12)
    const asym = applyPanelEaseToChest({
      panelWidthM: 0.216,
      panelScope: 'PATTERN_PANEL_HALF',
      easeDeltaM: 0.03,
      applySymmetrically: false,
    });
    expect(asym.halfGarmentFlat.valueCm).toBe(46.2);
  });

  it('invalidates semantic correspondence when mesh topology changes and blocks stale edits', () => {
    const engine = new DesignStateEngine(createInitialDesignState({ garmentId: 'g_topo', category: 'jacket' }));
    const initCorr = engine.getState().correspondence!;
    expect(initCorr.valid).toBe(true);

    engine.hydrateConstructionPattern(
      engine.getState().patternPieces,
      engine.getState().patternSeams,
      ['main_torso', 'lapels_and_collar', 'left_sleeve', 'right_sleeve'],
      1200,
      2000
    );

    const topoCheck = validateMappingTopology(engine.getState().correspondence!, 1500, 2000);
    expect(topoCheck.valid).toBe(false);
    expect(topoCheck.status).toBe('MAPPING_INVALID');

    engine.invalidateCorrespondence('Topology vertex count mutated');
    expect(engine.getState().syncStatus).toBe('MAPPING_INVALID');
    expect(engine.applyGeometryEdit({ torsoWidthScale: 1.1 }).ok).toBe(false);

    // Rebuilding mapping restores safe synchronized state
    engine.rebuildCorrespondence(['main_torso', 'lapels_and_collar', 'left_sleeve', 'right_sleeve'], 1500, 2000);
    expect(engine.applyGeometryEdit({ torsoWidthScale: 1.1 }).ok).toBe(true);
  });

  it('hydrates Phase 16.2 half-panels and executes exact scoped panel ease + undo/redo', () => {
    const engine = new DesignStateEngine(createInitialDesignState({ garmentId: 'g_hyd', category: 'jacket' }));
    const halfPiece = {
      ...engine.getState().patternPieces.front_body,
      piece_id: 'front_left_body',
      boundary_polygon: [
        { x: 0, y: 0 },
        { x: 0.216, y: 0 },
        { x: 0.216, y: 0.45 },
        { x: 0.19, y: 0.65 },
        { x: 0, y: 0.65 },
      ],
    };
    engine.hydrateConstructionPattern(
      { front_left_body: halfPiece, back_body: engine.getState().patternPieces.back_body },
      engine.getState().patternSeams
    );
    expect(engine.getState().measurements.activePanelScope).toBe('PATTERN_PANEL_HALF');
    expect(engine.getState().measurements.chestWidthM).toBe(0.432);

    const res = engine.applyPanelEase('front_left_body', 0.03, true);
    expect(res.ok).toBe(true);
    expect(engine.getState().measurements.activePanelWidthM).toBe(0.246);
    expect(engine.getState().measurements.chestWidthM).toBe(0.492);
    expect(engine.getState().measurements.chestCircumferenceM).toBe(0.984);

    engine.undo();
    expect(engine.getState().measurements.chestWidthM).toBe(0.432);
    engine.redo();
    expect(engine.getState().measurements.chestWidthM).toBe(0.492);
  });

  it('applies localized Three.js deformations across trousers & jackets preserving topologyHash', () => {
    const group = new THREE.Group();
    const legMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.08, 0.8, 12, 4));
    legMesh.name = 'left_leg';
    legMesh.userData = { component_id: 'left_leg', semantic_type: 'leg' };
    const wbMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.18, 0.06, 12, 2));
    wbMesh.name = 'waistband_and_pelvis';
    wbMesh.userData = { component_id: 'waistband_and_pelvis', semantic_type: 'waistband' };
    wbMesh.position.y = 0.42;
    group.add(legMesh, wbMesh);

    const editor = new RealtimeMeshEditor();
    const baseState = createInitialDesignState({ garmentId: 'g_jeans', category: 'bottoms' });
    const m0 = editor.applyGeometryParameters(group, baseState.geometryParams);
    const m1 = editor.applyGeometryParameters(group, {
      ...baseState.geometryParams,
      legWidthScale: 1.25,
      waistbandWidthScale: 1.15,
    });
    expect(m1.widthCm).toBeGreaterThan(m0.widthCm);
    expect(m1.topologyHash).toBe(m0.topologyHash);
    editor.dispose();
  });
});
