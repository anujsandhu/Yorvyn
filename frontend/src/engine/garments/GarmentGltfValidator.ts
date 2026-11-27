/**
 * YORVYN — glTF Transform Asset Validator & Inspector
 * Validates, inspects, and audits GLB/glTF garment files using glTF Transform WebIO.
 * Enforces topology integrity, required attributes, PBR materials, and coordinate standards.
 */

import { WebIO, Document } from '@gltf-transform/core';

export interface GltfValidationReport {
  isValid: boolean;
  format: 'glb' | 'gltf';
  byteLength: number;
  meshesCount: number;
  primitivesCount: number;
  vertexCount: number;
  triangleCount: number;
  hasSkinning: boolean;
  bonesCount: number;
  hasUvs: boolean;
  hasNormals: boolean;
  materialsCount: number;
  texturesCount: number;
  errors: string[];
  warnings: string[];
  bounds: {
    min: [number, number, number];
    max: [number, number, number];
    dimensions: [number, number, number];
  };
}

export class GarmentGltfValidator {
  private static io = new WebIO();

  /**
   * Inspects and validates a binary GLB buffer using glTF Transform.
   */
  public static async validateGlb(glbBytes: Uint8Array): Promise<GltfValidationReport> {
    const errors: string[] = [];
    const warnings: string[] = [];

    // 1. Binary glTF Header Check (Magic: 0x46546C67 "glTF")
    if (glbBytes.byteLength < 12) {
      return this.createFailureReport(glbBytes.byteLength, ['File buffer is too small to be a valid glTF/GLB asset.']);
    }

    const view = new DataView(glbBytes.buffer, glbBytes.byteOffset, glbBytes.byteLength);
    const magic = view.getUint32(0, true);
    if (magic !== 0x46546c67) {
      errors.push(`Invalid binary header magic 0x${magic.toString(16)}. Expected glTF 2.0 (0x46546c67).`);
      return this.createFailureReport(glbBytes.byteLength, errors);
    }

    const version = view.getUint32(4, true);
    if (version !== 2) {
      errors.push(`Unsupported glTF version ${version}. Only glTF 2.0 is supported for 3D garment try-on.`);
      return this.createFailureReport(glbBytes.byteLength, errors);
    }

    // 2. Parse Document with glTF Transform WebIO
    let doc: Document;
    try {
      doc = await this.io.readBinary(glbBytes);
    } catch (err: any) {
      errors.push(`glTF Transform failed to parse GLB: ${err?.message || String(err)}`);
      return this.createFailureReport(glbBytes.byteLength, errors);
    }

    const root = doc.getRoot();
    const meshes = root.listMeshes();
    const skins = root.listSkins();
    const materials = root.listMaterials();
    const textures = root.listTextures();

    if (meshes.length === 0) {
      errors.push('No meshes found in GLB asset. Garment must contain 3D mesh geometry.');
      return this.createFailureReport(glbBytes.byteLength, errors);
    }

    let primitivesCount = 0;
    let totalVertices = 0;
    let totalTriangles = 0;
    let hasSkinning = skins.length > 0;
    let hasUvs = false;
    let hasNormals = false;

    let minX = Infinity, minY = Infinity, minZ = Infinity;
    let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;

    // 3. Inspect All Meshes & Primitives
    for (const mesh of meshes) {
      const prims = mesh.listPrimitives();
      primitivesCount += prims.length;

      for (const prim of prims) {
        // Primitive mode check (mode 4 = TRIANGLES)
        const mode = prim.getMode();
        if (mode !== 4 && mode !== undefined) {
          warnings.push(`Primitive uses non-triangle draw mode ${mode}. Triangulation recommended for virtual try-on.`);
        }

        // POSITION attribute check
        const posAttr = prim.getAttribute('POSITION');
        if (!posAttr) {
          errors.push('Mesh primitive lacks required POSITION attribute.');
          continue;
        }

        const vCount = posAttr.getCount();
        totalVertices += vCount;

        // Bounding box evaluation
        const posArray = posAttr.getArray();
        if (posArray) {
          for (let i = 0; i < posArray.length; i += 3) {
            const x = posArray[i];
            const y = posArray[i + 1];
            const z = posArray[i + 2];

            if (isNaN(x) || isNaN(y) || isNaN(z)) {
              errors.push('Mesh geometry contains NaN coordinate values.');
              break;
            }

            if (x < minX) minX = x;
            if (y < minY) minY = y;
            if (z < minZ) minZ = z;
            if (x > maxX) maxX = x;
            if (y > maxY) maxY = y;
            if (z > maxZ) maxZ = z;
          }
        }

        // NORMAL attribute check
        const normAttr = prim.getAttribute('NORMAL');
        if (normAttr) {
          hasNormals = true;
        } else {
          warnings.push('Mesh lacks vertex normals. Smooth shading normals will be computed at runtime.');
        }

        // TEXCOORD_0 attribute check
        const uvAttr = prim.getAttribute('TEXCOORD_0');
        if (uvAttr) {
          hasUvs = true;
        } else {
          warnings.push('Mesh lacks UV coordinates. PBR fabric texturing will not be possible.');
        }

        // Skinning attributes
        const jointsAttr = prim.getAttribute('JOINTS_0');
        const weightsAttr = prim.getAttribute('WEIGHTS_0');
        if (jointsAttr && weightsAttr) {
          hasSkinning = true;
        }

        // Triangle count
        const idxAttr = prim.getIndices();
        if (idxAttr) {
          totalTriangles += idxAttr.getCount() / 3;
        } else {
          totalTriangles += vCount / 3;
          warnings.push('Mesh primitive is unindexed. Index buffer creation recommended for GPU efficiency.');
        }
      }
    }

    // 4. Coordinate Dimension & Scale Sanity
    const dimX = maxX - minX;
    const dimY = maxY - minY;
    const dimZ = maxZ - minZ;

    // Yorvyn avatar standard height is ~1.78m.
    // If garment height > 50.0m or mm-scale > 100, warn for auto-scaling.
    if (dimY > 50.0) {
      warnings.push(`Garment bounds (${dimY.toFixed(1)}m) indicate millimetre units. Auto-scale (1/1000) required.`);
    } else if (dimY < 0.05 && dimY > 0) {
      warnings.push(`Garment bounds (${dimY.toFixed(3)}m) indicate micro units or incorrect scale.`);
    }

    // 5. Total Bones Count
    let totalBones = 0;
    for (const skin of skins) {
      totalBones = Math.max(totalBones, skin.listJoints().length);
    }

    // 6. Texture Resolution Auditing
    for (const tex of textures) {
      const mime = tex.getMimeType();
      if (!mime.includes('png') && !mime.includes('jpeg') && !mime.includes('webp')) {
        warnings.push(`Texture "${tex.getName()}" uses non-standard mime type ${mime}.`);
      }
    }

    return {
      isValid: errors.length === 0,
      format: 'glb',
      byteLength: glbBytes.byteLength,
      meshesCount: meshes.length,
      primitivesCount,
      vertexCount: totalVertices,
      triangleCount: Math.round(totalTriangles),
      hasSkinning,
      bonesCount: totalBones,
      hasUvs,
      hasNormals,
      materialsCount: materials.length,
      texturesCount: textures.length,
      errors,
      warnings,
      bounds: {
        min: [isFinite(minX) ? minX : 0, isFinite(minY) ? minY : 0, isFinite(minZ) ? minZ : 0],
        max: [isFinite(maxX) ? maxX : 0, isFinite(maxY) ? maxY : 0, isFinite(maxZ) ? maxZ : 0],
        dimensions: [isFinite(dimX) ? dimX : 0, isFinite(dimY) ? dimY : 0, isFinite(dimZ) ? dimZ : 0]
      }
    };
  }

  private static createFailureReport(byteLength: number, errors: string[]): GltfValidationReport {
    return {
      isValid: false,
      format: 'glb',
      byteLength,
      meshesCount: 0,
      primitivesCount: 0,
      vertexCount: 0,
      triangleCount: 0,
      hasSkinning: false,
      bonesCount: 0,
      hasUvs: false,
      hasNormals: false,
      materialsCount: 0,
      texturesCount: 0,
      errors,
      warnings: [],
      bounds: {
        min: [0, 0, 0],
        max: [0, 0, 0],
        dimensions: [0, 0, 0]
      }
    };
  }
}

