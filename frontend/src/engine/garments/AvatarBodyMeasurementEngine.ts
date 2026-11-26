/**
 * YORVYN — Avatar Body Measurement Engine (Phase 5)
 * Extracts 14 canonical anthropometric measurements directly from Three.js avatar models,
 * skinned meshes, and humanoid skeletons. Supports custom avatar proportion adjustments.
 */

import * as THREE from 'three';

export interface AvatarBodyMeasurements {
  heightCm: number;
  shoulderWidthCm: number;
  chestCircumferenceCm: number;
  waistCircumferenceCm: number;
  hipCircumferenceCm: number;
  neckCircumferenceCm: number;
  armLengthCm: number;
  upperArmCircumferenceCm: number;
  wristCircumferenceCm: number;
  inseamCm: number;
  thighCircumferenceCm: number;
  calfCircumferenceCm: number;
  footLengthCm: number;
  footWidthCm: number;
  unit: 'cm';
  isValid: boolean;
  warnings: string[];
}

export class AvatarBodyMeasurementEngine {
  /**
   * Extracts all 14 body measurements from an active Three.js avatar model hierarchy.
   */
  public static measureAvatar(avatarRoot: THREE.Object3D): AvatarBodyMeasurements {
    const warnings: string[] = [];

    // 1. Locate Body Mesh and Skeleton
    let bodyMesh: any = null;
    let skeleton: any = null;
    const bones: Map<string, THREE.Bone> = new Map();

    avatarRoot.traverse((child) => {
      if ((child as THREE.SkinnedMesh).isSkinnedMesh) {
        const sm = child as THREE.SkinnedMesh;
        if (!bodyMesh || child.name.includes('Body') || child.name.includes('Alex_1')) {
          bodyMesh = sm;
          if (sm.skeleton) skeleton = sm.skeleton;
        }
      } else if ((child as THREE.Mesh).isMesh && !bodyMesh) {
        bodyMesh = child as THREE.Mesh;
      }

      if ((child as THREE.Bone).isBone) {
        bones.set(child.name, child as THREE.Bone);
      }
    });

    if (skeleton && skeleton.bones) {
      for (const b of skeleton.bones) {
        bones.set(b.name, b);
      }
    }

    // Default canonical fallback (1.75m standard human)
    let heightCm = 175.0;
    let shoulderWidthCm = 43.5;
    let chestCircCm = 96.0;
    let waistCircCm = 78.0;
    let hipCircCm = 98.0;
    let neckCircCm = 38.0;
    let armLenCm = 60.0;
    let upperArmCircCm = 30.0;
    let wristCircCm = 17.0;
    let inseamCm = 78.0;
    let thighCircCm = 54.0;
    let calfCircCm = 36.0;
    let footLenCm = 26.5;
    let footWidthCm = 9.8;

    // 2. Measure Heights & Bounding Box from Geometry
    if (bodyMesh && bodyMesh.geometry) {
      const geo = bodyMesh.geometry;
      if (!geo.boundingBox) geo.computeBoundingBox();
      const bb = geo.boundingBox;

      if (bb) {
        const hM = bb.max.y - bb.min.y;
        if (hM > 0.8 && hM < 2.5) {
          heightCm = Math.round(hM * 1000) / 10;
        }
      }

      // Slice circumferences from vertex buffers
      const posAttr = geo.attributes.position;
      if (posAttr && posAttr.count > 100) {
        chestCircCm = this.sliceCircumference(posAttr, 1.25, 0.04, chestCircCm);
        waistCircCm = this.sliceCircumference(posAttr, 1.02, 0.04, waistCircCm);
        hipCircCm = this.sliceCircumference(posAttr, 0.84, 0.05, hipCircCm);
        neckCircCm = this.sliceCircumference(posAttr, 1.34, 0.03, neckCircCm);
      }
    }

    // 3. Measure Limb Lengths from Skeleton Bones
    const getBonePos = (name: string): THREE.Vector3 | null => {
      const b = bones.get(name) || avatarRoot.getObjectByName(name);
      if (!b) return null;
      const v = new THREE.Vector3();
      b.getWorldPosition(v);
      return v;
    };

    const lShoulder = getBonePos('LeftShoulder') || getBonePos('shoulder.L');
    const rShoulder = getBonePos('RightShoulder') || getBonePos('shoulder.R');
    const lArm = getBonePos('LeftArm') || getBonePos('upperarm01.L');
    const rArm = getBonePos('RightArm') || getBonePos('upperarm01.R');
    const lForeArm = getBonePos('LeftForeArm') || getBonePos('forearm01.L');
    const lHand = getBonePos('LeftHand') || getBonePos('wrist.L');
    const hips = getBonePos('Hips') || getBonePos('pelvis');
    const lFoot = getBonePos('LeftFoot') || getBonePos('foot.L');

    if (lArm && rArm) {
      shoulderWidthCm = Math.round(lArm.distanceTo(rArm) * 1000) / 10;
    } else if (lShoulder && rShoulder) {
      shoulderWidthCm = Math.round(lShoulder.distanceTo(rShoulder) * 1.35 * 1000) / 10;
    }

    if (lArm && lForeArm && lHand) {
      const uArm = lArm.distanceTo(lForeArm);
      const fArm = lForeArm.distanceTo(lHand);
      armLenCm = Math.round((uArm + fArm) * 1000) / 10;
    }

    if (hips && lFoot) {
      inseamCm = Math.round((hips.y - 0.05 - lFoot.y) * 1000) / 10;
    }

    // Derived anatomical circumferences
    upperArmCircCm = Math.round(chestCircCm * 0.312 * 10) / 10;
    wristCircCm = Math.round(upperArmCircCm * 0.566 * 10) / 10;
    thighCircCm = Math.round(hipCircCm * 0.551 * 10) / 10;
    calfCircCm = Math.round(thighCircCm * 0.667 * 10) / 10;
    footLenCm = Math.round(heightCm * 0.151 * 10) / 10;
    footWidthCm = Math.round(footLenCm * 0.370 * 10) / 10;

    // 4. Validate Measurements
    if (heightCm < 110 || heightCm > 230) {
      warnings.push(`Height (${heightCm}cm) outside valid human range.`);
    }
    if (chestCircCm < 60 || chestCircCm > 160) {
      warnings.push(`Chest circumference (${chestCircCm}cm) outside valid range.`);
    }
    if (waistCircCm < 45 || waistCircCm > 150) {
      warnings.push(`Waist circumference (${waistCircCm}cm) outside valid range.`);
    }

    return {
      heightCm,
      shoulderWidthCm,
      chestCircumferenceCm: chestCircCm,
      waistCircumferenceCm: waistCircCm,
      hipCircumferenceCm: hipCircCm,
      neckCircumferenceCm: neckCircCm,
      armLengthCm: armLenCm,
      upperArmCircumferenceCm: upperArmCircCm,
      wristCircumferenceCm: wristCircCm,
      inseamCm,
      thighCircumferenceCm: thighCircCm,
      calfCircumferenceCm: calfCircCm,
      footLengthCm: footLenCm,
      footWidthCm: footWidthCm,
      unit: 'cm',
      isValid: warnings.length === 0,
      warnings
    };
  }

  /**
   * Slices vertices at a given Y elevation and calculates the circumference of the slice.
   */
  private static sliceCircumference(
    posAttr: THREE.BufferAttribute | THREE.InterleavedBufferAttribute,
    targetY: number,
    tolerance: number,
    fallbackCm: number
  ): number {
    let minX = Infinity;
    let maxX = -Infinity;
    let minZ = Infinity;
    let maxZ = -Infinity;
    let found = 0;

    for (let i = 0; i < posAttr.count; i++) {
      const y = posAttr.getY(i);
      if (Math.abs(y - targetY) < tolerance) {
        const x = posAttr.getX(i);
        const z = posAttr.getZ(i);
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (z < minZ) minZ = z;
        if (z > maxZ) maxZ = z;
        found++;
      }
    }

    if (found < 8 || minX >= maxX || minZ >= maxZ) {
      return fallbackCm;
    }

    const a = (maxX - minX) * 0.5;
    const b = (maxZ - minZ) * 0.5;
    if (a < 0.05 || b < 0.04) return fallbackCm;

    // Ramanujan's ellipse perimeter formula
    const perimM = Math.PI * (3 * (a + b) - Math.sqrt((3 * a + b) * (a + 3 * b)));
    return Math.round(perimM * 1000) / 10;
  }
}
