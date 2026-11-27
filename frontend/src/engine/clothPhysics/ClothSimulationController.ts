/**
 * YORVYN — Master Cloth Simulation Controller (Phase 10)
 * Orchestrates real-time fabric physics, decoupled fixed-timestep physics stepping,
 * avatar skeleton collision synchronization, inertial force response, and Three.js mesh deformation.
 */

import * as THREE from 'three';
import {
  ClothSimulationState,
  FabricProfileId,
  SimulatedGarment,
  SimulationQualityMode
} from './types';
import { FabricMaterialProfile } from './FabricMaterialProfile';
import { ClothCollisionSystem } from './ClothCollisionSystem';
import { ClothConstraintSolver } from './ClothConstraintSolver';
import { GarmentDeformationAdapter } from './GarmentDeformationAdapter';
import { ClothSimulationQualityManager } from './ClothSimulationQualityManager';
import { ClothSimulationDiagnostics } from './ClothSimulationDiagnostics';

export class ClothSimulationController {
  private activeGarments: Map<string, SimulatedGarment> = new Map();
  private collisionSystem: ClothCollisionSystem;
  private qualityManager: ClothSimulationQualityManager;
  private diagnostics: ClothSimulationDiagnostics;
  private state: ClothSimulationState = 'uninitialized';
  private modelRoot: THREE.Object3D | null = null;

  // Fixed timestep physics decoupling
  private timeAccumulator: number = 0;
  private readonly MAX_FRAME_TIME: number = 0.10; // 100ms max to prevent spiral of death

  // Avatar movement and inertia tracking
  private prevModelPos: THREE.Vector3 = new THREE.Vector3();
  private prevModelRotY: number = 0;
  private inertialForce: [number, number, number] = [0, 0, 0];
  private isEnabled: boolean = true;

  constructor(initialQuality: SimulationQualityMode = 'balanced') {
    this.collisionSystem = new ClothCollisionSystem();
    this.qualityManager = new ClothSimulationQualityManager(initialQuality);
    this.diagnostics = new ClothSimulationDiagnostics();
    this.diagnostics.updateMetrics({
      qualityMode: initialQuality,
      state: 'uninitialized'
    });
  }

  /**
   * Initializes the simulation controller with the active Three.js avatar model.
   */
  public init(modelRoot: THREE.Object3D): void {
    this.modelRoot = modelRoot;
    this.collisionSystem.syncWithAvatar(modelRoot);
    this.prevModelPos.copy(modelRoot.position);
    this.prevModelRotY = modelRoot.rotation.y;
    this.state = this.activeGarments.size > 0 ? 'simulating' : 'ready';
    this.diagnostics.updateMetrics({ state: this.state });
  }

  /**
   * Attaches a garment mesh to the real-time cloth simulation engine.
   */
  public attachGarment(
    mesh: THREE.Mesh,
    category: 'top' | 'bottom' | 'dress' | 'outerwear' | 'skirt',
    fabricProfileId: FabricProfileId = 'cotton',
    garmentId: string = 'active_garment'
  ): SimulatedGarment {
    // Detach if already exists
    if (this.activeGarments.has(garmentId)) {
      this.detachGarment(garmentId);
    }

    const fabric = FabricMaterialProfile.getProfile(fabricProfileId);
    const simGarment = GarmentDeformationAdapter.prepareGarment(
      mesh,
      category,
      fabric,
      garmentId
    );

    this.activeGarments.set(garmentId, simGarment);
    this.state = 'simulating';

    // Update diagnostics
    let totalParticles = 0;
    let totalDistConstraints = 0;
    let totalBendConstraints = 0;
    this.activeGarments.forEach((g) => {
      totalParticles += g.particleState.count;
      totalDistConstraints += g.constraints.distancePairs.length / 2;
      totalBendConstraints += g.constraints.bendingPairs.length / 2;
    });

    this.diagnostics.updateMetrics({
      state: this.state,
      particleCount: totalParticles,
      distanceConstraintCount: totalDistConstraints,
      bendingConstraintCount: totalBendConstraints,
      activeCollisionHulls: this.collisionSystem.getHulls().length,
      fabricProfile: fabricProfileId
    });

    return simGarment;
  }

  /**
   * Detaches and resets a simulated garment.
   */
  public detachGarment(garmentId: string): void {
    const simGarment = this.activeGarments.get(garmentId);
    if (simGarment) {
      GarmentDeformationAdapter.resetToRestPose(simGarment);
      this.activeGarments.delete(garmentId);
    }

    if (this.activeGarments.size === 0) {
      this.state = 'ready';
    }

    this.diagnostics.updateMetrics({
      state: this.state,
      particleCount: 0,
      distanceConstraintCount: 0,
      bendingConstraintCount: 0
    });
  }

  /**
   * Switches the physical fabric profile for an active garment.
   */
  public setFabricProfile(garmentId: string, profileId: FabricProfileId): boolean {
    const simGarment = this.activeGarments.get(garmentId);
    if (!simGarment) return false;

    const newProfile = FabricMaterialProfile.getProfile(profileId);
    simGarment.fabric = newProfile;

    // Recalculate inverse masses for free particles
    const baseInvMass = 1.0 / Math.max(0.01, newProfile.mass);
    for (let i = 0; i < simGarment.particleState.count; i++) {
      if (!simGarment.particleState.pinnedIndices.has(i)) {
        simGarment.particleState.invMasses[i] = baseInvMass;
      }
    }

    this.diagnostics.updateMetrics({ fabricProfile: profileId });
    return true;
  }

  /**
   * Updates the simulation quality mode (High, Balanced, Performance, Preview).
   */
  public setQualityMode(mode: SimulationQualityMode): void {
    this.qualityManager.setMode(mode);
    this.diagnostics.updateMetrics({ qualityMode: mode });
  }

  /**
   * Master simulation update tick. Call this once inside the Three.js requestAnimationFrame render loop.
   * Decouples rendering frame-rate from physics simulation rate using fixed time-step accumulation.
   */
  public step(deltaTime: number): void {
    if (!this.isEnabled || this.state !== 'simulating' || this.activeGarments.size === 0) {
      return;
    }

    const startTime = performance.now();
    const clampedDelta = Math.min(deltaTime, this.MAX_FRAME_TIME);
    this.timeAccumulator += clampedDelta;

    const settings = this.qualityManager.getSettings();
    const fixedDt = settings.fixedTimeStep;

    // Synchronize avatar collision hulls with skeleton motion
    if (this.modelRoot) {
      this.collisionSystem.syncWithAvatar(this.modelRoot);

      // Compute avatar inertial drag forces from rotation / translation
      if (clampedDelta > 1e-5) {
        const dX = (this.modelRoot.position.x - this.prevModelPos.x) / clampedDelta;
        const dZ = (this.modelRoot.position.z - this.prevModelPos.z) / clampedDelta;
        const dRot = (this.modelRoot.rotation.y - this.prevModelRotY) / clampedDelta;

        // Inertial reaction is opposite to character acceleration
        this.inertialForce = [
          -dX * 1.5 - Math.sin(this.modelRoot.rotation.y) * dRot * 0.8,
          0,
          -dZ * 1.5 - Math.cos(this.modelRoot.rotation.y) * dRot * 0.8
        ];

        this.prevModelPos.copy(this.modelRoot.position);
        this.prevModelRotY = this.modelRoot.rotation.y;
      }
    }

    let totalPenetrations = 0;
    let maxDisplacement = 0;
    let hasExploded = false;

    // Fixed timestep execution loop
    while (this.timeAccumulator >= fixedDt) {
      this.activeGarments.forEach((garment) => {
        const result = ClothConstraintSolver.solveStep(
          garment.particleState,
          garment.constraints,
          garment.fabric,
          this.collisionSystem,
          settings,
          fixedDt,
          this.inertialForce
        );

        totalPenetrations += result.penetrationResolutions;
        if (result.maxDisplacement > maxDisplacement) {
          maxDisplacement = result.maxDisplacement;
        }
        if (result.hasExploded) {
          hasExploded = true;
        }
      });

      this.timeAccumulator -= fixedDt;
    }

    // Apply updated positions directly to Three.js meshes
    this.activeGarments.forEach((garment) => {
      GarmentDeformationAdapter.applySimulationToMesh(garment);
    });

    const elapsedMs = performance.now() - startTime;
    this.qualityManager.recordStepTime(elapsedMs);

    this.diagnostics.updateMetrics({
      stepTimeMs: elapsedMs,
      penetrationResolutions: totalPenetrations,
      maxDisplacementMeters: maxDisplacement,
      hasExploded,
      isDegraded: this.qualityManager.isDegraded()
    });
  }

  /**
   * Resets all simulated garments back to their rest bind pose.
   */
  public resetSimulation(): void {
    this.activeGarments.forEach((garment) => {
      GarmentDeformationAdapter.resetToRestPose(garment);
    });
    this.timeAccumulator = 0;
    this.inertialForce = [0, 0, 0];
    this.diagnostics.updateMetrics({
      hasExploded: false,
      maxDisplacementMeters: 0,
      penetrationResolutions: 0
    });
  }

  public setEnabled(enabled: boolean): void {
    this.isEnabled = enabled;
    if (!enabled) {
      this.resetSimulation();
      this.state = 'paused';
    } else {
      this.state = this.activeGarments.size > 0 ? 'simulating' : 'ready';
    }
    this.diagnostics.updateMetrics({ state: this.state });
  }

  public getState(): ClothSimulationState {
    return this.state;
  }

  public getDiagnostics(): ClothSimulationDiagnostics {
    return this.diagnostics;
  }

  public getQualityManager(): ClothSimulationQualityManager {
    return this.qualityManager;
  }

  public getActiveGarment(id: string): SimulatedGarment | undefined {
    return this.activeGarments.get(id);
  }

  public getActiveGarments(): SimulatedGarment[] {
    return Array.from(this.activeGarments.values());
  }

  public dispose(): void {
    this.activeGarments.forEach((garment) => {
      GarmentDeformationAdapter.resetToRestPose(garment);
    });
    this.activeGarments.clear();
    this.state = 'uninitialized';
    this.modelRoot = null;
    this.diagnostics.updateMetrics({ state: 'uninitialized' });
  }
}

