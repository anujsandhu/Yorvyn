/**
 * YORVYN MotionCore — Hardware-Aware Compute & Quality Tier Orchestrator
 * Coordinates:
 * - CPUBackend / WASM SIMD probe / WebWorker availability / experimental WebGPU probe gate
 * - Internal adaptive quality tiers ('low', 'balanced', 'high', 'maximum') without exposing knobs to users
 * - Strict separation between native GPU hardware and software rasterizers (e.g. SwiftShader)
 */

import type { SimulationQualitySettings } from '../clothPhysics/types';
import { detectGraphicsCapabilities } from '../designStudio/GraphicsCapabilityService';
import type {
  ComputeBackendKind,
  MotionQualityTier,
  RenderBackendChoice,
} from './MotionTypes';

export interface ComputeSelectionSummary {
  renderBackend: RenderBackendChoice;
  physicsBackend: ComputeBackendKind;
  qualityTier: MotionQualityTier;
  webgpuAdapterAvailable: boolean;
  webgpuParityVerified: boolean;
  webgpuExperimentalOnly: true;
  wasmSimdSupported: boolean;
  workerSupported: boolean;
  hardwareConcurrency: number;
  isSoftwareRendered: boolean;
  rendererString: string;
  solverSettings: SimulationQualitySettings;
}

export const TIER_SOLVER_PRESETS: Record<MotionQualityTier, SimulationQualitySettings> = {
  low: {
    mode: 'performance',
    subSteps: 1,
    solverIterations: 4,
    enableBending: false,
    enableCollisions: true,
    collisionProxyDetail: 'minimal',
    fixedTimeStep: 1 / 45,
    maxActiveVertices: 1200,
  },
  balanced: {
    mode: 'balanced',
    subSteps: 2,
    solverIterations: 8,
    enableBending: true,
    enableCollisions: true,
    collisionProxyDetail: 'full',
    fixedTimeStep: 1 / 60,
    maxActiveVertices: 2500,
  },
  high: {
    mode: 'high',
    subSteps: 3,
    solverIterations: 12,
    enableBending: true,
    enableCollisions: true,
    collisionProxyDetail: 'full',
    fixedTimeStep: 1 / 75,
    maxActiveVertices: 4500,
  },
  maximum: {
    mode: 'high',
    subSteps: 4,
    solverIterations: 16,
    enableBending: true,
    enableCollisions: true,
    collisionProxyDetail: 'full',
    fixedTimeStep: 1 / 90,
    maxActiveVertices: 8000,
  },
};

export function detectSoftwareRendererString(): { isSoftware: boolean; renderer: string } {
  if (typeof document === 'undefined') {
    return { isSoftware: true, renderer: 'headless_node_vitest' };
  }
  try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
    if (!gl) return { isSoftware: true, renderer: 'no_webgl' };
    const dbg = gl.getExtension('WEBGL_debug_renderer_info');
    const renderer = dbg ? String(gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) || '') : String(gl.getParameter(gl.RENDERER) || '');
    const isSoftware = /swiftshader|llvmpipe|softpipe|mesa offscreen|microsoft basic/i.test(renderer);
    gl.getExtension('WEBGL_lose_context')?.loseContext();
    return { isSoftware, renderer: renderer || 'unknown_webgl' };
  } catch {
    return { isSoftware: true, renderer: 'probe_failed' };
  }
}

export function probeWasmSimdSupport(): boolean {
  try {
    if (typeof WebAssembly !== 'object' || typeof WebAssembly.validate !== 'function') return false;
    // Standard Wasm v128.const minimal valid module check
    return WebAssembly.validate(new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0, 1, 5, 1, 96, 0, 1, 123, 3, 2, 1, 0, 10, 10, 1, 8, 0, 65, 0, 253, 15, 253, 98, 11]));
  } catch {
    return false;
  }
}

export class ComputeOrchestrator {
  private current: ComputeSelectionSummary;

  constructor(initialTier?: MotionQualityTier) {
    const tier = initialTier || 'balanced';
    this.current = {
      renderBackend: 'webgl2',
      physicsBackend: 'cpu_xpbd',
      qualityTier: tier,
      webgpuAdapterAvailable: false,
      webgpuParityVerified: false,
      webgpuExperimentalOnly: true,
      wasmSimdSupported: probeWasmSimdSupport(),
      workerSupported: typeof Worker !== 'undefined',
      hardwareConcurrency: typeof navigator !== 'undefined' ? navigator.hardwareConcurrency || 4 : 4,
      isSoftwareRendered: false,
      rendererString: 'unprobed',
      solverSettings: { ...TIER_SOLVER_PRESETS[tier] },
    };
  }

  public async detectAndSelect(opts?: {
    vertexCount?: number;
    webgpuParityVerified?: boolean;
    probeWebGPU?: boolean;
  }): Promise<ComputeSelectionSummary> {
    const caps = await detectGraphicsCapabilities({ probeWebGPUAdapter: opts?.probeWebGPU ?? false });
    const sw = detectSoftwareRendererString();
    const wasmSimd = probeWasmSimdSupport();
    const workerOk = typeof Worker !== 'undefined';
    const vCount = opts?.vertexCount ?? 2000;

    // WebGPU stays gated behind verified parity flags; never promoted solely from adapter presence.
    const parityVerified = opts?.webgpuParityVerified === true;
    let physicsBackend: ComputeBackendKind = 'cpu_xpbd';
    if (parityVerified && caps.webgpuAdapterAvailable) {
      physicsBackend = 'webgpu_experimental';
    } else if (workerOk && vCount >= 2200 && !sw.isSoftware) {
      physicsBackend = 'webworker_xpbd';
    } else if (wasmSimd && vCount >= 3500) {
      physicsBackend = 'wasm_simd_xpbd';
    }

    let tier: MotionQualityTier = 'balanced';
    if (sw.isSoftware || !caps.webgl2Supported || caps.hardwareConcurrency <= 2) {
      tier = 'low';
    } else if (caps.hardwareConcurrency >= 10 && caps.tier === 'high' && vCount <= 4500) {
      tier = 'maximum';
    } else if (caps.tier === 'high' || caps.hardwareConcurrency >= 6) {
      tier = 'high';
    }

    this.current = {
      renderBackend: caps.webgl2Supported ? 'webgl2' : 'software_fallback',
      physicsBackend,
      qualityTier: tier,
      webgpuAdapterAvailable: caps.webgpuAdapterAvailable,
      webgpuParityVerified: parityVerified,
      webgpuExperimentalOnly: true,
      wasmSimdSupported: wasmSimd,
      workerSupported: workerOk,
      hardwareConcurrency: caps.hardwareConcurrency,
      isSoftwareRendered: sw.isSoftware,
      rendererString: sw.renderer,
      solverSettings: { ...TIER_SOLVER_PRESETS[tier] },
    };
    return this.current;
  }

  public adaptTierFromFrameTime(p95FrameMs: number): boolean {
    const order: MotionQualityTier[] = ['low', 'balanced', 'high', 'maximum'];
    const idx = order.indexOf(this.current.qualityTier);
    if (p95FrameMs > 24.0 && idx > 0) {
      const next = order[idx - 1];
      this.setQualityTier(next);
      return true;
    }
    if (p95FrameMs < 7.5 && !this.current.isSoftwareRendered && idx < order.length - 1 && this.current.hardwareConcurrency >= 8) {
      const next = order[idx + 1];
      this.setQualityTier(next);
      return true;
    }
    return false;
  }

  public setQualityTier(tier: MotionQualityTier): void {
    this.current.qualityTier = tier;
    this.current.solverSettings = { ...TIER_SOLVER_PRESETS[tier] };
  }

  public getSummary(): ComputeSelectionSummary {
    return this.current;
  }
}
