/**
 * YORVYN — Device & Workload Capability Manager (Phase 13)
 * Probes client hardware, GPU compute, memory tiers, and network constraints
 * to dynamically select between edge execution and remote GPU cloud routing.
 */

import { DeviceCapabilities, DeviceTier, RoutingPolicy, WorkloadType, HybridWorkloadPlan, ExecutionLocation } from '../../types/hybridAIContracts';

export class DeviceCapabilityManager {
  private static instance: DeviceCapabilityManager;
  private cachedCapabilities: DeviceCapabilities | null = null;
  private userPreference: RoutingPolicy = 'AUTO';

  private constructor() {
    this.loadUserPreference();
  }

  public static getInstance(): DeviceCapabilityManager {
    if (!DeviceCapabilityManager.instance) {
      DeviceCapabilityManager.instance = new DeviceCapabilityManager();
    }
    return DeviceCapabilityManager.instance;
  }

  private loadUserPreference(): void {
    if (typeof window !== 'undefined' && window.localStorage) {
      const saved = localStorage.getItem('yorvyn_ai_routing_preference');
      if (saved && ['AUTO', 'LOCAL_PREFERRED', 'CLOUD_PREFERRED', 'LOCAL_REQUIRED', 'CLOUD_REQUIRED'].includes(saved)) {
        this.userPreference = saved as RoutingPolicy;
      }
    }
  }

  public setUserPreference(pref: RoutingPolicy): void {
    this.userPreference = pref;
    if (typeof window !== 'undefined' && window.localStorage) {
      localStorage.setItem('yorvyn_ai_routing_preference', pref);
    }
    if (this.cachedCapabilities) {
      this.cachedCapabilities.userProcessingPreference = pref;
    }
  }

  public getUserPreference(): RoutingPolicy {
    return this.userPreference;
  }

  /**
   * Evaluates comprehensive hardware, graphics, memory, and network capabilities.
   */
  public async getCapabilities(forceRefresh = false): Promise<DeviceCapabilities> {
    if (this.cachedCapabilities && !forceRefresh) {
      return this.cachedCapabilities;
    }

    const hasNav = typeof navigator !== 'undefined';
    const hasWin = typeof window !== 'undefined';

    // 1. WebGPU Support Probe
    let webgpuSupported = false;
    if (hasNav && 'gpu' in navigator && (navigator as any).gpu) {
      try {
        const adapter = await (navigator as any).gpu.requestAdapter();
        webgpuSupported = Boolean(adapter);
      } catch {
        webgpuSupported = false;
      }
    }

    // 2. WebGL Support Probe & Max Texture Size
    let webglSupported = false;
    let maxTextureSize = 4096;
    if (hasWin) {
      try {
        const canvas = document.createElement('canvas');
        const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
        if (gl) {
          webglSupported = true;
          maxTextureSize = gl.getParameter(gl.MAX_TEXTURE_SIZE) || 4096;
        }
      } catch {
        webglSupported = false;
      }
    }

    // 3. WASM SIMD Support Probe (True byte probe testing v128 instruction)
    let simdWasmSupported = false;
    try {
      if (typeof WebAssembly === 'object' && typeof WebAssembly.validate === 'function') {
        const simdProbeBytes = new Uint8Array([
          0x00, 0x61, 0x73, 0x6d, 0x01, 0x00, 0x00, 0x00,
          0x01, 0x05, 0x01, 0x60, 0x00, 0x01, 0x7b,
          0x03, 0x02, 0x01, 0x00,
          0x0a, 0x16, 0x01, 0x14, 0x00,
          0xfd, 0x0c, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
          0x0b
        ]);
        simdWasmSupported = WebAssembly.validate(simdProbeBytes);
      }
    } catch {
      simdWasmSupported = false;
    }

    // 4. Web Workers Support
    const webWorkersSupported = hasWin && typeof Worker !== 'undefined';

    // 5. Hardware Concurrency (CPU Cores)
    const hardwareConcurrency = (hasNav && navigator.hardwareConcurrency) || 4;

    // 6. Device Memory (RAM Tier in GB, Chromium spec)
    const deviceMemoryGb = (hasNav && (navigator as any).deviceMemory) || 4;

    // 7. Network Quality
    const connection = hasNav && (navigator as any).connection;
    const networkEffectiveType = connection?.effectiveType || '4g';
    const networkSaveData = Boolean(connection?.saveData);
    const downlinkSpeedMbps = connection?.downlink || 10;
    const roundTripTimeMs = connection?.rtt || 50;

    // 8. Battery Status
    let batteryLevel: number | undefined;
    let batteryCharging: boolean | undefined;
    if (hasNav && 'getBattery' in navigator) {
      try {
        const battery: any = await (navigator as any).getBattery();
        batteryLevel = battery.level;
        batteryCharging = battery.charging;
      } catch {
        // Battery API blocked or unavailable
      }
    }

    // 9. Compute Overall Device Tier
    const deviceTier = this.calculateDeviceTier({
      webgpuSupported,
      webglSupported,
      hardwareConcurrency,
      deviceMemoryGb,
      maxTextureSize
    });

    const capabilities: DeviceCapabilities = {
      webgpuSupported,
      webglSupported,
      simdWasmSupported,
      webWorkersSupported,
      hardwareConcurrency,
      deviceMemoryGb,
      maxTextureSize,
      deviceTier,
      networkEffectiveType,
      networkSaveData,
      downlinkSpeedMbps,
      roundTripTimeMs,
      batteryLevel,
      batteryCharging,
      userProcessingPreference: this.userPreference
    };

    this.cachedCapabilities = capabilities;
    return capabilities;
  }

  private calculateDeviceTier(metrics: {
    webgpuSupported: boolean;
    webglSupported: boolean;
    hardwareConcurrency: number;
    deviceMemoryGb: number;
    maxTextureSize: number;
  }): DeviceTier {
    if (metrics.webgpuSupported && metrics.deviceMemoryGb >= 8 && metrics.hardwareConcurrency >= 8) {
      return 'ULTRA';
    }
    if (metrics.webglSupported && metrics.deviceMemoryGb >= 4 && metrics.hardwareConcurrency >= 4) {
      return 'HIGH';
    }
    if (metrics.webglSupported && metrics.deviceMemoryGb >= 2 && metrics.hardwareConcurrency >= 2) {
      return 'MID';
    }
    return 'LOW';
  }

  /**
   * Plans the optimal execution location for a given fashion workload.
   * Strictly enforces LOCAL_REQUIRED, CLOUD_REQUIRED, and AUTO policies with zero silent violations.
   */
  public async planWorkload(workloadType: WorkloadType, overridePolicy?: RoutingPolicy): Promise<HybridWorkloadPlan> {
    const caps = await this.getCapabilities();
    const policy = overridePolicy || this.userPreference;
    const tier = caps.deviceTier;
    const hasWebgpu = caps.webgpuSupported;

    // 1. STRICT POLICY: LOCAL_REQUIRED
    if (policy === 'LOCAL_REQUIRED') {
      if (['NEURAL_RECONSTRUCTION', 'TEXTURE_SYNTHESIS'].includes(workloadType)) {
        return {
          workloadType,
          status: 'POLICY_UNSATISFIED',
          selectedLocation: null,
          policy,
          reason: `Workload '${workloadType}' requires remote GPU tensor infrastructure and cannot execute locally under LOCAL_REQUIRED.`,
          estimatedDurationMs: 0,
          estimatedMemoryMb: 0,
          fallbackLocation: null,
          errorCode: 'POLICY_UNSATISFIED'
        };
      }
      if (workloadType === 'GARMENT_SEGMENTATION') {
        return {
          workloadType,
          status: 'POLICY_UNSATISFIED',
          selectedLocation: null,
          policy,
          reason: 'Garment segmentation requires server-side deep matting; client local execution is unsupported under LOCAL_REQUIRED.',
          estimatedDurationMs: 0,
          estimatedMemoryMb: 0,
          fallbackLocation: null,
          errorCode: 'POLICY_UNSATISFIED'
        };
      }
      if (workloadType === 'GARMENT_CLASSIFICATION' && tier === 'LOW') {
        return {
          workloadType,
          status: 'POLICY_UNSATISFIED',
          selectedLocation: null,
          policy,
          reason: 'LOW tier device has insufficient compute/memory to run garment classification locally under LOCAL_REQUIRED.',
          estimatedDurationMs: 0,
          estimatedMemoryMb: 0,
          fallbackLocation: null,
          errorCode: 'POLICY_UNSATISFIED'
        };
      }
      if (['IMAGE_PREPROCESS', 'BLUR_DETECTION', 'COLOR_PALETTE'].includes(workloadType)) {
        return {
          workloadType,
          status: 'SUCCESS',
          selectedLocation: 'CLIENT_WORKER',
          policy,
          reason: 'Client worker preprocessing satisfies LOCAL_REQUIRED.',
          estimatedDurationMs: 18,
          estimatedMemoryMb: 15,
          fallbackLocation: 'CLIENT_WORKER'
        };
      }
      if (['CLOTH_SIMULATION', 'AVATAR_FITTING'].includes(workloadType)) {
        const loc: ExecutionLocation = hasWebgpu ? 'CLIENT_WEBGPU' : 'CLIENT_WASM';
        return {
          workloadType,
          status: 'SUCCESS',
          selectedLocation: loc,
          policy,
          reason: `Interactive avatar fitting on ${loc} satisfies LOCAL_REQUIRED.`,
          estimatedDurationMs: 16.6,
          estimatedMemoryMb: 30,
          fallbackLocation: 'CLIENT_WASM'
        };
      }
      if (workloadType === 'POSE_ESTIMATION') {
        return {
          workloadType,
          status: 'SUCCESS',
          selectedLocation: 'CLIENT_WASM',
          policy,
          reason: 'Local MediaPipe Tasks Vision satisfies LOCAL_REQUIRED.',
          estimatedDurationMs: 15,
          estimatedMemoryMb: 20,
          fallbackLocation: 'CLIENT_WASM'
        };
      }
      if (workloadType === 'GARMENT_CLASSIFICATION') {
        const loc: ExecutionLocation = hasWebgpu ? 'CLIENT_WEBGPU' : 'CLIENT_WASM';
        return {
          workloadType,
          status: 'SUCCESS',
          selectedLocation: loc,
          policy,
          reason: `Edge inference on ${tier} tier device (${loc}) satisfies LOCAL_REQUIRED.`,
          estimatedDurationMs: hasWebgpu ? 35 : 75,
          estimatedMemoryMb: 35,
          fallbackLocation: 'CLIENT_WASM'
        };
      }
      if (workloadType === 'MESH_VALIDATION') {
        return {
          workloadType,
          status: 'SUCCESS',
          selectedLocation: 'CLIENT_WASM',
          policy,
          reason: 'Client-side BVH culling satisfies LOCAL_REQUIRED.',
          estimatedDurationMs: 30,
          estimatedMemoryMb: 20,
          fallbackLocation: 'CLIENT_WASM'
        };
      }
    }

    // 2. STRICT POLICY: CLOUD_REQUIRED
    if (policy === 'CLOUD_REQUIRED') {
      if (['CLOTH_SIMULATION', 'AVATAR_FITTING'].includes(workloadType)) {
        return {
          workloadType,
          status: 'POLICY_UNSATISFIED',
          selectedLocation: null,
          policy,
          reason: 'Interactive 60fps avatar simulation requires local vertex shader and cannot execute on cloud under CLOUD_REQUIRED.',
          estimatedDurationMs: 0,
          estimatedMemoryMb: 0,
          fallbackLocation: null,
          errorCode: 'POLICY_UNSATISFIED'
        };
      }
      if (['IMAGE_PREPROCESS', 'BLUR_DETECTION', 'COLOR_PALETTE'].includes(workloadType)) {
        return {
          workloadType,
          status: 'SUCCESS',
          selectedLocation: 'CLOUD_CPU',
          policy,
          reason: 'Image conditioning offloaded to server CPU per CLOUD_REQUIRED.',
          estimatedDurationMs: 45,
          estimatedMemoryMb: 30,
          fallbackLocation: 'CLOUD_CPU'
        };
      }
      if (['NEURAL_RECONSTRUCTION', 'TEXTURE_SYNTHESIS', 'GARMENT_CLASSIFICATION', 'GARMENT_SEGMENTATION'].includes(workloadType)) {
        return {
          workloadType,
          status: 'SUCCESS',
          selectedLocation: 'CLOUD_GPU',
          policy,
          reason: `Server GPU execution satisfies CLOUD_REQUIRED for ${workloadType}.`,
          estimatedDurationMs: workloadType.includes('RECONSTRUCTION') ? 3200 : 50,
          estimatedMemoryMb: workloadType.includes('RECONSTRUCTION') ? 1200 : 60,
          fallbackLocation: 'CLOUD_CPU'
        };
      }
      if (['POSE_ESTIMATION', 'MESH_VALIDATION'].includes(workloadType)) {
        return {
          workloadType,
          status: 'SUCCESS',
          selectedLocation: 'CLOUD_CPU',
          policy,
          reason: `Cloud CPU execution satisfies CLOUD_REQUIRED for ${workloadType}.`,
          estimatedDurationMs: 60,
          estimatedMemoryMb: 45,
          fallbackLocation: 'CLOUD_CPU'
        };
      }
    }

    // 3. PREFERENCE POLICIES: LOCAL_PREFERRED & CLOUD_PREFERRED
    if (policy === 'LOCAL_PREFERRED') {
      if (['IMAGE_PREPROCESS', 'BLUR_DETECTION', 'COLOR_PALETTE'].includes(workloadType)) {
        return {
          workloadType,
          status: 'SUCCESS',
          selectedLocation: 'CLIENT_WORKER',
          policy,
          reason: 'Local execution preferred on client worker.',
          estimatedDurationMs: 18,
          estimatedMemoryMb: 15,
          fallbackLocation: 'CLOUD_CPU'
        };
      }
      if (['CLOTH_SIMULATION', 'AVATAR_FITTING'].includes(workloadType)) {
        const loc: ExecutionLocation = hasWebgpu ? 'CLIENT_WEBGPU' : 'CLIENT_WASM';
        return {
          workloadType,
          status: 'SUCCESS',
          selectedLocation: loc,
          policy,
          reason: `Interactive avatar fitting preferred locally on ${loc}.`,
          estimatedDurationMs: 16.6,
          estimatedMemoryMb: 30,
          fallbackLocation: 'CLIENT_WASM'
        };
      }
      if (workloadType === 'POSE_ESTIMATION') {
        return {
          workloadType,
          status: 'SUCCESS',
          selectedLocation: 'CLIENT_WASM',
          policy,
          reason: 'Local MediaPipe Tasks Vision preferred.',
          estimatedDurationMs: 15,
          estimatedMemoryMb: 20,
          fallbackLocation: 'CLOUD_CPU'
        };
      }
      if (workloadType === 'GARMENT_CLASSIFICATION' && tier !== 'LOW') {
        const loc: ExecutionLocation = hasWebgpu ? 'CLIENT_WEBGPU' : 'CLIENT_WASM';
        return {
          workloadType,
          status: 'SUCCESS',
          selectedLocation: loc,
          policy,
          reason: `Edge classification preferred on ${tier} tier device (${loc}).`,
          estimatedDurationMs: hasWebgpu ? 35 : 75,
          estimatedMemoryMb: 35,
          fallbackLocation: 'CLOUD_GPU'
        };
      }
      return {
        workloadType,
        status: 'SUCCESS',
        selectedLocation: ['NEURAL_RECONSTRUCTION', 'TEXTURE_SYNTHESIS', 'GARMENT_CLASSIFICATION', 'GARMENT_SEGMENTATION'].includes(workloadType) ? 'CLOUD_GPU' : 'CLOUD_CPU',
        policy,
        reason: `LOCAL_PREFERRED fell back to cloud for ${workloadType}.`,
        estimatedDurationMs: 3200,
        estimatedMemoryMb: 1200,
        fallbackLocation: 'CLOUD_CPU'
      };
    }

    if (policy === 'CLOUD_PREFERRED') {
      if (['CLOTH_SIMULATION', 'AVATAR_FITTING'].includes(workloadType)) {
        const loc: ExecutionLocation = hasWebgpu ? 'CLIENT_WEBGPU' : 'CLIENT_WASM';
        return {
          workloadType,
          status: 'SUCCESS',
          selectedLocation: loc,
          policy,
          reason: 'CLOUD_PREFERRED fell back to local client for interactive avatar simulation.',
          estimatedDurationMs: 16.6,
          estimatedMemoryMb: 30,
          fallbackLocation: 'CLIENT_WASM'
        };
      }
      return {
        workloadType,
        status: 'SUCCESS',
        selectedLocation: ['NEURAL_RECONSTRUCTION', 'TEXTURE_SYNTHESIS', 'GARMENT_CLASSIFICATION', 'GARMENT_SEGMENTATION'].includes(workloadType) ? 'CLOUD_GPU' : 'CLOUD_CPU',
        policy,
        reason: `Cloud execution preferred and selected for ${workloadType}.`,
        estimatedDurationMs: 3200,
        estimatedMemoryMb: 1200,
        fallbackLocation: 'CLOUD_CPU'
      };
    }

    // 4. DEFAULT: AUTO POLICY
    if (['IMAGE_PREPROCESS', 'BLUR_DETECTION', 'COLOR_PALETTE'].includes(workloadType)) {
      return {
        workloadType,
        status: 'SUCCESS',
        selectedLocation: 'CLIENT_WORKER',
        policy,
        reason: 'Instant client-side canvas/worker preprocessing preserves bandwidth and avoids UI jank.',
        estimatedDurationMs: 18,
        estimatedMemoryMb: 15,
        fallbackLocation: 'CLOUD_CPU'
      };
    }

    if (['CLOTH_SIMULATION', 'AVATAR_FITTING'].includes(workloadType)) {
      const loc: ExecutionLocation = hasWebgpu ? 'CLIENT_WEBGPU' : 'CLIENT_WASM';
      return {
        workloadType,
        status: 'SUCCESS',
        selectedLocation: loc,
        policy,
        reason: '60fps interactive cloth simulation on avatar mannequin requires direct local GPU vertex access.',
        estimatedDurationMs: 16.6,
        estimatedMemoryMb: 30,
        fallbackLocation: 'CLIENT_WASM'
      };
    }

    if (workloadType === 'GARMENT_CLASSIFICATION') {
      if (tier === 'LOW') {
        return {
          workloadType,
          status: 'SUCCESS',
          selectedLocation: 'CLOUD_GPU',
          policy,
          reason: 'Low-tier device routes classification to server PyTorch.',
          estimatedDurationMs: 45,
          estimatedMemoryMb: 50,
          fallbackLocation: 'CLOUD_CPU'
        };
      }
      const loc: ExecutionLocation = hasWebgpu ? 'CLIENT_WEBGPU' : 'CLIENT_WASM';
      return {
        workloadType,
        status: 'SUCCESS',
        selectedLocation: loc,
        policy,
        reason: `Edge inference via ONNX Runtime Web on ${tier} tier device saves server GPU cycles.`,
        estimatedDurationMs: hasWebgpu ? 35 : 75,
        estimatedMemoryMb: 35,
        fallbackLocation: 'CLOUD_GPU'
      };
    }

    if (workloadType === 'GARMENT_SEGMENTATION') {
      return {
        workloadType,
        status: 'SUCCESS',
        selectedLocation: 'CLOUD_GPU',
        policy,
        reason: 'High-resolution boundary matting routes to server GPU.',
        estimatedDurationMs: 80,
        estimatedMemoryMb: 180,
        fallbackLocation: 'CLOUD_CPU'
      };
    }

    if (workloadType === 'POSE_ESTIMATION') {
      return {
        workloadType,
        status: 'SUCCESS',
        selectedLocation: 'CLIENT_WASM',
        policy,
        reason: 'MediaPipe Tasks Vision processes landmarks locally at 15ms without sending live camera feeds over network.',
        estimatedDurationMs: 15,
        estimatedMemoryMb: 20,
        fallbackLocation: 'CLOUD_CPU'
      };
    }

    if (['NEURAL_RECONSTRUCTION', 'TEXTURE_SYNTHESIS'].includes(workloadType)) {
      return {
        workloadType,
        status: 'SUCCESS',
        selectedLocation: 'CLOUD_GPU',
        policy,
        reason: 'High-precision 3D neural photogrammetry and texture synthesis require remote GPU tensor infrastructure.',
        estimatedDurationMs: 3200,
        estimatedMemoryMb: 1200,
        fallbackLocation: 'CLOUD_CPU'
      };
    }

    if (workloadType === 'MESH_VALIDATION') {
      return {
        workloadType,
        status: 'SUCCESS',
        selectedLocation: 'HYBRID_COLLABORATIVE',
        policy,
        reason: 'Fast culling via three-mesh-bvh on client; authoritative manifold certification via Trimesh on server.',
        estimatedDurationMs: 120,
        estimatedMemoryMb: 45,
        fallbackLocation: 'CLOUD_CPU'
      };
    }

    return {
      workloadType,
      status: 'SUCCESS',
      selectedLocation: 'CLOUD_GPU',
      policy,
      reason: 'General fallback cloud path.',
      estimatedDurationMs: 300,
      estimatedMemoryMb: 150,
      fallbackLocation: 'CLOUD_CPU'
    };
  }
}

export const deviceCapabilityManager = DeviceCapabilityManager.getInstance();
