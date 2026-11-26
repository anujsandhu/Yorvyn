/**
 * Phase 16.3.1 Semantic Pattern-to-Mesh Correspondence & Dimensional Integrity Engine
 * Replaces proportional bounding-box guesswork with explicit piece-to-region mappings,
 * topology-change invalidation, construction relationships, and explicit dimensional scopes.
 */

export type SyncStatus =
  | 'SYNCHRONIZED'
  | 'SYNCHRONIZED_WITH_UNCERTAINTY'
  | 'REQUIRES_REBUILD'
  | 'MAPPING_INVALID'
  | 'CONSTRUCTION_CONFLICT'
  | 'VALIDATION_FAILED'
  | 'NOT_SUPPORTED';

export type MeasurementScope =
  | 'BODY_BASELINE'
  | 'PATTERN_PANEL_HALF'
  | 'PATTERN_PANEL_FULL'
  | 'HALF_GARMENT_FLAT'
  | 'FULL_CIRCUMFERENCE'
  | 'EASE_ALLOWANCE'
  | 'SEAM_ALLOWANCE'
  | 'FINISHED_GARMENT';

export type ConstructionRelationType =
  | 'ATTACHED_TO'
  | 'PART_OF'
  | 'CONNECTED_TO'
  | 'OVERLAPS'
  | 'SYMMETRIC_WITH'
  | 'SEWN_TO'
  | 'FOLDED_FROM'
  | 'SUPPORTED_BY_VIEW';

export interface ScopedMeasurement {
  name: string;
  valueM: number;
  valueCm: number;
  unit: 'm';
  scope: MeasurementScope;
  panelId?: string;
  seamAllowanceIncluded: boolean;
}

export interface TopologySignature {
  vertexCount: number;
  triangleCount: number;
  componentIdsHash: string;
}

export interface PatternRegionMapping {
  mappingId: string;
  pieceId: string;
  patternVertexIds: string[];
  patternEdgeIds: string[];
  seamIds: string[];
  localCoordinateSystem: '2D_METRIC_Z_UP_CCW';
  unit: 'm';
  panelScope: MeasurementScope;
  meshId: string;
  meshRegionIds: string[];
  garmentComponentId: string;
  surfaceCorrespondence: 'direct_component' | 'parametric_zone' | 'unmapped';
  uvRegionId: string;
  materialRegionRef: string;
  sourceImageIds: string[];
  sourceViews: string[];
  verificationState: 'OBSERVED' | 'INFERRED' | 'AMBIGUOUS' | 'UNSUPPORTED';
  confidence: number;
  uncertainty: number;
  valid: boolean;
  invalidationReason?: string;
}

export interface SemanticCorrespondenceMap {
  mappingVersion: string;
  garmentId: string;
  candidateId: string | null;
  category: string;
  subcategory: string;
  patternVersion: number;
  geometryVersion: number;
  topologySignature: TopologySignature;
  pieceMappings: Record<string, PatternRegionMapping>;
  relationships: {
    relationId: string;
    relation: ConstructionRelationType;
    sourceId: string;
    targetId: string;
    verificationState: 'OBSERVED' | 'INFERRED' | 'AMBIGUOUS' | 'UNSUPPORTED';
  }[];
  valid: boolean;
  invalidatedReasons: string[];
}

export function panelWidthToHalfChestM(
  panelWidthM: number,
  scope: MeasurementScope,
  symmetryMultiplier = 2
): number {
  if (panelWidthM <= 0) throw new Error('Panel width must be positive.');
  if (scope === 'PATTERN_PANEL_HALF') return Number((panelWidthM * Math.max(1, symmetryMultiplier)).toFixed(5));
  if (scope === 'PATTERN_PANEL_FULL' || scope === 'HALF_GARMENT_FLAT') return Number(panelWidthM.toFixed(5));
  if (scope === 'FULL_CIRCUMFERENCE') return Number((panelWidthM * 0.5).toFixed(5));
  throw new Error(`Unsupported scope '${scope}' for half-chest conversion.`);
}

export function halfChestToCircumferenceM(halfChestM: number): number {
  if (halfChestM <= 0) throw new Error('Half-chest must be positive.');
  return Number((halfChestM * 2).toFixed(5));
}

export function applyPanelEaseToChest(opts: {
  panelWidthM: number;
  panelScope: MeasurementScope;
  easeDeltaM: number;
  applySymmetrically?: boolean;
}): {
  panelWidth: ScopedMeasurement;
  halfGarmentFlat: ScopedMeasurement;
  finishedGarmentCircumference: ScopedMeasurement;
  appliedEaseDelta: ScopedMeasurement;
} {
  const sym = opts.applySymmetrically ?? true;
  const newW = Number((opts.panelWidthM + opts.easeDeltaM).toFixed(5));
  if (newW <= 0.04) throw new Error('Panel width cannot collapse below 4 cm.');

  const halfFlat =
    opts.panelScope === 'PATTERN_PANEL_HALF'
      ? Number((sym ? newW * 2 : opts.panelWidthM * 2 + opts.easeDeltaM).toFixed(5))
      : newW;

  const fullCirc =
    opts.panelScope === 'PATTERN_PANEL_HALF'
      ? Number((sym ? halfFlat * 2 : opts.panelWidthM * 4 + opts.easeDeltaM).toFixed(5))
      : Number((sym ? newW * 2 : opts.panelWidthM * 2 + opts.easeDeltaM).toFixed(5));

  const mk = (name: string, valM: number, scope: MeasurementScope): ScopedMeasurement => ({
    name,
    valueM: valM,
    valueCm: Number((valM * 100).toFixed(2)),
    unit: 'm',
    scope,
    seamAllowanceIncluded: false,
  });

  return {
    panelWidth: mk('panel_width', newW, opts.panelScope),
    halfGarmentFlat: mk('half_garment_chest', halfFlat, 'HALF_GARMENT_FLAT'),
    finishedGarmentCircumference: mk('chest_circumference', fullCirc, 'FULL_CIRCUMFERENCE'),
    appliedEaseDelta: mk('panel_ease_delta', Number(opts.easeDeltaM.toFixed(5)), 'EASE_ALLOWANCE'),
  };
}

export function resolvePieceToMeshRegions(
  pieceId: string,
  parentComponent: string,
  available3DRegions: string[]
): { meshRegionIds: string[]; surface: 'direct_component' | 'parametric_zone' | 'unmapped'; uvRegion: string } {
  const avail = new Set(available3DRegions.map((s) => s.toLowerCase()));
  const pid = pieceId.toLowerCase();
  const has = (name: string) => avail.has(name.toLowerCase());

  if (pid.includes('left_sleeve')) {
    return { meshRegionIds: ['left_sleeve'], surface: has('left_sleeve') ? 'direct_component' : 'parametric_zone', uvRegion: 'sleeve_left_uv' };
  }
  if (pid.includes('right_sleeve')) {
    return { meshRegionIds: ['right_sleeve'], surface: has('right_sleeve') ? 'direct_component' : 'parametric_zone', uvRegion: 'sleeve_right_uv' };
  }
  if (pid.includes('left_cuff')) {
    return { meshRegionIds: ['left_cuff'], surface: has('left_cuff') ? 'direct_component' : 'parametric_zone', uvRegion: 'cuff_uv' };
  }
  if (pid.includes('right_cuff')) {
    return { meshRegionIds: ['right_cuff'], surface: has('right_cuff') ? 'direct_component' : 'parametric_zone', uvRegion: 'cuff_uv' };
  }
  if (pid.includes('hood')) {
    return { meshRegionIds: ['hood_cowl'], surface: has('hood_cowl') ? 'direct_component' : 'parametric_zone', uvRegion: 'hood_uv' };
  }
  if (pid.includes('kangaroo')) {
    if (has('kangaroo_pocket') || avail.size === 0) {
      return { meshRegionIds: ['kangaroo_pocket'], surface: has('kangaroo_pocket') ? 'direct_component' : 'parametric_zone', uvRegion: 'pocket_uv' };
    }
    return { meshRegionIds: [], surface: 'unmapped', uvRegion: 'pocket_uv' };
  }
  if (pid.includes('back_pocket')) {
    return { meshRegionIds: [], surface: 'unmapped', uvRegion: 'pocket_uv' };
  }
  if (pid.includes('collar') || pid.includes('neckband')) {
    const direct = has('lapels_and_collar') ? 'lapels_and_collar' : has('collar_and_stand') ? 'collar_and_stand' : null;
    return { meshRegionIds: [direct || 'lapels_and_collar'], surface: direct ? 'direct_component' : 'parametric_zone', uvRegion: 'collar_uv' };
  }
  if (pid.includes('left_front_leg') || pid.includes('left_back_leg')) {
    return { meshRegionIds: ['left_leg'], surface: has('left_leg') ? 'direct_component' : 'parametric_zone', uvRegion: 'left_leg_uv' };
  }
  if (pid.includes('right_front_leg') || pid.includes('right_back_leg')) {
    return { meshRegionIds: ['right_leg'], surface: has('right_leg') ? 'direct_component' : 'parametric_zone', uvRegion: 'right_leg_uv' };
  }
  if (pid.includes('waistband')) {
    return {
      meshRegionIds: [has('waistband_and_pelvis') ? 'waistband_and_pelvis' : 'main_torso'],
      surface: has('waistband_and_pelvis') ? 'direct_component' : 'parametric_zone',
      uvRegion: 'waistband_uv',
    };
  }
  if (pid.includes('front') || pid.includes('back') || pid.includes('bodice') || pid.includes('skirt') || pid.includes('hem') || pid.includes('placket')) {
    return { meshRegionIds: ['main_torso'], surface: has('main_torso') ? 'direct_component' : 'parametric_zone', uvRegion: `${parentComponent}_uv` };
  }
  return { meshRegionIds: [], surface: 'unmapped', uvRegion: 'main_uv_atlas' };
}

export function validateMappingTopology(
  corr: SemanticCorrespondenceMap,
  vertexCount: number,
  triangleCount: number
): { valid: boolean; status: SyncStatus; reasons: string[] } {
  const reasons: string[] = [];
  if (corr.topologySignature.vertexCount > 0 && corr.topologySignature.vertexCount !== vertexCount) {
    reasons.push(`Vertex count changed (${corr.topologySignature.vertexCount} -> ${vertexCount}); correspondence invalidated.`);
  }
  if (corr.topologySignature.triangleCount > 0 && corr.topologySignature.triangleCount !== triangleCount) {
    reasons.push(`Triangle count changed (${corr.topologySignature.triangleCount} -> ${triangleCount}); correspondence invalidated.`);
  }
  if (reasons.length > 0 || !corr.valid) {
    return { valid: false, status: 'MAPPING_INVALID', reasons: reasons.length ? reasons : corr.invalidatedReasons };
  }
  const hasUncertain = Object.values(corr.pieceMappings).some((m) => m.verificationState !== 'OBSERVED');
  return { valid: true, status: hasUncertain ? 'SYNCHRONIZED_WITH_UNCERTAINTY' : 'SYNCHRONIZED', reasons: [] };
}
