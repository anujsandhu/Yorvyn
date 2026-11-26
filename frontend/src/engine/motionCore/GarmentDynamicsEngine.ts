/**
 * YORVYN MotionCore — GarmentDynamics & Secondary Motion Engine
 * Bridges YORVYN's XPBD ClothConstraintSolver + ClothCollisionSystem with:
 * - Multi-component rigged/skinned custom garments (THREE.Group or THREE.SkinnedMesh/Mesh)
 * - Bone-driven anchor tracking during character WALK/RUN/TURN/RAISE_ARMS/BEND/SIT motion
 * - Category & Phase 16.1/16.2 construction-aware AdaptiveFabricPhysicsSpec profiles (explicitly estimated)
 * - Bounded spatial-hash self-collision for high/maximum quality tiers
 * - Coordinated SecondaryMotionSolver avoiding double-deforming XPBD cloth vertices
 */

import * as THREE from 'three';
import { MeshBVH } from 'three-mesh-bvh';
import { ClothCollisionSystem } from '../clothPhysics/ClothCollisionSystem';
import { ClothConstraintSolver } from '../clothPhysics/ClothConstraintSolver';
import { FabricMaterialProfile } from '../clothPhysics/FabricMaterialProfile';
import { GarmentDeformationAdapter } from '../clothPhysics/GarmentDeformationAdapter';
import type {
  FabricPhysicsProfile,
  FabricProfileId,
  SimulatedGarment,
  SimulationQualitySettings,
} from '../clothPhysics/types';
import type {
  AdaptiveFabricPhysicsSpec,
  MotionQualityTier,
  SecondaryMotionNodeConfig,
} from './MotionTypes';

export const EXTENDED_CATEGORY_DEFAULTS: Record<string, { fabric: FabricProfileId; density: number; sway: number }> = {
  denim_jacket: { fabric: 'denim', density: 0.45, sway: 0.35 },
  jacket: { fabric: 'denim', density: 0.42, sway: 0.42 },
  hoodie: { fabric: 'cotton', density: 0.32, sway: 0.65 },
  shirt: { fabric: 'cotton', density: 0.19, sway: 0.68 },
  tshirt: { fabric: 'cotton', density: 0.18, sway: 0.72 },
  tops: { fabric: 'cotton', density: 0.21, sway: 0.70 },
  trousers: { fabric: 'wool', density: 0.34, sway: 0.45 },
  jeans: { fabric: 'denim', density: 0.44, sway: 0.36 },
  dress: { fabric: 'silk', density: 0.14, sway: 0.92 },
  skirt: { fabric: 'linen', density: 0.22, sway: 0.90 },
  traditional: { fabric: 'silk', density: 0.20, sway: 0.88 },
  sportswear: { fabric: 'synthetic', density: 0.17, sway: 0.75 },
  footwear: { fabric: 'leather', density: 0.52, sway: 0.15 },
};

export class AdaptiveFabricProfileResolver {
  /**
   * Builds a construction- and evidence-aware estimated physical profile.
   * Explicitly distinguishes estimated parameters from real laboratory measurements (`isMeasuredPhysical: false`).
   */
  public static resolve(opts: {
    category: string;
    subcategory?: string | null;
    fabricHint?: string | null;
    hasMultiViewEvidence?: boolean;
    hasConstructionSeams?: boolean;
    visualRoughness?: number;
  }): AdaptiveFabricPhysicsSpec {
    const key = (opts.subcategory || opts.category || 'tops').toLowerCase().trim();
    const def = EXTENDED_CATEGORY_DEFAULTS[key] || EXTENDED_CATEGORY_DEFAULTS[(opts.category || '').toLowerCase()] || EXTENDED_CATEGORY_DEFAULTS.tops;
    const base = FabricMaterialProfile.getProfile((opts.fabricHint as FabricProfileId) || def.fabric);

    return {
      id: `${key}_${base.id}`,
      category: key,
      fabricFamily: base.id,
      arealDensityKgM2: base.mass,
      stretchResistance: base.stretchStiffness,
      shearResistance: base.shearStiffness,
      bendingResistance: base.bendingStiffness,
      damping: base.damping,
      friction: base.friction,
      thicknessM: base.thickness,
      anisotropyRatio: base.id === 'knitted' || base.id === 'knitwear' ? 1.35 : 1.12,
      seamStiffness: opts.hasConstructionSeams ? 0.94 : 0.88,
      secondarySwayGain: def.sway,
      surfaceRoughnessVisual: opts.visualRoughness ?? 0.65,
      isMeasuredPhysical: false,
      constructionProvenance: opts.hasMultiViewEvidence
        ? 'observed_multi_view'
        : opts.hasConstructionSeams
        ? 'single_view_with_inferred_back'
        : 'category_default',
    };
  }

  public static toSolverProfile(spec: AdaptiveFabricPhysicsSpec): FabricPhysicsProfile {
    const base = FabricMaterialProfile.getProfile(spec.fabricFamily as FabricProfileId);
    return {
      ...base,
      mass: spec.arealDensityKgM2,
      stretchStiffness: Math.max(0.45, Math.min(0.99, (spec.stretchResistance + spec.seamStiffness) * 0.5)),
      bendingStiffness: spec.bendingResistance,
      shearStiffness: spec.shearResistance,
      damping: spec.damping,
      friction: spec.friction,
      thickness: spec.thicknessM,
      isEstimate: true,
    };
  }
}

export interface BoundGarmentPart {
  sim: SimulatedGarment;
  isSkinned: boolean;
  localToRootBindMatrix: THREE.Matrix4;
  anchorBone: THREE.Object3D | null;
  lastAnchorWorldMatrix: THREE.Matrix4;
  maxSimulatedVertices: number;
}

/**
 * Spatial-hash self-collision pass for free cloth particles (active in high & maximum quality tiers).
 */
export class SelfCollisionAdapter {
  public static resolve(
    sim: SimulatedGarment,
    minDist: number = 0.008,
    maxParticlesBudget: number = 2500
  ): number {
    const p = sim.particleState;
    const count = Math.min(p.count, maxParticlesBudget);
    if (count < 4) return 0;

    const cellSize = Math.max(0.012, minDist * 1.5);
    const invCell = 1.0 / cellSize;
    const grid = new Map<number, number[]>();
    const minDistSq = minDist * minDist;

    for (let i = 0; i < count; i++) {
      const idx = i * 3;
      const cx = Math.floor(p.positions[idx] * invCell);
      const cy = Math.floor(p.positions[idx + 1] * invCell);
      const cz = Math.floor(p.positions[idx + 2] * invCell);
      const hash = ((cx * 73856093) ^ (cy * 19349663) ^ (cz * 83492791)) | 0;
      let bucket = grid.get(hash);
      if (!bucket) {
        bucket = [];
        grid.set(hash, bucket);
      }
      if (bucket.length < 8) bucket.push(i);
    }

    let resolved = 0;
    for (const bucket of grid.values()) {
      if (bucket.length < 2) continue;
      for (let a = 0; a < bucket.length; a++) {
        for (let b = a + 1; b < bucket.length; b++) {
          const ia = bucket[a];
          const ib = bucket[b];
          if (Math.abs(ia - ib) <= 2 || (p.invMasses[ia] === 0 && p.invMasses[ib] === 0)) continue;
          const ax = p.positions[ia * 3];
          const ay = p.positions[ia * 3 + 1];
          const az = p.positions[ia * 3 + 2];
          const dx = p.positions[ib * 3] - ax;
          const dy = p.positions[ib * 3 + 1] - ay;
          const dz = p.positions[ib * 3 + 2] - az;
          const d2 = dx * dx + dy * dy + dz * dz;
          if (d2 > 1e-9 && d2 < minDistSq) {
            const d = Math.sqrt(d2);
            const push = (minDist - d) * 0.35 / d;
            if (p.invMasses[ia] > 0) {
              p.positions[ia * 3] -= dx * push;
              p.positions[ia * 3 + 1] -= dy * push;
              p.positions[ia * 3 + 2] -= dz * push;
            }
            if (p.invMasses[ib] > 0) {
              p.positions[ib * 3] += dx * push;
              p.positions[ib * 3 + 1] += dy * push;
              p.positions[ib * 3 + 2] += dz * push;
            }
            resolved++;
          }
        }
      }
    }
    return resolved;
  }
}

/**
 * SecondaryMotionSolver: handles hair, accessories, sleeves, hems, hoods without double-deforming primary XPBD cloth meshes.
 */
export class SecondaryMotionSolver {
  private nodes: Map<string, SecondaryMotionNodeConfig> = new Map();
  private simulatedClothMeshIds = new Set<number>();

  public registerSimulatedClothMesh(meshId: number): void {
    this.simulatedClothMeshIds.add(meshId);
  }

  public clearClothRegistry(): void {
    this.simulatedClothMeshIds.clear();
  }

  public registerNode(
    id: string,
    object: THREE.Object3D,
    kind: SecondaryMotionNodeConfig['kind'],
    opts?: { stiffness?: number; damping?: number; maxAngleRad?: number; maxOffsetM?: number }
  ): boolean {
    // Do not double-deform geometry already simulated per-vertex by XPBD!
    if ((object as THREE.Mesh).isMesh && this.simulatedClothMeshIds.has(object.id)) {
      return false;
    }
    this.nodes.set(id, {
      id,
      kind,
      object,
      restLocalPos: object.position.clone(),
      restLocalQuat: object.quaternion.clone(),
      stiffness: opts?.stiffness ?? (kind === 'hair' ? 28 : kind === 'accessory' ? 45 : 22),
      damping: opts?.damping ?? 0.86,
      maxAngleRad: opts?.maxAngleRad ?? (kind === 'accessory' ? 0.08 : 0.22),
      maxOffsetM: opts?.maxOffsetM ?? 0.025,
      velocity: new THREE.Vector3(),
      angularOffset: new THREE.Vector3(),
    });
    return true;
  }

  public step(dt: number, inertiaWorld: [number, number, number], wind: [number, number, number], swayGain: number): number {
    if (this.nodes.size === 0 || dt <= 0) return 0;
    const clampedDt = Math.min(dt, 0.05);
    const ix = (inertiaWorld[0] + wind[0]) * swayGain;
    const iz = (inertiaWorld[2] + wind[2]) * swayGain;
    let updated = 0;

    for (const node of this.nodes.values()) {
      if ((node.object as THREE.Mesh).isMesh && this.simulatedClothMeshIds.has(node.object.id)) {
        continue;
      }
      // Spring-damper integration in bounded Euler angles
      const springFx = -node.stiffness * node.angularOffset.x + iz * 0.28;
      const springFz = -node.stiffness * node.angularOffset.z - ix * 0.28;
      node.velocity.x = (node.velocity.x + springFx * clampedDt) * Math.pow(node.damping, clampedDt * 60);
      node.velocity.z = (node.velocity.z + springFz * clampedDt) * Math.pow(node.damping, clampedDt * 60);

      node.angularOffset.x = THREE.MathUtils.clamp(
        node.angularOffset.x + node.velocity.x * clampedDt,
        -node.maxAngleRad,
        node.maxAngleRad
      );
      node.angularOffset.z = THREE.MathUtils.clamp(
        node.angularOffset.z + node.velocity.z * clampedDt,
        -node.maxAngleRad,
        node.maxAngleRad
      );

      const deltaQ = new THREE.Quaternion().setFromEuler(
        new THREE.Euler(node.angularOffset.x, 0, node.angularOffset.z)
      );
      node.object.quaternion.copy(node.restLocalQuat).multiply(deltaQ);
      updated++;
    }
    return updated;
  }

  public resetAll(): void {
    for (const node of this.nodes.values()) {
      node.velocity.set(0, 0, 0);
      node.angularOffset.set(0, 0, 0);
      node.object.position.copy(node.restLocalPos);
      node.object.quaternion.copy(node.restLocalQuat);
    }
  }

  public getNodeCount(): number {
    return this.nodes.size;
  }

  public dispose(): void {
    this.resetAll();
    this.nodes.clear();
    this.simulatedClothMeshIds.clear();
  }
}

export class GarmentDynamicsEngine {
  private boundParts: BoundGarmentPart[] = [];
  private collisionSystem = new ClothCollisionSystem();
  private secondarySolver = new SecondaryMotionSolver();
  private bodyBvh: MeshBVH | null = null;
  private modelRoot: THREE.Object3D | null = null;
  private timeAccumulator = 0;
  private prevModelPos = new THREE.Vector3();
  private prevModelRotY = 0;
  private activeProfile: AdaptiveFabricPhysicsSpec = AdaptiveFabricProfileResolver.resolve({ category: 'top' });
  private windVector: [number, number, number] = [0, 0, 0];

  public initAvatar(modelRoot: THREE.Object3D): void {
    this.modelRoot = modelRoot;
    this.collisionSystem.syncWithAvatar(modelRoot);
    this.prevModelPos.copy(modelRoot.position);
    this.prevModelRotY = modelRoot.rotation.y;

    // Optional BVH build on main body mesh for spatial acceleration without replacing capsule hulls
    this.bodyBvh = null;
    modelRoot.traverse((o) => {
      if (!this.bodyBvh && (o as THREE.Mesh).isMesh && /body|skin/i.test(o.name)) {
        const g = (o as THREE.Mesh).geometry;
        if (g.attributes.position && g.attributes.position.count >= 12) {
          this.bodyBvh = (g as any).boundsTree || new MeshBVH(g);
          (g as any).boundsTree = this.bodyBvh;
        }
      }
    });
  }

  /**
   * Attaches either a single Mesh/SkinnedMesh or multi-component Group garment safely into XPBD + rig anchor sync.
   * Never mutates stored design candidate revisions or dimensions.
   */
  public attachGarmentObject(
    garmentObj: THREE.Object3D,
    category: string,
    opts?: { fabricHint?: string; hasMultiViewEvidence?: boolean; hasConstructionSeams?: boolean }
  ): number {
    this.detachGarment();
    this.activeProfile = AdaptiveFabricProfileResolver.resolve({
      category,
      fabricHint: opts?.fabricHint,
      hasMultiViewEvidence: opts?.hasMultiViewEvidence,
      hasConstructionSeams: opts?.hasConstructionSeams,
    });
    const solverFabric = AdaptiveFabricProfileResolver.toSolverProfile(this.activeProfile);
    const clothCat: 'top' | 'bottom' | 'dress' | 'outerwear' | 'skirt' =
      category.includes('bottom') || category.includes('trouser') || category.includes('jean')
        ? 'bottom'
        : category.includes('dress')
        ? 'dress'
        : category.includes('skirt')
        ? 'skirt'
        : category.includes('jacket') || category.includes('outerwear')
        ? 'outerwear'
        : 'top';

    garmentObj.traverse((node) => {
      if ((node as THREE.Mesh).isMesh) {
        const mesh = node as THREE.Mesh;
        const pos = mesh.geometry?.attributes?.position;
        if (!pos || pos.count < 3) return;
        const sim = GarmentDeformationAdapter.prepareGarment(
          mesh,
          clothCat,
          solverFabric,
          `${garmentObj.name || 'garment'}_${mesh.name || this.boundParts.length}`
        );
        const anchorBone =
          this.modelRoot?.getObjectByName(clothCat === 'bottom' ? 'Hips' : 'Spine2') ||
          this.modelRoot?.getObjectByName('Spine') ||
          null;

        this.boundParts.push({
          sim,
          isSkinned: Boolean((mesh as THREE.SkinnedMesh).isSkinnedMesh),
          localToRootBindMatrix: mesh.matrixWorld.clone(),
          anchorBone,
          lastAnchorWorldMatrix: anchorBone ? anchorBone.matrixWorld.clone() : new THREE.Matrix4(),
          maxSimulatedVertices: pos.count,
        });
        this.secondarySolver.registerSimulatedClothMesh(mesh.id);
      }
    });

    return this.boundParts.length;
  }

  public setFabricSpec(opts: { category: string; fabricHint?: string }): AdaptiveFabricPhysicsSpec {
    this.activeProfile = AdaptiveFabricProfileResolver.resolve(opts);
    const solverFabric = AdaptiveFabricProfileResolver.toSolverProfile(this.activeProfile);
    for (const part of this.boundParts) {
      part.sim.fabric = solverFabric;
      const baseInv = 1.0 / Math.max(0.01, solverFabric.mass);
      for (let i = 0; i < part.sim.particleState.count; i++) {
        if (!part.sim.particleState.pinnedIndices.has(i)) {
          part.sim.particleState.invMasses[i] = baseInv;
        }
      }
    }
    return this.activeProfile;
  }

  public registerSecondaryNode(
    id: string,
    obj: THREE.Object3D,
    kind: SecondaryMotionNodeConfig['kind']
  ): boolean {
    return this.secondarySolver.registerNode(id, obj, kind);
  }

  public setWind(x: number, y: number, z: number): void {
    this.windVector = [
      Math.max(-8, Math.min(8, x)),
      Math.max(-4, Math.min(4, y)),
      Math.max(-8, Math.min(8, z)),
    ];
  }

  /**
   * Deterministic physics synchronization step (executed AFTER animation/IK/skeleton update):
   * 1. Sync collision hulls with active skeleton world transforms
   * 2. Compute inertial forces from bone & root acceleration
   * 3. Update pinned anchor vertices cleanly from skeleton motion
   * 4. Step XPBD solver + bounded self-collision (when tier enables)
   * 5. Step secondary spring nodes without double-deforming cloth
   */
  public step(
    deltaSeconds: number,
    tier: MotionQualityTier,
    settings: SimulationQualitySettings
  ): {
    stepTimeMs: number;
    collisions: number;
    activeVertices: number;
    constraintCount: number;
    maxDisplacement: number;
    hasExploded: boolean;
    secondaryUpdated: number;
  } {
    const t0 = performance.now();
    const clampedDelta = Math.min(Math.max(deltaSeconds, 0), 0.1);
    this.timeAccumulator += clampedDelta;

    let inertia: [number, number, number] = [0, 0, 0];
    if (this.modelRoot) {
      this.collisionSystem.syncWithAvatar(this.modelRoot);
      if (clampedDelta > 1e-5) {
        const dx = (this.modelRoot.position.x - this.prevModelPos.x) / clampedDelta;
        const dz = (this.modelRoot.position.z - this.prevModelPos.z) / clampedDelta;
        const dRot = (this.modelRoot.rotation.y - this.prevModelRotY) / clampedDelta;
        inertia = [
          Math.max(-12, Math.min(12, -dx * 1.4 - Math.sin(this.modelRoot.rotation.y) * dRot * 0.9 + this.windVector[0])),
          Math.max(-6, Math.min(6, this.windVector[1])),
          Math.max(-12, Math.min(12, -dz * 1.4 - Math.cos(this.modelRoot.rotation.y) * dRot * 0.9 + this.windVector[2])),
        ];
        this.prevModelPos.copy(this.modelRoot.position);
        this.prevModelRotY = this.modelRoot.rotation.y;
      }
    }

    let collisions = 0;
    let maxDisp = 0;
    let exploded = false;

    const fixedDt = settings.fixedTimeStep;
    while (this.timeAccumulator >= fixedDt) {
      for (const part of this.boundParts) {
        // Track subtle bone-space sway for inertial response without double-transforming SkinnedMesh vertices
        if (part.anchorBone) {
          const anchorDelta = new THREE.Vector3()
            .setFromMatrixPosition(part.anchorBone.matrixWorld)
            .sub(new THREE.Vector3().setFromMatrixPosition(part.lastAnchorWorldMatrix));
          part.lastAnchorWorldMatrix.copy(part.anchorBone.matrixWorld);
          if (clampedDelta > 1e-4 && anchorDelta.lengthSq() < 0.25) {
            inertia[0] = Math.max(-12, Math.min(12, inertia[0] - (anchorDelta.x / fixedDt) * 0.18));
            inertia[2] = Math.max(-12, Math.min(12, inertia[2] - (anchorDelta.z / fixedDt) * 0.18));
          }
        }

        const r = ClothConstraintSolver.solveStep(
          part.sim.particleState,
          part.sim.constraints,
          part.sim.fabric,
          this.collisionSystem,
          settings,
          fixedDt,
          inertia
        );
        collisions += r.penetrationResolutions;
        if (r.maxDisplacement > maxDisp) maxDisp = r.maxDisplacement;
        if (r.hasExploded) exploded = true;

        if (tier === 'high' || tier === 'maximum') {
          collisions += SelfCollisionAdapter.resolve(part.sim, 0.008, settings.maxActiveVertices);
        }

        // Preserve skeleton skinning stability: bound local bind-space drift on SkinnedMeshes
        // so GPU skin matrices and XPBD drape never compound or detach from the avatar skeleton.
        if (part.isSkinned) {
          const p = part.sim.particleState;
          const maxSkinLocalDrift = 0.065;
          for (let i = 0; i < p.count; i++) {
            if (p.invMasses[i] === 0) continue;
            const k = i * 3;
            const dx = p.positions[k] - p.restPositions[k];
            const dy = p.positions[k + 1] - p.restPositions[k + 1];
            const dz = p.positions[k + 2] - p.restPositions[k + 2];
            const d2 = dx * dx + dy * dy + dz * dz;
            if (d2 > maxSkinLocalDrift * maxSkinLocalDrift) {
              const s = maxSkinLocalDrift / Math.sqrt(d2);
              p.positions[k] = p.restPositions[k] + dx * s;
              p.positions[k + 1] = p.restPositions[k + 1] + dy * s;
              p.positions[k + 2] = p.restPositions[k + 2] + dz * s;
            }
          }
        }
      }
      this.timeAccumulator -= fixedDt;
    }

    let activeVertices = 0;
    let constraintCount = 0;
    for (const part of this.boundParts) {
      // Only commit direct buffer deformation on non-skinned parts unless skin matrices coexist cleanly;
      // GarmentDeformationAdapter writes local positions cleanly inside bounds.
      GarmentDeformationAdapter.applySimulationToMesh(part.sim);
      activeVertices += part.sim.particleState.count;
      constraintCount += part.sim.constraints.distancePairs.length / 2 + part.sim.constraints.bendingPairs.length / 2;
    }

    const secondaryUpdated = this.secondarySolver.step(
      clampedDelta,
      inertia,
      this.windVector,
      this.activeProfile.secondarySwayGain
    );

    return {
      stepTimeMs: Number((performance.now() - t0).toFixed(3)),
      collisions,
      activeVertices,
      constraintCount,
      maxDisplacement: Number(maxDisp.toFixed(4)),
      hasExploded: exploded,
      secondaryUpdated,
    };
  }

  public reset(): void {
    this.timeAccumulator = 0;
    for (const part of this.boundParts) {
      GarmentDeformationAdapter.resetToRestPose(part.sim);
    }
    this.secondarySolver.resetAll();
  }

  public detachGarment(): void {
    for (const part of this.boundParts) {
      GarmentDeformationAdapter.resetToRestPose(part.sim);
    }
    this.boundParts = [];
    this.secondarySolver.clearClothRegistry();
  }

  public getActiveProfile(): AdaptiveFabricPhysicsSpec {
    return this.activeProfile;
  }

  public getSecondaryNodeCount(): number {
    return this.secondarySolver.getNodeCount();
  }

  public getBodyBvhAvailable(): boolean {
    return this.bodyBvh !== null;
  }

  public getCollisionSystem(): ClothCollisionSystem {
    return this.collisionSystem;
  }

  public dispose(): void {
    this.detachGarment();
    this.secondarySolver.dispose();
    this.bodyBvh = null;
    this.modelRoot = null;
  }
}
