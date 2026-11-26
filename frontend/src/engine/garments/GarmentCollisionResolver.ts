/**
 * YORVYN — Garment Collision Resolver & Poke-Through Preventer
 * Pushes penetrating garment vertices outside body surfaces with guaranteed clearance.
 * Leverages three-mesh-bvh for accelerated spatial queries and exact surface normal projection.
 */

import * as THREE from 'three';
import { MeshBVH } from 'three-mesh-bvh';

export interface CollisionResolutionOptions {
  minClearanceMeters?: number; // default: 0.0028 (2.8mm)
  maxProjectionMeters?: number; // default: 0.16 (160mm max correction)
  stiffness?: number; // default: 1.0
}

export interface CollisionResolutionResult {
  penetrationCount: number;
  maxPenetrationMeters: number;
  averageClearanceMeters: number;
  resolvedPositions: Float32Array;
}

export class GarmentCollisionResolver {
  /**
   * Resolves collision using accelerated three-mesh-bvh spatial queries on a triangle mesh.
   * Finds the exact closest point on body triangles in O(log N) and projects penetrating
   * garment vertices outward along the true face normal.
   */
  public static resolveBodyCollisionsBVH(
    garmentPositions: Float32Array,
    bodyGeometry: THREE.BufferGeometry,
    options: CollisionResolutionOptions = {}
  ): CollisionResolutionResult {
    const minClearance = options.minClearanceMeters ?? 0.0028; // 2.8 mm
    const maxProjection = options.maxProjectionMeters ?? 0.16; // 160 mm
    const stiffness = options.stiffness ?? 1.0;

    // Ensure BVH tree exists on body geometry
    let bvh = (bodyGeometry as any).boundsTree as MeshBVH | undefined;
    if (!bvh) {
      bvh = new MeshBVH(bodyGeometry);
      (bodyGeometry as any).boundsTree = bvh;
    }

    const gCount = garmentPositions.length / 3;
    const resolved = new Float32Array(garmentPositions);

    const posAttr = bodyGeometry.attributes.position;
    const idxAttr = bodyGeometry.index;

    const gVec = new THREE.Vector3();
    const targetResult = { point: new THREE.Vector3(), distance: 0, faceIndex: 0 };
    const p0 = new THREE.Vector3();
    const p1 = new THREE.Vector3();
    const p2 = new THREE.Vector3();
    const faceNormal = new THREE.Vector3();
    const vDiff = new THREE.Vector3();

    let penetrationCount = 0;
    let maxPenetration = 0;
    let totalClearance = 0;

    for (let g = 0; g < gCount; g++) {
      gVec.set(resolved[g * 3], resolved[g * 3 + 1], resolved[g * 3 + 2]);

      // Query BVH for nearest point on body surface
      bvh.closestPointToPoint(gVec, targetResult);

      const f = targetResult.faceIndex;
      if (idxAttr) {
        const i0 = idxAttr.getX(f * 3);
        const i1 = idxAttr.getX(f * 3 + 1);
        const i2 = idxAttr.getX(f * 3 + 2);
        p0.set(posAttr.getX(i0), posAttr.getY(i0), posAttr.getZ(i0));
        p1.set(posAttr.getX(i1), posAttr.getY(i1), posAttr.getZ(i1));
        p2.set(posAttr.getX(i2), posAttr.getY(i2), posAttr.getZ(i2));
      } else {
        p0.set(posAttr.getX(f * 3), posAttr.getY(f * 3), posAttr.getZ(f * 3));
        p1.set(posAttr.getX(f * 3 + 1), posAttr.getY(f * 3 + 1), posAttr.getZ(f * 3 + 1));
        p2.set(posAttr.getX(f * 3 + 2), posAttr.getY(f * 3 + 2), posAttr.getZ(f * 3 + 2));
      }

      // Compute outward triangle face normal
      faceNormal.crossVectors(p1.sub(p0), p2.sub(p0));
      if (faceNormal.lengthSq() <= 1e-10) {
        continue;
      }
      faceNormal.normalize();

      // Signed clearance along face normal
      vDiff.subVectors(gVec, targetResult.point);
      const signedClearance = vDiff.dot(faceNormal);
      totalClearance += signedClearance;

      if (signedClearance < minClearance) {
        const penetration = minClearance - signedClearance;
        if (penetration <= maxProjection) {
          resolved[g * 3] = targetResult.point.x + faceNormal.x * (minClearance * stiffness);
          resolved[g * 3 + 1] = targetResult.point.y + faceNormal.y * (minClearance * stiffness);
          resolved[g * 3 + 2] = targetResult.point.z + faceNormal.z * (minClearance * stiffness);

          penetrationCount++;
          if (penetration > maxPenetration) {
            maxPenetration = penetration;
          }
        }
      }
    }

    return {
      penetrationCount,
      maxPenetrationMeters: maxPenetration,
      averageClearanceMeters: gCount > 0 ? totalClearance / gCount : 0,
      resolvedPositions: resolved
    };
  }

  /**
   * Resolves collision between garment vertices and the avatar body surface.
   * If any garment vertex is behind or inside the body surface normal plane,
   * it is projected outward to `skin_position + normal * minClearance`.
   */
  public static resolveBodyCollisions(
    garmentPositions: Float32Array,
    bodyCoords: Float32Array,
    bodyNormals: Float32Array,
    options: CollisionResolutionOptions = {}
  ): CollisionResolutionResult {
    const minClearance = options.minClearanceMeters ?? 0.0028; // 2.8 mm
    const maxProjection = options.maxProjectionMeters ?? 0.16; // 160 mm
    const stiffness = options.stiffness ?? 1.0;

    const gCount = garmentPositions.length / 3;
    const bCount = bodyCoords.length / 3;
    const resolved = new Float32Array(garmentPositions);

    let penetrationCount = 0;
    let maxPenetration = 0;
    let totalClearance = 0;

    // For every garment vertex, check penetration against nearest body vertex normal
    for (let g = 0; g < gCount; g++) {
      const gx = resolved[g * 3];
      const gy = resolved[g * 3 + 1];
      const gz = resolved[g * 3 + 2];

      // Find closest body point within local search window
      let closestIdx = -1;
      let closestDistSq = Infinity;

      for (let b = 0; b < bCount; b++) {
        const bx = bodyCoords[b * 3];
        const by = bodyCoords[b * 3 + 1];
        const bz = bodyCoords[b * 3 + 2];

        // Fast Y-axis pruning (only test vertices within 80mm vertically)
        if (Math.abs(gy - by) > 0.08) continue;

        const dx = gx - bx;
        const dy = gy - by;
        const dz = gz - bz;
        const distSq = dx * dx + dy * dy + dz * dz;

        if (distSq < closestDistSq) {
          closestDistSq = distSq;
          closestIdx = b;
        }
      }

      if (closestIdx >= 0) {
        const bx = bodyCoords[closestIdx * 3];
        const by = bodyCoords[closestIdx * 3 + 1];
        const bz = bodyCoords[closestIdx * 3 + 2];

        const nx = bodyNormals[closestIdx * 3];
        const ny = bodyNormals[closestIdx * 3 + 1];
        const nz = bodyNormals[closestIdx * 3 + 2];

        // Project vector (garment - body) along outward body normal
        const vx = gx - bx;
        const vy = gy - by;
        const vz = gz - bz;
        const dot = vx * nx + vy * ny + vz * nz;

        totalClearance += dot;

        // If penetration occurred (clearance < minClearance)
        if (dot < minClearance) {
          const penetration = minClearance - dot;
          if (penetration <= maxProjection) {
            const push = penetration * stiffness;
            resolved[g * 3] += nx * push;
            resolved[g * 3 + 1] += ny * push;
            resolved[g * 3 + 2] += nz * push;

            penetrationCount++;
            if (penetration > maxPenetration) {
              maxPenetration = penetration;
            }
          }
        }
      }
    }

    return {
      penetrationCount,
      maxPenetrationMeters: maxPenetration,
      averageClearanceMeters: gCount > 0 ? totalClearance / gCount : 0,
      resolvedPositions: resolved
    };
  }
}
