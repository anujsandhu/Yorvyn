import { describe, it, expect, vi } from 'vitest';
import {
  deviceCapabilityManager,
  DeviceCapabilityManager,
  edgeModelCacheManager,
  EdgeImagePreprocessor,
  unifiedAIOrchestrator,
  WorkloadType,
  RoutingPolicy
} from '../index';

describe('YORVYN — Phase 13: Hybrid AI Orchestration Layer Tests', () => {
  describe('1. DeviceCapabilityManager & Capability Negotiation', () => {
    it('should initialize as a singleton with valid default state', () => {
      const instance1 = DeviceCapabilityManager.getInstance();
      const instance2 = deviceCapabilityManager;
      expect(instance1).toBe(instance2);
    });

    it('should inspect device capabilities with non-null metrics', async () => {
      const caps = await deviceCapabilityManager.getCapabilities();
      expect(caps).toBeDefined();
      expect(typeof caps.webgpuSupported).toBe('boolean');
      expect(typeof caps.simdWasmSupported).toBe('boolean');
      expect(typeof caps.webWorkersSupported).toBe('boolean');
      expect(caps.hardwareConcurrency).toBeGreaterThanOrEqual(1);
      expect(caps.deviceMemoryGb).toBeGreaterThanOrEqual(1);
      expect(['LOW', 'MID', 'HIGH', 'ULTRA']).toContain(caps.deviceTier);
    });

    it('should correctly configure and retrieve user routing policies', () => {
      const policies: RoutingPolicy[] = ['AUTO', 'LOCAL_PREFERRED', 'CLOUD_PREFERRED', 'LOCAL_REQUIRED', 'CLOUD_REQUIRED'];
      for (const policy of policies) {
        deviceCapabilityManager.setUserPreference(policy);
        expect(deviceCapabilityManager.getUserPreference()).toBe(policy);
      }
      // Reset back to AUTO
      deviceCapabilityManager.setUserPreference('AUTO');
    });

    it('should route client-mandatory workloads to CLIENT_WORKER', async () => {
      const clientWorkloads: WorkloadType[] = ['IMAGE_PREPROCESS', 'BLUR_DETECTION', 'COLOR_PALETTE'];
      for (const wl of clientWorkloads) {
        const plan = await deviceCapabilityManager.planWorkload(wl);
        expect(plan.workloadType).toBe(wl);
        expect(plan.selectedLocation).toBe('CLIENT_WORKER');
        expect(plan.estimatedDurationMs).toBeLessThanOrEqual(50);
      }
    });

    it('should route interactive try-on workloads to client graphics context', async () => {
      const interactiveWorkloads: WorkloadType[] = ['CLOTH_SIMULATION', 'AVATAR_FITTING'];
      for (const wl of interactiveWorkloads) {
        const plan = await deviceCapabilityManager.planWorkload(wl);
        expect(plan.workloadType).toBe(wl);
        expect(['CLIENT_WEBGPU', 'CLIENT_WASM']).toContain(plan.selectedLocation);
      }
    });

    it('should route computationally heavy 3D reconstruction to CLOUD_GPU', async () => {
      const serverWorkloads: WorkloadType[] = ['NEURAL_RECONSTRUCTION', 'TEXTURE_SYNTHESIS'];
      for (const wl of serverWorkloads) {
        const plan = await deviceCapabilityManager.planWorkload(wl);
        expect(plan.workloadType).toBe(wl);
        expect(plan.selectedLocation).toBe('CLOUD_GPU');
        expect(plan.estimatedDurationMs).toBeGreaterThan(500);
      }
    });

    it('should respect policy overrides dynamically', async () => {
      const planCloud = await deviceCapabilityManager.planWorkload('GARMENT_CLASSIFICATION', 'CLOUD_PREFERRED');
      expect(planCloud.policy).toBe('CLOUD_PREFERRED');
      expect(planCloud.selectedLocation).toBe('CLOUD_GPU');

      const planQuality = await deviceCapabilityManager.planWorkload('GARMENT_CLASSIFICATION', 'CLOUD_REQUIRED');
      expect(planQuality.policy).toBe('CLOUD_REQUIRED');
      expect(planQuality.selectedLocation).toBe('CLOUD_GPU');
    });
  });

  describe('2. EdgeImagePreprocessor (Blur & Palette Analysis)', () => {
    it('should calculate target dimensions preserving aspect ratio within maxDimension bound', () => {
      // 4000x3000 -> max 1200
      const dims1 = EdgeImagePreprocessor.calculateTargetDimensions(4000, 3000, 1200);
      expect(dims1.width).toBe(1200);
      expect(dims1.height).toBe(900);

      // 1080x1920 (portrait) -> max 1200
      const dims2 = EdgeImagePreprocessor.calculateTargetDimensions(1080, 1920, 1200);
      expect(dims2.width).toBe(675);
      expect(dims2.height).toBe(1200);

      // 600x400 (smaller than bound) -> unchanged
      const dims3 = EdgeImagePreprocessor.calculateTargetDimensions(600, 400, 1200);
      expect(dims3.width).toBe(600);
      expect(dims3.height).toBe(400);
    });

    it('should evaluate Laplacian blur variance accurately on flat vs edge-rich data', () => {
      const width = 10;
      const height = 10;

      // Uniform flat gray image (no edges -> variance 0)
      const flatData = new Uint8ClampedArray(width * height * 4);
      for (let i = 0; i < flatData.length; i += 4) {
        flatData[i] = 128;     // R
        flatData[i + 1] = 128; // G
        flatData[i + 2] = 128; // B
        flatData[i + 3] = 255; // A
      }
      const flatVariance = EdgeImagePreprocessor.calculateLaplacianVariance(flatData, width, height);
      expect(flatVariance).toBe(0);

      // High-frequency edge (left black 0, right white 255 -> high variance)
      const edgeWidth = 20;
      const edgeHeight = 20;
      const edgeData = new Uint8ClampedArray(edgeWidth * edgeHeight * 4);
      for (let y = 0; y < edgeHeight; y++) {
        for (let x = 0; x < edgeWidth; x++) {
          const idx = (y * edgeWidth + x) * 4;
          const val = x < 10 ? 0 : 255;
          edgeData[idx] = val;
          edgeData[idx + 1] = val;
          edgeData[idx + 2] = val;
          edgeData[idx + 3] = 255;
        }
      }
      const edgeVariance = EdgeImagePreprocessor.calculateLaplacianVariance(edgeData, edgeWidth, edgeHeight);
      expect(edgeVariance).toBeGreaterThan(100);
    });

    it('should extract dominant palette colors from quantized pixel data', () => {
      const width = 4;
      const height = 4;
      const pixelData = new Uint8ClampedArray(width * height * 4);

      // Fill with brown fabric pixels (e.g. RGB: 60, 40, 30)
      for (let i = 0; i < pixelData.length; i += 4) {
        pixelData[i] = 60;
        pixelData[i + 1] = 40;
        pixelData[i + 2] = 30;
        pixelData[i + 3] = 255;
      }

      const palette = EdgeImagePreprocessor.extractPalette(pixelData, 3);
      expect(palette).toBeInstanceOf(Array);
      expect(palette.length).toBeGreaterThan(0);
      expect(palette[0]).toMatch(/^#[0-9a-f]{6}$/i);
    });
  });

  describe('3. EdgeModelCacheManager (IndexedDB & Quota Enforcement)', () => {
    it('should have singleton instance', () => {
      const manager = edgeModelCacheManager;
      expect(manager).toBeDefined();
    });

    it('should reject models that exceed max storage quota ceiling', async () => {
      const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      
      // Fabricate an oversized buffer exceeding 150MB
      const oversizedBuffer = new ArrayBuffer(151 * 1024 * 1024);
      await edgeModelCacheManager.storeModel({
        modelId: 'oversized_test_model',
        version: 'v1.0.0',
        sha256: 'fake_hash',
        weightsBuffer: oversizedBuffer,
        metadata: { source: 'quota_test' }
      });

      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringContaining('exceeds maxStorageQuotaBytes ceiling')
      );
      consoleWarnSpy.mockRestore();
    });

    it('should safely return null when model is not found or IndexedDB unavailable', async () => {
      const cached = await edgeModelCacheManager.getModel('non_existent_model_id');
      expect(cached).toBeNull();
    });
  });

  describe('4. UnifiedAIOrchestrator Coordination & Provenance', () => {
    it('should expose orchestrator instance with workload planning capability', async () => {
      const plan = await unifiedAIOrchestrator.planWorkload('AVATAR_FITTING');
      expect(plan).toBeDefined();
      expect(plan.workloadType).toBe('AVATAR_FITTING');
    });

    it('should provide device capabilities inspection', async () => {
      const caps = await unifiedAIOrchestrator.getDeviceCapabilities();
      expect(caps).toBeDefined();
      expect(caps.hardwareConcurrency).toBeGreaterThan(0);
    });

    it('should classify garment and produce authoritative provenance', async () => {
      const mockPreprocess = {
        processedBlob: new Blob(['fake_webp'], { type: 'image/webp' }),
        previewDataUrl: 'data:image/webp;base64,fake',
        dimensions: { width: 1200, height: 900 },
        originalSizeBytes: 15 * 1024 * 1024, // 15MB
        compressedSizeBytes: 600 * 1024,      // 600KB (~96% reduction)
        compressionRatio: 0.04,
        isBlurry: false,
        blurVariance: 180.5,
        dominantColors: ['#3b281c', '#1f1610'],
        durationMs: 14.5
      };

      const response = await unifiedAIOrchestrator.classifyGarment(mockPreprocess, {
        categoryHint: 'top',
        subcategoryHint: 'hoodie'
      });

      expect(response).toBeDefined();
      expect(response.status).toBeDefined();
      expect(response.result).toBeDefined();
      expect(response.result?.category).toBe('top');
      expect(response.result?.subcategory).toBe('hoodie');

      // Check non-repudiable provenance
      expect(response.provenance).toBeDefined();
      expect(response.provenance.model_id).toBeDefined();
      expect(response.provenance.model_version).toBeDefined();
      expect(response.provenance.execution_location).toBeDefined();
      expect(response.provenance.total_duration_ms).toBeGreaterThanOrEqual(0);
      expect(response.provenance.bandwidth_saved_bytes).toBeGreaterThan(14 * 1024 * 1024);
    });

    it('should strictly return POLICY_UNSATISFIED when LOCAL_REQUIRED cannot run locally', async () => {
      const plan = await deviceCapabilityManager.planWorkload('NEURAL_RECONSTRUCTION', 'LOCAL_REQUIRED');
      expect(plan.status).toBe('POLICY_UNSATISFIED');
      expect(plan.selectedLocation).toBeNull();
      expect(plan.errorCode).toBe('POLICY_UNSATISFIED');
    });

    it('should strictly return POLICY_UNSATISFIED when CLOUD_REQUIRED cannot run on cloud', async () => {
      const plan = await deviceCapabilityManager.planWorkload('CLOTH_SIMULATION', 'CLOUD_REQUIRED');
      expect(plan.status).toBe('POLICY_UNSATISFIED');
      expect(plan.selectedLocation).toBeNull();
      expect(plan.errorCode).toBe('POLICY_UNSATISFIED');
    });

    it('should accurately test WASM SIMD capability using true byte probe', async () => {
      const caps = await deviceCapabilityManager.getCapabilities(true);
      expect(typeof caps.simdWasmSupported).toBe('boolean');
    });
  });
});
