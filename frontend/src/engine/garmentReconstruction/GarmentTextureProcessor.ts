/**
 * YORVYN — Garment Texture & PBR Material Processor (Phase 5)
 * 
 * Implements:
 * 1. Physical PBR parameters for 9 fabric characteristics (Cotton, Fleece, Denim, Leather, Wool, Silk, Polyester, Linen, Knitted).
 * 2. Component-Isolated Diffuse Texture Atlas Synthesis:
 *    - ZERO monolithic photo decal pasting.
 *    - Fills entire base canvas with pure sampled fabric tone and micro-weave texture.
 *    - Maps front torso crop ONLY to Front Torso UV island.
 *    - Inferred rear surface with structural seams and neckline crescent (never mirrors front decals).
 *    - Sleeves, hood, pocket, and trims rendered on independent UV islands with aligned directional seams.
 * 3. Directional PBR Normal Maps for micro-textiles and ribbed boundary bands.
 */

import { 
  FabricType, 
  FabricPBRProperties, 
  GARMENT_UV_ISLANDS, 
  GarmentComponentBounds 
} from './garmentReconstructionTypes';

export class GarmentTextureProcessor {
  public static readonly FABRIC_PRESETS: Record<FabricType, FabricPBRProperties> = {
    cotton: {
      type: 'cotton',
      roughness: 0.78,
      metalness: 0.02,
      normalIntensity: 0.6,
      isEstimated: true,
      editorialNotes: 'Matte combed cotton with soft diffuse scatter and micro-slub weave.'
    },
    fleece: {
      type: 'fleece',
      roughness: 0.88,
      metalness: 0.01,
      normalIntensity: 0.75,
      isEstimated: true,
      editorialNotes: 'Brushed heavy fleece cotton with thermal plush surface and soft diffuse absorption.'
    },
    denim: {
      type: 'denim',
      roughness: 0.85,
      metalness: 0.04,
      normalIntensity: 1.0,
      isEstimated: true,
      editorialNotes: 'Heavyweight twill weave with directional diagonal ridges and washed highlights.'
    },
    leather: {
      type: 'leather',
      roughness: 0.38,
      metalness: 0.15,
      clearcoat: 0.6,
      normalIntensity: 0.45,
      isEstimated: true,
      editorialNotes: 'Supple full-grain nappa leather with specular highlights and micro-pebble grain.'
    },
    wool: {
      type: 'wool',
      roughness: 0.90,
      metalness: 0.01,
      normalIntensity: 0.85,
      isEstimated: true,
      editorialNotes: 'Fine spun merino wool with velvety diffuse absorption and subtle surface halo.'
    },
    silk: {
      type: 'silk',
      roughness: 0.28,
      metalness: 0.10,
      sheen: 0.75,
      anisotropy: 0.4,
      normalIntensity: 0.25,
      isEstimated: true,
      editorialNotes: 'Lustrous mulberry silk with anisotropic grazing sheen and liquid drape reflections.'
    },
    polyester: {
      type: 'polyester',
      roughness: 0.50,
      metalness: 0.08,
      normalIntensity: 0.4,
      isEstimated: true,
      editorialNotes: 'Performance technical microfiber with resilient mid-gloss sheen.'
    },
    linen: {
      type: 'linen',
      roughness: 0.82,
      metalness: 0.02,
      normalIntensity: 0.75,
      isEstimated: true,
      editorialNotes: 'Airy European flax linen with organic cross-hatch irregularities.'
    },
    knitted: {
      type: 'knitted',
      roughness: 0.88,
      metalness: 0.02,
      normalIntensity: 1.1,
      isEstimated: true,
      editorialNotes: 'Structured ribbed sweater knit with pronounced vertical wales and shadow depth.'
    }
  };

  /**
   * Derives PBR properties based on user selection or automatic classification.
   */
  public static getFabricProperties(type: FabricType): FabricPBRProperties {
    return this.FABRIC_PRESETS[type] || this.FABRIC_PRESETS.cotton;
  }

  /**
   * Synthesizes an albedo UV texture atlas from segmented photographic inputs using component-isolated UV islands.
   * Completely eliminates monolithic photo decal wrapping and background leakage.
   */
  public static async createDiffuseTextureAtlas(
    frontSegmentedUrl: string,
    baseColorHex: string,
    backSegmentedUrl?: string,
    size = 1024,
    pureFabricSampleRgb?: [number, number, number],
    componentBounds?: GarmentComponentBounds[]
  ): Promise<{ dataUrl: string; imageBytes?: Uint8Array }> {
    if (typeof document === 'undefined' || typeof document.createElement !== 'function') {
      return {
        dataUrl: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkWPjfDwAEeQHzj374ZAAAAABJRU5ErkJggg=='
      };
    }

    try {
      const canvas = document.createElement('canvas');
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext('2d');
      if (!ctx) return { dataUrl: frontSegmentedUrl };

      // ── LAYER 1: BASE FABRIC SYNTHESIZER ──
      // Fill the entire atlas with the detected true fabric base color (e.g. rich dark brown #4a2e18)
      const effectiveBaseHex = pureFabricSampleRgb
        ? `#${Math.max(0, Math.min(255, pureFabricSampleRgb[0])).toString(16).padStart(2, '0')}${Math.max(0, Math.min(255, pureFabricSampleRgb[1])).toString(16).padStart(2, '0')}${Math.max(0, Math.min(255, pureFabricSampleRgb[2])).toString(16).padStart(2, '0')}`
        : baseColorHex;
      ctx.fillStyle = effectiveBaseHex;
      ctx.fillRect(0, 0, size, size);

      // Add physical fabric micro-weave noise
      const imgData = ctx.getImageData(0, 0, size, size);
      const data = imgData.data;
      for (let i = 0; i < size * size; i++) {
        const noise = (Math.random() - 0.5) * 12;
        data[i * 4] = Math.max(0, Math.min(255, data[i * 4] + noise));
        data[i * 4 + 1] = Math.max(0, Math.min(255, data[i * 4 + 1] + noise));
        data[i * 4 + 2] = Math.max(0, Math.min(255, data[i * 4 + 2] + noise));
      }
      ctx.putImageData(imgData, 0, 0);

      // Load front transparent PNG
      const frontImg = await this.loadImageElement(frontSegmentedUrl);
      const fW = frontImg.naturalWidth || frontImg.width;
      const fH = frontImg.naturalHeight || frontImg.height;

      // ── LAYER 2: FRONT TORSO UV ISLAND ──
      // Island: U in [0.04, 0.46], V in [0.04, 0.50]
      // Canvas pixels: X in [0.04, 0.46], Y in [0.50, 0.96] (glTF V is flipped)
      const fIsland = GARMENT_UV_ISLANDS.FRONT_TORSO;
      const fDestX = Math.floor(fIsland.uMin * size);
      const fDestY = Math.floor((1.0 - fIsland.vMax) * size);
      const fDestW = Math.floor((fIsland.uMax - fIsland.uMin) * size);
      const fDestH = Math.floor((fIsland.vMax - fIsland.vMin) * size);

      // Isolate torso region from front image (excluding sleeve wings and background)
      const torsoBound = componentBounds?.find(b => b.type === 'front_torso');
      const cropSrcX = torsoBound ? torsoBound.x : Math.floor(fW * 0.20);
      const cropSrcY = torsoBound ? torsoBound.y : Math.floor(fH * 0.22);
      const cropSrcW = torsoBound ? torsoBound.width : Math.floor(fW * 0.60);
      const cropSrcH = torsoBound ? torsoBound.height : Math.floor(fH * 0.72);

      // Draw front torso with smooth alpha blending
      ctx.save();
      ctx.drawImage(
        frontImg,
        cropSrcX, cropSrcY, Math.max(10, cropSrcW), Math.max(10, cropSrcH),
        fDestX, fDestY, fDestW, fDestH
      );
      ctx.restore();

      // ── LAYER 3: BACK TORSO UV ISLAND ──
      // Island: U in [0.54, 0.96], V in [0.04, 0.50]
      // Canvas pixels: X in [0.54, 0.96], Y in [0.50, 0.96]
      const bIsland = GARMENT_UV_ISLANDS.BACK_TORSO;
      const bDestX = Math.floor(bIsland.uMin * size);
      const bDestY = Math.floor((1.0 - bIsland.vMax) * size);
      const bDestW = Math.floor((bIsland.uMax - bIsland.uMin) * size);
      const bDestH = Math.floor((bIsland.vMax - bIsland.vMin) * size);

      if (backSegmentedUrl) {
        // User provided an authentic rear photo
        const backImg = await this.loadImageElement(backSegmentedUrl);
        const bW = backImg.naturalWidth || backImg.width;
        const bH = backImg.naturalHeight || backImg.height;
        ctx.drawImage(
          backImg,
          Math.floor(bW * 0.20), Math.floor(bH * 0.22), Math.floor(bW * 0.60), Math.floor(bH * 0.72),
          bDestX, bDestY, bDestW, bDestH
        );
      } else {
        // INFERRED REAR SURFACE: Structural fabric with collar crescent and yoke seams (never mirrors front decals)
        ctx.save();
        // Rear yoke seam
        ctx.strokeStyle = 'rgba(0, 0, 0, 0.16)';
        ctx.lineWidth = Math.max(2, size * 0.003);
        ctx.beginPath();
        const yokeY = bDestY + Math.floor(bDestH * 0.18);
        ctx.moveTo(bDestX, yokeY);
        ctx.lineTo(bDestX + bDestW, yokeY);
        ctx.stroke();

        // Rear collar crescent
        ctx.fillStyle = 'rgba(0, 0, 0, 0.12)';
        ctx.beginPath();
        ctx.ellipse(
          bDestX + bDestW / 2, bDestY + Math.floor(bDestH * 0.05),
          bDestW * 0.25, bDestH * 0.08,
          0, 0, Math.PI
        );
        ctx.fill();
        ctx.restore();
      }

      // ── LAYER 4: ARTICULATED SLEEVES UV ISLANDS ──
      // Left: U in [0.04, 0.46], V in [0.54, 0.74] -> Canvas Y in [0.26, 0.46]
      // Right: U in [0.54, 0.96], V in [0.54, 0.74] -> Canvas Y in [0.26, 0.46]
      const drawSleevePanel = (uMin: number, uMax: number, _isLeft: boolean) => {
        const destX = Math.floor(uMin * size);
        const destY = Math.floor((1.0 - 0.74) * size);
        const destW = Math.floor((uMax - uMin) * size);
        const destH = Math.floor((0.74 - 0.54) * size);

        ctx.save();
        // Directional seam gradient along arm length
        const grad = ctx.createLinearGradient(destX, destY, destX + destW, destY);
        grad.addColorStop(0, 'rgba(0, 0, 0, 0.12)');
        grad.addColorStop(0.5, 'rgba(255, 255, 255, 0.05)');
        grad.addColorStop(1, 'rgba(0, 0, 0, 0.12)');
        ctx.fillStyle = grad;
        ctx.fillRect(destX, destY, destW, destH);

        // Ribbed cuff trim at bottom of sleeve panel (near wrist)
        ctx.fillStyle = 'rgba(0, 0, 0, 0.18)';
        ctx.fillRect(destX, destY + Math.floor(destH * 0.85), destW, Math.floor(destH * 0.15));

        ctx.strokeStyle = 'rgba(0, 0, 0, 0.25)';
        ctx.lineWidth = 1.5;
        for (let x = destX + 4; x < destX + destW; x += 6) {
          ctx.beginPath();
          ctx.moveTo(x, destY + Math.floor(destH * 0.85));
          ctx.lineTo(x, destY + destH);
          ctx.stroke();
        }
        ctx.restore();
      };

      drawSleevePanel(GARMENT_UV_ISLANDS.LEFT_SLEEVE.uMin, GARMENT_UV_ISLANDS.LEFT_SLEEVE.uMax, true);
      drawSleevePanel(GARMENT_UV_ISLANDS.RIGHT_SLEEVE.uMin, GARMENT_UV_ISLANDS.RIGHT_SLEEVE.uMax, false);

      // ── LAYER 5: HOOD COWL UV ISLAND ──
      // U in [0.04, 0.46], V in [0.76, 0.96] -> Canvas Y in [0.04, 0.24]
      const hIsland = GARMENT_UV_ISLANDS.HOOD;
      const hDestX = Math.floor(hIsland.uMin * size);
      const hDestY = Math.floor((1.0 - hIsland.vMax) * size);
      const hDestW = Math.floor((hIsland.uMax - hIsland.uMin) * size);
      const hDestH = Math.floor((hIsland.vMax - hIsland.vMin) * size);

      ctx.save();
      // Hood center ridge seam
      ctx.strokeStyle = 'rgba(0, 0, 0, 0.20)';
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(hDestX + hDestW / 2, hDestY);
      ctx.lineTo(hDestX + hDestW / 2, hDestY + hDestH);
      ctx.stroke();

      // Hood cowl face trim hem
      ctx.fillStyle = 'rgba(0, 0, 0, 0.14)';
      ctx.fillRect(hDestX, hDestY + Math.floor(hDestH * 0.88), hDestW, Math.floor(hDestH * 0.12));
      ctx.restore();

      // ── LAYER 6: KANGAROO POUCH POCKET & DRAWSTRING TRIMS ──
      // U in [0.54, 0.96], V in [0.76, 0.96] -> Canvas Y in [0.04, 0.24]
      const pIsland = GARMENT_UV_ISLANDS.POCKET_TRIM;
      const pDestX = Math.floor(pIsland.uMin * size);
      const pDestY = Math.floor((1.0 - pIsland.vMax) * size);
      const pDestW = Math.floor((pIsland.uMax - pIsland.uMin) * size);
      const pDestH = Math.floor((pIsland.vMax - pIsland.vMin) * size);

      ctx.save();
      // Kangaroo pocket outline with angled side slits
      ctx.strokeStyle = 'rgba(0, 0, 0, 0.22)';
      ctx.lineWidth = 2.0;
      ctx.strokeRect(pDestX + 8, pDestY + 8, pDestW - 16, pDestH - 16);

      // Angled hand warmer entry slits
      ctx.beginPath();
      ctx.moveTo(pDestX + 12, pDestY + 12);
      ctx.lineTo(pDestX + Math.floor(pDestW * 0.25), pDestY + pDestH - 12);
      ctx.moveTo(pDestX + pDestW - 12, pDestY + 12);
      ctx.lineTo(pDestX + Math.floor(pDestW * 0.75), pDestY + pDestH - 12);
      ctx.stroke();

      // Drawstring braided texture and metallic aglet tips in right margin
      const agletX = pDestX + Math.floor(pDestW * 0.88);
      ctx.fillStyle = '#c5a059'; // Metallic brass/gold aglet
      ctx.fillRect(agletX, pDestY + 12, Math.floor(pDestW * 0.08), Math.floor(pDestH * 0.35));
      ctx.restore();

      const dataUrl = canvas.toDataURL('image/png');
      return { dataUrl };
    } catch {
      return { dataUrl: frontSegmentedUrl };
    }
  }

  /**
   * Generates a procedural normal map canvas data URI simulating fabric weave.
   */
  public static generateProceduralNormalMap(type: FabricType, size = 256): string {
    if (typeof document === 'undefined' || typeof document.createElement !== 'function') {
      return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkWPjfDwAEeQHzj374ZAAAAABJRU5ErkJggg==';
    }

    try {
      const canvas = document.createElement('canvas');
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext('2d');
      if (!ctx) return '';

      const imgData = ctx.createImageData(size, size);
      const data = imgData.data;

      const props = this.getFabricProperties(type);
      const intensity = props.normalIntensity;

      for (let y = 0; y < size; y++) {
        for (let x = 0; x < size; x++) {
          const idx = (y * size + x) * 4;

          let nx = 0;
          let ny = 0;

          if (type === 'denim') {
            const diag = (x + y) % 6;
            nx = (diag < 3 ? 0.35 : -0.35) * intensity;
            ny = (diag < 3 ? 0.35 : -0.35) * intensity;
          } else if (type === 'fleece') {
            const noise = (Math.sin(x * 0.4) + Math.cos(y * 0.4)) * 0.25;
            nx = noise * intensity;
            ny = -noise * intensity;
          } else if (type === 'knitted') {
            const wale = Math.sin((x / size) * Math.PI * 32);
            nx = wale * 0.6 * intensity;
            ny = Math.cos((y / size) * Math.PI * 16) * 0.2 * intensity;
          } else if (type === 'leather') {
            const cell = (Math.sin(x * 0.2) * Math.sin(y * 0.2));
            nx = cell * 0.4 * intensity;
            ny = cell * 0.4 * intensity;
          } else {
            // Cotton / Linen cross-slub weave
            const slubX = (x % 4 === 0) ? 0.2 : -0.2;
            const slubY = (y % 4 === 0) ? 0.2 : -0.2;
            nx = slubX * intensity;
            ny = slubY * intensity;
          }

          // Convert tangent space normal [-1..1] to RGB [0..255]
          // Normal Z points towards viewer (default 1.0)
          const nz = Math.sqrt(Math.max(0, 1.0 - nx * nx - ny * ny));
          data[idx] = Math.round((nx * 0.5 + 0.5) * 255);
          data[idx + 1] = Math.round((ny * 0.5 + 0.5) * 255);
          data[idx + 2] = Math.round((nz * 0.5 + 0.5) * 255);
          data[idx + 3] = 255;
        }
      }

      ctx.putImageData(imgData, 0, 0);
      return canvas.toDataURL('image/png');
    } catch {
      return '';
    }
  }

  private static loadImageElement(url: string): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error('Failed to load image in texture processor.'));
      img.src = url;
    });
  }
}
