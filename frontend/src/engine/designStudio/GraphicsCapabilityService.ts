/**
 * Phase 16.3 Graphics Capability & Telemetry Service
 * Probes WebGL2, WebGPU (`navigator.gpu`), device memory/DPR tiers, and enforces safe fallbacks.
 */

export type RenderBackendKind = 'webgl2' | 'webgpu_experimental' | 'software_fallback';
export type DeviceCapabilityTier = 'high' | 'balanced' | 'constrained';

export interface GraphicsCapabilitiesReport {
  preferredBackend: RenderBackendKind;
  webgl2Supported: boolean;
  webgpuNavigatorPresent: boolean;
  webgpuAdapterAvailable: boolean;
  webgpuAdapterInfo?: string;
  threeWebgpuModuleBundled: boolean;
  maxTextureSize: number;
  devicePixelRatio: number;
  hardwareConcurrency: number;
  tier: DeviceCapabilityTier;
  fallbackReason?: string;
}

export async function detectGraphicsCapabilities(options?: {
  probeWebGPUAdapter?: boolean;
}): Promise<GraphicsCapabilitiesReport> {
  let webgl2Supported = false;
  let maxTextureSize = 2048;

  if (typeof document !== 'undefined') {
    try {
      const testCanvas = document.createElement('canvas');
      const gl2 = testCanvas.getContext('webgl2', { failIfMajorPerformanceCaveat: false });
      if (gl2) {
        webgl2Supported = true;
        maxTextureSize = Number(gl2.getParameter(gl2.MAX_TEXTURE_SIZE)) || 4096;
        const lose = gl2.getExtension('WEBGL_lose_context');
        lose?.loseContext();
      }
    } catch {
      webgl2Supported = false;
    }
  }

  const nav = typeof navigator !== 'undefined' ? (navigator as any) : undefined;
  const webgpuNavigatorPresent = Boolean(nav && 'gpu' in nav && nav.gpu);
  let webgpuAdapterAvailable = false;
  let webgpuAdapterInfo: string | undefined;

  if (webgpuNavigatorPresent && options?.probeWebGPUAdapter !== false) {
    try {
      const adapter = await nav.gpu.requestAdapter();
      if (adapter) {
        webgpuAdapterAvailable = true;
        const info = adapter.info || (await adapter.requestAdapterInfo?.());
        webgpuAdapterInfo = info
          ? `${info.vendor || 'gpu'}:${info.architecture || 'generic'}`
          : 'adapter_available';
      }
    } catch {
      webgpuAdapterAvailable = false;
    }
  }

  // Three.js 0.186.1 includes three.webgpu.js; WebGL2 remains production primary until
  // full WebGPU adapter & TSL shader parity passes across all client browsers.
  const dpr = typeof window !== 'undefined' ? Math.min(window.devicePixelRatio || 1, 2) : 1;
  const cores = Number(nav?.hardwareConcurrency) || 4;
  const tier: DeviceCapabilityTier =
    !webgl2Supported || cores <= 2
      ? 'constrained'
      : maxTextureSize >= 8192 && cores >= 8
      ? 'high'
      : 'balanced';

  return {
    preferredBackend: webgl2Supported ? 'webgl2' : 'software_fallback',
    webgl2Supported,
    webgpuNavigatorPresent,
    webgpuAdapterAvailable,
    webgpuAdapterInfo,
    threeWebgpuModuleBundled: true,
    maxTextureSize,
    devicePixelRatio: dpr,
    hardwareConcurrency: cores,
    tier,
    fallbackReason: webgpuAdapterAvailable
      ? 'WebGPU adapter detected; production path stays on WebGL2 for material & GLB compatibility.'
      : 'WebGPU adapter unavailable or gated; active production renderer is WebGL2.',
  };
}
