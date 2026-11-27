/**
 * YORVYN — Cloth Collision System & Anatomical Proxies (Phase 10)
 * Fast, hierarchical collision detection and resolution against avatar body hulls.
 * Prevents clothing poke-through, sleeve penetration, trouser intersection, and waist clipping.
 */

import * as THREE from 'three';
import { BodyCollisionHull, SimulationQualityMode } from './types';

export class ClothCollisionSystem {
  private hulls: BodyCollisionHull[] = [];
  private scratchVecA = new THREE.Vector3();
  private scratchVecB = new THREE.Vector3();

  constructor() {
    this.initDefaultHulls();
  }

  /**
   * Initializes anatomical collision proxy hulls scaled to a standard 1.75m human body.
   */
  private initDefaultHulls(): void {
    this.hulls = [
      // Upper Torso / Chest (Spine2 to Neck)
      {
        name: 'chest',
        boneName: 'Spine2',
        alternativeBoneNames: ['spine02', 'Spine1', 'chest'],
        type: 'capsule',
        localStart: [0, 0, 0],
        localEnd: [0, 0.22, 0],
        worldStart: new THREE.Vector3(0, 1.25, 0),
        worldEnd: new THREE.Vector3(0, 1.48, 0),
        radiusStart: 0.165,
        radiusEnd: 0.150,
        friction: 0.45
      },

      // Lower Torso / Abdomen (Spine to Spine2)
      {
        name: 'abdomen',
        boneName: 'Spine',
        alternativeBoneNames: ['spine04', 'spine03', 'Spine1'],
        type: 'capsule',
        localStart: [0, 0, 0],
        localEnd: [0, 0.18, 0],
        worldStart: new THREE.Vector3(0, 1.05, 0),
        worldEnd: new THREE.Vector3(0, 1.25, 0),
        radiusStart: 0.155,
        radiusEnd: 0.160,
        friction: 0.45
      },

      // Pelvis / Hips
      {
        name: 'pelvis',
        boneName: 'Hips',
        alternativeBoneNames: ['spine05', 'pelvis', 'root'],
        type: 'capsule',
        localStart: [-0.08, 0, 0],
        localEnd: [0.08, 0, 0],
        worldStart: new THREE.Vector3(-0.08, 0.95, 0),
        worldEnd: new THREE.Vector3(0.08, 0.95, 0),
        radiusStart: 0.165,
        radiusEnd: 0.165,
        friction: 0.50
      },

      // Left Upper Arm (Shoulder to Elbow)
      {
        name: 'upperarm_l',
        boneName: 'LeftArm',
        alternativeBoneNames: ['upperarm01.L', 'upperarm02.L', 'shoulder.L'],
        type: 'capsule',
        localStart: [0, 0, 0],
        localEnd: [0, -0.28, 0],
        worldStart: new THREE.Vector3(0.20, 1.40, 0),
        worldEnd: new THREE.Vector3(0.28, 1.15, 0),
        radiusStart: 0.055,
        radiusEnd: 0.045,
        friction: 0.35
      },

      // Right Upper Arm (Shoulder to Elbow)
      {
        name: 'upperarm_r',
        boneName: 'RightArm',
        alternativeBoneNames: ['upperarm01.R', 'upperarm02.R', 'shoulder.R'],
        type: 'capsule',
        localStart: [0, 0, 0],
        localEnd: [0, -0.28, 0],
        worldStart: new THREE.Vector3(-0.20, 1.40, 0),
        worldEnd: new THREE.Vector3(-0.28, 1.15, 0),
        radiusStart: 0.055,
        radiusEnd: 0.045,
        friction: 0.35
      },

      // Left Thigh (Hip to Knee)
      {
        name: 'thigh_l',
        boneName: 'LeftUpLeg',
        alternativeBoneNames: ['upperleg01.L', 'upperleg02.L', 'thigh.L'],
        type: 'capsule',
        localStart: [0, 0, 0],
        localEnd: [0, -0.42, 0],
        worldStart: new THREE.Vector3(0.10, 0.90, 0),
        worldEnd: new THREE.Vector3(0.10, 0.50, 0),
        radiusStart: 0.095,
        radiusEnd: 0.065,
        friction: 0.40
      },

      // Right Thigh (Hip to Knee)
      {
        name: 'thigh_r',
        boneName: 'RightUpLeg',
        alternativeBoneNames: ['upperleg01.R', 'upperleg02.R', 'thigh.R'],
        type: 'capsule',
        localStart: [0, 0, 0],
        localEnd: [0, -0.42, 0],
        worldStart: new THREE.Vector3(-0.10, 0.90, 0),
        worldEnd: new THREE.Vector3(-0.10, 0.50, 0),
        radiusStart: 0.095,
        radiusEnd: 0.065,
        friction: 0.40
      },

      // Left Calf (Knee to Ankle)
      {
        name: 'calf_l',
        boneName: 'LeftLeg',
        alternativeBoneNames: ['lowerleg01.L', 'lowerleg02.L', 'calf.L'],
        type: 'capsule',
        localStart: [0, 0, 0],
        localEnd: [0, -0.40, 0],
        worldStart: new THREE.Vector3(0.10, 0.50, 0),
        worldEnd: new THREE.Vector3(0.10, 0.10, 0),
        radiusStart: 0.065,
        radiusEnd: 0.048,
        friction: 0.40
      },

      // Right Calf (Knee to Ankle)
      {
        name: 'calf_r',
        boneName: 'RightLeg',
        alternativeBoneNames: ['lowerleg01.R', 'lowerleg02.R', 'calf.R'],
        type: 'capsule',
        localStart: [0, 0, 0],
        localEnd: [0, -0.40, 0],
        worldStart: new THREE.Vector3(-0.10, 0.50, 0),
        worldEnd: new THREE.Vector3(-0.10, 0.10, 0),
        radiusStart: 0.065,
        radiusEnd: 0.048,
        friction: 0.40
      },

      // Head & Neck
      {
        name: 'head',
        boneName: 'Head',
        alternativeBoneNames: ['head', 'neck01'],
        type: 'sphere',
        localStart: [0, 0, 0],
        localEnd: [0, 0.15, 0],
        worldStart: new THREE.Vector3(0, 1.55, 0),
        worldEnd: new THREE.Vector3(0, 1.70, 0),
        radiusStart: 0.105,
        radiusEnd: 0.105,
        friction: 0.30
      },

      // Articulated Joint Spheres (elbows, knees, shoulders)
      {
        name: 'shoulder_l',
        boneName: 'LeftArm',
        alternativeBoneNames: ['upperarm01.L', 'shoulder.L'],
        type: 'sphere',
        localStart: [0, 0, 0],
        localEnd: [0, 0, 0],
        worldStart: new THREE.Vector3(0.20, 1.40, 0),
        worldEnd: new THREE.Vector3(0.20, 1.40, 0),
        radiusStart: 0.065,
        radiusEnd: 0.065,
        friction: 0.35
      },
      {
        name: 'shoulder_r',
        boneName: 'RightArm',
        alternativeBoneNames: ['upperarm01.R', 'shoulder.R'],
        type: 'sphere',
        localStart: [0, 0, 0],
        localEnd: [0, 0, 0],
        worldStart: new THREE.Vector3(-0.20, 1.40, 0),
        worldEnd: new THREE.Vector3(-0.20, 1.40, 0),
        radiusStart: 0.065,
        radiusEnd: 0.065,
        friction: 0.35
      },
      {
        name: 'elbow_l',
        boneName: 'LeftForeArm',
        alternativeBoneNames: ['lowerarm01.L', 'forearm.L'],
        type: 'sphere',
        localStart: [0, 0, 0],
        localEnd: [0, 0, 0],
        worldStart: new THREE.Vector3(0.28, 1.15, 0),
        worldEnd: new THREE.Vector3(0.28, 1.15, 0),
        radiusStart: 0.048,
        radiusEnd: 0.048,
        friction: 0.35
      },
      {
        name: 'elbow_r',
        boneName: 'RightForeArm',
        alternativeBoneNames: ['lowerarm01.R', 'forearm.R'],
        type: 'sphere',
        localStart: [0, 0, 0],
        localEnd: [0, 0, 0],
        worldStart: new THREE.Vector3(-0.28, 1.15, 0),
        worldEnd: new THREE.Vector3(-0.28, 1.15, 0),
        radiusStart: 0.048,
        radiusEnd: 0.048,
        friction: 0.35
      },
      {
        name: 'knee_l',
        boneName: 'LeftLeg',
        alternativeBoneNames: ['lowerleg01.L', 'calf.L'],
        type: 'sphere',
        localStart: [0, 0, 0],
        localEnd: [0, 0, 0],
        worldStart: new THREE.Vector3(0.10, 0.50, 0),
        worldEnd: new THREE.Vector3(0.10, 0.50, 0),
        radiusStart: 0.068,
        radiusEnd: 0.068,
        friction: 0.40
      },
      {
        name: 'knee_r',
        boneName: 'RightLeg',
        alternativeBoneNames: ['lowerleg01.R', 'calf.R'],
        type: 'sphere',
        localStart: [0, 0, 0],
        localEnd: [0, 0, 0],
        worldStart: new THREE.Vector3(-0.10, 0.50, 0),
        worldEnd: new THREE.Vector3(-0.10, 0.50, 0),
        radiusStart: 0.068,
        radiusEnd: 0.068,
        friction: 0.40
      }
    ];
  }

  /**
   * Synchronizes collision hull world positions from the active Three.js avatar skeleton.
   * If bones are animated or posed, the collision capsules follow the limbs in real-time.
   */
  public syncWithAvatar(modelRoot: THREE.Object3D, heightScale: number = 1.0): void {
    modelRoot.updateWorldMatrix(true, true);

    for (const hull of this.hulls) {
      // Find matching bone in model hierarchy
      let bone: THREE.Object3D | null = modelRoot.getObjectByName(hull.boneName) || null;
      if (!bone) {
        for (const alt of hull.alternativeBoneNames) {
          bone = modelRoot.getObjectByName(alt) || null;
          if (bone) break;
        }
      }

      if (bone) {
        // Derive world coordinates from bone transform
        this.scratchVecA.set(
          hull.localStart[0] * heightScale,
          hull.localStart[1] * heightScale,
          hull.localStart[2] * heightScale
        );
        this.scratchVecA.applyMatrix4(bone.matrixWorld);
        hull.worldStart.copy(this.scratchVecA);

        this.scratchVecB.set(
          hull.localEnd[0] * heightScale,
          hull.localEnd[1] * heightScale,
          hull.localEnd[2] * heightScale
        );
        this.scratchVecB.applyMatrix4(bone.matrixWorld);
        hull.worldEnd.copy(this.scratchVecB);
      } else {
        // Fallback: apply global stature scale directly to default world positions
        hull.worldStart.y *= heightScale;
        hull.worldEnd.y *= heightScale;
      }
    }
  }

  /**
   * Resolves collision for a single cloth particle against all active body hulls.
   * Modifies (px, py, pz) in place if penetrating, and returns true if penetration was resolved.
   */
  public resolveParticleCollision(
    positions: Float32Array,
    particleIndex: number,
    fabricThickness: number,
    qualityMode: SimulationQualityMode = 'balanced'
  ): boolean {
    const pIdx = particleIndex * 3;
    let px = positions[pIdx];
    let py = positions[pIdx + 1];
    let pz = positions[pIdx + 2];

    let hasCollided = false;

    // Filter hulls based on quality mode
    const activeHulls = qualityMode === 'preview'
      ? this.hulls.filter(h => h.name === 'chest' || h.name === 'pelvis')
      : qualityMode === 'performance'
      ? this.hulls.filter(h => h.name !== 'calf_l' && h.name !== 'calf_r')
      : this.hulls;

    for (let i = 0; i < activeHulls.length; i++) {
      const hull = activeHulls[i];
      const a = hull.worldStart;
      const b = hull.worldEnd;

      // Segment vector AB
      const abX = b.x - a.x;
      const abY = b.y - a.y;
      const abZ = b.z - a.z;
      const abLenSq = abX * abX + abY * abY + abZ * abZ;

      // Vector AP
      const apX = px - a.x;
      const apY = py - a.y;
      const apZ = pz - a.z;

      // Compute projection factor t along segment [0, 1]
      let t = 0;
      if (abLenSq > 1e-8) {
        t = (apX * abX + apY * abY + apZ * abZ) / abLenSq;
        if (t < 0) t = 0;
        else if (t > 1) t = 1;
      }

      // Closest point on capsule line segment
      const cX = a.x + t * abX;
      const cY = a.y + t * abY;
      const cZ = a.z + t * abZ;

      // Distance vector from segment to particle
      const diffX = px - cX;
      const diffY = py - cY;
      const diffZ = pz - cZ;
      const distSq = diffX * diffX + diffY * diffY + diffZ * diffZ;

      // Effective tapered radius at t plus fabric clearance margin
      const r = hull.radiusStart + t * (hull.radiusEnd - hull.radiusStart);
      const minClearance = r + fabricThickness;
      const minClearanceSq = minClearance * minClearance;

      // Check penetration
      if (distSq < minClearanceSq) {
        const dist = Math.sqrt(distSq);
        let normalX = 0;
        let normalY = 0;
        let normalZ = 1;

        if (dist > 1e-6) {
          normalX = diffX / dist;
          normalY = diffY / dist;
          normalZ = diffZ / dist;
        } else {
          // Degenerate center intersection: push radially outward along local Y/Z
          normalX = 0;
          normalY = 1;
          normalZ = 0;
        }

        // Project particle to hull surface + clearance
        px = cX + normalX * minClearance;
        py = cY + normalY * minClearance;
        pz = cZ + normalZ * minClearance;

        hasCollided = true;
      }
    }

    if (hasCollided) {
      positions[pIdx] = px;
      positions[pIdx + 1] = py;
      positions[pIdx + 2] = pz;
    }

    return hasCollided;
  }

  /**
   * Returns active collision hull definitions for debugging or visualization.
   */
  public getHulls(): BodyCollisionHull[] {
    return this.hulls;
  }
}
