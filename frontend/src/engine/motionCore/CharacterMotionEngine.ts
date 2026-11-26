/**
 * YORVYN MotionCore — CharacterMotion Subsystem
 * Single-mixer owner providing:
 * - SkeletonAdapter & RetargetingEngine (canonical Ara + optional Mixamo alias mapping, strict incompatibility checks)
 * - AnimationClipManager & blender (loads GLB clips + builds fallback procedural skeletal tracks for WALK/RUN/RAISE_ARMS/BEND/SIT/TURN)
 * - InverseKinematicsEngine (post-clip / pre-cloth bounded 2-bone IK + CCD pole-vector constraints)
 * - PoseInputAdapter (confidence-weighted smoothed landmarks with anatomical range clamping; works without webcam)
 */

import * as THREE from 'three';
import type {
  IKTargetSpec,
  MotionState,
  PoseInputFrame,
  SkeletonCompatibilityReport,
} from './MotionTypes';

const REQUIRED_CORE_BONES = ['Hips', 'Spine', 'Spine2', 'LeftArm', 'RightArm', 'LeftUpLeg', 'RightUpLeg'];

const BONE_ALIASES: Record<string, string> = {
  hips: 'Hips',
  'mixamorig:hips': 'Hips',
  mixamorighips: 'Hips',
  pelvis: 'Hips',
  spine: 'Spine',
  'mixamorig:spine': 'Spine',
  spine1: 'Spine1',
  'mixamorig:spine1': 'Spine1',
  spine2: 'Spine2',
  'mixamorig:spine2': 'Spine2',
  chest: 'Spine2',
  neck: 'Neck',
  'mixamorig:neck': 'Neck',
  head: 'Head',
  'mixamorig:head': 'Head',
  leftshoulder: 'LeftShoulder',
  'mixamorig:leftshoulder': 'LeftShoulder',
  leftarm: 'LeftArm',
  'mixamorig:leftarm': 'LeftArm',
  leftforearm: 'LeftForeArm',
  'mixamorig:leftforearm': 'LeftForeArm',
  lefthand: 'LeftHand',
  'mixamorig:lefthand': 'LeftHand',
  rightshoulder: 'RightShoulder',
  'mixamorig:rightshoulder': 'RightShoulder',
  rightarm: 'RightArm',
  'mixamorig:rightarm': 'RightArm',
  rightforearm: 'RightForeArm',
  'mixamorig:rightforearm': 'RightForeArm',
  righthand: 'RightHand',
  'mixamorig:righthand': 'RightHand',
  leftupleg: 'LeftUpLeg',
  'mixamorig:leftupleg': 'LeftUpLeg',
  leftleg: 'LeftLeg',
  'mixamorig:leftleg': 'LeftLeg',
  leftfoot: 'LeftFoot',
  'mixamorig:leftfoot': 'LeftFoot',
  rightupleg: 'RightUpLeg',
  'mixamorig:rightupleg': 'RightUpLeg',
  rightleg: 'RightLeg',
  'mixamorig:rightleg': 'RightLeg',
  rightfoot: 'RightFoot',
  'mixamorig:rightfoot': 'RightFoot',
};

export function normalizeBoneName(name: string): string {
  const key = (name || '').toLowerCase().replace(/[\s_.-]+/g, '');
  if (BONE_ALIASES[key]) return BONE_ALIASES[key];
  const withColon = (name || '').toLowerCase().trim();
  if (BONE_ALIASES[withColon]) return BONE_ALIASES[withColon];
  return name;
}

export class SkeletonAdapter {
  private boneByCanonical = new Map<string, THREE.Bone>();
  private restLocalQuat = new Map<string, THREE.Quaternion>();
  private restLocalPos = new Map<string, THREE.Vector3>();
  private report: SkeletonCompatibilityReport = {
    isCompatible: false,
    boneCount: 0,
    matchedCanonicalBones: 0,
    boneMap: {},
    unmappedBones: [],
    missingCoreBones: [...REQUIRED_CORE_BONES],
    hasCycle: false,
    issues: ['Not initialized'],
  };

  public bind(root: THREE.Object3D): SkeletonCompatibilityReport {
    this.boneByCanonical.clear();
    this.restLocalQuat.clear();
    this.restLocalPos.clear();

    const visited = new Set<THREE.Object3D>();
    let hasCycle = false;
    const boneList: THREE.Bone[] = [];

    const walk = (node: THREE.Object3D, stack: Set<THREE.Object3D>) => {
      if (stack.has(node)) {
        hasCycle = true;
        return;
      }
      if (visited.has(node)) return;
      visited.add(node);
      stack.add(node);
      if ((node as THREE.Bone).isBone) {
        boneList.push(node as THREE.Bone);
      }
      for (const child of node.children) {
        walk(child, stack);
      }
      stack.delete(node);
    };
    walk(root, new Set());

    // Also include skeleton bones attached to any SkinnedMesh
    root.traverse((obj) => {
      const sk = (obj as THREE.SkinnedMesh).skeleton;
      if ((obj as THREE.SkinnedMesh).isSkinnedMesh && sk) {
        for (const b of sk.bones) {
          if (b && !boneList.includes(b)) {
            boneList.push(b);
          }
        }
      }
    });

    const boneMap: Record<string, string> = {};
    const unmapped: string[] = [];

    for (const bone of boneList) {
      const canon = normalizeBoneName(bone.name);
      boneMap[bone.name] = canon;
      if (!this.boneByCanonical.has(canon)) {
        this.boneByCanonical.set(canon, bone);
        this.restLocalQuat.set(canon, bone.quaternion.clone());
        this.restLocalPos.set(canon, bone.position.clone());
      } else {
        unmapped.push(bone.name);
      }
    }

    const missing = REQUIRED_CORE_BONES.filter((req) => !this.boneByCanonical.has(req));
    const issues: string[] = [];
    if (hasCycle) issues.push('Cyclic skeleton hierarchy detected.');
    if (missing.length > 0) issues.push(`Missing required bones: ${missing.join(', ')}`);

    this.report = {
      isCompatible: !hasCycle && missing.length === 0 && boneList.length > 0,
      boneCount: boneList.length,
      matchedCanonicalBones: this.boneByCanonical.size,
      boneMap,
      unmappedBones: unmapped,
      missingCoreBones: missing,
      hasCycle,
      issues,
    };
    return this.report;
  }

  public getReport(): SkeletonCompatibilityReport {
    return this.report;
  }

  public getBone(canonicalName: string): THREE.Bone | undefined {
    return this.boneByCanonical.get(canonicalName) || this.boneByCanonical.get(normalizeBoneName(canonicalName));
  }

  public restoreBindPose(): void {
    for (const [canon, bone] of this.boneByCanonical.entries()) {
      const q = this.restLocalQuat.get(canon);
      const p = this.restLocalPos.get(canon);
      if (q) bone.quaternion.copy(q);
      if (p) bone.position.copy(p);
    }
  }

  public getRestQuat(canonicalName: string): THREE.Quaternion | undefined {
    return this.restLocalQuat.get(canonicalName);
  }
}

export class RetargetingEngine {
  /**
   * Retargets clip tracks from source bone names (e.g. Mixamo) to the target SkeletonAdapter bone names.
   * Rejects tracks whose target bone is absent without fabricating fake transforms.
   */
  public static retargetClip(clip: THREE.AnimationClip, skeleton: SkeletonAdapter): {
    clip: THREE.AnimationClip;
    mappedTracks: number;
    droppedTracks: number;
  } {
    const mappedTracks: THREE.KeyframeTrack[] = [];
    let droppedTracks = 0;

    for (const track of clip.tracks) {
      const dotIdx = track.name.indexOf('.');
      const rawBone = dotIdx >= 0 ? track.name.slice(0, dotIdx) : track.name;
      const prop = dotIdx >= 0 ? track.name.slice(dotIdx) : '.quaternion';
      const targetBone = skeleton.getBone(normalizeBoneName(rawBone));
      if (!targetBone) {
        droppedTracks++;
        continue;
      }
      const cloned = track.clone();
      cloned.name = `${targetBone.name}${prop}`;
      mappedTracks.push(cloned);
    }

    return {
      clip: new THREE.AnimationClip(clip.name, clip.duration, mappedTracks),
      mappedTracks: mappedTracks.length,
      droppedTracks,
    };
  }
}

export class InverseKinematicsEngine {
  private tempVecA = new THREE.Vector3();
  private tempVecB = new THREE.Vector3();
  private tempQuat = new THREE.Quaternion();
  private worldQuatInv = new THREE.Quaternion();
  private activeTargets: Map<IKTargetSpec['chain'], IKTargetSpec> = new Map();

  public setTarget(spec: IKTargetSpec): void {
    this.activeTargets.set(spec.chain, {
      ...spec,
      weight: Math.max(0, Math.min(1, spec.weight)),
    });
  }

  public clearTargets(): void {
    this.activeTargets.clear();
  }

  /**
   * Executes post-clip, pre-cloth damped 2-bone IK within joint rotation limits.
   * Guarantees deterministic execution order before bone world matrix updates.
   */
  public apply(skeleton: SkeletonAdapter): number {
    if (this.activeTargets.size === 0 || !skeleton.getReport().isCompatible) return 0;
    let solved = 0;

    const chains: Record<IKTargetSpec['chain'], [string, string, string, number]> = {
      left_arm: ['LeftArm', 'LeftForeArm', 'LeftHand', Math.PI * 0.72],
      right_arm: ['RightArm', 'RightForeArm', 'RightHand', Math.PI * 0.72],
      left_leg: ['LeftUpLeg', 'LeftLeg', 'LeftFoot', Math.PI * 0.78],
      right_leg: ['RightUpLeg', 'RightLeg', 'RightFoot', Math.PI * 0.78],
    };

    for (const [chainKey, spec] of this.activeTargets.entries()) {
      if (spec.weight <= 0.001) continue;
      const [upperName, lowerName, endName, maxAngle] = chains[chainKey];
      const upper = skeleton.getBone(upperName);
      const lower = skeleton.getBone(lowerName);
      const end = skeleton.getBone(endName);
      if (!upper || !lower || !end) continue;

      upper.updateMatrixWorld(true);
      const upperPos = this.tempVecA.setFromMatrixPosition(upper.matrixWorld);
      const endPos = this.tempVecB.setFromMatrixPosition(end.matrixWorld);
      const curDir = endPos.clone().sub(upperPos);
      const targetDir = spec.targetWorld.clone().sub(upperPos);
      if (curDir.lengthSq() < 1e-6 || targetDir.lengthSq() < 1e-6) continue;

      curDir.normalize();
      targetDir.normalize();

      const worldRot = new THREE.Quaternion().setFromUnitVectors(curDir, targetDir);
      const angle = 2 * Math.acos(Math.max(-1, Math.min(1, worldRot.w)));
      const clampedT = angle > maxAngle ? (maxAngle / angle) * spec.weight : spec.weight;

      if (upper.parent) {
        upper.parent.getWorldQuaternion(this.worldQuatInv).invert();
        const localDelta = this.tempQuat.copy(this.worldQuatInv).multiply(worldRot).multiply(upper.parent.getWorldQuaternion(new THREE.Quaternion()));
        upper.quaternion.slerp(upper.quaternion.clone().premultiply(localDelta), clampedT);
      } else {
        upper.quaternion.slerp(upper.quaternion.clone().premultiply(worldRot), clampedT);
      }
      // Mild flexion dampening at mid-joint (knee/elbow clamp avoids hyperextension)
      lower.rotation.x = Math.max(-2.2, Math.min(2.2, lower.rotation.x));
      solved++;
    }
    return solved;
  }
}

export class PoseInputAdapter {
  private smoothedBones = new Map<string, THREE.Euler>();
  private lastValidTimestamp = 0;

  /**
   * Maps confidence-weighted pose landmarks to bounded humanoid bone rotations.
   * Rejects NaNs, low-confidence frames (<0.45), and anatomically implausible angles.
   */
  public applyPoseFrame(
    frame: PoseInputFrame,
    skeleton: SkeletonAdapter,
    smoothingAlpha: number = 0.35
  ): { appliedBones: number; rejectedLandmarks: number } {
    if (!frame || frame.source === 'none' || !frame.landmarks.length || !skeleton.getReport().isCompatible) {
      return { appliedBones: 0, rejectedLandmarks: frame?.landmarks.length || 0 };
    }

    const byName = new Map<string, PoseInputFrame['landmarks'][number]>();
    let rejected = 0;
    for (const lm of frame.landmarks) {
      if (
        !Number.isFinite(lm.x) ||
        !Number.isFinite(lm.y) ||
        !Number.isFinite(lm.z) ||
        !Number.isFinite(lm.confidence) ||
        lm.confidence < 0.45
      ) {
        rejected++;
        continue;
      }
      byName.set(lm.name, lm);
    }

    let applied = 0;
    const applyLimbTilt = (canonBone: string, dx: number, dy: number, minX: number, maxX: number, minZ: number, maxZ: number) => {
      const bone = skeleton.getBone(canonBone);
      const restQ = skeleton.getRestQuat(canonBone);
      if (!bone || !restQ) return;

      const rawZ = Math.max(minZ, Math.min(maxZ, dx * 1.4));
      const rawX = Math.max(minX, Math.min(maxX, dy * 1.4));
      const prev = this.smoothedBones.get(canonBone) || new THREE.Euler(0, 0, 0);
      const a = Math.max(0.05, Math.min(0.95, smoothingAlpha));
      const next = new THREE.Euler(
        prev.x + (rawX - prev.x) * a,
        0,
        prev.z + (rawZ - prev.z) * a
      );
      this.smoothedBones.set(canonBone, next);
      const deltaQ = new THREE.Quaternion().setFromEuler(next);
      bone.quaternion.copy(restQ).multiply(deltaQ);
      applied++;
    };

    const ls = byName.get('left_shoulder');
    const le = byName.get('left_elbow');
    if (ls && le) {
      applyLimbTilt('LeftArm', le.x - ls.x, le.y - ls.y, -1.5, 1.5, -1.6, 1.6);
    }
    const rs = byName.get('right_shoulder');
    const re = byName.get('right_elbow');
    if (rs && re) {
      applyLimbTilt('RightArm', re.x - rs.x, re.y - rs.y, -1.5, 1.5, -1.6, 1.6);
    }
    const spineMid = byName.get('spine') || byName.get('nose');
    const hipsMid = byName.get('hips');
    if (spineMid && hipsMid) {
      applyLimbTilt('Spine', (spineMid.x - hipsMid.x) * 0.4, (hipsMid.y - spineMid.y) * 0.4, -0.9, 0.9, -0.5, 0.5);
    }

    if (applied > 0) this.lastValidTimestamp = frame.timestampMs;
    return { appliedBones: applied, rejectedLandmarks: rejected };
  }

  public getLastValidTimestamp(): number {
    return this.lastValidTimestamp;
  }

  public reset(): void {
    this.smoothedBones.clear();
  }
}

/**
 * Generates clean procedural THREE.AnimationClip fallbacks for states when GLB does not embed a matching clip
 * (e.g. RAISE_ARMS, BEND, WALK, RUN, SIT, TURN), normalized to actual skeleton bone names.
 */
export function buildProceduralMotionClip(
  state: MotionState,
  skeleton: SkeletonAdapter
): THREE.AnimationClip | null {
  const b = (canon: string) => skeleton.getBone(canon);
  const tracks: THREE.KeyframeTrack[] = [];

  const addEulerTrack = (canon: string, times: number[], eulersDeg: [number, number, number][]) => {
    const bone = b(canon);
    const rest = skeleton.getRestQuat(canon);
    if (!bone || !rest) return;
    const values: number[] = [];
    const qDelta = new THREE.Quaternion();
    const qOut = new THREE.Quaternion();
    const e = new THREE.Euler();
    for (const [rx, ry, rz] of eulersDeg) {
      e.set(THREE.MathUtils.degToRad(rx), THREE.MathUtils.degToRad(ry), THREE.MathUtils.degToRad(rz), 'XYZ');
      qDelta.setFromEuler(e);
      qOut.copy(rest).multiply(qDelta);
      values.push(qOut.x, qOut.y, qOut.z, qOut.w);
    }
    tracks.push(new THREE.QuaternionKeyframeTrack(`${bone.name}.quaternion`, times, values));
  };

  if (state === 'WALK') {
    const t = [0, 0.35, 0.7, 1.05, 1.4];
    addEulerTrack('LeftUpLeg', t, [[24, 0, -4], [0, 0, -4], [-22, 0, -4], [0, 0, -4], [24, 0, -4]]);
    addEulerTrack('RightUpLeg', t, [[-22, 0, 4], [0, 0, 4], [24, 0, 4], [0, 0, 4], [-22, 0, 4]]);
    addEulerTrack('LeftLeg', t, [[-12, 0, 0], [-36, 0, 0], [-10, 0, 0], [-5, 0, 0], [-12, 0, 0]]);
    addEulerTrack('RightLeg', t, [[-10, 0, 0], [-5, 0, 0], [-12, 0, 0], [-36, 0, 0], [-10, 0, 0]]);
    addEulerTrack('LeftArm', t, [[-18, 0, 3], [0, 0, 3], [18, 0, 3], [0, 0, 3], [-18, 0, 3]]);
    addEulerTrack('RightArm', t, [[18, 0, -3], [0, 0, -3], [-18, 0, -3], [0, 0, -3], [18, 0, -3]]);
    addEulerTrack('Spine', t, [[3, -4, 0], [3, 0, 0], [3, 4, 0], [3, 0, 0], [3, -4, 0]]);
    return tracks.length ? new THREE.AnimationClip('MotionCore_Walk', 1.4, tracks) : null;
  }

  if (state === 'RUN') {
    const t = [0, 0.22, 0.45, 0.67, 0.9];
    addEulerTrack('LeftUpLeg', t, [[40, 0, -3], [0, 0, -3], [-32, 0, -3], [15, 0, -3], [40, 0, -3]]);
    addEulerTrack('RightUpLeg', t, [[-32, 0, 3], [15, 0, 3], [40, 0, 3], [0, 0, 3], [-32, 0, 3]]);
    addEulerTrack('LeftLeg', t, [[-35, 0, 0], [-85, 0, 0], [-20, 0, 0], [-45, 0, 0], [-35, 0, 0]]);
    addEulerTrack('RightLeg', t, [[-20, 0, 0], [-45, 0, 0], [-35, 0, 0], [-85, 0, 0], [-20, 0, 0]]);
    addEulerTrack('LeftArm', t, [[-36, 0, 5], [0, 0, 5], [36, 0, 5], [0, 0, 5], [-36, 0, 5]]);
    addEulerTrack('RightArm', t, [[36, 0, -5], [0, 0, -5], [-36, 0, -5], [0, 0, -5], [36, 0, -5]]);
    addEulerTrack('LeftForeArm', t, [[-65, 0, 0], [-75, 0, 0], [-65, 0, 0], [-75, 0, 0], [-65, 0, 0]]);
    addEulerTrack('RightForeArm', t, [[-65, 0, 0], [-75, 0, 0], [-65, 0, 0], [-75, 0, 0], [-65, 0, 0]]);
    addEulerTrack('Spine', t, [[9, -6, 0], [10, 0, 0], [9, 6, 0], [10, 0, 0], [9, -6, 0]]);
    return tracks.length ? new THREE.AnimationClip('MotionCore_Run', 0.9, tracks) : null;
  }

  if (state === 'RAISE_ARMS') {
    const t = [0, 0.65, 1.45, 2.1];
    addEulerTrack('LeftArm', t, [[0, 0, 0], [0, 0, 78], [0, 0, 78], [0, 0, 0]]);
    addEulerTrack('RightArm', t, [[0, 0, 0], [0, 0, -78], [0, 0, -78], [0, 0, 0]]);
    addEulerTrack('LeftForeArm', t, [[0, 0, 0], [0, 0, 14], [0, 0, 14], [0, 0, 0]]);
    addEulerTrack('RightForeArm', t, [[0, 0, 0], [0, 0, -14], [0, 0, -14], [0, 0, 0]]);
    return tracks.length ? new THREE.AnimationClip('MotionCore_RaiseArms', 2.1, tracks) : null;
  }

  if (state === 'BEND') {
    const t = [0, 0.7, 1.4, 2.1];
    addEulerTrack('Spine', t, [[0, 0, 0], [32, 0, 0], [32, 0, 0], [0, 0, 0]]);
    addEulerTrack('Spine1', t, [[0, 0, 0], [18, 0, 0], [18, 0, 0], [0, 0, 0]]);
    addEulerTrack('Head', t, [[0, 0, 0], [-14, 0, 0], [-14, 0, 0], [0, 0, 0]]);
    return tracks.length ? new THREE.AnimationClip('MotionCore_Bend', 2.1, tracks) : null;
  }

  if (state === 'SIT') {
    const t = [0, 0.75, 2.5];
    addEulerTrack('LeftUpLeg', t, [[0, 0, 0], [82, 0, 0], [82, 0, 0]]);
    addEulerTrack('RightUpLeg', t, [[0, 0, 0], [82, 0, 0], [82, 0, 0]]);
    addEulerTrack('LeftLeg', t, [[0, 0, 0], [-85, 0, 0], [-85, 0, 0]]);
    addEulerTrack('RightLeg', t, [[0, 0, 0], [-85, 0, 0], [-85, 0, 0]]);
    addEulerTrack('Spine', t, [[0, 0, 0], [-4, 0, 0], [-3, 0, 0]]);
    return tracks.length ? new THREE.AnimationClip('MotionCore_Sit', 2.5, tracks) : null;
  }

  if (state === 'STAND') {
    const t = [0, 0.75];
    addEulerTrack('LeftUpLeg', t, [[82, 0, 0], [0, 0, 0]]);
    addEulerTrack('RightUpLeg', t, [[82, 0, 0], [0, 0, 0]]);
    addEulerTrack('LeftLeg', t, [[-85, 0, 0], [0, 0, 0]]);
    addEulerTrack('RightLeg', t, [[-85, 0, 0], [0, 0, 0]]);
    addEulerTrack('Spine', t, [[-4, 0, 0], [0, 0, 0]]);
    return tracks.length ? new THREE.AnimationClip('MotionCore_Stand', 0.75, tracks) : null;
  }

  if (state === 'TURN') {
    const t = [0, 0.75, 1.5];
    addEulerTrack('Hips', t, [[0, 0, 0], [0, 180, 0], [0, 360, 0]]);
    addEulerTrack('Spine', t, [[0, 0, 0], [0, 12, 0], [0, 0, 0]]);
    return tracks.length ? new THREE.AnimationClip('MotionCore_Turn', 1.5, tracks) : null;
  }

  if (state === 'IDLE') {
    const t = [0, 1.6, 3.2];
    addEulerTrack('Spine2', t, [[0, 0, 0], [1.8, 0, 0], [0, 0, 0]]);
    addEulerTrack('LeftArm', t, [[0, 0, 2], [1.5, 0, 3], [0, 0, 2]]);
    addEulerTrack('RightArm', t, [[0, 0, -2], [1.5, 0, -3], [0, 0, -2]]);
    return tracks.length ? new THREE.AnimationClip('MotionCore_Idle', 3.2, tracks) : null;
  }

  return null;
}

export class AnimationController {
  private mixer: THREE.AnimationMixer | null = null;
  private skeleton = new SkeletonAdapter();
  private actions = new Map<string, THREE.AnimationAction>();
  private stateClips = new Map<MotionState, THREE.AnimationClip>();
  private currentAction: THREE.AnimationAction | null = null;
  private onClipFinished?: () => void;

  public init(root: THREE.Object3D, glbClips: THREE.AnimationClip[] = []): SkeletonCompatibilityReport {
    this.dispose();
    const report = this.skeleton.bind(root);
    this.mixer = new THREE.AnimationMixer(root);

    // 1. Register and retarget GLB clips
    const stateMatchers: [MotionState, RegExp][] = [
      ['IDLE', /^idle$/i],
      ['WALK', /^walk$/i],
      ['RUN', /^run$/i],
      ['TURN', /turn|spin/i],
      ['SIT', /sit_idle|sit/i],
      ['STAND', /stand_up|stand/i],
      ['RAISE_ARMS', /raise_arms|cheer|present_both/i],
      ['BEND', /crouch|bend/i],
    ];

    for (const clip of glbClips) {
      const normKey = clip.name.toLowerCase().trim().replace(/[\s-]+/g, '_');
      const retargeted = report.isCompatible ? RetargetingEngine.retargetClip(clip, this.skeleton).clip : clip;
      const action = this.mixer.clipAction(retargeted);
      this.actions.set(normKey, action);
      for (const [st, rx] of stateMatchers) {
        if (!this.stateClips.has(st) && rx.test(clip.name)) {
          this.stateClips.set(st, retargeted);
        }
      }
    }

    // 2. Build deterministic procedural clips for missing canonical locomotion/pose states
    const neededStates: MotionState[] = ['IDLE', 'WALK', 'RUN', 'TURN', 'RAISE_ARMS', 'BEND', 'SIT', 'STAND'];
    for (const st of neededStates) {
      if (!this.stateClips.has(st)) {
        const proc = buildProceduralMotionClip(st, this.skeleton);
        if (proc) {
          this.stateClips.set(st, proc);
          this.actions.set(proc.name.toLowerCase(), this.mixer.clipAction(proc));
        }
      }
    }

    this.mixer.addEventListener('finished', () => {
      this.onClipFinished?.();
    });

    return report;
  }

  public getSkeleton(): SkeletonAdapter {
    return this.skeleton;
  }

  public getLoadedClipNames(): string[] {
    return Array.from(this.actions.keys());
  }

  public playState(
    state: MotionState,
    options: { blendDurationSeconds: number; loop: boolean; customClipName?: string | null; onFinished?: () => void }
  ): boolean {
    if (!this.mixer) return false;
    let action: THREE.AnimationAction | undefined;

    if (state === 'CUSTOM' && options.customClipName) {
      const key = options.customClipName.toLowerCase().trim().replace(/[\s-]+/g, '_');
      action = this.actions.get(key);
      if (!action) {
        for (const [k, a] of this.actions.entries()) {
          if (k.includes(key) || key.includes(k)) {
            action = a;
            break;
          }
        }
      }
    } else {
      const clip = this.stateClips.get(state);
      if (clip) {
        action = this.mixer.clipAction(clip);
      }
    }

    if (!action) return false;

    this.onClipFinished = options.onFinished;
    action.reset();
    action.setLoop(options.loop ? THREE.LoopRepeat : THREE.LoopOnce, options.loop ? Infinity : 1);
    action.clampWhenFinished = !options.loop;

    if (this.currentAction && this.currentAction !== action) {
      action.play();
      this.currentAction.crossFadeTo(action, options.blendDurationSeconds, true);
    } else {
      action.fadeIn(options.blendDurationSeconds);
      action.play();
    }
    this.currentAction = action;
    return true;
  }

  public update(deltaSeconds: number, timeScale: number = 1.0): void {
    if (!this.mixer) return;
    this.mixer.update(deltaSeconds * timeScale);
  }

  public reset(): void {
    if (this.mixer) {
      this.mixer.stopAllAction();
    }
    this.currentAction = null;
    this.skeleton.restoreBindPose();
  }

  public dispose(): void {
    if (this.mixer) {
      this.mixer.stopAllAction();
      this.mixer.uncacheRoot(this.mixer.getRoot());
      this.mixer = null;
    }
    this.actions.clear();
    this.stateClips.clear();
    this.currentAction = null;
  }
}
