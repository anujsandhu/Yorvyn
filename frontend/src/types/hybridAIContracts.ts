/**
 * YORVYN — Unified Hybrid AI Processing Contracts (Phase 13)
 * Defines shared schemas for client-side edge computing, server-side GPU processing,
 * and unified orchestration.
 */

export type WorkloadType =
  | 'IMAGE_PREPROCESS'
  | 'BLUR_DETECTION'
  | 'COLOR_PALETTE'
  | 'GARMENT_CLASSIFICATION'
  | 'GARMENT_SEGMENTATION'
  | 'POSE_ESTIMATION'
  | 'NEURAL_RECONSTRUCTION'
  | 'TEXTURE_SYNTHESIS'
  | 'MESH_VALIDATION'
  | 'CLOTH_SIMULATION'
  | 'AVATAR_FITTING';

export type RoutingPolicy =
  | 'AUTO'
  | 'LOCAL_PREFERRED'
  | 'CLOUD_PREFERRED'
  | 'LOCAL_REQUIRED'
  | 'CLOUD_REQUIRED';

export type ExecutionLocation =
  | 'CLIENT_WEBGPU'
  | 'CLIENT_WASM'
  | 'CLIENT_WORKER'
  | 'CLOUD_GPU'
  | 'CLOUD_CPU'
  | 'HYBRID_COLLABORATIVE';

export type DeviceTier = 'LOW' | 'MID' | 'HIGH' | 'ULTRA';

export interface DeviceCapabilities {
  webgpuSupported: boolean;
  webglSupported: boolean;
  simdWasmSupported: boolean;
  webWorkersSupported: boolean;
  hardwareConcurrency: number;
  deviceMemoryGb?: number;
  maxTextureSize: number;
  deviceTier: DeviceTier;
  networkEffectiveType?: '4g' | '3g' | '2g' | 'slow-2g';
  networkSaveData?: boolean;
  downlinkSpeedMbps?: number;
  roundTripTimeMs?: number;
  batteryLevel?: number;
  batteryCharging?: boolean;
  userProcessingPreference: RoutingPolicy;
}

export interface HybridGarmentFeatures {
  category: string;
  subcategory: string;
  confidence_score: number;
  palette: string[];
  primary_color_hex: string;
  primary_color_name: string;
  secondary_color_name?: string;
  pattern: string;
  material_hint: string;
  fit: string;
  neckline_type?: string;
  sleeve_length?: string;
  has_hood?: boolean;
  has_kangaroo_pocket?: boolean;
  has_collar?: boolean;
  components?: string[];
}

export interface HybridGarmentProvenance {
  original_ai_prediction?: HybridGarmentFeatures;
  edge_prediction?: HybridGarmentFeatures;
  cloud_prediction?: HybridGarmentFeatures;
  user_correction?: Partial<HybridGarmentFeatures>;
  final_authoritative_features: HybridGarmentFeatures;
  execution_location: ExecutionLocation;
  routing_reason: string;
  edge_latency_ms?: number;
  cloud_latency_ms?: number;
  total_duration_ms: number;
  bandwidth_saved_bytes?: number;
  model_id: string;
  model_version: string;
}

export interface HybridPreprocessResult {
  processedBlob: Blob;
  previewDataUrl: string;
  dimensions: { width: number; height: number };
  originalSizeBytes: number;
  compressedSizeBytes: number;
  compressionRatio: number;
  isBlurry: boolean;
  blurVariance: number;
  dominantColors: string[];
  durationMs: number;
}

export interface HybridWorkloadPlan {
  workloadType: WorkloadType;
  selectedLocation: ExecutionLocation | null;
  policy: RoutingPolicy;
  status?: 'SUCCESS' | 'POLICY_UNSATISFIED';
  reason: string;
  estimatedDurationMs: number;
  estimatedMemoryMb: number;
  fallbackLocation: ExecutionLocation | null;
  errorCode?: string;
}

export interface HybridProcessingRequest {
  requestId: string;
  workloadType: WorkloadType;
  policy: RoutingPolicy;
  clientCapabilities: Partial<DeviceCapabilities>;
  payloadRef?: string;
  imageBlob?: Blob;
  metadata?: Record<string, any>;
  timestamp: string;
}

export interface HybridProcessingResponse<T = any> {
  requestId: string;
  status: 'success' | 'fallback' | 'failed';
  executionLocation: ExecutionLocation;
  modelId: string;
  modelVersion: string;
  durationMs: number;
  result?: T;
  provenance: HybridGarmentProvenance;
  fallbackReason?: string;
  error?: string;
}

