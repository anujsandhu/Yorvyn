/**
 * YORVYN — Garment Asset Exporter (Phase 3)
 * 
 * Packages reconstructed 3D geometry, PBR material properties, photographic diffuse atlas,
 * and fitting metadata into binary glTF (.glb) assets compatible with Three.js GLTFLoader and Ara 3D Gen.
 */

import { 
  ReconstructedMeshGeometry, 
  FabricPBRProperties, 
  GarmentFittingMetadata, 
  ReconstructedGarmentAsset,
  GarmentReconstructionCategory,
  GarmentQualityReport,
  GarmentIntelligenceFeatures
} from './garmentReconstructionTypes';

export class GarmentAssetExporter {
  /**
   * Generates a complete ReconstructedGarmentAsset including binary GLB container with embedded texture atlas.
   */
  public static exportGarmentAsset(
    id: string,
    name: string,
    category: GarmentReconstructionCategory,
    subcategory: string,
    geometry: ReconstructedMeshGeometry,
    fabric: FabricPBRProperties,
    dominantColorHex: string,
    qualityScore: number,
    options: {
      textureDataUrl?: string;
      normalMapDataUrl?: string;
      qualityReport?: GarmentQualityReport;
      intelligence?: GarmentIntelligenceFeatures;
      thumbnailUrl?: string;
    } = {}
  ): ReconstructedGarmentAsset {
    const fittingMetadata = this.generateFittingMetadata(category, subcategory);
    const glbBuffer = this.buildGlbBuffer(geometry, dominantColorHex, fabric, options.textureDataUrl);
    
    let glbBlobUrl: string | undefined;
    if (typeof URL !== 'undefined' && typeof Blob !== 'undefined') {
      const blob = new Blob([glbBuffer], { type: 'model/gltf-binary' });
      glbBlobUrl = URL.createObjectURL(blob);
    }

    const limitations: string[] = [
      'Single-view rear pattern is symmetrically synthesized from front reference.',
      'Fabric elasticity and physical drape simulation are real-time approximations.',
      'Surface PBR parameters are estimated from optical color and texture variance.'
    ];

    if (subcategory === 'hoodie') {
      limitations.push('Hood cowl volume and kangaroo pocket dimensions are derived from 2D silhouette.');
    }

    return {
      id,
      name,
      category,
      subcategory,
      fabric,
      geometry,
      fittingMetadata,
      qualityScore,
      qualityReport: options.qualityReport,
      intelligence: options.intelligence,
      glbBlobUrl,
      glbArrayBuffer: glbBuffer,
      thumbnailUrl: options.thumbnailUrl,
      textureDataUrl: options.textureDataUrl,
      normalMapDataUrl: options.normalMapDataUrl,
      createdAt: new Date().toISOString(),
      knownLimitations: limitations
    };
  }

  /**
   * Derives anatomical fitting metadata based on garment category and subcategory.
   */
  public static generateFittingMetadata(
    category: GarmentReconstructionCategory,
    subcategory: string
  ): GarmentFittingMetadata {
    switch (category) {
      case 'bottom':
      case 'skirt':
        return {
          targetSlot: 'bottom',
          suggestedScale: [1.0, 1.0, 1.0],
          suggestedOffset: [0, 0, 0],
          occlusionMaskIds: ['Body_Pelvis', 'Body_Thigh_Upper', 'Body_Thigh_Inner'],
          anchorBone: 'pelvis',
          tightnessFactor: 1.0,
          rigType: 'Ara3D_Humanoid_20Bone'
        };
      case 'outerwear':
        return {
          targetSlot: 'outerwear',
          suggestedScale: [1.03, 1.0, 1.03],
          suggestedOffset: [0, 0.01, 0],
          occlusionMaskIds: ['Body_Chest', 'Body_Back_Upper', 'Body_UpperArm'],
          anchorBone: 'spine02',
          tightnessFactor: 0.85,
          rigType: 'Ara3D_Humanoid_20Bone'
        };
      case 'dress':
        return {
          targetSlot: 'full_outfit',
          suggestedScale: [1.0, 1.0, 1.0],
          suggestedOffset: [0, 0, 0],
          occlusionMaskIds: ['Body_Chest', 'Body_Pelvis', 'Body_Thigh_Upper'],
          anchorBone: 'spine01',
          tightnessFactor: 0.95,
          rigType: 'Ara3D_Humanoid_20Bone'
        };
      case 'top':
      default: {
        const isHoodie = subcategory === 'hoodie';
        return {
          targetSlot: 'top',
          suggestedScale: isHoodie ? [1.025, 1.0, 1.025] : [1.0, 1.0, 1.0],
          suggestedOffset: [0, 0, 0],
          occlusionMaskIds: isHoodie 
            ? ['Body_Chest', 'Body_Back_Upper', 'Body_Neck_Base'] 
            : ['Body_Chest', 'Body_Back_Upper'],
          anchorBone: 'spine02',
          tightnessFactor: isHoodie ? 0.90 : 1.0,
          rigType: 'Ara3D_Humanoid_20Bone'
        };
      }
    }
  }

  /**
   * Constructs a self-contained, valid binary glTF (.glb) buffer with JSON scene and BIN chunks.
   * Embeds photographic diffuse texture into the BIN chunk when textureDataUrl is provided.
   */
  public static buildGlbBuffer(
    geometry: ReconstructedMeshGeometry,
    colorHex: string,
    fabric: FabricPBRProperties,
    textureDataUrl?: string
  ): ArrayBuffer {
    const pos = geometry.positions;
    const norm = geometry.normals;
    const uv = geometry.uvs;
    const idx = geometry.indices;

    const posByteLength = pos.byteLength;
    const normByteLength = norm.byteLength;
    const uvByteLength = uv.byteLength;
    const idxByteLength = idx.byteLength;

    // Optional texture extraction
    let imageBytes: Uint8Array | null = null;
    let imageMime = 'image/png';

    if (textureDataUrl && textureDataUrl.startsWith('data:')) {
      try {
        const parsed = this.dataUriToUint8Array(textureDataUrl);
        imageBytes = parsed.bytes;
        imageMime = parsed.mimeType;
      } catch {
        imageBytes = null;
      }
    }

    const imageByteLength = imageBytes ? imageBytes.byteLength : 0;
    const totalBinLength = posByteLength + normByteLength + uvByteLength + idxByteLength + imageByteLength;
    const paddedBinLength = (totalBinLength + 3) & ~3;

    const binBuffer = new Uint8Array(paddedBinLength);
    let offset = 0;

    binBuffer.set(new Uint8Array(pos.buffer, pos.byteOffset, posByteLength), offset);
    const posOffset = offset;
    offset += posByteLength;

    binBuffer.set(new Uint8Array(norm.buffer, norm.byteOffset, normByteLength), offset);
    const normOffset = offset;
    offset += normByteLength;

    binBuffer.set(new Uint8Array(uv.buffer, uv.byteOffset, uvByteLength), offset);
    const uvOffset = offset;
    offset += uvByteLength;

    binBuffer.set(new Uint8Array(idx.buffer, idx.byteOffset, idxByteLength), offset);
    const idxOffset = offset;
    offset += idxByteLength;

    let imageOffset = 0;
    if (imageBytes) {
      binBuffer.set(imageBytes, offset);
      imageOffset = offset;
      offset += imageByteLength;
    }

    // Convert hex color to linear float [r, g, b, a]
    const cleanHex = colorHex.replace('#', '');
    const r = (parseInt(cleanHex.slice(0, 2), 16) || 74) / 255.0;
    const g = (parseInt(cleanHex.slice(2, 4), 16) || 46) / 255.0;
    const b = (parseInt(cleanHex.slice(4, 6), 16) || 24) / 255.0;

    const bufferViews: any[] = [
      { buffer: 0, byteOffset: posOffset, byteLength: posByteLength, target: 34962 },
      { buffer: 0, byteOffset: normOffset, byteLength: normByteLength, target: 34962 },
      { buffer: 0, byteOffset: uvOffset, byteLength: uvByteLength, target: 34962 },
      { buffer: 0, byteOffset: idxOffset, byteLength: idxByteLength, target: 34963 }
    ];

    if (imageBytes) {
      bufferViews.push({
        buffer: 0,
        byteOffset: imageOffset,
        byteLength: imageByteLength
      });
    }

    const materialPbr: any = {
      baseColorFactor: imageBytes ? [1.0, 1.0, 1.0, 1.0] : [r, g, b, 1.0],
      metallicFactor: fabric.metalness,
      roughnessFactor: fabric.roughness
    };

    if (imageBytes) {
      materialPbr.baseColorTexture = {
        index: 0,
        texCoord: 0
      };
    }

    const gltf: any = {
      asset: {
        version: '2.0',
        generator: 'Yorvyn-AdvancedGarment3D-Engine-Phase3'
      },
      scene: 0,
      scenes: [{ nodes: [0] }],
      nodes: [{ mesh: 0, name: 'ReconstructedGarment' }],
      meshes: [
        {
          name: 'GarmentMesh',
          primitives: [
            {
              attributes: {
                POSITION: 0,
                NORMAL: 1,
                TEXCOORD_0: 2
              },
              indices: 3,
              material: 0,
              mode: 4 // TRIANGLES
            }
          ]
        }
      ],
      materials: [
        {
          name: `PBR_${fabric.type.toUpperCase()}`,
          pbrMetallicRoughness: materialPbr,
          doubleSided: true
        }
      ],
      accessors: [
        {
          bufferView: 0,
          byteOffset: 0,
          componentType: 5126, // FLOAT
          count: geometry.vertexCount,
          type: 'VEC3',
          min: geometry.boundingBox.min,
          max: geometry.boundingBox.max
        },
        {
          bufferView: 1,
          byteOffset: 0,
          componentType: 5126,
          count: geometry.vertexCount,
          type: 'VEC3'
        },
        {
          bufferView: 2,
          byteOffset: 0,
          componentType: 5126,
          count: geometry.vertexCount,
          type: 'VEC2'
        },
        {
          bufferView: 3,
          byteOffset: 0,
          componentType: 5125, // UNSIGNED_INT
          count: geometry.triangleCount * 3,
          type: 'SCALAR'
        }
      ],
      bufferViews,
      buffers: [
        {
          byteLength: paddedBinLength
        }
      ]
    };

    if (imageBytes) {
      gltf.images = [{ bufferView: 4, mimeType: imageMime }];
      gltf.samplers = [{ magFilter: 9729, minFilter: 9987, wrapS: 10497, wrapT: 10497 }];
      gltf.textures = [{ sampler: 0, source: 0 }];
    }

    const jsonString = JSON.stringify(gltf);
    const jsonBytes = new TextEncoder().encode(jsonString);
    const paddedJsonLength = (jsonBytes.byteLength + 3) & ~3;
    const jsonBuffer = new Uint8Array(paddedJsonLength);
    jsonBuffer.set(jsonBytes);
    for (let i = jsonBytes.byteLength; i < paddedJsonLength; i++) {
      jsonBuffer[i] = 0x20; // Spaces
    }

    const totalGlbLength = 12 + 8 + paddedJsonLength + 8 + paddedBinLength;
    const glb = new ArrayBuffer(totalGlbLength);
    const view = new DataView(glb);

    // Header: Magic 'glTF', Version 2, Total Length
    view.setUint32(0, 0x46546C67, true);
    view.setUint32(4, 2, true);
    view.setUint32(8, totalGlbLength, true);

    // Chunk 0: JSON
    view.setUint32(12, paddedJsonLength, true);
    view.setUint32(16, 0x4E4F534A, true);
    new Uint8Array(glb, 20, paddedJsonLength).set(jsonBuffer);

    // Chunk 1: BIN
    const binHeaderOffset = 20 + paddedJsonLength;
    view.setUint32(binHeaderOffset, paddedBinLength, true);
    view.setUint32(binHeaderOffset + 4, 0x004E4942, true);
    new Uint8Array(glb, binHeaderOffset + 8, paddedBinLength).set(binBuffer);

    return glb;
  }

  private static dataUriToUint8Array(dataUri: string): { bytes: Uint8Array; mimeType: string } {
    const parts = dataUri.split(',');
    const mimeMatch = parts[0]?.match(/:(.*?);/);
    const mimeType = mimeMatch ? mimeMatch[1] : 'image/png';
    const base64 = parts[1] || '';

    let binaryStr = '';
    if (typeof atob !== 'undefined') {
      binaryStr = atob(base64);
    } else {
      const gBuf = (globalThis as any).Buffer;
      if (gBuf) {
        binaryStr = gBuf.from(base64, 'base64').toString('binary');
      }
    }

    const len = binaryStr.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = binaryStr.charCodeAt(i);
    }

    return { bytes, mimeType };
  }
}
