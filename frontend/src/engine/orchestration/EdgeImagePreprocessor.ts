/**
 * YORVYN — Edge Image Preprocessor & Computer Vision Engine (Phase 13.2 Remediated)
 * Executes ultra-fast background image normalization, blur detection,
 * palette extraction, and intelligent multi-scale WebP compression.
 * Offloads compute to dedicated Web Worker + OffscreenCanvas with main-thread fallback.
 */

import { HybridPreprocessResult } from '../../types/hybridAIContracts';
import type { WorkerPreprocessRequest, WorkerPreprocessResponse } from './edgeImagePreprocessor.worker';

export interface PreprocessingOptions {
  maxDimension?: number;
  quality?: number;
  format?: 'image/webp' | 'image/png' | 'image/jpeg';
  blurThreshold?: number;
  extractPaletteCount?: number;
}

export class EdgeImagePreprocessor {
  private static readonly DEFAULT_MAX_DIMENSION = 1200;
  private static readonly DEFAULT_QUALITY = 0.85;
  private static readonly DEFAULT_BLUR_THRESHOLD = 90.0;
  private static workerInstance: Worker | null = null;
  private static pendingRequests: Map<string, { resolve: (res: any) => void; reject: (err: any) => void }> = new Map();

  /**
   * Explicitly terminates the background Web Worker and cancels pending requests.
   */
  public static terminateWorker(): void {
    if (this.workerInstance) {
      this.workerInstance.terminate();
      this.workerInstance = null;
    }
    for (const [id, pending] of this.pendingRequests.entries()) {
      pending.reject(new Error(`Worker terminated: request ${id} cancelled`));
    }
    this.pendingRequests.clear();
  }

  /**
   * Cancels a pending in-flight preprocessing request.
   */
  public static cancelRequest(reqId: string): boolean {
    const pending = this.pendingRequests.get(reqId);
    if (pending) {
      this.pendingRequests.delete(reqId);
      pending.reject(new Error(`Request ${reqId} cancelled by caller`));
      return true;
    }
    return false;
  }

  private static getWorker(): Worker | null {
    if (typeof window === 'undefined' || typeof Worker === 'undefined') {
      return null;
    }
    if (!this.workerInstance) {
      try {
        // Instantiate Worker using standard Vite module worker import URL
        this.workerInstance = new Worker(
          new URL('./edgeImagePreprocessor.worker.ts', import.meta.url),
          { type: 'module' }
        );

        this.workerInstance.onmessage = (e: MessageEvent<WorkerPreprocessResponse>) => {
          const { id, error } = e.data;
          const pending = EdgeImagePreprocessor.pendingRequests.get(id);
          if (pending) {
            EdgeImagePreprocessor.pendingRequests.delete(id);
            if (error) {
              pending.reject(new Error(error));
            } else {
              pending.resolve(e.data);
            }
          }
        };

        this.workerInstance.onerror = (err) => {
          console.warn('[EdgeImagePreprocessor Worker Error]:', err);
        };
      } catch (err) {
        console.warn('[EdgeImagePreprocessor] Worker instantiation fallback to main thread:', err);
        this.workerInstance = null;
      }
    }
    return this.workerInstance;
  }

  /**
   * Complete photographic optimization and analytical CV pipeline.
   * Dispatches to background Web Worker where OffscreenCanvas is available,
   * otherwise cleanly executes on main-thread canvas.
   */
  public static async preprocessImage(
    fileOrBlob: Blob | File,
    options: PreprocessingOptions = {}
  ): Promise<HybridPreprocessResult> {
    const startT = performance.now();
    const maxDim = options.maxDimension || this.DEFAULT_MAX_DIMENSION;
    const quality = options.quality || this.DEFAULT_QUALITY;
    const format = options.format || 'image/webp';
    const blurThreshold = options.blurThreshold || this.DEFAULT_BLUR_THRESHOLD;
    const paletteCount = options.extractPaletteCount || 5;

    const originalSizeBytes = fileOrBlob.size;

    // 1. Inspect dimensions
    const dims = await this.getImageDimensions(fileOrBlob);
    const targetDims = this.calculateTargetDimensions(dims.width, dims.height, maxDim);
    const targetWidth = targetDims.width;
    const targetHeight = targetDims.height;

    // 2. Try Worker + OffscreenCanvas off-thread execution
    const worker = this.getWorker();
    const canUseWorker = Boolean(
      worker &&
      typeof createImageBitmap === 'function' &&
      typeof OffscreenCanvas !== 'undefined'
    );

    if (canUseWorker && worker) {
      try {
        const bitmap = await createImageBitmap(fileOrBlob);
        const reqId = `prep_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;

        const workerPromise = new Promise<WorkerPreprocessResponse>((resolve, reject) => {
          EdgeImagePreprocessor.pendingRequests.set(reqId, { resolve, reject });
        });

        const reqPayload: WorkerPreprocessRequest = {
          id: reqId,
          bitmap,
          targetWidth,
          targetHeight,
          quality,
          format,
          blurThreshold,
          paletteCount
        };

        worker.postMessage(reqPayload, [bitmap]);
        const workerResult = await workerPromise;

        if (workerResult.blob) {
          const processedBlob = workerResult.blob;
          const compressedSizeBytes = processedBlob.size;
          const compressionRatio = originalSizeBytes > 0 ? compressedSizeBytes / originalSizeBytes : 1.0;
          const durationMs = performance.now() - startT;

          return {
            processedBlob,
            previewDataUrl: URL.createObjectURL(processedBlob),
            dimensions: { width: targetWidth, height: targetHeight },
            originalSizeBytes,
            compressedSizeBytes,
            compressionRatio: Math.round(compressionRatio * 1000) / 1000,
            isBlurry: workerResult.isBlurry,
            blurVariance: workerResult.blurVariance,
            dominantColors: workerResult.dominantColors,
            durationMs: Math.round(durationMs * 10) / 10
          };
        }
      } catch (workerErr) {
        console.warn('[EdgeImagePreprocessor] Worker processing failed, falling back to main thread canvas:', workerErr);
      }
    }

    // 3. Main-thread Fallback Execution Path
    const img = await this.loadImage(fileOrBlob);
    let canvas: HTMLCanvasElement;
    let ctx: CanvasRenderingContext2D;

    if (typeof document !== 'undefined') {
      canvas = document.createElement('canvas');
      canvas.width = targetWidth;
      canvas.height = targetHeight;
      ctx = canvas.getContext('2d', { willReadFrequently: true }) as CanvasRenderingContext2D;
    } else {
      throw new Error('Canvas rendering context unavailable in current execution environment.');
    }

    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(img, 0, 0, targetWidth, targetHeight);

    const imageData = ctx.getImageData(0, 0, targetWidth, targetHeight);
    const pixels = imageData.data;

    const blurVariance = this.calculateLaplacianVariance(pixels, targetWidth, targetHeight);
    const isBlurry = blurVariance < blurThreshold;
    const dominantColors = this.extractPalette(pixels, paletteCount);

    const processedBlob = await this.canvasToBlob(canvas, format, quality);
    const compressedSizeBytes = processedBlob.size;
    const compressionRatio = originalSizeBytes > 0 ? compressedSizeBytes / originalSizeBytes : 1.0;
    const previewDataUrl = canvas.toDataURL ? canvas.toDataURL('image/jpeg', 0.70) : URL.createObjectURL(processedBlob);
    const durationMs = performance.now() - startT;

    return {
      processedBlob,
      previewDataUrl,
      dimensions: { width: targetWidth, height: targetHeight },
      originalSizeBytes,
      compressedSizeBytes,
      compressionRatio: Math.round(compressionRatio * 1000) / 1000,
      isBlurry,
      blurVariance: Math.round(blurVariance * 10) / 10,
      dominantColors,
      durationMs: Math.round(durationMs * 10) / 10
    };
  }

  private static async getImageDimensions(blob: Blob): Promise<{ width: number; height: number }> {
    if (typeof createImageBitmap === 'function') {
      try {
        const bmp = await createImageBitmap(blob);
        const res = { width: bmp.width, height: bmp.height };
        bmp.close();
        return res;
      } catch {
        // Fallback to Image
      }
    }
    const img = await this.loadImage(blob);
    return {
      width: img.naturalWidth || img.width,
      height: img.naturalHeight || img.height
    };
  }

  private static loadImage(blob: Blob): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(blob);
      const img = new Image();
      img.onload = () => {
        URL.revokeObjectURL(url);
        resolve(img);
      };
      img.onerror = (err) => {
        URL.revokeObjectURL(url);
        reject(err);
      };
      img.src = url;
    });
  }

  private static canvasToBlob(canvas: HTMLCanvasElement, format: string, quality: number): Promise<Blob> {
    return new Promise((resolve, reject) => {
      canvas.toBlob(
        (blob) => {
          if (blob) resolve(blob);
          else reject(new Error('Canvas toBlob failed'));
        },
        format,
        quality
      );
    });
  }

  public static calculateTargetDimensions(origWidth: number, origHeight: number, maxDim: number): { width: number; height: number } {
    if (origWidth > maxDim || origHeight > maxDim) {
      if (origWidth >= origHeight) {
        return {
          width: maxDim,
          height: Math.round((origHeight * maxDim) / origWidth)
        };
      } else {
        return {
          width: Math.round((origWidth * maxDim) / origHeight),
          height: maxDim
        };
      }
    }
    return { width: origWidth, height: origHeight };
  }

  public static calculateLaplacianVariance(pixels: Uint8ClampedArray, width: number, height: number): number {
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

  public static extractPalette(pixels: Uint8ClampedArray, count = 5): string[] {
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
}
