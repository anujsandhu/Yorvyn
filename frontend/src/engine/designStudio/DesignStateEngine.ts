/**
 * Phase 16.3.1 Real-Time Garment Design State Engine
 * Centralized, versioned, transactionally safe state with semantic pattern-to-mesh correspondence,
 * explicit dimensional semantics, compact undo/redo delta history, and construction constraints.
 */

import {
  MeasurementScope,
  SemanticCorrespondenceMap,
  SyncStatus,
  applyPanelEaseToChest,
  halfChestToCircumferenceM,
  panelWidthToHalfChestM,
  resolvePieceToMeshRegions,
} from './SemanticCorrespondenceEngine';

export type { SyncStatus, MeasurementScope, SemanticCorrespondenceMap };

export type SimulationPreviewMode =
  | 'static'
  | 'interactive_deform'
  | 'collision_aware'
  | 'cloth_sim'
  | 'avatar_fit';

export type CameraPreset = 'front' | 'three_quarter' | 'side' | 'back' | 'detail';
export type LightingPreset = 'studio_day' | 'runway_spotlight' | 'warm_atelier';

export interface DesignPoint2D {
  x: number;
  y: number;
}

export interface DesignPatternEdge {
  edge_id: string;
  role: string;
  vertices: DesignPoint2D[];
  length_m: number;
}

export interface DesignPatternDart {
  dart_id: string;
  apex: DesignPoint2D;
  base_left: DesignPoint2D;
  base_right: DesignPoint2D;
  depth_m: number;
  angle_deg: number;
}

export interface DesignPatternNotch {
  notch_id: string;
  edge_id: string;
  position_t: number;
  style: string;
}

export interface DesignGrainline {
  start: DesignPoint2D;
  end: DesignPoint2D;
  angle_deg: number;
  direction: string;
}

export interface DesignPatternPiece {
  piece_id: string;
  piece_type: string;
  name: string;
  parent_component: string;
  boundary_polygon: DesignPoint2D[];
  edges: DesignPatternEdge[];
  darts: DesignPatternDart[];
  notches: DesignPatternNotch[];
  fold_lines: { line_id: string; kind: string; points: DesignPoint2D[] }[];
  grainline: DesignGrainline;
  seam_allowance_m: number;
  area_m2: number;
  perimeter_m: number;
  verification_state: 'OBSERVED' | 'INFERRED' | 'AMBIGUOUS' | 'UNSUPPORTED';
}

export interface DesignSeamConnection {
  seam_id: string;
  piece_a: string;
  edge_a: string;
  piece_b: string;
  edge_b: string;
  seam_type: string;
  edge_a_length_m: number;
  edge_b_length_m: number;
}

export interface PatternLayerVisibility {
  cutLine: boolean;
  seamAllowance: boolean;
  seams: boolean;
  dartsAndNotches: boolean;
  grainlineAndMeasurements: boolean;
  grid: boolean;
}

export interface DesignMeasurements {
  garmentLengthM: number;
  chestWidthM: number;
  chestCircumferenceM: number;
  sleeveLengthM: number;
  sleeveWidthM: number;
  collarWidthM: number;
  hemWidthM: number;
  activePanelWidthM: number;
  activePanelScope: MeasurementScope;
  seamAllowanceM: number;
}

export interface GeometryDeformationParams {
  torsoLengthScale: number;
  torsoWidthScale: number;
  shoulderWidthScale: number;
  sleeveLengthScale: number;
  sleeveWidthScale: number;
  collarWidthScale: number;
  cuffWidthScale: number;
  hemWidthScale: number;
  waistbandWidthScale: number;
  legWidthScale: number;
  legLengthScale: number;
  pocketOffsetYM: number;
}

export type FabricPresetKey =
  | 'cotton'
  | 'denim'
  | 'leather'
  | 'silk'
  | 'wool'
  | 'linen'
  | 'techwear';

export interface DesignMaterialState {
  preset: FabricPresetKey;
  baseColor: string;
  roughness: number;
  metalness: number;
  sheen: number;
  clearcoat: number;
  normalIntensity: number;
  repeatX: number;
  repeatY: number;
  rotationDeg: number;
  offsetX: number;
  offsetY: number;
  stitchVisible: boolean;
  stitchColor: string;
  printScale: number;
  /** Visual material presets do NOT assert laboratory textile certification. */
  isPhysicallyVerified: false;
}

export interface ViewportInspectionModes {
  wireframe: boolean;
  showNormals: boolean;
  showUVs: boolean;
  showPanels: boolean;
  showSeams: boolean;
  showMeasurements: boolean;
  lightingPreset: LightingPreset;
  exposure: number;
}

export interface DesignOperationRecord {
  operationId: string;
  kind: string;
  targetComponent: string;
  source: 'studio' | 'pattern_2d' | 'stylist_chat';
  parameters: Record<string, unknown>;
  timestamp: string;
}

export interface DesignHistoryDelta {
  operation: DesignOperationRecord;
  beforeGeometry: GeometryDeformationParams;
  afterGeometry: GeometryDeformationParams;
  beforeMaterial: DesignMaterialState;
  afterMaterial: DesignMaterialState;
  beforePieces: Record<string, DesignPatternPiece>;
  afterPieces: Record<string, DesignPatternPiece>;
  beforeMeasurements: DesignMeasurements;
  afterMeasurements: DesignMeasurements;
  beforeSyncStatus: SyncStatus;
  afterSyncStatus: SyncStatus;
  correspondenceVersion: string;
}

export interface GarmentDesignState {
  garmentId: string;
  candidateId: string | null;
  category: string;
  subcategory: string;
  designVersion: number;
  geometryVersion: number;
  patternVersion: number;
  materialVersion: number;
  textureVersion: number;
  correspondenceVersion: string;
  selectedComponent: string | null;
  hoveredComponent: string | null;
  activeOperation: string | null;
  baseMeasurements: DesignMeasurements;
  measurements: DesignMeasurements;
  geometryParams: GeometryDeformationParams;
  material: DesignMaterialState;
  viewModes: ViewportInspectionModes;
  cameraPreset: CameraPreset;
  simulationMode: SimulationPreviewMode;
  patternPieces: Record<string, DesignPatternPiece>;
  patternSeams: DesignSeamConnection[];
  selectedPieceId: string | null;
  patternLayers: PatternLayerVisibility;
  patternValidationErrors: string[];
  correspondence: SemanticCorrespondenceMap | null;
  syncStatus: SyncStatus;
  lastValidationSummary: string;
}

export const GEOMETRY_PARAM_BOUNDS: Record<
  keyof GeometryDeformationParams,
  { min: number; max: number; label: string }
> = {
  torsoLengthScale: { min: 0.70, max: 1.35, label: 'Garment Length' },
  torsoWidthScale: { min: 0.75, max: 1.40, label: 'Body Width' },
  shoulderWidthScale: { min: 0.82, max: 1.28, label: 'Shoulder Width' },
  sleeveLengthScale: { min: 0.55, max: 1.30, label: 'Sleeve Length' },
  sleeveWidthScale: { min: 0.75, max: 1.40, label: 'Sleeve Width' },
  collarWidthScale: { min: 0.75, max: 1.30, label: 'Collar Opening' },
  cuffWidthScale: { min: 0.78, max: 1.32, label: 'Cuff Opening' },
  hemWidthScale: { min: 0.80, max: 1.35, label: 'Hem Width' },
  waistbandWidthScale: { min: 0.78, max: 1.35, label: 'Waistband Width' },
  legWidthScale: { min: 0.75, max: 1.45, label: 'Leg Width' },
  legLengthScale: { min: 0.60, max: 1.30, label: 'Leg Length' },
  pocketOffsetYM: { min: -0.06, max: 0.06, label: 'Pocket Offset Y (m)' },
};

export const MATERIAL_PRESET_DEFAULTS: Record<FabricPresetKey, Partial<DesignMaterialState>> = {
  cotton: { roughness: 0.78, metalness: 0.02, sheen: 0.08, clearcoat: 0.0, normalIntensity: 0.65 },
  denim: { roughness: 0.86, metalness: 0.04, sheen: 0.05, clearcoat: 0.0, normalIntensity: 1.05, baseColor: '#25426b' },
  leather: { roughness: 0.34, metalness: 0.12, sheen: 0.10, clearcoat: 0.55, normalIntensity: 0.45, baseColor: '#2b211c' },
  silk: { roughness: 0.28, metalness: 0.08, sheen: 0.85, clearcoat: 0.15, normalIntensity: 0.25 },
  wool: { roughness: 0.90, metalness: 0.01, sheen: 0.15, clearcoat: 0.0, normalIntensity: 0.85 },
  linen: { roughness: 0.83, metalness: 0.02, sheen: 0.06, clearcoat: 0.0, normalIntensity: 0.80 },
  techwear: { roughness: 0.44, metalness: 0.12, sheen: 0.20, clearcoat: 0.30, normalIntensity: 0.40 },
};

export function signedPolygonArea2D(poly: DesignPoint2D[]): number {
  const n = poly.length;
  if (n < 3) return 0;
  let sum = 0;
  for (let i = 0; i < n; i++) {
    const a = poly[i];
    const b = poly[(i + 1) % n];
    sum += a.x * b.y - b.x * a.y;
  }
  return 0.5 * sum;
}

export function polygonPerimeter2D(poly: DesignPoint2D[]): number {
  let perim = 0;
  for (let i = 0; i < poly.length; i++) {
    const a = poly[i];
    const b = poly[(i + 1) % poly.length];
    perim += Math.hypot(b.x - a.x, b.y - a.y);
  }
  return Number(perim.toFixed(5));
}

function orient2D(a: DesignPoint2D, b: DesignPoint2D, c: DesignPoint2D): number {
  return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
}

function segmentsIntersect2D(
  a1: DesignPoint2D,
  a2: DesignPoint2D,
  b1: DesignPoint2D,
  b2: DesignPoint2D
): boolean {
  const o1 = orient2D(a1, a2, b1);
  const o2 = orient2D(a1, a2, b2);
  const o3 = orient2D(b1, b2, a1);
  const o4 = orient2D(b1, b2, a2);
  const eps = 1e-8;
  return ((o1 > eps && o2 < -eps) || (o1 < -eps && o2 > eps)) && ((o3 > eps && o4 < -eps) || (o3 < -eps && o4 > eps));
}

export function validatePatternPolygon2D(poly: DesignPoint2D[]): string[] {
  const errors: string[] = [];
  const n = poly.length;
  if (n < 3) return ['Polygon requires at least 3 vertices.'];
  for (let i = 0; i < n; i++) {
    const a = poly[i];
    const b = poly[(i + 1) % n];
    if (!Number.isFinite(a.x) || !Number.isFinite(a.y)) {
      errors.push(`Vertex ${i} is non-finite.`);
    }
    if (Math.hypot(b.x - a.x, b.y - a.y) < 1e-4) {
      errors.push(`Degenerate edge at vertex ${i}.`);
    }
  }
  const area = signedPolygonArea2D(poly);
  if (Math.abs(area) < 1e-5) {
    errors.push('Pattern area is near zero.');
  } else if (area < 0) {
    errors.push('Pattern outline must be counter-clockwise.');
  }
  for (let i = 0; i < n; i++) {
    for (let j = i + 2; j < n; j++) {
      if (i === 0 && j === n - 1) continue;
      if (segmentsIntersect2D(poly[i], poly[(i + 1) % n], poly[j], poly[(j + 1) % n])) {
        errors.push(`Self-intersection between edge ${i} and edge ${j}.`);
        break;
      }
    }
  }
  return errors;
}

export function buildDefaultPatternPieces(category: string, measurements: DesignMeasurements): {
  pieces: Record<string, DesignPatternPiece>;
  seams: DesignSeamConnection[];
} {
  const w = measurements.chestWidthM;
  const h = measurements.garmentLengthM;
  const sw = measurements.sleeveWidthM;
  const sl = measurements.sleeveLengthM;
  const mkRect = (
    pieceId: string,
    pieceType: string,
    name: string,
    comp: string,
    pw: number,
    ph: number,
    verified: 'OBSERVED' | 'INFERRED'
  ): DesignPatternPiece => {
    const poly = [
      { x: 0, y: 0 },
      { x: Number(pw.toFixed(4)), y: 0 },
      { x: Number(pw.toFixed(4)), y: Number((ph * 0.65).toFixed(4)) },
      { x: Number((pw * 0.88).toFixed(4)), y: Number(ph.toFixed(4)) },
      { x: Number((pw * 0.12).toFixed(4)), y: Number(ph.toFixed(4)) },
      { x: 0, y: Number((ph * 0.65).toFixed(4)) },
    ];
    return {
      piece_id: pieceId,
      piece_type: pieceType,
      name,
      parent_component: comp,
      boundary_polygon: poly,
      edges: [
        { edge_id: 'hem', role: 'HEMMED', vertices: [poly[0], poly[1]], length_m: pw },
        { edge_id: 'side_right', role: 'SEWN', vertices: [poly[1], poly[2]], length_m: ph * 0.65 },
        { edge_id: 'top_right', role: 'SEWN', vertices: [poly[2], poly[3]], length_m: ph * 0.35 },
        { edge_id: 'neckline', role: 'COLLAR_ATTACHMENT', vertices: [poly[3], poly[4]], length_m: pw * 0.76 },
        { edge_id: 'top_left', role: 'SEWN', vertices: [poly[4], poly[5]], length_m: ph * 0.35 },
        { edge_id: 'side_left', role: 'SEWN', vertices: [poly[5], poly[0]], length_m: ph * 0.65 },
      ],
      darts: category === 'dress' && pieceId.includes('front')
        ? [{
            dart_id: 'waist_dart',
            apex: { x: pw * 0.5, y: ph * 0.25 },
            base_left: { x: pw * 0.46, y: 0 },
            base_right: { x: pw * 0.54, y: 0 },
            depth_m: ph * 0.25,
            angle_deg: 12,
          }]
        : [],
      notches: [{ notch_id: `${pieceId}_center`, edge_id: 'neckline', position_t: 0.5, style: 'center' }],
      fold_lines: [],
      grainline: {
        start: { x: pw * 0.5, y: ph * 0.15 },
        end: { x: pw * 0.5, y: ph * 0.85 },
        angle_deg: 90,
        direction: 'warp',
      },
      seam_allowance_m: 0.01,
      area_m2: Number(Math.abs(signedPolygonArea2D(poly)).toFixed(4)),
      perimeter_m: polygonPerimeter2D(poly),
      verification_state: verified,
    };
  };

  const pieces: Record<string, DesignPatternPiece> = {
    front_body: mkRect('front_body', 'front_body', 'Front Body Panel', 'front_body', w, h, 'OBSERVED'),
    back_body: mkRect('back_body', 'back_body', 'Back Body Panel', 'back_body', w, h, 'INFERRED'),
    left_sleeve: mkRect('left_sleeve', 'left_sleeve', 'Left Sleeve Panel', 'left_sleeve', sw, sl, 'OBSERVED'),
    right_sleeve: mkRect('right_sleeve', 'right_sleeve', 'Right Sleeve Panel', 'right_sleeve', sw, sl, 'OBSERVED'),
  };
  const seams: DesignSeamConnection[] = [
    { seam_id: 'seam_side_l', piece_a: 'front_body', edge_a: 'side_left', piece_b: 'back_body', edge_b: 'side_left', seam_type: 'SEWN', edge_a_length_m: h * 0.65, edge_b_length_m: h * 0.65 },
    { seam_id: 'seam_side_r', piece_a: 'front_body', edge_a: 'side_right', piece_b: 'back_body', edge_b: 'side_right', seam_type: 'SEWN', edge_a_length_m: h * 0.65, edge_b_length_m: h * 0.65 },
    { seam_id: 'seam_sleeve_l', piece_a: 'front_body', edge_a: 'top_left', piece_b: 'left_sleeve', edge_b: 'hem', seam_type: 'SLEEVE_ATTACHMENT', edge_a_length_m: h * 0.35, edge_b_length_m: sw },
  ];
  return { pieces, seams };
}

function clonePieces(src: Record<string, DesignPatternPiece>): Record<string, DesignPatternPiece> {
  return JSON.parse(JSON.stringify(src));
}

function scalePatternPiece(piece: DesignPatternPiece, scaleX: number, scaleY: number): DesignPatternPiece {
  const poly = piece.boundary_polygon.map((p) => ({
    x: Number((p.x * scaleX).toFixed(5)),
    y: Number((p.y * scaleY).toFixed(5)),
  }));
  return {
    ...piece,
    boundary_polygon: poly,
    edges: piece.edges.map((e) => ({
      ...e,
      vertices: e.vertices.map((p) => ({
        x: Number((p.x * scaleX).toFixed(5)),
        y: Number((p.y * scaleY).toFixed(5)),
      })),
    })),
    grainline: {
      ...piece.grainline,
      start: { x: piece.grainline.start.x * scaleX, y: piece.grainline.start.y * scaleY },
      end: { x: piece.grainline.end.x * scaleX, y: piece.grainline.end.y * scaleY },
    },
    area_m2: Number(Math.abs(signedPolygonArea2D(poly)).toFixed(4)),
    perimeter_m: polygonPerimeter2D(poly),
  };
}

export function buildClientCorrespondenceMap(opts: {
  garmentId: string;
  candidateId: string | null;
  category: string;
  subcategory: string;
  pieces: Record<string, DesignPatternPiece>;
  seams: DesignSeamConnection[];
  available3DRegions?: string[];
  vertexCount?: number;
  triangleCount?: number;
  patternVersion?: number;
  geometryVersion?: number;
}): SemanticCorrespondenceMap {
  const regions = opts.available3DRegions || [];
  const pieceMappings: SemanticCorrespondenceMap['pieceMappings'] = {};
  for (const [pid, piece] of Object.entries(opts.pieces)) {
    const resolved = resolvePieceToMeshRegions(pid, piece.parent_component, regions);
    const panelScope: MeasurementScope =
      pid.includes('front_left') || pid.includes('front_right') ? 'PATTERN_PANEL_HALF' : 'PATTERN_PANEL_FULL';
    pieceMappings[pid] = {
      mappingId: `map_${pid}_v${opts.patternVersion || 1}_${opts.geometryVersion || 1}`,
      pieceId: pid,
      patternVertexIds: piece.boundary_polygon.map((_, i) => `${pid}:v${i}`),
      patternEdgeIds: piece.edges.map((e) => `${pid}:${e.edge_id}`),
      seamIds: opts.seams.filter((s) => s.piece_a === pid || s.piece_b === pid).map((s) => s.seam_id),
      localCoordinateSystem: '2D_METRIC_Z_UP_CCW',
      unit: 'm',
      panelScope,
      meshId: opts.candidateId || 'candidate_mesh_v1',
      meshRegionIds: resolved.meshRegionIds,
      garmentComponentId: piece.parent_component,
      surfaceCorrespondence: resolved.surface,
      uvRegionId: resolved.uvRegion,
      materialRegionRef: 'main_shell',
      sourceImageIds: [],
      sourceViews: [],
      verificationState: piece.verification_state,
      confidence: piece.verification_state === 'OBSERVED' ? 0.85 : 0.45,
      uncertainty: piece.verification_state === 'OBSERVED' ? 0.15 : 0.55,
      valid: resolved.surface !== 'unmapped',
      invalidationReason: resolved.surface === 'unmapped' ? `Unmapped panel '${pid}'` : undefined,
    };
  }
  return {
    mappingVersion: '16.3.1',
    garmentId: opts.garmentId,
    candidateId: opts.candidateId,
    category: opts.category,
    subcategory: opts.subcategory,
    patternVersion: opts.patternVersion || 1,
    geometryVersion: opts.geometryVersion || 1,
    topologySignature: {
      vertexCount: opts.vertexCount || 0,
      triangleCount: opts.triangleCount || 0,
      componentIdsHash: regions.slice().sort().join(','),
    },
    pieceMappings,
    relationships: opts.seams.map((s) => ({
      relationId: `rel_${s.seam_id}`,
      relation: s.seam_type.includes('ATTACHMENT') ? 'ATTACHED_TO' : 'SEWN_TO',
      sourceId: s.piece_a,
      targetId: s.piece_b,
      verificationState: 'INFERRED',
    })),
    valid: true,
    invalidatedReasons: [],
  };
}

export function createInitialDesignState(opts: {
  garmentId: string;
  candidateId?: string | null;
  category?: string;
  subcategory?: string;
  baseColor?: string;
  measurements?: Partial<DesignMeasurements>;
}): GarmentDesignState {
  const category = (opts.category || 'jacket').toLowerCase();
  const chestWidthM = opts.measurements?.chestWidthM ?? 0.54;
  const baseMeasurements: DesignMeasurements = {
    garmentLengthM: opts.measurements?.garmentLengthM ?? (category === 'dress' ? 1.05 : category === 'bottoms' ? 1.02 : 0.68),
    chestWidthM,
    chestCircumferenceM: halfChestToCircumferenceM(chestWidthM),
    sleeveLengthM: opts.measurements?.sleeveLengthM ?? (category === 'tops' ? 0.24 : 0.62),
    sleeveWidthM: opts.measurements?.sleeveWidthM ?? 0.36,
    collarWidthM: opts.measurements?.collarWidthM ?? 0.42,
    hemWidthM: opts.measurements?.hemWidthM ?? 0.52,
    activePanelWidthM: chestWidthM,
    activePanelScope: 'PATTERN_PANEL_FULL',
    seamAllowanceM: 0.01,
  };
  const { pieces, seams } = buildDefaultPatternPieces(category, baseMeasurements);
  const corr = buildClientCorrespondenceMap({
    garmentId: opts.garmentId,
    candidateId: opts.candidateId ?? null,
    category,
    subcategory: opts.subcategory || category,
    pieces,
    seams,
  });
  return {
    garmentId: opts.garmentId,
    candidateId: opts.candidateId ?? null,
    category,
    subcategory: opts.subcategory || category,
    designVersion: 1,
    geometryVersion: 1,
    patternVersion: 1,
    materialVersion: 1,
    textureVersion: 1,
    correspondenceVersion: '16.3.1',
    selectedComponent: null,
    hoveredComponent: null,
    activeOperation: null,
    baseMeasurements,
    measurements: { ...baseMeasurements },
    geometryParams: {
      torsoLengthScale: 1.0,
      torsoWidthScale: 1.0,
      shoulderWidthScale: 1.0,
      sleeveLengthScale: 1.0,
      sleeveWidthScale: 1.0,
      collarWidthScale: 1.0,
      cuffWidthScale: 1.0,
      hemWidthScale: 1.0,
      waistbandWidthScale: 1.0,
      legWidthScale: 1.0,
      legLengthScale: 1.0,
      pocketOffsetYM: 0.0,
    },
    material: {
      preset: category.includes('denim') ? 'denim' : 'cotton',
      baseColor: opts.baseColor || '#ffffff',
      roughness: 0.78,
      metalness: 0.02,
      sheen: 0.08,
      clearcoat: 0.0,
      normalIntensity: 0.65,
      repeatX: 1.0,
      repeatY: 1.0,
      rotationDeg: 0.0,
      offsetX: 0.0,
      offsetY: 0.0,
      stitchVisible: false,
      stitchColor: '#e2e8f0',
      printScale: 1.0,
      isPhysicallyVerified: false,
    },
    viewModes: {
      wireframe: false,
      showNormals: false,
      showUVs: false,
      showPanels: false,
      showSeams: false,
      showMeasurements: true,
      lightingPreset: 'studio_day',
      exposure: 1.05,
    },
    cameraPreset: 'front',
    simulationMode: 'static',
    patternPieces: pieces,
    patternSeams: seams,
    selectedPieceId: Object.keys(pieces)[0] || null,
    patternLayers: {
      cutLine: true,
      seamAllowance: true,
      seams: true,
      dartsAndNotches: true,
      grainlineAndMeasurements: true,
      grid: true,
    },
    patternValidationErrors: [],
    correspondence: corr,
    syncStatus: Object.values(pieces).some((p) => p.verification_state !== 'OBSERVED')
      ? 'SYNCHRONIZED_WITH_UNCERTAINTY'
      : 'SYNCHRONIZED',
    lastValidationSummary: 'Initialized semantic correspondence.',
  };
}

export class DesignStateEngine {
  private state: GarmentDesignState;
  private undoStack: DesignHistoryDelta[] = [];
  private redoStack: DesignHistoryDelta[] = [];
  private listeners = new Set<(state: GarmentDesignState) => void>();

  constructor(initial: GarmentDesignState) {
    this.state = initial;
  }

  public getState(): GarmentDesignState {
    return this.state;
  }

  public subscribe(fn: (state: GarmentDesignState) => void): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  private emit(): void {
    this.listeners.forEach((fn) => fn(this.state));
  }

  public canUndo(): boolean {
    return this.undoStack.length > 0;
  }

  public canRedo(): boolean {
    return this.redoStack.length > 0;
  }

  public getOperationHistory(): DesignOperationRecord[] {
    return this.undoStack.map((d) => d.operation);
  }

  /** Replace 2D pieces from authoritative Phase 16.2/16.3.1 construction-plan API response & align base measurements. */
  public hydrateConstructionPattern(
    pieces: Record<string, DesignPatternPiece>,
    seams: DesignSeamConnection[],
    available3DRegions?: string[],
    vertexCount?: number,
    triangleCount?: number
  ): void {
    const firstId = Object.keys(pieces)[0] || null;
    const frontPiece = pieces.front_left_body || pieces.front_body || pieces.bodice_front || (firstId ? pieces[firstId] : null);
    let nextBase = { ...this.state.baseMeasurements };
    let nextMeas = { ...this.state.measurements };
    if (frontPiece && frontPiece.boundary_polygon.length >= 3) {
      const xs = frontPiece.boundary_polygon.map((p) => p.x);
      const ys = frontPiece.boundary_polygon.map((p) => p.y);
      const pw = Math.max(0.08, Math.max(...xs) - Math.min(...xs));
      const ph = Math.max(0.15, Math.max(...ys) - Math.min(...ys));
      const isHalf = frontPiece.piece_id.includes('front_left') || frontPiece.piece_id.includes('front_right');
      const scope: MeasurementScope = isHalf ? 'PATTERN_PANEL_HALF' : 'PATTERN_PANEL_FULL';
      const halfChest = panelWidthToHalfChestM(pw, scope, 2);
      nextBase = {
        ...nextBase,
        chestWidthM: halfChest,
        chestCircumferenceM: halfChestToCircumferenceM(halfChest),
        garmentLengthM: Number(ph.toFixed(4)),
        activePanelWidthM: Number(pw.toFixed(4)),
        activePanelScope: scope,
        seamAllowanceM: frontPiece.seam_allowance_m || 0.01,
      };
      nextMeas = {
        ...nextBase,
        chestWidthM: Number((nextBase.chestWidthM * this.state.geometryParams.torsoWidthScale).toFixed(4)),
        chestCircumferenceM: Number((nextBase.chestCircumferenceM * this.state.geometryParams.torsoWidthScale).toFixed(4)),
        garmentLengthM: Number((nextBase.garmentLengthM * this.state.geometryParams.torsoLengthScale).toFixed(4)),
      };
    }

    const corr = buildClientCorrespondenceMap({
      garmentId: this.state.garmentId,
      candidateId: this.state.candidateId,
      category: this.state.category,
      subcategory: this.state.subcategory,
      pieces,
      seams,
      available3DRegions,
      vertexCount,
      triangleCount,
      patternVersion: this.state.patternVersion + 1,
      geometryVersion: this.state.geometryVersion,
    });
    const hasUncertain = Object.values(pieces).some((p) => p.verification_state !== 'OBSERVED');

    this.state = {
      ...this.state,
      patternPieces: clonePieces(pieces),
      patternSeams: [...seams],
      selectedPieceId: firstId,
      baseMeasurements: nextBase,
      measurements: nextMeas,
      correspondence: corr,
      patternVersion: this.state.patternVersion + 1,
      syncStatus: hasUncertain ? 'SYNCHRONIZED_WITH_UNCERTAINTY' : 'SYNCHRONIZED',
      lastValidationSummary: 'Synchronized with Phase 16.2/16.3.1 construction correspondence.',
    };
    this.emit();
  }

  public invalidateCorrespondence(reason: string): void {
    const corr = this.state.correspondence
      ? {
          ...this.state.correspondence,
          valid: false,
          invalidatedReasons: [...this.state.correspondence.invalidatedReasons, reason],
        }
      : null;
    this.state = {
      ...this.state,
      correspondence: corr,
      syncStatus: 'MAPPING_INVALID',
      lastValidationSummary: reason,
    };
    this.emit();
  }

  public rebuildCorrespondence(available3DRegions: string[], vertexCount: number, triangleCount: number): void {
    const corr = buildClientCorrespondenceMap({
      garmentId: this.state.garmentId,
      candidateId: this.state.candidateId,
      category: this.state.category,
      subcategory: this.state.subcategory,
      pieces: this.state.patternPieces,
      seams: this.state.patternSeams,
      available3DRegions,
      vertexCount,
      triangleCount,
      patternVersion: this.state.patternVersion,
      geometryVersion: this.state.geometryVersion,
    });
    const hasUncertain = Object.values(this.state.patternPieces).some((p) => p.verification_state !== 'OBSERVED');
    this.state = {
      ...this.state,
      correspondence: corr,
      syncStatus: hasUncertain ? 'SYNCHRONIZED_WITH_UNCERTAINTY' : 'SYNCHRONIZED',
      lastValidationSummary: 'Rebuilt semantic correspondence for current 3D topology.',
    };
    this.emit();
  }

  public setViewState(patch: Partial<ViewportInspectionModes> & {
    selectedComponent?: string | null;
    hoveredComponent?: string | null;
    cameraPreset?: CameraPreset;
    simulationMode?: SimulationPreviewMode;
    selectedPieceId?: string | null;
    patternLayers?: Partial<PatternLayerVisibility>;
  }): void {
    this.state = {
      ...this.state,
      selectedComponent: patch.selectedComponent !== undefined ? patch.selectedComponent : this.state.selectedComponent,
      hoveredComponent: patch.hoveredComponent !== undefined ? patch.hoveredComponent : this.state.hoveredComponent,
      cameraPreset: patch.cameraPreset ?? this.state.cameraPreset,
      simulationMode: patch.simulationMode ?? this.state.simulationMode,
      selectedPieceId: patch.selectedPieceId !== undefined ? patch.selectedPieceId : this.state.selectedPieceId,
      patternLayers: patch.patternLayers ? { ...this.state.patternLayers, ...patch.patternLayers } : this.state.patternLayers,
      viewModes: {
        ...this.state.viewModes,
        wireframe: patch.wireframe ?? this.state.viewModes.wireframe,
        showNormals: patch.showNormals ?? this.state.viewModes.showNormals,
        showUVs: patch.showUVs ?? this.state.viewModes.showUVs,
        showPanels: patch.showPanels ?? this.state.viewModes.showPanels,
        showSeams: patch.showSeams ?? this.state.viewModes.showSeams,
        showMeasurements: patch.showMeasurements ?? this.state.viewModes.showMeasurements,
        lightingPreset: patch.lightingPreset ?? this.state.viewModes.lightingPreset,
        exposure: patch.exposure ?? this.state.viewModes.exposure,
      },
    };
    this.emit();
  }

  /** Apply validated 3D parametric geometry edit and synchronize into 2D pattern pieces & measurements. */
  public applyGeometryEdit(
    patch: Partial<GeometryDeformationParams>,
    source: 'studio' | 'stylist_chat' = 'studio',
    expectedVersion?: number
  ): { ok: boolean; error?: string } {
    if (this.state.syncStatus === 'MAPPING_INVALID') {
      return { ok: false, error: 'Semantic mapping invalidated by topology change; rebuild correspondence before editing.' };
    }
    if (expectedVersion !== undefined && expectedVersion !== this.state.designVersion) {
      this.state = { ...this.state, syncStatus: 'CONSTRUCTION_CONFLICT', lastValidationSummary: 'Stale revision rejected.' };
      this.emit();
      return { ok: false, error: `Stale version ${expectedVersion} (current ${this.state.designVersion}).` };
    }
    const nextGeom = { ...this.state.geometryParams, ...patch };
    for (const [k, bounds] of Object.entries(GEOMETRY_PARAM_BOUNDS)) {
      const val = nextGeom[k as keyof GeometryDeformationParams];
      if (!Number.isFinite(val) || val < bounds.min || val > bounds.max) {
        return { ok: false, error: `${bounds.label} (${val}) is outside valid bounds [${bounds.min}, ${bounds.max}].` };
      }
    }

    const beforeGeometry = { ...this.state.geometryParams };
    const beforeMeasurements = { ...this.state.measurements };
    const beforePieces = clonePieces(this.state.patternPieces);
    const beforeSyncStatus = this.state.syncStatus;

    const b = this.state.baseMeasurements;
    const chestWidthM = Number((b.chestWidthM * nextGeom.torsoWidthScale).toFixed(4));
    const nextMeasurements: DesignMeasurements = {
      ...b,
      garmentLengthM: Number((b.garmentLengthM * nextGeom.torsoLengthScale).toFixed(4)),
      chestWidthM,
      chestCircumferenceM: halfChestToCircumferenceM(chestWidthM),
      sleeveLengthM: Number((b.sleeveLengthM * nextGeom.sleeveLengthScale).toFixed(4)),
      sleeveWidthM: Number((b.sleeveWidthM * nextGeom.sleeveWidthScale).toFixed(4)),
      collarWidthM: Number((b.collarWidthM * nextGeom.collarWidthScale).toFixed(4)),
      hemWidthM: Number((b.hemWidthM * nextGeom.hemWidthScale).toFixed(4)),
      activePanelWidthM: Number((b.activePanelWidthM * nextGeom.torsoWidthScale).toFixed(4)),
    };

    const nextPieces = clonePieces(this.state.patternPieces);
    const rxW = nextGeom.torsoWidthScale / beforeGeometry.torsoWidthScale;
    const rxL = nextGeom.torsoLengthScale / beforeGeometry.torsoLengthScale;
    const rsW = nextGeom.sleeveWidthScale / beforeGeometry.sleeveWidthScale;
    const rsL = nextGeom.sleeveLengthScale / beforeGeometry.sleeveLengthScale;
    const rcW = nextGeom.collarWidthScale / beforeGeometry.collarWidthScale;
    const rhW = nextGeom.hemWidthScale / beforeGeometry.hemWidthScale;
    const rlW = nextGeom.legWidthScale / beforeGeometry.legWidthScale;
    const rlL = nextGeom.legLengthScale / beforeGeometry.legLengthScale;
    const rwbW = nextGeom.waistbandWidthScale / beforeGeometry.waistbandWidthScale;

    for (const [pid, piece] of Object.entries(nextPieces)) {
      if (pid.includes('cuff')) {
        const rcuff = nextGeom.cuffWidthScale / beforeGeometry.cuffWidthScale;
        nextPieces[pid] = scalePatternPiece(piece, rcuff, 1.0);
      } else if (pid.includes('sleeve') || piece.parent_component.includes('sleeve')) {
        nextPieces[pid] = scalePatternPiece(piece, rsW, rsL);
      } else if (pid.includes('collar') || pid.includes('neck') || pid.includes('hood')) {
        nextPieces[pid] = scalePatternPiece(piece, rcW, 1.0);
      } else if (pid.includes('leg')) {
        nextPieces[pid] = scalePatternPiece(piece, rlW, rlL);
      } else if (pid.includes('waistband')) {
        nextPieces[pid] = scalePatternPiece(piece, rwbW * rhW, 1.0);
      } else if (pid.includes('hem')) {
        nextPieces[pid] = scalePatternPiece(piece, rhW, 1.0);
      } else if (pid.includes('front') || pid.includes('back') || pid.includes('bodice') || pid.includes('skirt')) {
        nextPieces[pid] = scalePatternPiece(piece, rxW, rxL);
      }
    }

    const op: DesignOperationRecord = {
      operationId: `op_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      kind: 'geometry_edit',
      targetComponent: this.state.selectedComponent || Object.keys(patch)[0] || 'garment',
      source,
      parameters: patch,
      timestamp: new Date().toISOString(),
    };
    const nextSync: SyncStatus = Object.values(nextPieces).some((p) => p.verification_state !== 'OBSERVED')
      ? 'SYNCHRONIZED_WITH_UNCERTAINTY'
      : 'SYNCHRONIZED';

    this.undoStack.push({
      operation: op,
      beforeGeometry,
      afterGeometry: nextGeom,
      beforeMaterial: { ...this.state.material },
      afterMaterial: { ...this.state.material },
      beforePieces,
      afterPieces: clonePieces(nextPieces),
      beforeMeasurements,
      afterMeasurements: nextMeasurements,
      beforeSyncStatus,
      afterSyncStatus: nextSync,
      correspondenceVersion: this.state.correspondenceVersion,
    });
    this.redoStack = [];

    this.state = {
      ...this.state,
      designVersion: this.state.designVersion + 1,
      geometryVersion: this.state.geometryVersion + 1,
      patternVersion: this.state.patternVersion + 1,
      geometryParams: nextGeom,
      measurements: nextMeasurements,
      patternPieces: nextPieces,
      activeOperation: op.kind,
      patternValidationErrors: [],
      syncStatus: nextSync,
      lastValidationSummary: `Synchronized 3D -> 2D (${op.targetComponent}).`,
    };
    this.emit();
    return { ok: true };
  }

  /** Apply deterministic panel ease (+cm) using explicit scoped dimensional conversion rules. */
  public applyPanelEase(
    pieceId: string,
    easeDeltaM: number,
    applySymmetrically = true
  ): { ok: boolean; error?: string } {
    const piece = this.state.patternPieces[pieceId];
    if (!piece || piece.boundary_polygon.length < 3) {
      return { ok: false, error: `Pattern piece '${pieceId}' not found.` };
    }
    const xs = piece.boundary_polygon.map((p) => p.x);
    const oldW = Math.max(0.05, Math.max(...xs) - Math.min(...xs));
    const panelScope: MeasurementScope =
      pieceId.includes('front_left') || pieceId.includes('front_right') ? 'PATTERN_PANEL_HALF' : 'PATTERN_PANEL_FULL';
    const conv = applyPanelEaseToChest({ panelWidthM: oldW, panelScope, easeDeltaM, applySymmetrically });
    const ratioW = conv.panelWidth.valueM / oldW;

    const beforePieces = clonePieces(this.state.patternPieces);
    const beforeGeometry = { ...this.state.geometryParams };
    const beforeMeasurements = { ...this.state.measurements };
    const beforeSyncStatus = this.state.syncStatus;

    const nextPieces = clonePieces(this.state.patternPieces);
    nextPieces[pieceId] = scalePatternPiece(nextPieces[pieceId], ratioW, 1.0);
    if (applySymmetrically) {
      const mate = pieceId === 'front_left_body' ? 'front_right_body' : pieceId === 'front_right_body' ? 'front_left_body' : null;
      if (mate && nextPieces[mate]) nextPieces[mate] = scalePatternPiece(nextPieces[mate], ratioW, 1.0);
      if ((pieceId.includes('front') || pieceId.includes('bodice')) && nextPieces.back_body) {
        nextPieces.back_body = scalePatternPiece(nextPieces.back_body, ratioW, 1.0);
      }
    }

    const nextGeom = {
      ...this.state.geometryParams,
      torsoWidthScale: Math.max(
        GEOMETRY_PARAM_BOUNDS.torsoWidthScale.min,
        Math.min(GEOMETRY_PARAM_BOUNDS.torsoWidthScale.max, Number((this.state.geometryParams.torsoWidthScale * ratioW).toFixed(4)))
      ),
    };
    const nextMeasurements: DesignMeasurements = {
      ...this.state.measurements,
      chestWidthM: conv.halfGarmentFlat.valueM,
      chestCircumferenceM: conv.finishedGarmentCircumference.valueM,
      activePanelWidthM: conv.panelWidth.valueM,
      activePanelScope: panelScope,
    };

    const nextSync: SyncStatus = Object.values(nextPieces).some((p) => p.verification_state !== 'OBSERVED')
      ? 'SYNCHRONIZED_WITH_UNCERTAINTY'
      : 'SYNCHRONIZED';
    const op: DesignOperationRecord = {
      operationId: `op_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      kind: 'panel_ease_edit',
      targetComponent: pieceId,
      source: 'pattern_2d',
      parameters: { easeDeltaM, panelScope, applySymmetrically },
      timestamp: new Date().toISOString(),
    };
    this.undoStack.push({
      operation: op,
      beforeGeometry,
      afterGeometry: nextGeom,
      beforeMaterial: { ...this.state.material },
      afterMaterial: { ...this.state.material },
      beforePieces,
      afterPieces: clonePieces(nextPieces),
      beforeMeasurements,
      afterMeasurements: nextMeasurements,
      beforeSyncStatus,
      afterSyncStatus: nextSync,
      correspondenceVersion: this.state.correspondenceVersion,
    });
    this.redoStack = [];

    this.state = {
      ...this.state,
      designVersion: this.state.designVersion + 1,
      patternVersion: this.state.patternVersion + 1,
      geometryVersion: this.state.geometryVersion + 1,
      geometryParams: nextGeom,
      measurements: nextMeasurements,
      patternPieces: nextPieces,
      activeOperation: op.kind,
      patternValidationErrors: [],
      syncStatus: nextSync,
      lastValidationSummary: `Applied ${(easeDeltaM * 100).toFixed(1)} cm panel ease (${panelScope}).`,
    };
    this.emit();
    return { ok: true };
  }

  /** Edit a 2D pattern vertex with full geometric validation and automatic 3D synchronization. */
  public applyPatternVertexEdit(
    pieceId: string,
    vertexIndex: number,
    nextPoint: DesignPoint2D
  ): { ok: boolean; errors?: string[] } {
    if (this.state.syncStatus === 'MAPPING_INVALID') {
      return { ok: false, errors: ['Semantic correspondence invalidated; rebuild mapping before pattern editing.'] };
    }
    const piece = this.state.patternPieces[pieceId];
    if (!piece || vertexIndex < 0 || vertexIndex >= piece.boundary_polygon.length) {
      return { ok: false, errors: ['Unknown pattern piece or vertex index.'] };
    }
    const candidatePoly = piece.boundary_polygon.map((p, idx) =>
      idx === vertexIndex ? { x: Number(nextPoint.x.toFixed(5)), y: Number(nextPoint.y.toFixed(5)) } : p
    );
    const errors = validatePatternPolygon2D(candidatePoly);
    if (errors.length > 0) {
      this.state = { ...this.state, patternValidationErrors: errors, syncStatus: 'VALIDATION_FAILED' };
      this.emit();
      return { ok: false, errors };
    }

    const beforePieces = clonePieces(this.state.patternPieces);
    const beforeGeometry = { ...this.state.geometryParams };
    const beforeMeasurements = { ...this.state.measurements };
    const beforeSyncStatus = this.state.syncStatus;

    const nextPieces = clonePieces(this.state.patternPieces);
    const updated: DesignPatternPiece = {
      ...nextPieces[pieceId],
      boundary_polygon: candidatePoly,
      area_m2: Number(Math.abs(signedPolygonArea2D(candidatePoly)).toFixed(4)),
      perimeter_m: polygonPerimeter2D(candidatePoly),
    };
    nextPieces[pieceId] = updated;

    const xs = candidatePoly.map((p) => p.x);
    const ys = candidatePoly.map((p) => p.y);
    const newW = Math.max(0.05, Math.max(...xs) - Math.min(...xs));
    const newH = Math.max(0.05, Math.max(...ys) - Math.min(...ys));
    const oldXs = piece.boundary_polygon.map((p) => p.x);
    const oldYs = piece.boundary_polygon.map((p) => p.y);
    const oldW = Math.max(0.05, Math.max(...oldXs) - Math.min(...oldXs));
    const oldH = Math.max(0.05, Math.max(...oldYs) - Math.min(...oldYs));

    const nextGeom = { ...this.state.geometryParams };
    const ratioW = newW / oldW;
    const ratioH = newH / oldH;
    const clamp = (v: number, min: number, max: number) => Math.max(min, Math.min(max, Number(v.toFixed(4))));

    if (pieceId.includes('cuff')) {
      nextGeom.cuffWidthScale = clamp(nextGeom.cuffWidthScale * ratioW, GEOMETRY_PARAM_BOUNDS.cuffWidthScale.min, GEOMETRY_PARAM_BOUNDS.cuffWidthScale.max);
    } else if (pieceId.includes('sleeve')) {
      nextGeom.sleeveWidthScale = clamp(nextGeom.sleeveWidthScale * ratioW, GEOMETRY_PARAM_BOUNDS.sleeveWidthScale.min, GEOMETRY_PARAM_BOUNDS.sleeveWidthScale.max);
      nextGeom.sleeveLengthScale = clamp(nextGeom.sleeveLengthScale * ratioH, GEOMETRY_PARAM_BOUNDS.sleeveLengthScale.min, GEOMETRY_PARAM_BOUNDS.sleeveLengthScale.max);
    } else if (pieceId.includes('leg')) {
      nextGeom.legWidthScale = clamp(nextGeom.legWidthScale * ratioW, GEOMETRY_PARAM_BOUNDS.legWidthScale.min, GEOMETRY_PARAM_BOUNDS.legWidthScale.max);
      nextGeom.legLengthScale = clamp(nextGeom.legLengthScale * ratioH, GEOMETRY_PARAM_BOUNDS.legLengthScale.min, GEOMETRY_PARAM_BOUNDS.legLengthScale.max);
    } else if (pieceId.includes('collar') || pieceId.includes('neck')) {
      nextGeom.collarWidthScale = clamp(nextGeom.collarWidthScale * ratioW, GEOMETRY_PARAM_BOUNDS.collarWidthScale.min, GEOMETRY_PARAM_BOUNDS.collarWidthScale.max);
    } else if (pieceId.includes('waistband')) {
      nextGeom.waistbandWidthScale = clamp(nextGeom.waistbandWidthScale * ratioW, GEOMETRY_PARAM_BOUNDS.waistbandWidthScale.min, GEOMETRY_PARAM_BOUNDS.waistbandWidthScale.max);
    } else if (pieceId.includes('front') || pieceId.includes('back') || pieceId.includes('bodice')) {
      nextGeom.torsoWidthScale = clamp(nextGeom.torsoWidthScale * ratioW, GEOMETRY_PARAM_BOUNDS.torsoWidthScale.min, GEOMETRY_PARAM_BOUNDS.torsoWidthScale.max);
      nextGeom.torsoLengthScale = clamp(nextGeom.torsoLengthScale * ratioH, GEOMETRY_PARAM_BOUNDS.torsoLengthScale.min, GEOMETRY_PARAM_BOUNDS.torsoLengthScale.max);
    }

    const b = this.state.baseMeasurements;
    const chestWidthM = Number((b.chestWidthM * nextGeom.torsoWidthScale).toFixed(4));
    const nextMeasurements: DesignMeasurements = {
      ...b,
      garmentLengthM: Number((b.garmentLengthM * nextGeom.torsoLengthScale).toFixed(4)),
      chestWidthM,
      chestCircumferenceM: halfChestToCircumferenceM(chestWidthM),
      sleeveLengthM: Number((b.sleeveLengthM * nextGeom.sleeveLengthScale).toFixed(4)),
      sleeveWidthM: Number((b.sleeveWidthM * nextGeom.sleeveWidthScale).toFixed(4)),
      collarWidthM: Number((b.collarWidthM * nextGeom.collarWidthScale).toFixed(4)),
      hemWidthM: Number((b.hemWidthM * nextGeom.hemWidthScale).toFixed(4)),
      activePanelWidthM: Number(newW.toFixed(4)),
      activePanelScope: pieceId.includes('front_left') || pieceId.includes('front_right') ? 'PATTERN_PANEL_HALF' : 'PATTERN_PANEL_FULL',
    };

    const nextSync: SyncStatus = Object.values(nextPieces).some((p) => p.verification_state !== 'OBSERVED')
      ? 'SYNCHRONIZED_WITH_UNCERTAINTY'
      : 'SYNCHRONIZED';

    const op: DesignOperationRecord = {
      operationId: `op_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      kind: 'pattern_vertex_edit',
      targetComponent: pieceId,
      source: 'pattern_2d',
      parameters: { pieceId, vertexIndex, nextPoint },
      timestamp: new Date().toISOString(),
    };

    this.undoStack.push({
      operation: op,
      beforeGeometry,
      afterGeometry: nextGeom,
      beforeMaterial: { ...this.state.material },
      afterMaterial: { ...this.state.material },
      beforePieces,
      afterPieces: clonePieces(nextPieces),
      beforeMeasurements,
      afterMeasurements: nextMeasurements,
      beforeSyncStatus,
      afterSyncStatus: nextSync,
      correspondenceVersion: this.state.correspondenceVersion,
    });
    this.redoStack = [];

    this.state = {
      ...this.state,
      designVersion: this.state.designVersion + 1,
      patternVersion: this.state.patternVersion + 1,
      geometryVersion: this.state.geometryVersion + 1,
      geometryParams: nextGeom,
      measurements: nextMeasurements,
      patternPieces: nextPieces,
      patternValidationErrors: [],
      activeOperation: op.kind,
      syncStatus: nextSync,
      lastValidationSummary: `Validated 2D -> 3D edit on '${pieceId}'.`,
    };
    this.emit();
    return { ok: true };
  }

  public applyMaterialEdit(
    patch: Partial<DesignMaterialState>,
    source: 'studio' | 'stylist_chat' = 'studio'
  ): void {
    const beforeMaterial = { ...this.state.material };
    let nextMaterial: DesignMaterialState = {
      ...beforeMaterial,
      ...patch,
      isPhysicallyVerified: false,
    };
    if (patch.preset && patch.preset !== beforeMaterial.preset) {
      const defaults = MATERIAL_PRESET_DEFAULTS[patch.preset] || {};
      nextMaterial = { ...nextMaterial, ...defaults, ...patch, isPhysicallyVerified: false };
    }
    const op: DesignOperationRecord = {
      operationId: `op_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      kind: 'material_edit',
      targetComponent: this.state.selectedComponent || 'material',
      source,
      parameters: patch,
      timestamp: new Date().toISOString(),
    };
    this.undoStack.push({
      operation: op,
      beforeGeometry: { ...this.state.geometryParams },
      afterGeometry: { ...this.state.geometryParams },
      beforeMaterial,
      afterMaterial: nextMaterial,
      beforePieces: clonePieces(this.state.patternPieces),
      afterPieces: clonePieces(this.state.patternPieces),
      beforeMeasurements: { ...this.state.measurements },
      afterMeasurements: { ...this.state.measurements },
      beforeSyncStatus: this.state.syncStatus,
      afterSyncStatus: this.state.syncStatus,
      correspondenceVersion: this.state.correspondenceVersion,
    });
    this.redoStack = [];

    this.state = {
      ...this.state,
      designVersion: this.state.designVersion + 1,
      materialVersion: this.state.materialVersion + 1,
      textureVersion:
        patch.repeatX !== undefined ||
        patch.repeatY !== undefined ||
        patch.offsetX !== undefined ||
        patch.offsetY !== undefined ||
        patch.rotationDeg !== undefined ||
        patch.printScale !== undefined
          ? this.state.textureVersion + 1
          : this.state.textureVersion,
      material: nextMaterial,
      activeOperation: op.kind,
    };
    this.emit();
  }

  public undo(): boolean {
    const delta = this.undoStack.pop();
    if (!delta) return false;
    this.redoStack.push(delta);
    this.state = {
      ...this.state,
      designVersion: this.state.designVersion + 1,
      geometryVersion: this.state.geometryVersion + 1,
      patternVersion: this.state.patternVersion + 1,
      materialVersion: this.state.materialVersion + 1,
      geometryParams: { ...delta.beforeGeometry },
      material: { ...delta.beforeMaterial },
      patternPieces: clonePieces(delta.beforePieces),
      measurements: { ...delta.beforeMeasurements },
      patternValidationErrors: [],
      syncStatus: delta.beforeSyncStatus,
    };
    this.emit();
    return true;
  }

  public redo(): boolean {
    const delta = this.redoStack.pop();
    if (!delta) return false;
    this.undoStack.push(delta);
    this.state = {
      ...this.state,
      designVersion: this.state.designVersion + 1,
      geometryVersion: this.state.geometryVersion + 1,
      patternVersion: this.state.patternVersion + 1,
      materialVersion: this.state.materialVersion + 1,
      geometryParams: { ...delta.afterGeometry },
      material: { ...delta.afterMaterial },
      patternPieces: clonePieces(delta.afterPieces),
      measurements: { ...delta.afterMeasurements },
      patternValidationErrors: [],
      syncStatus: delta.afterSyncStatus,
    };
    this.emit();
    return true;
  }

  public restoreRevisionSnapshot(snapshot: {
    designVersion: number;
    geometryParams: Partial<GeometryDeformationParams>;
    materialConfig: Partial<DesignMaterialState>;
    measurements?: Partial<DesignMeasurements>;
    patternPieces?: Record<string, DesignPatternPiece>;
    syncStatus?: SyncStatus;
  }): void {
    const nextGeom = { ...this.state.geometryParams, ...snapshot.geometryParams };
    const nextMat = { ...this.state.material, ...snapshot.materialConfig, isPhysicallyVerified: false as const };
    const nextMeas = { ...this.state.measurements, ...(snapshot.measurements || {}) };
    this.state = {
      ...this.state,
      designVersion: snapshot.designVersion,
      geometryVersion: this.state.geometryVersion + 1,
      patternVersion: this.state.patternVersion + 1,
      materialVersion: this.state.materialVersion + 1,
      geometryParams: nextGeom,
      material: nextMat,
      measurements: nextMeas,
      patternPieces: snapshot.patternPieces ? clonePieces(snapshot.patternPieces) : this.state.patternPieces,
      syncStatus: snapshot.syncStatus || 'SYNCHRONIZED_WITH_UNCERTAINTY',
    };
    this.emit();
  }
}
