/**
 * YORVYN — Garment Asset Intelligence & Immutable Source Snapshot (Phase 17.5)
 *
 * Inspects geometry, UVs, materials, textures, and skeletal bindings before fitting,
 * and preserves an immutable source baseline so fitting mutations are always reversible.
 */

import * as THREE from 'three';

export type AssetConstructionKind =
  | 'static_garment'
  | 'skinned_garment'
  | 'rigid_accessory'
  | 'soft_accessory'
  | 'simulated_cloth'
  | 'invalid';

export interface GarmentAssetInspectionReport {
  valid: boolean;
  assetKind: AssetConstructionKind;
  meshCount: number;
  vertexCount: number;
  triangleCount: number;
  degenerateTriangleCount: number;
  nanVertexCount: number;
  hasUVs: boolean;
  uvOutOfRangeRatio: number;
  materialCount: number;
  hasDiffuseMap: boolean;
  hasNormalMap: boolean;
  hasRoughnessMap: boolean;
  hasMetallicMap: boolean;
  hasTransparency: boolean;
  isDoubleSided: boolean;
  hasSkeleton: boolean;
  boneCount: number;
  unnormalizedWeightCount: number;
  localBounds: { min: [number, number, number]; max: [number, number, number]; size: [number, number, number] };
  sourceFingerprint: string;
  assetVersion: string;
  issues: string[];
}

export interface ImmutableSourceSnapshot {
  fingerprint: string;
  createdAtIso: string;
  clonedSource: THREE.Object3D;
  inspection: GarmentAssetInspectionReport;
}

export class GarmentAssetInspector {
  public static readonly ASSET_INSPECTOR_VERSION = '17.5.0';

  public static inspectAndSnapshot(
    source: THREE.Object3D,
    hintKind?: AssetConstructionKind
  ): ImmutableSourceSnapshot {
    const inspection = this.inspect(source, hintKind);
    const clonedSource = source.clone(true);
    return {
      fingerprint: inspection.sourceFingerprint,
      createdAtIso: new Date().toISOString(),
      clonedSource,
      inspection,
    };
  }

  public static inspect(source: THREE.Object3D, hintKind?: AssetConstructionKind): GarmentAssetInspectionReport {
    source.updateMatrixWorld(true);
    const issues: string[] = [];

    let meshCount = 0;
    let vertexCount = 0;
    let triangleCount = 0;
    let degenerateTriangleCount = 0;
    let nanVertexCount = 0;
    let uvCountTotal = 0;
    let uvOutOfRange = 0;
    let hasUVs = false;

    let materialCount = 0;
    let hasDiffuseMap = false;
    let hasNormalMap = false;
    let hasRoughnessMap = false;
    let hasMetallicMap = false;
    let hasTransparency = false;
    let isDoubleSided = false;

    let hasSkeleton = false;
    let boneCount = 0;
    let unnormalizedWeightCount = 0;

    const bounds = new THREE.Box3();
    let hashAccum = 2166136261;

    source.traverse((obj) => {
      if ((obj as THREE.Bone).isBone) {
        boneCount++;
      }
      if ((obj as THREE.Mesh).isMesh) {
        meshCount++;
        const mesh = obj as THREE.Mesh;
        const geo = mesh.geometry;
        if (!geo || !geo.attributes?.position) {
          issues.push(`Mesh '${mesh.name || meshCount}' missing position attribute.`);
          return;
        }

        const pos = geo.attributes.position;
        const vN = pos.count;
        vertexCount += vN;

        const mWorld = mesh.matrixWorld;
        const vTmp = new THREE.Vector3();
        for (let i = 0; i < vN; i++) {
          const x = pos.getX(i);
          const y = pos.getY(i);
          const z = pos.getZ(i);
          if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) {
            nanVertexCount++;
            continue;
          }
          vTmp.set(x, y, z).applyMatrix4(mWorld);
          bounds.expandByPoint(vTmp);
          if (i % 17 === 0) {
            hashAccum ^= Math.round(x * 1000) + Math.round(y * 1000) * 31 + Math.round(z * 1000) * 131;
            hashAccum = Math.imul(hashAccum, 16777619) >>> 0;
          }
        }

        const idx = geo.index;
        const triN = idx ? Math.floor(idx.count / 3) : Math.floor(vN / 3);
        triangleCount += triN;
        const a = new THREE.Vector3();
        const b = new THREE.Vector3();
        const c = new THREE.Vector3();
        const e1 = new THREE.Vector3();
        const e2 = new THREE.Vector3();
        for (let t = 0; t < triN; t++) {
          const i0 = idx ? idx.getX(t * 3) : t * 3;
          const i1 = idx ? idx.getX(t * 3 + 1) : t * 3 + 1;
          const i2 = idx ? idx.getX(t * 3 + 2) : t * 3 + 2;
          if (i0 >= vN || i1 >= vN || i2 >= vN || i0 === i1 || i1 === i2 || i2 === i0) {
            degenerateTriangleCount++;
            continue;
          }
          a.fromBufferAttribute(pos, i0);
          b.fromBufferAttribute(pos, i1);
          c.fromBufferAttribute(pos, i2);
          e1.subVectors(b, a);
          e2.subVectors(c, a);
          if (e1.cross(e2).lengthSq() < 1e-12) {
            degenerateTriangleCount++;
          }
        }

        const uv = geo.attributes.uv;
        if (uv && uv.count > 0) {
          hasUVs = true;
          for (let i = 0; i < uv.count; i++) {
            const u = uv.getX(i);
            const v = uv.getY(i);
            uvCountTotal++;
            if (u < -0.05 || u > 1.05 || v < -0.05 || v > 1.05) {
              uvOutOfRange++;
            }
          }
        }

        const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
        for (const mat of mats) {
          if (!mat) continue;
          materialCount++;
          const std = mat as THREE.MeshStandardMaterial;
          if (std.map) hasDiffuseMap = true;
          if (std.normalMap) hasNormalMap = true;
          if (std.roughnessMap) hasRoughnessMap = true;
          if (std.metalnessMap) hasMetallicMap = true;
          if (mat.transparent || (mat.opacity ?? 1) < 1) hasTransparency = true;
          if (mat.side === THREE.DoubleSide) isDoubleSided = true;
        }

        if ((mesh as THREE.SkinnedMesh).isSkinnedMesh) {
          const sm = mesh as THREE.SkinnedMesh;
          if (sm.skeleton && sm.skeleton.bones.length > 0) {
            hasSkeleton = true;
            boneCount = Math.max(boneCount, sm.skeleton.bones.length);
          }
          const sw = geo.attributes.skinWeight;
          if (sw) {
            for (let i = 0; i < vN; i++) {
              const sum = sw.getX(i) + sw.getY(i) + sw.getZ(i) + sw.getW(i);
              if (Math.abs(sum - 1.0) > 0.05) {
                unnormalizedWeightCount++;
              }
            }
          }
        }
      }
    });

    if (meshCount === 0 || vertexCount === 0) {
      issues.push('Asset contains no renderable mesh vertices.');
    }
    if (nanVertexCount > 0) {
      issues.push(`Asset contains ${nanVertexCount} non-finite vertex coordinates.`);
    }
    if (triangleCount === 0) {
      issues.push('Asset contains zero triangles.');
    }
    if (!hasUVs && vertexCount > 0) {
      issues.push('UV channel unavailable; procedural fallback shading will apply if textured.');
    }

    const sizeVec = new THREE.Vector3();
    if (!bounds.isEmpty()) {
      bounds.getSize(sizeVec);
    }
    if (vertexCount > 0 && (sizeVec.length() < 0.005 || sizeVec.length() > 15.0)) {
      issues.push(`Asset physical extents (${sizeVec.length().toFixed(3)}m) outside expected garment scale range.`);
    }

    let assetKind: AssetConstructionKind = hintKind || 'static_garment';
    if (meshCount === 0 || vertexCount === 0 || nanVertexCount > vertexCount * 0.25) {
      assetKind = 'invalid';
    } else if (!hintKind) {
      assetKind = hasSkeleton ? 'skinned_garment' : 'static_garment';
    }

    const valid = meshCount > 0 && vertexCount > 0 && triangleCount > 0 && nanVertexCount === 0;
    const fingerprint = `v175_${meshCount}_${vertexCount}_${triangleCount}_${hashAccum.toString(16)}`;

    return {
      valid,
      assetKind,
      meshCount,
      vertexCount,
      triangleCount,
      degenerateTriangleCount,
      nanVertexCount,
      hasUVs,
      uvOutOfRangeRatio: uvCountTotal > 0 ? Math.round((uvOutOfRange / uvCountTotal) * 10000) / 10000 : 0,
      materialCount,
      hasDiffuseMap,
      hasNormalMap,
      hasRoughnessMap,
      hasMetallicMap,
      hasTransparency,
      isDoubleSided,
      hasSkeleton,
      boneCount,
      unnormalizedWeightCount,
      localBounds: bounds.isEmpty()
        ? { min: [0, 0, 0], max: [0, 0, 0], size: [0, 0, 0] }
        : {
            min: [bounds.min.x, bounds.min.y, bounds.min.z],
            max: [bounds.max.x, bounds.max.y, bounds.max.z],
            size: [sizeVec.x, sizeVec.y, sizeVec.z],
          },
      sourceFingerprint: fingerprint,
      assetVersion: this.ASSET_INSPECTOR_VERSION,
      issues,
    };
  }
}
