/**
 * YORVYN MotionCore (Phase 16.9) — Master Unified Animation, Adaptive Cloth & Motion Orchestrator
 * Coordinates:
 *   1. AnimationMixer state progression & transitions
 *   2. Optional PoseInputAdapter & ordered InverseKinematicsEngine
 *   3. World-space skeleton transform updates
 *   4. Garment anchor & collision capsule synchronization
 *   5. Adaptive fabric physics (XPBD) + Secondary motion (no double deformation)
 *   6. Hardware-aware ComputeOrchestrator + P50/P95/P99 performance telemetry
 */

import type * as THREE from 'three';
import {
  AnimationController,
  InverseKinematicsEngine,
  PoseInputAdapter,
  SkeletonAdapter,
} from './CharacterMotionEngine';
import { ComputeOrchestrator, type ComputeSelectionSummary } from './ComputeOrchestrator';
import {
  AdaptiveFabricProfileResolver,
  GarmentDynamicsEngine,
} from './GarmentDynamicsEngine';
import { MotionStateManager, type TransitionDecision } from './MotionStateManager';
import type {
  AdaptiveFabricPhysicsSpec,
  IKTargetSpec,
  MotionPerformanceTelemetry,
  MotionState,
  PoseInputFrame,
  SecondaryMotionNodeConfig,
  SkeletonCompatibilityReport,
} from './MotionTypes';
import { MotionPerformanceEvaluator } from './MotionValidator';

export class MotionCoreOrchestrator {
  public readonly stateManager = new MotionStateManager();
  public readonly animationController = new AnimationController();
  public readonly ikEngine = new InverseKinematicsEngine();
  public readonly poseAdapter = new PoseInputAdapter();
  public readonly garmentDynamics = new GarmentDynamicsEngine();
  public readonly compute = new ComputeOrchestrator('balanced');
  public readonly evaluator = new MotionPerformanceEvaluator();

  private modelRoot: THREE.Object3D | null = null;
  private latestTelemetry: MotionPerformanceTelemetry | null = null;
  private secondaryCallback?: (deltaSeconds: number, state: MotionState) => void;
  private isDisposed = false;

  public async initAvatar(
    root: THREE.Object3D,
    clips: THREE.AnimationClip[] = [],
    options?: {
      onExternalFacialAndGestureTick?: (deltaSeconds: number, state: MotionState) => void;
    }
  ): Promise<{ skeletonReport: SkeletonCompatibilityReport; compute: ComputeSelectionSummary }> {
    this.isDisposed = false;
    this.modelRoot = root;
    this.secondaryCallback = options?.onExternalFacialAndGestureTick;

    const skeletonReport = this.animationController.init(root, clips);
    this.garmentDynamics.initAvatar(root);
    const compute = await this.compute.detectAndSelect({ probeWebGPU: false });

    // Start in deterministic IDLE loop
    this.stateManager.reset();
    const clipOk = this.animationController.playState('IDLE', {
      blendDurationSeconds: 0.25,
      loop: true,
    });
    if (!clipOk && clips.length === 0) {
      // Procedural idle handles default rigged bones cleanly; tolerate headless synthetic scenes safely.
    }

    return { skeletonReport, compute };
  }

  public transitionTo(target: MotionState, opts?: { customClipName?: string; blendDurationSeconds?: number }): TransitionDecision {
    const decision = this.stateManager.requestTransition(target, opts?.customClipName);
    if (!decision.accepted) return decision;

    if (target === 'PAUSED') {
      return decision;
    }
    if (target === 'RESETTING') {
      this.resetAll();
      return this.stateManager.reset();
    }

    const blend = opts?.blendDurationSeconds ?? decision.policy.blendDurationSeconds;
    const played = this.animationController.playState(target, {
      blendDurationSeconds: blend,
      loop: decision.policy.loop,
      customClipName: opts?.customClipName,
      onFinished: decision.policy.returnToState
        ? () => {
            if (!this.isDisposed && this.stateManager.getState() === target) {
              this.transitionTo(decision.policy.returnToState!);
            }
          }
        : undefined,
    });

    if (!played && target !== 'IDLE') {
      // Gracefully keep current pose without crashing if custom clip missing
      return decision;
    }
    return decision;
  }

  public pause(): TransitionDecision {
    return this.stateManager.pause();
  }

  public resume(): TransitionDecision {
    const d = this.stateManager.resume();
    if (d.accepted) {
      this.animationController.playState(d.toState, {
        blendDurationSeconds: 0.2,
        loop: d.policy.loop,
        customClipName: this.stateManager.getCustomClipName(),
      });
    }
    return d;
  }

  public resetAll(): void {
    this.animationController.reset();
    this.poseAdapter.reset();
    this.ikEngine.clearTargets();
    this.garmentDynamics.reset();
    this.evaluator.reset();
    if (this.modelRoot) {
      this.modelRoot.updateMatrixWorld(true);
    }
  }

  public setIKTarget(spec: IKTargetSpec): void {
    this.ikEngine.setTarget(spec);
  }

  public clearIKTargets(): void {
    this.ikEngine.clearTargets();
  }

  public applyPoseInput(frame: PoseInputFrame): { appliedBones: number; rejectedLandmarks: number } {
    return this.poseAdapter.applyPoseFrame(frame, this.animationController.getSkeleton());
  }

  public attachGarment(
    garmentObj: THREE.Object3D,
    category: string,
    opts?: { fabricHint?: string; hasMultiViewEvidence?: boolean; hasConstructionSeams?: boolean }
  ): number {
    return this.garmentDynamics.attachGarmentObject(garmentObj, category, opts);
  }

  public detachGarment(): void {
    this.garmentDynamics.detachGarment();
  }

  public setFabric(category: string, fabricHint?: string): AdaptiveFabricPhysicsSpec {
    return this.garmentDynamics.setFabricSpec({ category, fabricHint });
  }

  public setWind(x: number, y: number, z: number): void {
    this.garmentDynamics.setWind(x, y, z);
  }

  public registerSecondaryNode(id: string, obj: THREE.Object3D, kind: SecondaryMotionNodeConfig['kind']): boolean {
    return this.garmentDynamics.registerSecondaryNode(id, obj, kind);
  }

  /**
   * Executes the deterministic 10-step per-frame synchronization pipeline.
   * Call once inside the viewport's requestAnimationFrame loop.
   */
  public step(deltaSeconds: number): MotionPerformanceTelemetry {
    const frameStart = performance.now();
    const state = this.stateManager.getState();

    // Steps 1-3: Advance animation mixer & ordered post-clip IK (skip advancing time when PAUSED)
    if (state !== 'PAUSED' && state !== 'ERROR') {
      this.animationController.update(deltaSeconds, this.stateManager.getTimeScale());
      this.ikEngine.apply(this.animationController.getSkeleton());
      this.secondaryCallback?.(deltaSeconds, state);
    }

    if (this.modelRoot) {
      this.modelRoot.updateMatrixWorld(true);
    }

    // Steps 4-9: Update collision hulls, step XPBD cloth, self-collision & secondary motion
    const summary = this.compute.getSummary();
    const dyn = state === 'PAUSED'
      ? {
          stepTimeMs: 0,
          collisions: 0,
          activeVertices: 0,
          constraintCount: 0,
          maxDisplacement: 0,
          hasExploded: false,
          secondaryUpdated: 0,
        }
      : this.garmentDynamics.step(deltaSeconds, summary.qualityTier, summary.solverSettings);

    const frameMs = Math.max(0.1, performance.now() - frameStart);
    this.latestTelemetry = this.evaluator.buildTelemetry(state, summary, {
      renderFrameMs: frameMs,
      simulationStepMs: dyn.stepTimeMs,
      activeClothVertices: dyn.activeVertices,
      constraintCount: dyn.constraintCount,
      collisionCount: dyn.collisions,
      secondaryNodeCount: this.garmentDynamics.getSecondaryNodeCount(),
    });

    // Adaptive quality scaling if persistent overload observed
    this.compute.adaptTierFromFrameTime(this.latestTelemetry.p95FrameMs);
    return this.latestTelemetry;
  }

  public getTelemetry(): MotionPerformanceTelemetry | null {
    return this.latestTelemetry;
  }

  public getSkeleton(): SkeletonAdapter {
    return this.animationController.getSkeleton();
  }

  public getActiveFabricProfile(): AdaptiveFabricPhysicsSpec {
    return this.garmentDynamics.getActiveProfile();
  }

  public getAvailableClipNames(): string[] {
    return this.animationController.getLoadedClipNames();
  }

  public dispose(): void {
    this.isDisposed = true;
    this.garmentDynamics.dispose();
    this.animationController.dispose();
    this.ikEngine.clearTargets();
    this.poseAdapter.reset();
    this.modelRoot = null;
    this.latestTelemetry = null;
  }
}

export { AdaptiveFabricProfileResolver };
