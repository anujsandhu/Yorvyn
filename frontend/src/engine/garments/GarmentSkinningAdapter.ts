/**
 * YORVYN — Garment Skinning Adapter
 * Validates, repairs, and normalizes skeletal bone weights and indices for garment meshes.
 * Provides BVH-accelerated barycentric surface weight transfer for unrigged garments.
 */

import * as THREE from 'three';
import { MeshBVH } from 'three-mesh-bvh';

export interface SkinningAdaptationResult {
  valid: boolean;
  normalizedCount: number;
  prunedCount: number;
  skinIndices: Uint16Array;
  skinWeights: Float32Array;
}

export interface SemanticSkinningLandmarks {
  hipsPos: THREE.Vector3;
  spinePos?: THREE.Vector3;
  spine1Pos?: THREE.Vector3;
  spine2Pos: THREE.Vector3;
  neckPos: THREE.Vector3;
  headPos: THREE.Vector3;
  leftShoulderPos?: THREE.Vector3;
  rightShoulderPos?: THREE.Vector3;
  leftArmPos: THREE.Vector3;
  rightArmPos: THREE.Vector3;
  leftForeArmPos?: THREE.Vector3;
  rightForeArmPos?: THREE.Vector3;
  leftHandPos?: THREE.Vector3;
  rightHandPos?: THREE.Vector3;
  leftUpLegPos?: THREE.Vector3;
  rightUpLegPos?: THREE.Vector3;
  leftLegPos?: THREE.Vector3;
  rightLegPos?: THREE.Vector3;
  leftFootPos?: THREE.Vector3;
  rightFootPos?: THREE.Vector3;
  waistY: number;
  neckY: number;
}

export interface SemanticSkinningParams {
  positions: Float32Array;
  componentTags?: string[];
  skeleton: THREE.Skeleton;
  landmarks: SemanticSkinningLandmarks;
  category?: string;
  influencesPerVertex?: number;
}

export class GarmentSkinningAdapter {
  /**
   * Normalizes bone weights such that the sum of weights for every vertex strictly equals 1.0.
   * Prunes insignificant weights (< 0.005) and enforces bone index limits.
   */
  public static normalizeAndValidateWeights(
    skinIndices: Uint16Array,
    skinWeights: Float32Array,
    numBones: number,
    influencesPerVertex: number = 4
  ): SkinningAdaptationResult {
    const vCount = skinWeights.length / influencesPerVertex;
    const cleanIndices = new Uint16Array(skinIndices);
    const cleanWeights = new Float32Array(skinWeights);

    let normalizedCount = 0;
    let prunedCount = 0;

    for (let v = 0; v < vCount; v++) {
      const offset = v * influencesPerVertex;
      let sum = 0;

      // 1. Clamp invalid bone indices and sum weights
      for (let k = 0; k < influencesPerVertex; k++) {
        if (cleanIndices[offset + k] >= numBones) {
          cleanIndices[offset + k] = 0;
          cleanWeights[offset + k] = 0;
        }

        // Prune trivial weights
        if (cleanWeights[offset + k] < 0.005) {
          if (cleanWeights[offset + k] > 0) prunedCount++;
          cleanWeights[offset + k] = 0;
        }

        sum += cleanWeights[offset + k];
      }

      // 2. Normalize weights to sum strictly to 1.0
      if (sum > 1e-6) {
        const invSum = 1.0 / sum;
        for (let k = 0; k < influencesPerVertex; k++) {
          cleanWeights[offset + k] *= invSum;
        }
        if (Math.abs(sum - 1.0) > 1e-4) {
          normalizedCount++;
        }
      } else {
        // Fallback for unweighted vertices: bind 100% to root/pelvis bone 0
        cleanIndices[offset] = 0;
        cleanWeights[offset] = 1.0;
        for (let k = 1; k < influencesPerVertex; k++) {
          cleanIndices[offset + k] = 0;
          cleanWeights[offset + k] = 0;
        }
        normalizedCount++;
      }
    }

    return {
      valid: true,
      normalizedCount,
      prunedCount,
      skinIndices: cleanIndices,
      skinWeights: cleanWeights
    };
  }

  /**
   * Transfers skeletal skin weights from an avatar body mesh to an unrigged garment mesh
   * using BVH-accelerated nearest triangle spatial lookup and barycentric weight interpolation.
   */
  public static transferBodySkinWeightsBVH(
    garmentPositions: Float32Array,
    bodyGeometry: THREE.BufferGeometry,
    influencesPerVertex: number = 4
  ): SkinningAdaptationResult {
    // Ensure BVH tree exists on body geometry
    let bvh = (bodyGeometry as any).boundsTree as MeshBVH | undefined;
    if (!bvh) {
      bvh = new MeshBVH(bodyGeometry);
      (bodyGeometry as any).boundsTree = bvh;
    }

    const posAttr = bodyGeometry.attributes.position;
    const idxAttr = bodyGeometry.index;
    const bodySkinIdx = bodyGeometry.attributes.skinIndex;
    const bodySkinWgt = bodyGeometry.attributes.skinWeight;

    const gCount = garmentPositions.length / 3;
    const skinIndices = new Uint16Array(gCount * influencesPerVertex);
    const skinWeights = new Float32Array(gCount * influencesPerVertex);

    if (!bodySkinIdx || !bodySkinWgt) {
      // Body has no skinning; default all to bone 0
      for (let i = 0; i < gCount; i++) {
        skinIndices[i * influencesPerVertex] = 0;
        skinWeights[i * influencesPerVertex] = 1.0;
      }
      return {
        valid: true,
        normalizedCount: gCount,
        prunedCount: 0,
        skinIndices,
        skinWeights
      };
    }

    const gVec = new THREE.Vector3();
    const targetResult = { point: new THREE.Vector3(), distance: 0, faceIndex: 0 };
    const p0 = new THREE.Vector3();
    const p1 = new THREE.Vector3();
    const p2 = new THREE.Vector3();
    const v0 = new THREE.Vector3();
    const v1 = new THREE.Vector3();
    const v2 = new THREE.Vector3();

    for (let g = 0; g < gCount; g++) {
      gVec.set(garmentPositions[g * 3], garmentPositions[g * 3 + 1], garmentPositions[g * 3 + 2]);

      // Query closest point on body surface
      bvh.closestPointToPoint(gVec, targetResult);

      const f = targetResult.faceIndex;
      let i0 = f * 3, i1 = f * 3 + 1, i2 = f * 3 + 2;
      if (idxAttr) {
        i0 = idxAttr.getX(f * 3);
        i1 = idxAttr.getX(f * 3 + 1);
        i2 = idxAttr.getX(f * 3 + 2);
      }

      p0.set(posAttr.getX(i0), posAttr.getY(i0), posAttr.getZ(i0));
      p1.set(posAttr.getX(i1), posAttr.getY(i1), posAttr.getZ(i1));
      p2.set(posAttr.getX(i2), posAttr.getY(i2), posAttr.getZ(i2));

      // Calculate barycentric coordinates of targetResult.point with respect to triangle (p0, p1, p2)
      v0.subVectors(p1, p0);
      v1.subVectors(p2, p0);
      v2.subVectors(targetResult.point, p0);

      const d00 = v0.dot(v0);
      const d01 = v0.dot(v1);
      const d11 = v1.dot(v1);
      const d20 = v2.dot(v0);
      const d21 = v2.dot(v1);
      const denom = d00 * d11 - d01 * d01;

      let v = 0.33, w = 0.33, u = 0.34;
      if (Math.abs(denom) > 1e-8) {
        v = (d11 * d20 - d01 * d21) / denom;
        w = (d00 * d21 - d01 * d20) / denom;
        u = 1.0 - v - w;
      }

      // Clamp barycentrics to [0, 1]
      u = Math.max(0, Math.min(1, u));
      v = Math.max(0, Math.min(1, v));
      w = Math.max(0, Math.min(1, w));
      const bSum = u + v + w || 1.0;
      u /= bSum;
      v /= bSum;
      w /= bSum;

      // Accumulate bone weights from the 3 vertices
      const boneMap = new Map<number, number>();
      const addBone = (bone: number, weight: number) => {
        if (weight <= 0) return;
        boneMap.set(bone, (boneMap.get(bone) || 0) + weight);
      };

      for (let k = 0; k < 4; k++) {
        addBone(bodySkinIdx.getComponent(i0, k), bodySkinWgt.getComponent(i0, k) * u);
        addBone(bodySkinIdx.getComponent(i1, k), bodySkinWgt.getComponent(i1, k) * v);
        addBone(bodySkinIdx.getComponent(i2, k), bodySkinWgt.getComponent(i2, k) * w);
      }

      // Sort by weight descending and keep top 4
      const sortedBones = Array.from(boneMap.entries()).sort((a, b) => b[1] - a[1]);
      let totalW = 0;
      const count = Math.min(influencesPerVertex, sortedBones.length);

      for (let k = 0; k < count; k++) {
        totalW += sortedBones[k][1];
      }

      const offset = g * influencesPerVertex;
      if (totalW > 1e-6) {
        for (let k = 0; k < influencesPerVertex; k++) {
          if (k < count) {
            skinIndices[offset + k] = sortedBones[k][0];
            skinWeights[offset + k] = sortedBones[k][1] / totalW;
          } else {
            skinIndices[offset + k] = 0;
            skinWeights[offset + k] = 0;
          }
        }
      } else {
        skinIndices[offset] = 0;
        skinWeights[offset] = 1.0;
      }
    }

    return {
      valid: true,
      normalizedCount: gCount,
      prunedCount: 0,
      skinIndices,
      skinWeights
    };
  }

  /**
   * Resolves a bone index from a skeleton by matching candidate names case-insensitively.
   */
  public static findBoneIndex(skeleton: THREE.Skeleton, candidateNames: string[]): number {
    if (!skeleton || !skeleton.bones || skeleton.bones.length === 0) return 0;
    for (const cand of candidateNames) {
      const lower = cand.toLowerCase();
      const idx = skeleton.bones.findIndex((b) => {
        const bName = b.name.toLowerCase();
        return (
          bName === lower ||
          bName.endsWith(lower) ||
          bName.replace(/^mixamorig/, '') === lower ||
          bName.replace(/^ara_/, '') === lower
        );
      });
      if (idx >= 0) return idx;
    }
    return 0;
  }

  /**
   * Generates anatomically guaranteed, component-isolated skeletal bone weights for garment meshes.
   * Eliminates sleeve wing distortion by guaranteeing sleeve vertices bind strictly to arm bones,
   * torso vertices bind strictly to spine bones, and hood vertices bind to neck/head bones.
   */
  public static generateSemanticSkinWeights(params: SemanticSkinningParams): SkinningAdaptationResult {
    const {
      positions,
      componentTags,
      skeleton,
      landmarks,
      category = 'top',
      influencesPerVertex = 4
    } = params;

    const numBones = skeleton?.bones?.length || 1;
    const vCount = positions.length / 3;
    const skinIndices = new Uint16Array(vCount * influencesPerVertex);
    const skinWeights = new Float32Array(vCount * influencesPerVertex);

    // Resolve key bone indices
    const bHips = this.findBoneIndex(skeleton, ['Hips', 'pelvis']);
    const bSpine = this.findBoneIndex(skeleton, ['Spine', 'spine_01']);
    const bSpine2 = this.findBoneIndex(skeleton, ['Spine2', 'spine_03', 'chest']);
    const bNeck = this.findBoneIndex(skeleton, ['Neck']);
    const bHead = this.findBoneIndex(skeleton, ['Head']);

    const bLShoulder = this.findBoneIndex(skeleton, ['LeftShoulder', 'clavicle_l']);
    const bLArm = this.findBoneIndex(skeleton, ['LeftArm', 'upperarm_l', 'arm_l']);
    const bLFore = this.findBoneIndex(skeleton, ['LeftForeArm', 'lowerarm_l', 'forearm_l']);
    const bLHand = this.findBoneIndex(skeleton, ['LeftHand', 'hand_l', 'wrist_l']);

    const bRShoulder = this.findBoneIndex(skeleton, ['RightShoulder', 'clavicle_r']);
    const bRArm = this.findBoneIndex(skeleton, ['RightArm', 'upperarm_r', 'arm_r']);
    const bRFore = this.findBoneIndex(skeleton, ['RightForeArm', 'lowerarm_r', 'forearm_r']);
    const bRHand = this.findBoneIndex(skeleton, ['RightHand', 'hand_r', 'wrist_r']);

    const bLLegUpper = this.findBoneIndex(skeleton, ['LeftUpLeg', 'thigh_l']);
    const bLLegLower = this.findBoneIndex(skeleton, ['LeftLeg', 'calf_l']);
    const bLFoot = this.findBoneIndex(skeleton, ['LeftFoot', 'foot_l']);

    const bRLegUpper = this.findBoneIndex(skeleton, ['RightUpLeg', 'thigh_r']);
    const bRLegLower = this.findBoneIndex(skeleton, ['RightLeg', 'calf_r']);
    const bRFoot = this.findBoneIndex(skeleton, ['RightFoot', 'foot_r']);

    // Landmark references
    const waistY = landmarks.waistY ?? 0.785;
    const neckY = landmarks.neckY ?? 1.191;
    const torsoSpan = Math.max(0.1, neckY - waistY);

    const lArmPos = landmarks.leftArmPos;
    const lForePos = landmarks.leftForeArmPos || new THREE.Vector3(lArmPos.x + 0.14, lArmPos.y - 0.15, lArmPos.z);
    const lHandPos = landmarks.leftHandPos || new THREE.Vector3(lForePos.x + 0.10, lForePos.y - 0.10, lForePos.z + 0.14);

    const rArmPos = landmarks.rightArmPos;
    const rForePos = landmarks.rightForeArmPos || new THREE.Vector3(rArmPos.x - 0.14, rArmPos.y - 0.15, rArmPos.z);
    const rHandPos = landmarks.rightHandPos || new THREE.Vector3(rForePos.x - 0.10, rForePos.y - 0.10, rForePos.z + 0.14);

    const shoulderBoundaryX = Math.max(0.12, Math.abs(lArmPos.x) * 0.75);

    // Helper: assign 2 bone weights with normalized sum
    const setTwoWeights = (v: number, bone0: number, weight0: number, bone1: number, weight1: number) => {
      const off = v * influencesPerVertex;
      const sum = weight0 + weight1;
      const inv = sum > 1e-6 ? 1.0 / sum : 1.0;
      skinIndices[off] = bone0;
      skinWeights[off] = weight0 * inv;
      skinIndices[off + 1] = bone1;
      skinWeights[off + 1] = weight1 * inv;
      for (let k = 2; k < influencesPerVertex; k++) {
        skinIndices[off + k] = 0;
        skinWeights[off + k] = 0;
      }
    };

    // Helper: assign 3 bone weights
    const setThreeWeights = (v: number, b0: number, w0: number, b1: number, w1: number, b2: number, w2: number) => {
      const off = v * influencesPerVertex;
      const sum = w0 + w1 + w2;
      const inv = sum > 1e-6 ? 1.0 / sum : 1.0;
      skinIndices[off] = b0;
      skinWeights[off] = w0 * inv;
      skinIndices[off + 1] = b1;
      skinWeights[off + 1] = w1 * inv;
      skinIndices[off + 2] = b2;
      skinWeights[off + 2] = w2 * inv;
      for (let k = 3; k < influencesPerVertex; k++) {
        skinIndices[off + k] = 0;
        skinWeights[off + k] = 0;
      }
    };

    const isBottomCategory = category === 'bottom' || category === 'pants' || category === 'trousers' || category === 'jeans' || category === 'shorts';

    for (let v = 0; v < vCount; v++) {
      const px = positions[v * 3];
      const py = positions[v * 3 + 1];
      const pz = positions[v * 3 + 2];

      const tag = componentTags && componentTags[v] ? componentTags[v] : '';

      if (isBottomCategory) {
        // Bottoms / Trousers / Jeans
        const isLeftLeg = tag === 'left_leg' || (!tag && px >= 0.005);
        const isRightLeg = tag === 'right_leg' || (!tag && px <= -0.005);
        const isWaist = tag === 'waistband' || (!tag && Math.abs(px) < 0.04 && py > waistY - 0.12);

        if (isWaist) {
          setTwoWeights(v, bHips, 0.70, bSpine, 0.30);
        } else if (isLeftLeg) {
          const legFrac = THREE.MathUtils.clamp((waistY - py) / Math.max(0.1, waistY - 0.05), 0, 1);
          if (legFrac < 0.40) {
            const t = legFrac / 0.40;
            setTwoWeights(v, bHips, (1 - t) * 0.4, bLLegUpper, 0.6 + t * 0.4);
          } else if (legFrac < 0.85) {
            const t = (legFrac - 0.40) / 0.45;
            setTwoWeights(v, bLLegUpper, 1 - t, bLLegLower, t);
          } else {
            const t = (legFrac - 0.85) / 0.15;
            setTwoWeights(v, bLLegLower, 1 - t, bLFoot, t);
          }
        } else if (isRightLeg) {
          const legFrac = THREE.MathUtils.clamp((waistY - py) / Math.max(0.1, waistY - 0.05), 0, 1);
          if (legFrac < 0.40) {
            const t = legFrac / 0.40;
            setTwoWeights(v, bHips, (1 - t) * 0.4, bRLegUpper, 0.6 + t * 0.4);
          } else if (legFrac < 0.85) {
            const t = (legFrac - 0.40) / 0.45;
            setTwoWeights(v, bRLegUpper, 1 - t, bRLegLower, t);
          } else {
            const t = (legFrac - 0.85) / 0.15;
            setTwoWeights(v, bRLegLower, 1 - t, bRFoot, t);
          }
        }
        continue;
      }

      // Upper Garment (Hoodie, Jacket, Top, Shirt)
      const isLeftSleeve = tag === 'left_sleeve' || tag === 'left_cuff' ||
        (!tag && px > shoulderBoundaryX && py < neckY + 0.06);
      const isRightSleeve = tag === 'right_sleeve' || tag === 'right_cuff' ||
        (!tag && px < -shoulderBoundaryX && py < neckY + 0.06);
      const isHood = tag === 'hood' || (!tag && py > neckY - 0.03 && pz <= 0.02);

      if (isLeftSleeve) {
        // Left Sleeve strictly along Left Shoulder -> Arm -> ForeArm -> Hand
        const vArm1 = new THREE.Vector3().subVectors(lForePos, lArmPos);
        const lenArm1 = vArm1.length() || 0.20;
        const dir1 = vArm1.clone().normalize();

        const vArm2 = new THREE.Vector3().subVectors(lHandPos, lForePos);
        const lenArm2 = vArm2.length() || 0.20;
        const dir2 = vArm2.clone().normalize();

        const pt = new THREE.Vector3(px, py, pz);
        const toPt1 = new THREE.Vector3().subVectors(pt, lArmPos);
        const u1 = THREE.MathUtils.clamp(toPt1.dot(dir1) / lenArm1, 0, 1);

        const toPt2 = new THREE.Vector3().subVectors(pt, lForePos);
        const u2 = THREE.MathUtils.clamp(toPt2.dot(dir2) / lenArm2, 0, 1);

        const distToSeg1 = toPt1.clone().sub(dir1.clone().multiplyScalar(u1 * lenArm1)).length();
        const distToSeg2 = toPt2.clone().sub(dir2.clone().multiplyScalar(u2 * lenArm2)).length();

        if (distToSeg1 <= distToSeg2 && u1 < 0.95) {
          if (u1 < 0.25) {
            const s = u1 / 0.25;
            setThreeWeights(v, bLShoulder, (1 - s) * 0.35, bLArm, 0.65 + s * 0.25, bLFore, s * 0.10);
          } else {
            setTwoWeights(v, bLArm, 1 - u1, bLFore, u1);
          }
        } else {
          if (u2 > 0.80) {
            const s = (u2 - 0.80) / 0.20;
            setTwoWeights(v, bLFore, (1 - s) * 0.2, bLHand, 0.8 + s * 0.2);
          } else {
            setTwoWeights(v, bLFore, 1 - u2 * 0.5, bLHand, u2 * 0.5);
          }
        }
      } else if (isRightSleeve) {
        // Right Sleeve strictly along Right Shoulder -> Arm -> ForeArm -> Hand
        const vArm1 = new THREE.Vector3().subVectors(rForePos, rArmPos);
        const lenArm1 = vArm1.length() || 0.20;
        const dir1 = vArm1.clone().normalize();

        const vArm2 = new THREE.Vector3().subVectors(rHandPos, rForePos);
        const lenArm2 = vArm2.length() || 0.20;
        const dir2 = vArm2.clone().normalize();

        const pt = new THREE.Vector3(px, py, pz);
        const toPt1 = new THREE.Vector3().subVectors(pt, rArmPos);
        const u1 = THREE.MathUtils.clamp(toPt1.dot(dir1) / lenArm1, 0, 1);

        const toPt2 = new THREE.Vector3().subVectors(pt, rForePos);
        const u2 = THREE.MathUtils.clamp(toPt2.dot(dir2) / lenArm2, 0, 1);

        const distToSeg1 = toPt1.clone().sub(dir1.clone().multiplyScalar(u1 * lenArm1)).length();
        const distToSeg2 = toPt2.clone().sub(dir2.clone().multiplyScalar(u2 * lenArm2)).length();

        if (distToSeg1 <= distToSeg2 && u1 < 0.95) {
          if (u1 < 0.25) {
            const s = u1 / 0.25;
            setThreeWeights(v, bRShoulder, (1 - s) * 0.35, bRArm, 0.65 + s * 0.25, bRFore, s * 0.10);
          } else {
            setTwoWeights(v, bRArm, 1 - u1, bRFore, u1);
          }
        } else {
          if (u2 > 0.80) {
            const s = (u2 - 0.80) / 0.20;
            setTwoWeights(v, bRFore, (1 - s) * 0.2, bRHand, 0.8 + s * 0.2);
          } else {
            setTwoWeights(v, bRFore, 1 - u2 * 0.5, bRHand, u2 * 0.5);
          }
        }
      } else if (isHood) {
        // Hood cowl draped behind head/neck
        const hoodFrac = THREE.MathUtils.clamp((py - (neckY - 0.02)) / 0.18, 0, 1);
        setTwoWeights(v, bNeck, 1 - hoodFrac * 0.70, bHead, hoodFrac * 0.70);
      } else if ((category === 'dress' || category === 'skirt' || tag === 'skirt') && py < waistY - 0.015) {
        // Skirt / Dress lower flare: blend hips at waist seamlessly into Left/Right UpLeg & knee so thighs never pierce fabric
        const skirtSpan = Math.max(0.25, waistY - 0.15);
        const skirtT = THREE.MathUtils.clamp((waistY - py) / skirtSpan, 0, 1);
        const legSideBlend = THREE.MathUtils.clamp(Math.abs(px) / 0.08, 0, 1);
        const legFollow = Math.min(0.85, skirtT * 0.95) * (0.35 + 0.65 * legSideBlend);

        if (px >= 0.01) {
          if (skirtT > 0.55) {
            const kneeMix = ((skirtT - 0.55) / 0.45) * 0.45;
            setThreeWeights(v, bHips, 1 - legFollow, bLLegUpper, legFollow * (1 - kneeMix), bLLegLower, legFollow * kneeMix);
          } else {
            setTwoWeights(v, bHips, 1 - legFollow, bLLegUpper, legFollow);
          }
        } else if (px <= -0.01) {
          if (skirtT > 0.55) {
            const kneeMix = ((skirtT - 0.55) / 0.45) * 0.45;
            setThreeWeights(v, bHips, 1 - legFollow, bRLegUpper, legFollow * (1 - kneeMix), bRLegLower, legFollow * kneeMix);
          } else {
            setTwoWeights(v, bHips, 1 - legFollow, bRLegUpper, legFollow);
          }
        } else {
          setThreeWeights(v, bHips, 1 - legFollow * 0.6, bLLegUpper, legFollow * 0.3, bRLegUpper, legFollow * 0.3);
        }
      } else {
        // Torso / Kangaroo Pocket / Drawstrings / Waistband
        const torsoFrac = THREE.MathUtils.clamp((py - (waistY - 0.06)) / (torsoSpan + 0.06), 0, 1);

        if (torsoFrac < 0.20) {
          const t = torsoFrac / 0.20;
          setTwoWeights(v, bHips, 1 - t * 0.6, bSpine, t * 0.6);
        } else if (torsoFrac < 0.55) {
          const t = (torsoFrac - 0.20) / 0.35;
          setTwoWeights(v, bSpine, 1 - t, bSpine2, t);
        } else if (torsoFrac < 0.88) {
          const t = (torsoFrac - 0.55) / 0.33;
          setTwoWeights(v, bSpine2, 1 - t * 0.4, bNeck, t * 0.4);
        } else {
          const t = (torsoFrac - 0.88) / 0.12;
          setTwoWeights(v, bSpine2, (1 - t) * 0.35, bNeck, 0.65 + t * 0.35);
        }
      }
    }

    return this.normalizeAndValidateWeights(skinIndices, skinWeights, numBones, influencesPerVertex);
  }
}
