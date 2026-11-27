/**
 * YORVYN — ADVANCED AI GARMENT RECONSTRUCTION ENGINE (Phase 3)
 * 
 * Provides strongly-typed data contracts for:
 * 1. Universal multi-view clothing image upload & validation (front, back, sides, details)
 * 2. Background removal & transparent PNG segmentation with mask touch-up
 * 3. Garment understanding & component segmentation (hood, kangaroo pocket, drawstrings, etc.)
 * 4. Multi-image matching, view classification, and conflict detection
 * 5. 3D geometry reconstruction, connected sleeve topology, and manifold validation
 * 6. PBR texture synthesis with photographic UV embedding
 * 7. Quality validation reporting, avatar fitting, and cloth physics integration
 */

export type GarmentReconstructionCategory = 
  | 'top' 
  | 'bottom' 
  | 'outerwear' 
  | 'dress' 
  | 'skirt' 
  | 'footwear';

export type GarmentSubcategory =
  | 'hoodie'
  | 'sweatshirt'
  | 'tshirt'
  | 'shirt'
  | 'jacket'
  | 'coat'
  | 'jeans'
  | 'trousers'
  | 'shorts'
  | 'dress'
  | 'skirt'
  | 'sneakers'
  | 'boots';

export type FabricType = 
  | 'cotton' 
  | 'fleece'
  | 'denim' 
  | 'leather' 
  | 'wool' 
  | 'silk' 
  | 'polyester' 
  | 'linen' 
  | 'knitted';

export interface FabricPBRProperties {
  type: FabricType;
  roughness: number;     // 0.0 - 1.0
  metalness: number;     // 0.0 - 1.0
  clearcoat?: number;    // For leather / coated materials
  sheen?: number;        // For silk / satin
  anisotropy?: number;
  normalIntensity: number;
  isEstimated: true;     // Transparent disclaimer: derived from optical heuristics
  editorialNotes: string;
}

export interface MultiViewInput {
  front: File | Blob | string; // Base64 or Blob
  back?: File | Blob | string;
  side?: File | Blob | string;
  leftSide?: File | Blob | string;
  rightSide?: File | Blob | string;
  hoodDetail?: File | Blob | string;
  pocketDetail?: File | Blob | string;
  sleeveDetail?: File | Blob | string;
  fabricMacro?: File | Blob | string;
}

export interface ImageValidationResult {
  isValid: boolean;
  issues: string[];
  warnings: string[];
  resolution?: { width: number; height: number };
  aspectRatio?: number;
  hasCompleteGarment: boolean;
  requiresAdditionalView: boolean;
  recommendedViewReason?: string;
  detectedFormat?: string;
}

export interface MaskTouchupAction {
  x: number;
  y: number;
  radius: number;
  mode: 'erase' | 'restore';
}

export type GarmentImageViewType = 
  | 'flat_lay_front' 
  | 'flat_lay_back' 
  | 'side_view' 
  | 'mannequin_view' 
  | 'person_wearing_view' 
  | 'detail_shot' 
  | 'catalog_product';

export interface GarmentComponentBounds {
  type: GarmentComponentType;
  x: number;
  y: number;
  width: number;
  height: number;
  confidence: number;
}

export interface UVIsland {
  uMin: number;
  uMax: number;
  vMin: number;
  vMax: number;
}

/**
 * Standard Canonical Garment UV Islands (Phase 5 Non-Overlapping Layout)
 * Eliminates monolithic photographic decaling and ensures clean component unwrapping.
 */
export const GARMENT_UV_ISLANDS = {
  FRONT_TORSO: { uMin: 0.04, uMax: 0.46, vMin: 0.04, vMax: 0.50 } as UVIsland,
  BACK_TORSO:  { uMin: 0.54, uMax: 0.96, vMin: 0.04, vMax: 0.50 } as UVIsland,
  LEFT_SLEEVE: { uMin: 0.04, uMax: 0.46, vMin: 0.54, vMax: 0.74 } as UVIsland,
  RIGHT_SLEEVE:{ uMin: 0.54, uMax: 0.96, vMin: 0.54, vMax: 0.74 } as UVIsland,
  HOOD:        { uMin: 0.04, uMax: 0.46, vMin: 0.76, vMax: 0.96 } as UVIsland,
  POCKET_TRIM: { uMin: 0.54, uMax: 0.96, vMin: 0.76, vMax: 0.96 } as UVIsland
} as const;

export interface GarmentSegmentationResult {
  segmentedDataUrl: string;
  maskDataUrl: string;
  backgroundMaskUrl?: string;
  transparentPngUrl?: string;
  dominantColorHex: string;
  secondaryColorHex?: string;
  pureFabricSampleRgb?: [number, number, number];
  palette: string[];
  detectedPattern: 'solid' | 'striped' | 'plaid' | 'graphic' | 'floral' | 'textured_knit';
  boundingBox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  hasInternalOpenings: boolean;
  edgeContrastScore: number; // 0 - 100
  segmentationConfidence?: number;
  silhouetteContour?: Array<{ x: number; y: number }>;
  componentBounds?: GarmentComponentBounds[];
  viewType?: GarmentImageViewType;
}

export type GarmentComponentType =
  | 'front_torso'
  | 'back_torso'
  | 'left_sleeve'
  | 'right_sleeve'
  | 'hood'
  | 'kangaroo_pocket'
  | 'drawstrings'
  | 'ribbed_cuffs'
  | 'ribbed_waistband'
  | 'collar'
  | 'placket'
  | 'buttons'
  | 'left_leg'
  | 'right_leg'
  | 'waistband'
  | 'fly'
  | 'hem';

export type ComponentSourceStatus = 'observed' | 'inferred' | 'procedural' | 'manual';

export interface GarmentComponentPart {
  type: GarmentComponentType;
  name: string;
  status: ComponentSourceStatus;
  confidence: number; // 0 - 1
  description: string;
  triangleCount?: number;
}

export interface GarmentIntelligenceFeatures {
  category: GarmentReconstructionCategory;
  subcategory: GarmentSubcategory;
  silhouette: 'relaxed' | 'tailored' | 'oversized' | 'slim' | 'regular';
  hasHood: boolean;
  hasKangarooPocket: boolean;
  hasDrawstrings: boolean;
  hasRibbedTrim: boolean;
  sleeveStyle: 'set_in' | 'raglan' | 'drop_shoulder' | 'sleeveless';
  sleeveLength: 'sleeveless' | 'short' | 'three_quarter' | 'long';
  necklineType: 'crewneck' | 'v_neck' | 'hoodie_collar' | 'collar' | 'scoop' | 'turtle';
  primaryColorName: string;
  primaryColorHex: string;
  secondaryColorName?: string;
  secondaryColorHex?: string;
  palette: string[];
  pattern: string;
  materialHint: FabricType;
  components: GarmentComponentPart[];
  confidenceScore: number;
  qualityNotes: string;
}

export interface MultiImageMatchResult {
  isConsistent: boolean;
  confidence: number; // 0 - 1
  mismatchedViews: string[];
  detectedGarmentIdMatch: boolean;
  colorVarianceScore: number;
  notes: string[];
}

export interface BoundaryLoop {
  name: 'neck' | 'left_cuff' | 'right_cuff' | 'waist' | 'left_ankle' | 'right_ankle' | 'hem' | 'hood_aperture' | 'pocket_left' | 'pocket_right';
  vertexIndices: number[];
  center: [number, number, number];
  radius: number;
}

export interface ReconstructedMeshGeometry {
  positions: Float32Array;
  normals: Float32Array;
  uvs: Float32Array;
  indices: Uint32Array;
  boundaryLoops: BoundaryLoop[];
  vertexCount: number;
  triangleCount: number;
  boundingBox: {
    min: [number, number, number];
    max: [number, number, number];
  };
  components?: GarmentComponentPart[];
  componentTags?: string[];
  componentIndices?: Uint8Array;
}

export interface GarmentQualityCheckItem {
  name: string;
  status: 'pass' | 'warning' | 'fail';
  detail: string;
}

export interface GarmentQualityReport {
  overallScore: number; // 0 - 100
  status: 'pass' | 'warning' | 'fail';
  checks: GarmentQualityCheckItem[];
  observedComponents: string[];
  inferredComponents: string[];
  proceduralComponents: string[];
  actionableSuggestions: string[];
}

export interface MeshTopologyValidationResult {
  isValid: boolean;
  isManifold: boolean;
  hasDegenerateTriangles: boolean;
  vertexCount: number;
  triangleCount: number;
  issues: string[];
  warnings: string[];
  qualityScore: number; // 0 - 100
  qualityReport?: GarmentQualityReport;
}

export interface GarmentFittingMetadata {
  targetSlot: 'top' | 'bottom' | 'outerwear' | 'full_outfit';
  suggestedScale: [number, number, number];
  suggestedOffset: [number, number, number];
  occlusionMaskIds: string[];
  anchorBone: string;
  tightnessFactor: number;
  rigType: 'Ara3D_Humanoid_20Bone';
}

export interface ReconstructedGarmentAsset {
  id: string;
  name: string;
  category: GarmentReconstructionCategory;
  subcategory: string;
  fabric: FabricPBRProperties;
  geometry: ReconstructedMeshGeometry;
  fittingMetadata: GarmentFittingMetadata;
  qualityScore: number; // 0 - 100
  qualityReport?: GarmentQualityReport;
  intelligence?: GarmentIntelligenceFeatures;
  glbBlobUrl?: string;
  glbArrayBuffer?: ArrayBuffer;
  thumbnailUrl?: string;
  textureDataUrl?: string;
  normalMapDataUrl?: string;
  createdAt: string;
  knownLimitations: string[];
}

export type ReconstructionJobStatus = 
  | 'queued'
  | 'validating_images'
  | 'segmenting_garment'
  | 'analyzing_intelligence'
  | 'reconstructing_geometry'
  | 'synthesizing_textures'
  | 'validating_topology'
  | 'assembling_glb'
  | 'completed'
  | 'failed'
  | 'cancelled';

export interface ReconstructionJobProgress {
  jobId: string;
  status: ReconstructionJobStatus;
  progressPercent: number; // 0 - 100
  currentStage: string;
  error?: string;
  result?: ReconstructedGarmentAsset;
}
