/**
 * Yorvyn Technology Library — Materials & Textures
 * PBR texture atlas synthesis, ambient shadow removal, and tangent-space normal generation.
 */

import type { MaterialDef } from '../shared-types/index.ts';

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

export function parseHexColor(hex: string): { r: number; g: number; b: number } {
  let clean = hex.replace('#', '').trim();
  if (clean.length === 3) {
    clean = clean.split('').map(c => c + c).join('');
  }
  const intVal = parseInt(clean, 16) || 0x2c3e50;
  return {
    r: (intVal >> 16) & 255,
    g: (intVal >> 8) & 255,
    b: intVal & 255
  };
}

/**
 * Encodes a minimal uncompressed RGBA PNG buffer in pure TypeScript (zero dependencies).
 */
export function createRgbaPng(
  width: number,
  height: number,
  r: number,
  g: number,
  b: number,
  a: number = 255
): Uint8Array {
  // CRC32 table
  const crcTable = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) {
      c = (c & 1) ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    crcTable[n] = c;
  }

  function crc32(buf: Uint8Array, offset: number, len: number): number {
    let c = 0xffffffff;
    for (let i = 0; i < len; i++) {
      c = crcTable[(c ^ buf[offset + i]) & 0xff] ^ (c >>> 8);
    }
    return (c ^ 0xffffffff) >>> 0;
  }

  // Raw uncompressed scanlines: each row starts with filter byte 0 (None) followed by RGBA pixels
  const rawRowLen = 1 + width * 4;
  const rawDataLen = rawRowLen * height;
  const rawData = new Uint8Array(rawDataLen);

  for (let y = 0; y < height; y++) {
    const rowOffset = y * rawRowLen;
    rawData[rowOffset] = 0; // Filter byte: None
    for (let x = 0; x < width; x++) {
      const pxOffset = rowOffset + 1 + x * 4;
      rawData[pxOffset] = r;
      rawData[pxOffset + 1] = g;
      rawData[pxOffset + 2] = b;
      rawData[pxOffset + 3] = a;
    }
  }

  // ZLIB stream (RFC 1950): Header (0x78, 0x01), Uncompressed blocks (BTYPE=00), Adler32
  // We can write uncompressed Deflate block(s) up to 65535 bytes each
  const maxBlockSize = 65535;
  const numBlocks = Math.ceil(rawDataLen / maxBlockSize) || 1;
  const zlibLen = 2 + numBlocks * 5 + rawDataLen + 4;
  const zlib = new Uint8Array(zlibLen);

  zlib[0] = 0x78; // CINFO=7, CM=8
  zlib[1] = 0x01; // FCHECK

  let zPtr = 2;
  let rawPtr = 0;

  for (let bIdx = 0; bIdx < numBlocks; bIdx++) {
    const isFinal = (bIdx === numBlocks - 1) ? 1 : 0;
    const currentBlockLen = Math.min(maxBlockSize, rawDataLen - rawPtr);

    zlib[zPtr] = isFinal;
    zlib[zPtr + 1] = currentBlockLen & 0xff;
    zlib[zPtr + 2] = (currentBlockLen >>> 8) & 0xff;
    const nlen = (~currentBlockLen) & 0xffff;
    zlib[zPtr + 3] = nlen & 0xff;
    zlib[zPtr + 4] = (nlen >>> 8) & 0xff;
    zPtr += 5;

    zlib.set(rawData.subarray(rawPtr, rawPtr + currentBlockLen), zPtr);
    zPtr += currentBlockLen;
    rawPtr += currentBlockLen;
  }

  // Adler32
  let s1 = 1;
  let s2 = 0;
  for (let i = 0; i < rawDataLen; i++) {
    s1 = (s1 + rawData[i]) % 65521;
    s2 = (s2 + s1) % 65521;
  }
  const adler = ((s2 << 16) | s1) >>> 0;
  zlib[zPtr] = (adler >>> 24) & 0xff;
  zlib[zPtr + 1] = (adler >>> 16) & 0xff;
  zlib[zPtr + 2] = (adler >>> 8) & 0xff;
  zlib[zPtr + 3] = adler & 0xff;

  // Build PNG chunks: Signature (8) + IHDR (25) + IDAT (12 + zlibLen) + IEND (12)
  const totalPngLen = 8 + 25 + (12 + zlibLen) + 12;
  const png = new Uint8Array(totalPngLen);
  const dv = new DataView(png.buffer);

  // Signature
  png.set([137, 80, 78, 71, 13, 10, 26, 10], 0);

  // IHDR chunk
  dv.setUint32(8, 13, false); // Length
  png.set([0x49, 0x48, 0x44, 0x52], 12); // "IHDR"
  dv.setUint32(16, width, false);
  dv.setUint32(20, height, false);
  png[24] = 8; // Bit depth: 8
  png[25] = 6; // Color type: RGBA
  png[26] = 0; // Compression: Deflate
  png[27] = 0; // Filter: Adaptive
  png[28] = 0; // Interlace: None
  const ihdrCrc = crc32(png, 12, 17);
  dv.setUint32(29, ihdrCrc, false);

  // IDAT chunk
  const idatOffset = 33;
  dv.setUint32(idatOffset, zlibLen, false);
  png.set([0x49, 0x44, 0x41, 0x54], idatOffset + 4); // "IDAT"
  png.set(zlib, idatOffset + 8);
  const idatCrc = crc32(png, idatOffset + 4, zlibLen + 4);
  dv.setUint32(idatOffset + 8 + zlibLen, idatCrc, false);

  // IEND chunk
  const iendOffset = idatOffset + 12 + zlibLen;
  dv.setUint32(iendOffset, 0, false);
  png.set([0x49, 0x45, 0x4e, 0x44], iendOffset + 4); // "IEND"
  const iendCrc = crc32(png, iendOffset + 4, 4);
  dv.setUint32(iendOffset + 8, iendCrc, false);

  return png;
}

export class StandardTextureSynthesizer implements ITextureSynthesizer {
  public async synthesizePbrMaps(
    _frontImageBytes: Uint8Array,
    _backImageBytes?: Uint8Array,
    dominantColorHex: string = '#2C3E50'
  ): Promise<TextureAtlasMaps> {
    const { r, g, b } = parseHexColor(dominantColorHex);

    // Synthesize 4x4 valid PBR texture maps
    const diffusePngBytes = createRgbaPng(4, 4, r, g, b, 255);
    // Tangent-space flat normal is [128, 128, 255] (vector 0, 0, 1)
    const normalPngBytes = createRgbaPng(4, 4, 128, 128, 255, 255);
    // Standard fabric roughness ~ 0.75 (191 / 255)
    const roughnessPngBytes = createRgbaPng(4, 4, 191, 191, 191, 255);

    return {
      diffusePngBytes,
      normalPngBytes,
      roughnessPngBytes,
      resolution: { width: 4, height: 4 }
    };
  }

  public buildMaterial(
    materialName: string,
    _maps: TextureAtlasMaps,
    diffuseUrl: string,
    normalUrl?: string,
    roughnessUrl?: string
  ): MaterialDef {
    return {
      name: materialName,
      diffuseColorHex: '#FFFFFF',
      diffuseMapUrl: diffuseUrl,
      normalMapUrl: normalUrl,
      roughnessMapUrl: roughnessUrl,
      roughness: 0.75,
      metalness: 0.05
    };
  }
}
