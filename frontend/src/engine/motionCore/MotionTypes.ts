/**
 * YORVYN MotionCore (Phase 16.9) — Unified Animation, Garment Dynamics & Compute Telemetry Contracts
 */

import type * as THREE from 'three';

export type MotionState =
  | 'IDLE'
  | 'WALK'
  | 'RUN'
  | 'TURN'
  | 'RAISE_ARMS'
  | 'BEND'
  | 'SIT'
  | 'STAND'
  | 'CUSTOM'
  | 'PAUSED'
  | 'RESETTING'
  | 'ERROR';

export type MotionQualityTier = 'low' | 'balanced' | 'high' | 'maximum';

export type ComputeBackendKind =
  | 'cpu_xpbd'
  | 'webworker_xpbd'
  | 'wasm_simd_xpbd'
  | 'webgpu_experimental';

export type RenderBackendChoice = 'webgl2' | 'software_fallback';

export type ExportAnimationKind =
  | 'skeletal_animation_export'
  | 'skeletal_with_garment_deformation'
  | 'baked_simulation_export'
  | 'static_garment_export';

export interface MotionTransitionPolicy {
  blendDurationSeconds: number;
  priority: number;
  loop: boolean;
  returnToState?: MotionState;
}

export interface SkeletonCompatibilityReport {
  isCompatible: boolean;
  boneCount: number;
  matchedCanonicalBones: number;
  boneMap: Record<string, string>;
  unmappedBones: string[];
  missingCoreBones: string[];
  hasCycle: boolean;
  issues: string[];
}

export interface PoseLandmarkPoint {
  name: string;
  x: number;
  y: number;
  z: number;
  confidence: number;
}

export interface PoseInputFrame {
  timestampMs: number;
  landmarks: PoseLandmarkPoint[];
  source: 'mediapipe_live' | 'movenet_adapter' | 'offline_sequence' | 'none';
}

export interface IKTargetSpec {
  chain: 'left_arm' | 'right_arm' | 'left_leg' | 'right_leg';
  targetWorld: THREE.Vector3;
  poleWorld?: THREE.Vector3;
  weight: number; // [0..1]
}

export interface AdaptiveFabricPhysicsSpec {
  id: string;
  category: string;
  fabricFamily: string;
  arealDensityKgM2: number;
  stretchResistance: number;
  shearResistance: number;
  bendingResistance: number;
  damping: number;
  friction: number;
  thicknessM: number;
  anisotropyRatio: number;
  seamStiffness: number;
  secondarySwayGain: number;
  surfaceRoughnessVisual: number;
  /** Explicitly labeled estimated coefficient (never physical laboratory measurements). */
  isMeasuredPhysical: false;
  constructionProvenance: 'observed_multi_view' | 'single_view_with_inferred_back' | 'category_default';
}

export interface SecondaryMotionNodeConfig {
  id: string;
  kind: 'sleeve' | 'hem' | 'hood' | 'panel' | 'hair' | 'accessory';
  object: THREE.Object3D;
  restLocalPos: THREE.Vector3;
  restLocalQuat: THREE.Quaternion;
  stiffness: number;
  damping: number;
  maxAngleRad: number;
  maxOffsetM: number;
  velocity: THREE.Vector3;
  angularOffset: THREE.Vector3;
}

export interface MotionPerformanceTelemetry {
  state: MotionState;
  qualityTier: MotionQualityTier;
  renderBackend: RenderBackendChoice;
  physicsBackend: ComputeBackendKind;
  webgpuExperimentalOnly: true;
  isSoftwareRendered: boolean;
  renderFrameMs: number;
  simulationStepMs: number;
  p50FrameMs: number;
  p95FrameMs: number;
  p99FrameMs: number;
  fps: number;
  droppedFrames: number;
  activeClothVertices: number;
  constraintCount: number;
  collisionCount: number;
  secondaryNodeCount: number;
  workerExecutionMs: number;
  memoryMb: number | null;
}

export interface AnimatedExportValidation {
  isValid: boolean;
  exportKind: ExportAnimationKind;
  clipCount: number;
  boneCount: number;
  hasGarmentAttachment: boolean;
  hasBakedClothDeformation: boolean;
  byteLength: number;
  issues: string[];
}
