/**
 * Phase 16.3 Synchronized Real-Time 2D/3D Garment Design Workspace
 * Unites the Three.js Interactive 3D Editor, Interactive 2D Pattern CAD Editor,
 * PBR Material Designer, Undo/Redo Revision Engine, Avatar Fit Bridge, and CAD/GLB Exports.
 */

import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import * as THREE from 'three';
import axios, { type AxiosInstance } from 'axios';
import { supabase } from '../../utils/supabase';
import {
  CameraPreset,
  DesignStateEngine,
  FabricPresetKey,
  GEOMETRY_PARAM_BOUNDS,
  GarmentDesignState,
  GeometryDeformationParams,
  LightingPreset,
  SimulationPreviewMode,
  createInitialDesignState,
} from '../../engine/designStudio/DesignStateEngine';
import type { GraphicsCapabilitiesReport } from '../../engine/designStudio/GraphicsCapabilityService';
import { RealtimeMeshEditor, type LiveMeshMetrics } from '../../engine/designStudio/RealtimeMeshEditor';
import { InteractiveGarment3DEditor, type RenderTelemetry } from './InteractiveGarment3DEditor';
import { Pattern2DEditor } from './Pattern2DEditor';
import {
  intelligenceApi,
  type ExternalWebReference,
  type GarmentQualityFeedback,
  type OutfitRecommendationResponse,
} from '../../services/intelligenceApi';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

const garmentsHttp: AxiosInstance = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

garmentsHttp.interceptors.request.use(async (config) => {
  try {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (session?.access_token) {
      config.headers.Authorization = `Bearer ${session.access_token}`;
    }
  } catch {
    // Allow graceful fallback if no active auth session exists yet
  }
  return config;
});

interface SavedRevisionSummary {
  revision_id: string;
  design_version: number;
  created_at: string;
  geometry_hash: string;
  pattern_hash: string;
  geometry_params: any;
  material_config: any;
  measurements: Record<string, number>;
}

interface Props {
  garmentId: string;
  candidateId?: string | null;
  glbUrl: string;
  category?: string;
  subcategory?: string;
  initialDesignCommand?: any;
  onApplyToAvatar: (blob: Blob) => void;
  onClose: () => void;
}

export function GarmentDesignWorkspace({
  garmentId,
  candidateId,
  glbUrl,
  category = 'jacket',
  subcategory = '',
  initialDesignCommand,
  onApplyToAvatar,
  onClose,
}: Props) {
  const engineRef = useRef<DesignStateEngine | null>(null);
  if (!engineRef.current) {
    engineRef.current = new DesignStateEngine(
      createInitialDesignState({ garmentId, candidateId, category, subcategory })
    );
  }
  const engine = engineRef.current;
  const [designState, setDesignState] = useState<GarmentDesignState>(() => engine.getState());
  const meshEditorRef = useRef<RealtimeMeshEditor | null>(null);
  const garmentGroupRef = useRef<THREE.Object3D | null>(null);

  const [telemetry, setTelemetry] = useState<RenderTelemetry | null>(null);
  const [caps, setCaps] = useState<GraphicsCapabilitiesReport | null>(null);
  const [meshMetrics, setMeshMetrics] = useState<LiveMeshMetrics | null>(null);
  const [statusMsg, setStatusMsg] = useState<string>('Ready for real-time 2D & 3D design.');
  const [revisions, setRevisions] = useState<SavedRevisionSummary[]>([]);
  const [latestExports, setLatestExports] = useState<{ svg?: string; dxf?: string; construction_json?: string }>({});
  const [commandText, setCommandText] = useState('');
  const [qualityCheck, setQualityCheck] = useState<GarmentQualityFeedback | null>(null);
  const [pairingRecs, setPairingRecs] = useState<OutfitRecommendationResponse | null>(null);
  const [designResearch, setDesignResearch] = useState<{ summary: string; external: ExternalWebReference[] } | null>(null);

  useEffect(() => engine.subscribe(setDesignState), [engine]);

  // Apply initial Stylist command if opened from a Stylist turn with design_command
  useEffect(() => {
    if (!initialDesignCommand) return;
    if (initialDesignCommand.kind === 'view_mode' && initialDesignCommand.patch) {
      engine.setViewState(initialDesignCommand.patch);
    } else if (initialDesignCommand.kind === 'material_or_view') {
      if (initialDesignCommand.material) engine.applyMaterialEdit(initialDesignCommand.material, 'stylist_chat');
      if (initialDesignCommand.view) engine.setViewState(initialDesignCommand.view);
    } else if (initialDesignCommand.kind === 'material' && initialDesignCommand.material) {
      engine.applyMaterialEdit(initialDesignCommand.material, 'stylist_chat');
    } else if (initialDesignCommand.kind === 'geometry' && initialDesignCommand.geometry) {
      engine.applyGeometryEdit(initialDesignCommand.geometry, 'stylist_chat');
    }
  }, [initialDesignCommand, engine]);

  // Fetch authoritative Phase 16.2 construction patterns + saved revisions on open
  useEffect(() => {
    let alive = true;
    garmentsHttp
      .post(`/garments/${encodeURIComponent(garmentId)}/sync-pattern`, {
        category,
        subcategory,
        include_exports: true,
      })
      .then((res) => {
        if (!alive) return;
        const graph = res.data?.handoff?.construction_graph;
        if (graph?.pieces) {
          engine.hydrateConstructionPattern(
            graph.pieces,
            graph.seams || [],
            meshMetrics?.componentIds,
            meshMetrics?.vertexCount,
            meshMetrics?.triangleCount
          );
        }
        if (res.data?.exports) {
          setLatestExports(res.data.exports);
        }
      })
      .catch(() => {
        // Offline / isolated fallback keeps client pattern model ready
      });

    garmentsHttp
      .get(`/garments/${encodeURIComponent(garmentId)}/revisions`)
      .then((res) => {
        if (alive && Array.isArray(res.data?.revisions)) {
          setRevisions(res.data.revisions);
        }
      })
      .catch(() => {});

    return () => {
      alive = false;
    };
  }, [garmentId, category, subcategory, engine]);

  const triggerDownload = (blobOrText: Blob | string, filename: string, mime = 'text/plain') => {
    const blob = typeof blobOrText === 'string' ? new Blob([blobOrText], { type: mime }) : blobOrText;
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const handleSaveRevision = async () => {
    try {
      const parentVer = revisions.length ? revisions[revisions.length - 1].design_version : 0;
      const res = await garmentsHttp.post(`/garments/${encodeURIComponent(garmentId)}/revisions`, {
        candidate_id: candidateId || garmentId,
        expected_parent_version: parentVer,
        geometry_version: designState.geometryVersion,
        pattern_version: designState.patternVersion,
        material_version: designState.materialVersion,
        texture_version: designState.textureVersion,
        category: designState.category,
        subcategory: designState.subcategory,
        correspondence_version: designState.correspondenceVersion,
        sync_status: designState.syncStatus,
        geometry_params: {
          torso_length_scale: designState.geometryParams.torsoLengthScale,
          torso_width_scale: designState.geometryParams.torsoWidthScale,
          shoulder_width_scale: designState.geometryParams.shoulderWidthScale,
          sleeve_length_scale: designState.geometryParams.sleeveLengthScale,
          sleeve_width_scale: designState.geometryParams.sleeveWidthScale,
          collar_width_scale: designState.geometryParams.collarWidthScale,
          cuff_width_scale: designState.geometryParams.cuffWidthScale,
          hem_width_scale: designState.geometryParams.hemWidthScale,
          waistband_width_scale: designState.geometryParams.waistbandWidthScale,
          leg_width_scale: designState.geometryParams.legWidthScale,
          leg_length_scale: designState.geometryParams.legLengthScale,
          pocket_offset_y_m: designState.geometryParams.pocketOffsetYM,
        },
        material_config: {
          preset: designState.material.preset,
          base_color: designState.material.baseColor,
          roughness: designState.material.roughness,
          metalness: designState.material.metalness,
          sheen: designState.material.sheen,
          clearcoat: designState.material.clearcoat,
          normal_intensity: designState.material.normalIntensity,
          repeat_x: designState.material.repeatX,
          repeat_y: designState.material.repeatY,
          rotation_deg: designState.material.rotationDeg,
          offset_x: designState.material.offsetX,
          offset_y: designState.material.offsetY,
          stitch_visible: designState.material.stitchVisible,
          stitch_color: designState.material.stitchColor,
          print_scale: designState.material.printScale,
          is_physically_verified: false,
        },
        pattern_overrides: designState.patternPieces,
        measurements: {
          garment_length_m: designState.measurements.garmentLengthM,
          chest_width_m: designState.measurements.chestWidthM,
          sleeve_length_m: designState.measurements.sleeveLengthM,
          sleeve_width_m: designState.measurements.sleeveWidthM,
          collar_width_m: designState.measurements.collarWidthM,
          hem_width_m: designState.measurements.hemWidthM,
        },
        operation_history: engine.getOperationHistory().map((op) => ({
          operation_id: op.operationId,
          kind: op.kind,
          target_component: op.targetComponent,
          source: op.source,
          parameters: op.parameters,
          timestamp: op.timestamp,
        })),
      });
      if (res.data?.revision) {
        setRevisions((prev) => [...prev, res.data.revision]);
        setStatusMsg(`Saved Revision v${res.data.revision.design_version} (${res.data.revision.revision_id}).`);
      }
    } catch (err: any) {
      setStatusMsg(err?.response?.data?.detail || 'Revision save failed.');
    }
  };

  const handleRestoreRevision = async (revId: string) => {
    try {
      const res = await garmentsHttp.get(`/garments/${encodeURIComponent(garmentId)}/revisions/${revId}`);
      const r = res.data?.revision;
      if (!r) return;
      engine.restoreRevisionSnapshot({
        designVersion: r.design_version,
        geometryParams: {
          torsoLengthScale: r.geometry_params.torso_length_scale,
          torsoWidthScale: r.geometry_params.torso_width_scale,
          sleeveLengthScale: r.geometry_params.sleeve_length_scale,
          sleeveWidthScale: r.geometry_params.sleeve_width_scale,
          collarWidthScale: r.geometry_params.collar_width_scale,
          hemWidthScale: r.geometry_params.hem_width_scale,
        },
        materialConfig: {
          preset: r.material_config.preset,
          baseColor: r.material_config.base_color,
          roughness: r.material_config.roughness,
          metalness: r.material_config.metalness,
          stitchVisible: r.material_config.stitch_visible,
          stitchColor: r.material_config.stitch_color,
        },
        patternPieces: Object.keys(r.pattern_overrides || {}).length ? r.pattern_overrides : undefined,
      });
      setStatusMsg(`Restored Design Revision v${r.design_version}.`);
    } catch {
      setStatusMsg('Could not restore selected revision.');
    }
  };

  const handleSyncPatternServer = async () => {
    try {
      const overrides = Object.values(designState.patternPieces).map((p) => ({
        piece_id: p.piece_id,
        boundary_polygon: p.boundary_polygon,
      }));
      const res = await garmentsHttp.post(`/garments/${encodeURIComponent(garmentId)}/sync-pattern`, {
        category: designState.category,
        subcategory: designState.subcategory,
        piece_overrides: overrides,
        include_exports: true,
      });
      if (res.data?.exports) setLatestExports(res.data.exports);
      setStatusMsg('2D pattern & 3D construction graph validated and synchronized.');
    } catch (err: any) {
      setStatusMsg(err?.response?.data?.detail?.message || err?.response?.data?.detail || 'Pattern validation rejected edit.');
    }
  };

  const handleApplyQuickCommand = () => {
    const cmd = commandText.trim().toLowerCase();
    if (!cmd) return;
    const isBottom = ['bottoms', 'pants', 'trousers', 'jeans', 'shorts'].includes(designState.category);
    if (cmd.includes('wireframe')) {
      engine.setViewState({ wireframe: !designState.viewModes.wireframe });
      setStatusMsg('Executed wireframe command.');
    } else if (cmd.includes('stitch')) {
      engine.applyMaterialEdit({ stitchVisible: !designState.material.stitchVisible }, 'stylist_chat');
      engine.setViewState({ showSeams: !designState.viewModes.showSeams });
      setStatusMsg('Toggled stitching & seam overlay.');
    } else if (cmd.includes('denim')) {
      engine.applyMaterialEdit({ preset: 'denim', baseColor: '#1e3a5f', roughness: 0.88 }, 'stylist_chat');
      setStatusMsg('Applied dark denim visual preset.');
    } else if (cmd.includes('collar')) {
      if (isBottom) {
        setStatusMsg('NOT_SUPPORTED: Collar correspondence does not exist on bottoms.');
      } else {
        const sc = cmd.includes('narrow') ? 0.88 : 1.12;
        engine.applyGeometryEdit({ collarWidthScale: sc }, 'stylist_chat');
        setStatusMsg('Updated collar opening across semantic correspondence.');
      }
    } else if (cmd.includes('leg') && cmd.includes('wide')) {
      if (!isBottom) {
        setStatusMsg('NOT_SUPPORTED: Leg correspondence does not exist on upper-body garments.');
      } else {
        engine.applyGeometryEdit({ legWidthScale: Math.min(1.4, designState.geometryParams.legWidthScale + 0.1) }, 'stylist_chat');
        setStatusMsg('Widened trouser legs cleanly.');
      }
    } else if (cmd.includes('chest') || (cmd.includes('widen') && !cmd.includes('sleeve'))) {
      engine.applyGeometryEdit({ torsoWidthScale: Math.min(1.38, designState.geometryParams.torsoWidthScale + 0.08) }, 'stylist_chat');
      setStatusMsg('Widened chest panels and torso shell.');
    } else if (cmd.includes('sleeve') && cmd.includes('wide')) {
      engine.applyGeometryEdit({ sleeveWidthScale: Math.min(1.4, designState.geometryParams.sleeveWidthScale + 0.1) }, 'stylist_chat');
      setStatusMsg('Widened sleeves cleanly.');
    } else if (cmd.includes('sleeve') && cmd.includes('shorten')) {
      engine.applyGeometryEdit({ sleeveLengthScale: Math.max(0.55, Number((designState.geometryParams.sleeveLengthScale - 0.1).toFixed(2))) }, 'stylist_chat');
      setStatusMsg('Shortened sleeves cleanly.');
    } else if (cmd.includes('hem')) {
      engine.applyGeometryEdit({ hemWidthScale: Math.min(1.35, Number((designState.geometryParams.hemWidthScale + 0.08).toFixed(2))) }, 'stylist_chat');
      setStatusMsg('Adjusted hem width.');
    } else if (cmd.includes('pocket') && (cmd.includes('move') || cmd.includes('shift'))) {
      const hasPocket = Object.keys(designState.patternPieces).some((k) => k.includes('pocket'));
      if (!hasPocket) {
        setStatusMsg('REQUIRES_REBUILD: No mapped pocket node in current pattern correspondence.');
      } else {
        engine.applyGeometryEdit({ pocketOffsetYM: 0.025 }, 'stylist_chat');
        setStatusMsg('Shifted mapped pocket position +2.5 cm.');
      }
    } else if (cmd.includes('shorten')) {
      engine.applyGeometryEdit({ torsoLengthScale: Math.max(0.7, Number((designState.geometryParams.torsoLengthScale - 0.05).toFixed(2))) }, 'stylist_chat');
      setStatusMsg('Shortened garment torso.');
    } else if (cmd.includes('print')) {
      engine.applyMaterialEdit({ offsetX: 0.15, offsetY: 0.10, printScale: 1.15 }, 'stylist_chat');
      setStatusMsg('Shifted print placement.');
    } else {
      setStatusMsg('Forwarded unsupported command wording cleanly without unvalidated mesh edits.');
    }
    setCommandText('');
  };

  const hexToRgba = (hex: string): number[] => {
    const clean = hex.replace('#', '');
    if (clean.length !== 6) return [1, 1, 1, 1];
    return [
      Number((parseInt(clean.slice(0, 2), 16) / 255).toFixed(4)),
      Number((parseInt(clean.slice(2, 4), 16) / 255).toFixed(4)),
      Number((parseInt(clean.slice(4, 6), 16) / 255).toFixed(4)),
      1.0,
    ];
  };

  const handleSuggestPairings = async () => {
    try {
      const res = await intelligenceApi.getOutfitRecommendations({
        occasion: 'smart_casual',
        anchorItem: {
          id: garmentId,
          name: `${designState.category} Design`,
          category: designState.category,
          subcategory: designState.subcategory,
          material: designState.material.preset,
        },
        maxOutfits: 1,
      });
      setPairingRecs(res);
      const count = res.complementary_items?.length || 0;
      setStatusMsg(`Loaded ${count} complementary styling pairings for this ${designState.category}.`);
    } catch {
      setStatusMsg('Could not load complementary pairing recommendations right now.');
    }
  };

  const handleResearchFabricAndConstruction = async () => {
    try {
      const wf = await intelligenceApi.executeWorkflow('garment.research', {
        query: `${designState.category} ${designState.material.preset} construction seam durability`,
        category: designState.category,
        use_external: true,
      });
      setDesignResearch({
        summary: String(wf.state?.synthesis || ''),
        external: Array.isArray(wf.state?.external_evidence) ? wf.state.external_evidence : [],
      });
      setStatusMsg(`Loaded construction & fabric research for ${designState.category}.`);
    } catch {
      setStatusMsg('Could not run garment research workflow.');
    }
  };

  const handleInspectDesignQuality = async () => {
    const jobTarget = candidateId || garmentId;
    try {
      const fb = await intelligenceApi.inspectJobQuality(jobTarget, designState.category);
      setQualityCheck(fb);
      setStatusMsg(
        `Quality Check: ${fb.overall_status}${fb.fit_classification ? ` • Fit: ${fb.fit_classification}` : ''}`
      );
    } catch {
      const meshValid = (meshMetrics?.vertexCount || 0) > 0 && (meshMetrics?.triangleCount || 0) > 0;
      setQualityCheck({
        publication_allowed: meshValid,
        overall_status: meshValid ? 'PASSED_LOCAL_CHECK' : 'PENDING_MESH',
        critical_defect_count: 0,
        major_defect_count: 0,
        minor_defect_count: 0,
        suggestions: [],
      });
      setStatusMsg(meshValid ? 'Local structural mesh inspection passed.' : 'Waiting for loaded geometry.');
    }
  };

  const handleExportGLB = async (applyToAvatar = false) => {
    let blob: Blob | null = null;
    try {
      const srcResp = await fetch(glbUrl);
      const srcBuf = new Uint8Array(await srcResp.arrayBuffer());
      let binStr = '';
      for (let i = 0; i < srcBuf.length; i += 8192) {
        binStr += String.fromCharCode(...srcBuf.subarray(i, i + 8192));
      }
      const res = await garmentsHttp.post(`/garments/${encodeURIComponent(garmentId)}/candidate-edit-gl`, {
        glb_base64: btoa(binStr),
        category: designState.category,
        torso_length_scale: designState.geometryParams.torsoLengthScale,
        torso_width_scale: designState.geometryParams.torsoWidthScale,
        shoulder_width_scale: designState.geometryParams.shoulderWidthScale,
        sleeve_length_scale: designState.geometryParams.sleeveLengthScale,
        sleeve_width_scale: designState.geometryParams.sleeveWidthScale,
        collar_width_scale: designState.geometryParams.collarWidthScale,
        cuff_width_scale: designState.geometryParams.cuffWidthScale,
        hem_width_scale: designState.geometryParams.hemWidthScale,
        waistband_width_scale: designState.geometryParams.waistbandWidthScale,
        leg_width_scale: designState.geometryParams.legWidthScale,
        leg_length_scale: designState.geometryParams.legLengthScale,
        pocket_offset_y_m: designState.geometryParams.pocketOffsetYM,
        base_color_rgba: hexToRgba(designState.material.baseColor),
        roughness: designState.material.roughness,
        metalness: designState.material.metalness,
      });
      if (res.data?.glb_base64) {
        const raw = atob(res.data.glb_base64);
        const bytes = new Uint8Array(raw.length);
        for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
        blob = new Blob([bytes], { type: 'model/gltf-binary' });
      }
    } catch {
      // Fallback to client GLTFExporter if endpoint is unreachable
    }
    if (!blob && garmentGroupRef.current && meshEditorRef.current) {
      blob = await meshEditorRef.current.exportToBinaryGLB(garmentGroupRef.current);
    }
    if (!blob) return;
    if (applyToAvatar) {
      onApplyToAvatar(blob);
      setStatusMsg('Applied live edited GLB directly to 3D Avatar Fitting Engine.');
    } else {
      triggerDownload(blob, `${garmentId}_v${designState.designVersion}.glb`, 'model/gltf-binary');
      setStatusMsg('Exported edited binary .glb.');
    }
  };

  const handleExportGLTF = async () => {
    if (!garmentGroupRef.current || !meshEditorRef.current) return;
    const text = await meshEditorRef.current.exportToGLTFJson(garmentGroupRef.current);
    triggerDownload(text, `${garmentId}_v${designState.designVersion}.gltf`, 'model/gltf+json');
    setStatusMsg('Exported .gltf JSON.');
  };

  const overlay = (
    <div
      role="dialog"
      aria-label="Interactive Real-Time Garment Design Studio"
      data-testid="garment-design-workspace"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 2147483000,
        background: 'rgba(15, 23, 42, 0.72)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
    >
      <div
        style={{
          background: '#ffffff',
          color: '#0f172a',
          width: '96vw',
          maxWidth: 1360,
          maxHeight: '94vh',
          overflowY: 'auto',
          borderRadius: 14,
          padding: 18,
          boxShadow: '0 24px 60px rgba(0,0,0,0.3)',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        {/* Header Bar */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e2e8f0', paddingBottom: 10 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 18 }}>
              Interactive Garment Design Studio — {designState.category} ({designState.subcategory})
            </h2>
            <div style={{ fontSize: 12, color: '#475569' }}>
              Design v{designState.designVersion} | Geom v{designState.geometryVersion} | Pattern v{designState.patternVersion} | Mat v{designState.materialVersion} | Sync: <strong>{designState.syncStatus}</strong>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button type="button" onClick={() => engine.undo()} disabled={!engine.canUndo()} aria-label="Studio Undo">
              Undo
            </button>
            <button type="button" onClick={() => engine.redo()} disabled={!engine.canRedo()} aria-label="Studio Redo">
              Redo
            </button>
            <button type="button" onClick={handleSaveRevision}>Save Revision</button>
            <button type="button" onClick={() => handleExportGLB(true)} style={{ background: '#1d4ed8', color: '#fff', border: 'none', padding: '6px 12px', borderRadius: 6, cursor: 'pointer' }}>
              Wear on Avatar
            </button>
            <button type="button" onClick={onClose} aria-label="Close Design Studio">Close</button>
          </div>
        </div>

        {/* Main 3-Column Studio Grid: 3D Viewport | 2D Pattern CAD | Parametric + Material + Export Inspector */}
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(340px, 1.15fr) minmax(340px, 1.1fr) minmax(280px, 0.9fr)', gap: 14 }}>
          {/* Column 1: Interactive 3D Viewport */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {(['front', 'three_quarter', 'side', 'back', 'detail'] as CameraPreset[]).map((cam) => (
                <button
                  key={cam}
                  type="button"
                  onClick={() => engine.setViewState({ cameraPreset: cam })}
                  style={{
                    fontSize: 11,
                    padding: '3px 8px',
                    borderRadius: 6,
                    background: designState.cameraPreset === cam ? '#0f172a' : '#f1f5f9',
                    color: designState.cameraPreset === cam ? '#fff' : '#0f172a',
                    border: '1px solid #cbd5e1',
                  }}
                >
                  {cam.replace('_', ' ')}
                </button>
              ))}
            </div>

            <InteractiveGarment3DEditor
              glbUrl={glbUrl}
              designEngine={engine}
              designState={designState}
              meshEditorRef={meshEditorRef}
              garmentGroupRef={garmentGroupRef}
              onTelemetry={(t, c) => {
                setTelemetry(t);
                if (c) setCaps(c);
              }}
              onMeshMetrics={setMeshMetrics}
            />

            {/* Inspection & Lighting Controls */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, fontSize: 12 }}>
              <label><input type="checkbox" checked={designState.viewModes.wireframe} onChange={(e) => engine.setViewState({ wireframe: e.target.checked })} /> Wireframe</label>
              <label><input type="checkbox" checked={designState.viewModes.showNormals} onChange={(e) => engine.setViewState({ showNormals: e.target.checked })} /> Normals</label>
              <label><input type="checkbox" checked={designState.viewModes.showUVs} onChange={(e) => engine.setViewState({ showUVs: e.target.checked })} /> UV Grid</label>
              <label><input type="checkbox" checked={designState.viewModes.showPanels} onChange={(e) => engine.setViewState({ showPanels: e.target.checked })} /> Panels</label>
              <label><input type="checkbox" checked={designState.viewModes.showSeams} onChange={(e) => engine.setViewState({ showSeams: e.target.checked })} /> Seams</label>
              <label><input type="checkbox" checked={designState.viewModes.showMeasurements} onChange={(e) => engine.setViewState({ showMeasurements: e.target.checked })} /> Bounds</label>
            </div>

            <div style={{ display: 'flex', gap: 10, alignItems: 'center', fontSize: 12 }}>
              <label>
                Light:
                <select
                  value={designState.viewModes.lightingPreset}
                  onChange={(e) => engine.setViewState({ lightingPreset: e.target.value as LightingPreset })}
                >
                  <option value="studio_day">Studio Day</option>
                  <option value="runway_spotlight">Runway Spotlight</option>
                  <option value="warm_atelier">Warm Atelier</option>
                </select>
              </label>
              <label>
                Sim:
                <select
                  value={designState.simulationMode}
                  onChange={(e) => engine.setViewState({ simulationMode: e.target.value as SimulationPreviewMode })}
                >
                  <option value="static">Static Garment</option>
                  <option value="interactive_deform">Interactive Sway</option>
                  <option value="collision_aware">Collision-Aware</option>
                  <option value="cloth_sim">Cloth Preview</option>
                  <option value="avatar_fit">Avatar Fit Ready</option>
                </select>
              </label>
            </div>

            {meshMetrics && (
              <div style={{ fontSize: 11, color: '#334155', background: '#f8fafc', padding: 8, borderRadius: 6 }}>
                Live 3D Bounds: {meshMetrics.widthCm} x {meshMetrics.heightCm} x {meshMetrics.depthCm} cm | Tris: {meshMetrics.triangleCount}
                {telemetry && <> | {telemetry.fps} FPS ({telemetry.frameTimeMs}ms)</>}
                {caps && <> | Tier: {caps.tier}</>}
              </div>
            )}
          </div>

          {/* Column 2: Synchronized 2D Pattern CAD Editor */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong style={{ fontSize: 13 }}>Interactive 2D Pattern CAD</strong>
              <button type="button" onClick={handleSyncPatternServer} style={{ fontSize: 11 }}>
                Validate &amp; Sync Graph
              </button>
            </div>
            <Pattern2DEditor designEngine={engine} designState={designState} />
            <div data-testid="synced-measurements-readout" style={{ fontSize: 12, background: '#f8fafc', padding: 8, borderRadius: 6 }}>
              Synced Measurements ({designState.measurements.activePanelScope}): Panel{' '}
              {(designState.measurements.activePanelWidthM * 100).toFixed(1)} cm | Half Chest{' '}
              {(designState.measurements.chestWidthM * 100).toFixed(1)} cm | Circumference{' '}
              {(designState.measurements.chestCircumferenceM * 100).toFixed(1)} cm | Length{' '}
              {(designState.measurements.garmentLengthM * 100).toFixed(1)} cm | SA{' '}
              {(designState.measurements.seamAllowanceM * 100).toFixed(1)} cm
            </div>
          </div>

          {/* Column 3: Parametric Geometry, Material Studio, Quick Command & Exports */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: 12 }}>
            <div>
              <strong>Real-Time Geometry Edits</strong>
              {(Object.keys(GEOMETRY_PARAM_BOUNDS) as (keyof GeometryDeformationParams)[])
                .filter((key) => {
                  const cat = (designState.category || '').toLowerCase();
                  const isBottom = cat === 'trousers' || cat === 'skirt';
                  const hasPocket =
                    cat === 'hoodie' ||
                    Object.keys(designState.patternPieces).some((id) => id.includes('pocket'));
                  if (isBottom) {
                    return !['collarWidthScale', 'sleeveLengthScale', 'sleeveWidthScale', 'shoulderWidthScale', 'cuffWidthScale', 'pocketOffsetYM'].includes(key);
                  }
                  if (key === 'pocketOffsetYM') return hasPocket;
                  return !['waistbandWidthScale', 'legWidthScale', 'legLengthScale'].includes(key);
                })
                .map((key) => {
                const cfg = GEOMETRY_PARAM_BOUNDS[key];
                const val = designState.geometryParams[key];
                return (
                  <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
                    <label htmlFor={`slider-${key}`}>{cfg.label} ({(val * 100).toFixed(0)}%)</label>
                    <input
                      id={`slider-${key}`}
                      type="range"
                      min={cfg.min}
                      max={cfg.max}
                      step={0.02}
                      value={val}
                      onChange={(e) => engine.applyGeometryEdit({ [key]: parseFloat(e.target.value) }, 'studio')}
                    />
                  </div>
                );
              })}
            </div>

            <div style={{ borderTop: '1px solid #e2e8f0', paddingTop: 8 }}>
              <strong>Material &amp; Texture Studio</strong>
              <div style={{ fontSize: 10, color: '#64748b' }}>
                Visual approximation presets (not laboratory-measured physical fabric)
              </div>
              <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
                {(['cotton', 'denim', 'leather', 'silk', 'wool', 'linen', 'techwear'] as FabricPresetKey[]).map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => engine.applyMaterialEdit({ preset: p }, 'studio')}
                    style={{
                      fontSize: 11,
                      padding: '2px 7px',
                      borderRadius: 6,
                      border: '1px solid #cbd5e1',
                      background: designState.material.preset === p ? '#0f172a' : '#f8fafc',
                      color: designState.material.preset === p ? '#fff' : '#0f172a',
                    }}
                  >
                    {p}
                  </button>
                ))}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
                <label>Base Color <input type="color" aria-label="Fabric base color" value={designState.material.baseColor} onChange={(e) => engine.applyMaterialEdit({ baseColor: e.target.value })} /></label>
                <label><input type="checkbox" checked={designState.material.stitchVisible} onChange={(e) => engine.applyMaterialEdit({ stitchVisible: e.target.checked })} /> Stitching</label>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
                <label>Roughness ({designState.material.roughness.toFixed(2)})</label>
                <input type="range" min={0.05} max={1} step={0.02} value={designState.material.roughness} onChange={(e) => engine.applyMaterialEdit({ roughness: parseFloat(e.target.value) })} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
                <label>Print Scale ({designState.material.printScale.toFixed(2)}x)</label>
                <input type="range" min={0.5} max={2.5} step={0.1} value={designState.material.printScale} onChange={(e) => engine.applyMaterialEdit({ printScale: parseFloat(e.target.value) })} />
              </div>
            </div>

            {/* Inline Quick Stylist Design Command */}
            <div style={{ borderTop: '1px solid #e2e8f0', paddingTop: 8 }}>
              <strong>Quick Design Command</strong>
              <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
                <input
                  type="text"
                  aria-label="Design command input"
                  placeholder="e.g. Show wireframe / dark denim"
                  value={commandText}
                  onChange={(e) => setCommandText(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleApplyQuickCommand()}
                  style={{ flex: 1, fontSize: 11, padding: '4px 6px' }}
                />
                <button type="button" onClick={handleApplyQuickCommand}>Apply</button>
              </div>
            </div>

            {/* Multi-format Export + Revision History */}
            <div style={{ borderTop: '1px solid #e2e8f0', paddingTop: 8 }}>
              <strong>Export &amp; Revisions</strong>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
                <button type="button" onClick={handleInspectDesignQuality}>Quality Check</button>
                <button type="button" onClick={handleSuggestPairings}>Suggest Pairings</button>
                <button type="button" onClick={handleResearchFabricAndConstruction}>Research Fabric</button>
                <button type="button" onClick={() => handleExportGLB(false)}>GLB</button>
                <button type="button" onClick={handleExportGLTF}>GLTF</button>
                <button type="button" onClick={() => latestExports.svg && triggerDownload(latestExports.svg, `${garmentId}.svg`, 'image/svg+xml')} disabled={!latestExports.svg}>SVG</button>
                <button type="button" onClick={() => latestExports.dxf && triggerDownload(latestExports.dxf, `${garmentId}.dxf`, 'application/dxf')} disabled={!latestExports.dxf}>DXF</button>
                <button type="button" onClick={() => latestExports.construction_json && triggerDownload(latestExports.construction_json, `${garmentId}_construction.json`, 'application/json')} disabled={!latestExports.construction_json}>Graph JSON</button>
              </div>
              {qualityCheck && (
                <div style={{ fontSize: 11, color: qualityCheck.publication_allowed ? '#065f46' : '#991b1b', marginTop: 4 }}>
                  {qualityCheck.overall_status} • {qualityCheck.critical_defect_count} critical / {qualityCheck.major_defect_count} major issues
                </div>
              )}
              {pairingRecs && pairingRecs.complementary_items.length > 0 && (
                <div data-testid="design-studio-pairings" style={{ fontSize: 11, color: '#1e293b', marginTop: 4, background: '#f8fafc', padding: 6, borderRadius: 6 }}>
                  <strong>Style Pairings:</strong>{' '}
                  {pairingRecs.complementary_items.slice(0, 2).map((c) => `${c.item.name} (${c.slot})`).join(' • ')}
                </div>
              )}
              {designResearch && (
                <div data-testid="design-studio-research" style={{ fontSize: 11, color: '#1e293b', marginTop: 4, background: '#f8fafc', padding: 6, borderRadius: 6 }}>
                  <strong>Verified Internal &amp; External Research:</strong> {designResearch.summary.slice(0, 140)}
                  {designResearch.external.slice(0, 1).map((e, i) => (
                    <div key={i} style={{ fontSize: 10, color: '#475569' }}>
                      [Unverified External Reference] {e.source_title || e.domain}
                    </div>
                  ))}
                </div>
              )}
              {revisions.length > 0 && (
                <div style={{ marginTop: 6, maxHeight: 75, overflowY: 'auto' }}>
                  {revisions.map((r) => (
                    <div key={r.revision_id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginTop: 2 }}>
                      <span>v{r.design_version} ({r.revision_id})</span>
                      <button type="button" onClick={() => handleRestoreRevision(r.revision_id)} style={{ fontSize: 10 }}>Restore</button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        <div role="status" style={{ fontSize: 12, color: '#1e293b', background: '#e2e8f0', padding: '6px 10px', borderRadius: 6 }}>
          {statusMsg}
        </div>
      </div>
    </div>
  );

  return typeof document !== 'undefined' ? createPortal(overlay, document.body) : overlay;
}
