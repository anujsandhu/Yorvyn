/**
 * YORVYN — Cloth Physics & Realistic Fabric Simulation Engine (Phase 10)
 * Type definitions, data contracts, and physical property interfaces.
 */

import * as THREE from 'three';

export type FabricProfileId = 'cotton' | 'denim' | 'silk' | 'wool' | 'leather' | 'knitted' | 'knitwear' | 'synthetic' | 'linen';

export type SimulationQualityMode = 'high' | 'balanced' | 'performance' | 'preview';

export type ClothSimulationState = 'uninitialized' | 'ready' | 'simulating' | 'paused' | 'error';

/**
 * Physical properties of a fabric profile.
 * All profiles are configurable approximations based on asset metadata,
 * explicitly not claiming exact laboratory physical measurements.
 */
export interface FabricPhysicsProfile {
  id: FabricProfileId;
  name: string;
  description: string;
  /** Mass per unit area or particle relative mass (kg/m²), default ~ 0.22 */
  mass: number;
  /** Stretch resistance factor in [0.0, 1.0] (higher = less stretchable) */
  stretchStiffness: number;
  /** Bending resistance factor in [0.0, 1.0] (higher = stiffer folds/creases) */
  bendingStiffness: number;
  /** Shear resistance factor in [0.0, 1.0] */
  shearStiffness: number;
  /** Velocity damping per second to simulate air drag and internal friction */
  damping: number;
  /** Dynamic friction when sliding across body collision surfaces */
  friction: number;
  /** Approximate fabric thickness in meters (used for collision clearance) */
  thickness: number;
  /** Gravity multiplier applied to standard -9.81 m/s² */
  gravityMultiplier: number;
  /** Honesty guarantee: true for all estimated profiles */
  isEstimate: boolean;
}

/**
 * Configuration options per simulation quality mode.
 */
export interface SimulationQualitySettings {
  mode: SimulationQualityMode;
  /** Number of physics substeps per frame (e.g. 2–4) */
  subSteps: number;
  /** Solver constraint projection iterations per substep (e.g. 4–15) */
  solverIterations: number;
  /** Whether 2-ring isometric bending constraints are active */
  enableBending: boolean;
  /** Whether body collision response is active */
  enableCollisions: boolean;
  /** Level of detail for avatar collision proxies */
  collisionProxyDetail: 'full' | 'simplified' | 'minimal';
  /** Fixed physics delta time in seconds (e.g. 1/60 or 1/120) */
  fixedTimeStep: number;
  /** Maximum allowable vertex count for live simulation before auto-downscaling */
  maxActiveVertices: number;
}

/**
 * Represents a body collision capsule or hull proxy.
 */
export interface BodyCollisionHull {
  name: string;
  boneName: string;
  alternativeBoneNames: string[];
  type: 'capsule' | 'sphere';
  /** Relative local start point offset from bone head */
  localStart: [number, number, number];
  /** Relative local end point offset from bone tail */
  localEnd: [number, number, number];
  /** Current world-space start coordinates */
  worldStart: THREE.Vector3;
  /** Current world-space end coordinates */
  worldEnd: THREE.Vector3;
  /** Capsule radius at top/start */
  radiusStart: number;
  /** Capsule radius at bottom/end */
  radiusEnd: number;
  /** Friction modifier */
  friction: number;
}

/**
 * Particle state for a simulated garment mesh.
 * Stored in typed Float32Arrays for zero garbage-collection during simulation loops.
 */
export interface ClothParticleState {
  count: number;
  /** Flat [x, y, z, ...] current positions */
  positions: Float32Array;
  /** Flat [x, y, z, ...] previous positions for Verlet integration */
  prevPositions: Float32Array;
  /** Flat [x, y, z, ...] initial bind positions */
  restPositions: Float32Array;
  /** Flat [vx, vy, vz, ...] instantaneous velocities */
  velocities: Float32Array;
  /** Inverse masses: 0.0 for pinned/anchor vertices, > 0 for free cloth */
  invMasses: Float32Array;
  /** Set of pinned vertex indices that follow skeletal motion strictly */
  pinnedIndices: Set<number>;
}

/**
 * Structural distance and bending constraints for the cloth mesh.
 */
export interface ClothConstraints {
  /** Pairs of vertex indices [p1, p2, p1, p2, ...] for stretch/shear edges */
  distancePairs: Uint32Array;
  /** Rest lengths for distance pairs */
  restLengths: Float32Array;
  /** Pairs of vertex indices for 2-hop or opposite-triangle bending edges */
  bendingPairs: Uint32Array;
  /** Rest lengths for bending pairs */
  bendingRestLengths: Float32Array;
}

/**
 * Real-time diagnostic metrics for cloth simulation performance and stability.
 */
export interface ClothDiagnosticMetrics {
  state: ClothSimulationState;
  qualityMode: SimulationQualityMode;
  fps: number;
  stepTimeMs: number;
  particleCount: number;
  distanceConstraintCount: number;
  bendingConstraintCount: number;
  activeCollisionHulls: number;
  penetrationResolutions: number;
  maxDisplacementMeters: number;
  hasExploded: boolean;
  isDegraded: boolean;
  fabricProfile: FabricProfileId;
}

/**
 * Metadata and handles for a currently simulated garment in Three.js.
 */
export interface SimulatedGarment {
  id: string;
  name: string;
  category: 'top' | 'bottom' | 'dress' | 'outerwear' | 'skirt';
  mesh: THREE.Mesh;
  geometry: THREE.BufferGeometry;
  particleState: ClothParticleState;
  constraints: ClothConstraints;
  fabric: FabricPhysicsProfile;
  anchorBoneName?: string;
  isBakedOnly?: boolean;
}

