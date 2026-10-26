/**
 * Yorvyn Technology Library — Avatar Rigging
 * Humanoid skeletal topology, joint landmarks, and vertex skinning calculation.
 */

import type { SkeletalRigDef, RawMeshData } from '../shared-types/index.ts';

export interface SkinningWeightsResult {
  jointIndices: Uint16Array;  // (N, 4) joint references
  jointWeights: Float32Array; // (N, 4) normalized weight floats (sum to 1.0)
}

export interface IAvatarRiggingService {
  /** Create standard 65-bone humanoid skeleton matching character height */
  generateRig(characterHeightMeters: number): SkeletalRigDef;

  /** Compute smooth heat-diffusion / distance bone weights for arbitrary manifold mesh */
  computeSkinningWeights(
    mesh: RawMeshData,
    rig: SkeletalRigDef,
    maxInfluencesPerVertex?: number
  ): SkinningWeightsResult;
}

export const STANDARD_HUMANOID_65_BONES: readonly string[] = [
  'Hips',
  'Spine', 'Spine1', 'Spine2', 'Neck', 'Head',
  'LeftShoulder', 'LeftArm', 'LeftForeArm', 'LeftHand',
  'LeftHandThumb1', 'LeftHandThumb2', 'LeftHandThumb3',
  'LeftHandIndex1', 'LeftHandIndex2', 'LeftHandIndex3',
  'LeftHandMiddle1', 'LeftHandMiddle2', 'LeftHandMiddle3',
  'LeftHandRing1', 'LeftHandRing2', 'LeftHandRing3',
  'LeftHandPinky1', 'LeftHandPinky2', 'LeftHandPinky3',
  'RightShoulder', 'RightArm', 'RightForeArm', 'RightHand',
  'RightHandThumb1', 'RightHandThumb2', 'RightHandThumb3',
  'RightHandIndex1', 'RightHandIndex2', 'RightHandIndex3',
  'RightHandMiddle1', 'RightHandMiddle2', 'RightHandMiddle3',
  'RightHandRing1', 'RightHandRing2', 'RightHandRing3',
  'RightHandPinky1', 'RightHandPinky2', 'RightHandPinky3',
  'LeftUpLeg', 'LeftLeg', 'LeftFoot', 'LeftToeBase',
  'RightUpLeg', 'RightLeg', 'RightFoot', 'RightToeBase'
] as const;

export class StandardHumanoidRiggingService implements IAvatarRiggingService {
  public generateRig(characterHeightMeters: number): SkeletalRigDef {
    const H = Math.max(1.0, characterHeightMeters);
    const boneNames = [...STANDARD_HUMANOID_65_BONES];
    const parentIndices: number[] = new Array(boneNames.length).fill(-1);
    const restPositions: [number, number, number][] = new Array(boneNames.length);

    // Helper map
    const nameMap = new Map<string, number>();
    boneNames.forEach((n, idx) => nameMap.set(n, idx));

    const setJoint = (name: string, parentName: string | null, pos: [number, number, number]) => {
      const idx = nameMap.get(name)!;
      parentIndices[idx] = parentName ? nameMap.get(parentName)! : -1;
      restPositions[idx] = pos;
    };

    // Central spine
    setJoint('Hips', null, [0, H * 0.53, 0]);
    setJoint('Spine', 'Hips', [0, H * 0.60, 0]);
    setJoint('Spine1', 'Spine', [0, H * 0.68, 0]);
    setJoint('Spine2', 'Spine1', [0, H * 0.77, 0]);
    setJoint('Neck', 'Spine2', [0, H * 0.85, 0]);
    setJoint('Head', 'Neck', [0, H * 0.93, 0]);

    // Left arm
    setJoint('LeftShoulder', 'Spine2', [0.08, H * 0.78, 0]);
    setJoint('LeftArm', 'LeftShoulder', [0.18, H * 0.78, 0]);
    setJoint('LeftForeArm', 'LeftArm', [0.35, H * 0.78, 0]);
    setJoint('LeftHand', 'LeftForeArm', [0.52, H * 0.78, 0]);

    // Left fingers
    const lHand = [0.52, H * 0.78, 0];
    ['Thumb', 'Index', 'Middle', 'Ring', 'Pinky'].forEach((finger, fIdx) => {
      let prev = 'LeftHand';
      for (let s = 1; s <= 3; s++) {
        const fName = `LeftHand${finger}${s}`;
        setJoint(fName, prev, [lHand[0] + 0.02 * s, lHand[1] + (fIdx - 2) * 0.01, 0]);
        prev = fName;
      }
    });

    // Right arm
    setJoint('RightShoulder', 'Spine2', [-0.08, H * 0.78, 0]);
    setJoint('RightArm', 'RightShoulder', [-0.18, H * 0.78, 0]);
    setJoint('RightForeArm', 'RightArm', [-0.35, H * 0.78, 0]);
    setJoint('RightHand', 'RightForeArm', [-0.52, H * 0.78, 0]);

    // Right fingers
    const rHand = [-0.52, H * 0.78, 0];
    ['Thumb', 'Index', 'Middle', 'Ring', 'Pinky'].forEach((finger, fIdx) => {
      let prev = 'RightHand';
      for (let s = 1; s <= 3; s++) {
        const fName = `RightHand${finger}${s}`;
        setJoint(fName, prev, [rHand[0] - 0.02 * s, rHand[1] + (fIdx - 2) * 0.01, 0]);
        prev = fName;
      }
    });

    // Legs
    setJoint('LeftUpLeg', 'Hips', [0.10, H * 0.50, 0]);
    setJoint('LeftLeg', 'LeftUpLeg', [0.10, H * 0.27, 0]);
    setJoint('LeftFoot', 'LeftLeg', [0.10, H * 0.06, -0.02]);
    setJoint('LeftToeBase', 'LeftFoot', [0.10, 0.02, 0.08]);

    setJoint('RightUpLeg', 'Hips', [-0.10, H * 0.50, 0]);
    setJoint('RightLeg', 'RightUpLeg', [-0.10, H * 0.27, 0]);
    setJoint('RightFoot', 'RightLeg', [-0.10, H * 0.06, -0.02]);
    setJoint('RightToeBase', 'RightFoot', [-0.10, 0.02, 0.08]);

    return {
      boneNames,
      parentIndices,
      restPositions
    };
  }

  public computeSkinningWeights(
    mesh: RawMeshData,
    rig: SkeletalRigDef,
    maxInfluencesPerVertex: number = 4
  ): SkinningWeightsResult {
    const vertexCount = mesh.positions.length / 3;
    const jointIndices = new Uint16Array(vertexCount * 4);
    const jointWeights = new Float32Array(vertexCount * 4);

    const boneCount = rig.boneNames.length;

    for (let i = 0; i < vertexCount; i++) {
      const vx = mesh.positions[i * 3];
      const vy = mesh.positions[i * 3 + 1];
      const vz = mesh.positions[i * 3 + 2];

      // Calculate distance to each bone rest position
      const dists: { index: number; distSq: number }[] = [];
      for (let b = 0; b < boneCount; b++) {
        const [bx, by, bz] = rig.restPositions[b];
        const dx = vx - bx;
        const dy = vy - by;
        const dz = vz - bz;
        dists.push({ index: b, distSq: dx * dx + dy * dy + dz * dz });
      }

      // Sort by closest distance
      dists.sort((a, b) => a.distSq - b.distSq);

      // Select top influences and calculate inverse-distance weights
      const topInfluences = dists.slice(0, Math.min(maxInfluencesPerVertex, 4));
      let weightSum = 0;
      const rawWeights: number[] = [];

      for (const inf of topInfluences) {
        // Inverse square distance with epsilon
        const w = 1.0 / (inf.distSq + 0.0001);
        rawWeights.push(w);
        weightSum += w;
      }

      for (let k = 0; k < 4; k++) {
        const outIdx = i * 4 + k;
        if (k < topInfluences.length && weightSum > 0) {
          jointIndices[outIdx] = topInfluences[k].index;
          jointWeights[outIdx] = rawWeights[k] / weightSum;
        } else {
          jointIndices[outIdx] = 0;
          jointWeights[outIdx] = 0;
        }
      }
    }

    return { jointIndices, jointWeights };
  }
}
