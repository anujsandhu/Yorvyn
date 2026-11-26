/**
 * YORVYN — ONNX Runtime Web Adapter (Phase 13)
 * Provides WebGPU-accelerated and WASM-fallback inference execution
 * for client-side garment attribute and feature extraction models.
 */

import { edgeModelCacheManager } from './EdgeModelCacheManager';

export interface OnnxInferenceResult {
  outputTensor: Float32Array;
  dims: readonly number[];
  executionProvider: 'webgpu' | 'wasm' | 'cpu';
  durationMs: number;
  outputs?: Record<string, { data: Float32Array; dims: readonly number[] }>;
}

export class OnnxRuntimeWebAdapter {
  private static ortInstance: any = null;
  private activeSessions: Map<string, any> = new Map();

  /**
   * Lazily loads onnxruntime-web to prevent upfront bundle bloat.
   */
  private static async getOrt(): Promise<any> {
    if (!OnnxRuntimeWebAdapter.ortInstance) {
      try {
        const ort = await import('onnxruntime-web');
        // Configure wasm paths
        if (ort.env && ort.env.wasm) {
          ort.env.wasm.numThreads = 2;
          ort.env.wasm.simd = true;
        }
        OnnxRuntimeWebAdapter.ortInstance = ort;
      } catch (err) {
        console.warn('[OnnxRuntimeWebAdapter] Could not import onnxruntime-web:', err);
        throw err;
      }
    }
    return OnnxRuntimeWebAdapter.ortInstance;
  }

  /**
   * Initializes an inference session with WebGPU preferred and WASM fallback.
   */
  public async createSession(
    modelId: string,
    modelUrlOrBuffer: string | ArrayBuffer,
    preferWebGPU = true
  ): Promise<any> {
    if (this.activeSessions.has(modelId)) {
      return this.activeSessions.get(modelId);
    }

    const ort = await OnnxRuntimeWebAdapter.getOrt();
    const providers: string[] = preferWebGPU ? ['webgpu', 'wasm', 'cpu'] : ['wasm', 'cpu'];

    let inputTarget: string | ArrayBuffer = modelUrlOrBuffer;
    if (typeof modelUrlOrBuffer === 'string') {
      try {
        const cached = await edgeModelCacheManager.getModel(modelId);
        if (cached && cached.weightsBuffer) {
          inputTarget = cached.weightsBuffer;
        }
      } catch (cacheErr) {
        console.warn(`[OnnxRuntimeWebAdapter] Cache lookup failed for ${modelId}:`, cacheErr);
      }
    }

    let session: any = null;
    let lastError: any = null;

    for (const provider of providers) {
      try {
        const options = {
          executionProviders: [provider],
          graphOptimizationLevel: 'all'
        };

        session = await ort.InferenceSession.create(inputTarget, options);

        if (session) {
          this.activeSessions.set(modelId, session);
          return session;
        }
      } catch (err) {
        lastError = err;
        // Try next fallback provider
      }
    }

    throw new Error(`Failed to initialize ONNX session for ${modelId}: ${lastError?.message || 'Unsupported provider'}`);
  }

  /**
   * Executes inference on a float32 input tensor.
   */
  public async runInference(
    modelId: string,
    inputName: string,
    inputData: Float32Array,
    dims: number[]
  ): Promise<OnnxInferenceResult> {
    const session = this.activeSessions.get(modelId);
    if (!session) {
      throw new Error(`Session for model ${modelId} not found. Must call createSession first.`);
    }

    const ort = await OnnxRuntimeWebAdapter.getOrt();
    const inputTensor = new ort.Tensor('float32', inputData, dims);

    const startT = performance.now();
    const feeds = { [inputName]: inputTensor };
    const results = await session.run(feeds);
    const durationMs = performance.now() - startT;

    const outputNames = Object.keys(results);
    const primaryOutput = results[outputNames[0]];

    const outputs: Record<string, { data: Float32Array; dims: readonly number[] }> = {};
    for (const name of outputNames) {
      outputs[name] = {
        data: results[name].data as Float32Array,
        dims: results[name].dims
      };
    }

    return {
      outputTensor: primaryOutput.data as Float32Array,
      dims: primaryOutput.dims,
      executionProvider: (session as any).handler?.provider || 'wasm',
      durationMs,
      outputs
    };
  }

  public async disposeSession(modelId: string): Promise<void> {
    const session = this.activeSessions.get(modelId);
    if (session && typeof session.release === 'function') {
      try {
        await session.release();
      } catch {
        // Ignore release error
      }
    }
    this.activeSessions.delete(modelId);
  }

  public async disposeAll(): Promise<void> {
    for (const modelId of Array.from(this.activeSessions.keys())) {
      await this.disposeSession(modelId);
    }
  }
}

export const onnxRuntimeWebAdapter = new OnnxRuntimeWebAdapter();
