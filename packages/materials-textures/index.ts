/**
 * Yorvyn Technology Library — Materials & Textures
 * PBR texture atlas synthesis, ambient shadow removal, and tangent-space normal generation.
 */

import { MaterialDef } from '../shared-types';

export interface TextureAtlasMaps {
  diffusePngBytes: Uint8Array;
  normalPngBytes?: Uint8Array;
  roughnessPngBytes?: Uint8Array;
  resolution: { width: number; height: number };
}

export interface ITextureSynthesizer {
  /** Synthesize de-lighted diffuse texture, normal map, and roughness map */
  synthesizePbrMaps(
    frontImageBytes: Uint8Array,
    backImageBytes?: Uint8Array,
    dominantColorHex?: string
  ): Promise<TextureAtlasMaps>;

  /** Construct complete PBR Material definition */
  buildMaterial(
    materialName: string,
    maps: TextureAtlasMaps,
    diffuseUrl: string,
    normalUrl?: string,
    roughnessUrl?: string
  ): MaterialDef;
}
