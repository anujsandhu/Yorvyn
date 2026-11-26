/**
 * YORVYN — Edge Image Preprocessor Dedicated Web Worker (Phase 13.2)
 * Executes non-blocking background image scaling, discrete Laplacian variance blur analysis,
 * and RGB quantization palette extraction off the main DOM thread using OffscreenCanvas.
 */

export interface WorkerPreprocessRequest {
  id: string;
  bitmap: ImageBitmap;
  targetWidth: number;
  targetHeight: number;
  quality: number;
  format: 'image/webp' | 'image/png' | 'image/jpeg';
  blurThreshold: number;
  paletteCount: number;
}

export interface WorkerPreprocessResponse {
  id: string;
  blob?: Blob;
  blurVariance: number;
  isBlurry: boolean;
  dominantColors: string[];
  durationMs: number;
  error?: string;
}

self.onmessage = async (e: MessageEvent<WorkerPreprocessRequest>) => {
  const startT = performance.now();
  const { id, bitmap, targetWidth, targetHeight, quality, format, blurThreshold, paletteCount } = e.data;

  try {
    const canvas = new OffscreenCanvas(targetWidth, targetHeight);
    const ctx = canvas.getContext('2d', { willReadFrequently: true }) as OffscreenCanvasRenderingContext2D;

    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(bitmap, 0, 0, targetWidth, targetHeight);
    bitmap.close();

    const imageData = ctx.getImageData(0, 0, targetWidth, targetHeight);
    const pixels = imageData.data;

    // Laplacian variance
    const blurVariance = calculateLaplacianVariance(pixels, targetWidth, targetHeight);
    const isBlurry = blurVariance < blurThreshold;

    // Palette extraction
    const dominantColors = extractPalette(pixels, paletteCount);

    // Convert to Blob
    let blob: Blob;
    if (typeof canvas.convertToBlob === 'function') {
      blob = await canvas.convertToBlob({ type: format, quality });
    } else {
      throw new Error('OffscreenCanvas.convertToBlob unsupported in current worker runtime');
    }

    const durationMs = performance.now() - startT;

    const response: WorkerPreprocessResponse = {
      id,
      blob,
      blurVariance: Math.round(blurVariance * 10) / 10,
      isBlurry,
      dominantColors,
      durationMs: Math.round(durationMs * 10) / 10
    };

    self.postMessage(response);
  } catch (err: any) {
    self.postMessage({
      id,
      blurVariance: 0,
      isBlurry: false,
      dominantColors: ['#333333'],
      durationMs: performance.now() - startT,
      error: err?.message || 'Worker preprocessing failed'
    });
  }
};

function calculateLaplacianVariance(pixels: Uint8ClampedArray, width: number, height: number): number {
  const step = 2;
  const subW = Math.floor(width / step);
  const subH = Math.floor(height / step);
  const gray = new Float32Array(subW * subH);

  for (let y = 0; y < subH; y++) {
    for (let x = 0; x < subW; x++) {
      const srcIdx = (y * step * width + x * step) * 4;
      gray[y * subW + x] = 0.2126 * pixels[srcIdx] + 0.7152 * pixels[srcIdx + 1] + 0.0722 * pixels[srcIdx + 2];
    }
  }

  let sum = 0;
  let sumSq = 0;
  let count = 0;

  for (let y = 1; y < subH - 1; y++) {
    for (let x = 1; x < subW - 1; x++) {
      const idx = y * subW + x;
      const lap =
        gray[idx - subW] +
        gray[idx + subW] +
        gray[idx - 1] +
        gray[idx + 1] -
        4.0 * gray[idx];

      sum += lap;
      sumSq += lap * lap;
      count++;
    }
  }

  if (count === 0) return 0;
  const mean = sum / count;
  const variance = (sumSq / count) - (mean * mean);
  return Math.max(0, variance);
}

function extractPalette(pixels: Uint8ClampedArray, count = 5): string[] {
  const buckets: Map<string, number> = new Map();
  const step = 8;

  for (let i = 0; i < pixels.length; i += 4 * step) {
    const a = pixels[i + 3];
    if (a < 128) continue;

    const r = (pixels[i] >> 3) << 3;
    const g = (pixels[i + 1] >> 3) << 3;
    const b = (pixels[i + 2] >> 3) << 3;
    const key = `${r},${g},${b}`;
    buckets.set(key, (buckets.get(key) || 0) + 1);
  }

  const sorted = Array.from(buckets.entries()).sort((a, b) => b[1] - a[1]);
  const palette: string[] = [];

  for (const [key] of sorted.slice(0, count)) {
    const [r, g, b] = key.split(',').map(Number);
    const hex = `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
    palette.push(hex);
  }

  return palette.length > 0 ? palette : ['#333333', '#888888', '#ffffff'];
}

