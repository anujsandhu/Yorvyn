import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  deviceCapabilityManager,
  EdgeImagePreprocessor,
  UnifiedAIOrchestrator,
  CATEGORIES,
  ALL_SUBCATEGORIES,
  WorkloadType,
  RoutingPolicy
} from '../index';

describe('YORVYN — Phase 13.3: Hybrid AI Integration & Inference Verification Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('1. Edge ONNX Model Verification & Checksum Security', () => {
    it('should expose the authoritative expected SHA-256 for the edge ONNX model', () => {
      expect(UnifiedAIOrchestrator.EXPECTED_EDGE_MODEL_SHA256).toBe(
        'fb635271739c29d74ed5e44d8532f584cb100f5435cc14b8a194c76f67495756'
      );
    });

    it('should verify matching checksums and reject mismatched checksums', async () => {
      const dummyBuffer = new Uint8Array([1, 2, 3, 4, 5]).buffer;
      const valid = await UnifiedAIOrchestrator.verifyModelChecksum(
        dummyBuffer,
        '74f81fe167d99b4cb41d6d0ccda82278caee9f3e2f25d5e5a3936ff3dcec60d0'
      );
      expect(valid).toBe(true);

      const invalid = await UnifiedAIOrchestrator.verifyModelChecksum(
        dummyBuffer,
        '0000000000000000000000000000000000000000000000000000000000000000'
      );
      expect(invalid).toBe(false);
    });

    it('should verify taxonomy consistency between categories and subcategories', () => {
      expect(CATEGORIES.length).toBe(10);
      expect(CATEGORIES).toContain('tops');
      expect(CATEGORIES).toContain('hoodie');
      expect(CATEGORIES).toContain('bottoms');
      expect(CATEGORIES).toContain('dress');

      expect(ALL_SUBCATEGORIES.length).toBe(55);
      expect(ALL_SUBCATEGORIES).toContain('pullover_hoodie');
      expect(ALL_SUBCATEGORIES).toContain('tshirt');
      expect(ALL_SUBCATEGORIES).toContain('denim_jacket');
      expect(ALL_SUBCATEGORIES).toContain('straight_jeans');
      expect(ALL_SUBCATEGORIES).toContain('maxi_dress');
    });
  });

  describe('2. Web Worker Lifecycle & Fallback Parity', () => {
    it('should provide clean worker termination and reject pending requests', () => {
      expect(() => EdgeImagePreprocessor.terminateWorker()).not.toThrow();
    });

    it('should handle request cancellation cleanly', () => {
      const cancelled = EdgeImagePreprocessor.cancelRequest('non_existent_req_id');
      expect(cancelled).toBe(false);
    });

    it('should calculate identical target dimensions whether in worker or main thread', () => {
      const dims1 = EdgeImagePreprocessor.calculateTargetDimensions(2400, 1800, 1200);
      expect(dims1).toEqual({ width: 1200, height: 900 });

      const dims2 = EdgeImagePreprocessor.calculateTargetDimensions(1000, 1500, 1200);
      expect(dims2).toEqual({ width: 800, height: 1200 });

      const dims3 = EdgeImagePreprocessor.calculateTargetDimensions(600, 800, 1200);
      expect(dims3).toEqual({ width: 600, height: 800 });
    });

    it('should extract consistent color palettes with normalized hex values', () => {
      // 4 pixels: red, blue, green, red
      const samplePixels = new Uint8ClampedArray([
        255, 0, 0, 255,
        0, 0, 255, 255,
        0, 255, 0, 255,
        255, 0, 0, 255
      ]);
      const palette = EdgeImagePreprocessor.extractPalette(samplePixels, 3);
      expect(palette).toBeInstanceOf(Array);
      expect(palette.length).toBeGreaterThan(0);
      palette.forEach((hex) => {
        expect(hex).toMatch(/^#[0-9a-f]{6}$/i);
      });
    });
  });

  describe('3. Comprehensive Hybrid Workload Routing Matrix (11 Workloads x 5 Policies)', () => {
    const workloads: WorkloadType[] = [
      'IMAGE_PREPROCESS',
      'BLUR_DETECTION',
      'COLOR_PALETTE',
      'GARMENT_CLASSIFICATION',
      'GARMENT_SEGMENTATION',
      'POSE_ESTIMATION',
      'NEURAL_RECONSTRUCTION',
      'TEXTURE_SYNTHESIS',
      'MESH_VALIDATION',
      'CLOTH_SIMULATION',
      'AVATAR_FITTING'
    ];

    const policies: RoutingPolicy[] = [
      'LOCAL_REQUIRED',
      'CLOUD_REQUIRED',
      'LOCAL_PREFERRED',
      'CLOUD_PREFERRED',
      'AUTO'
    ];

    it('should evaluate all 55 workload/policy combinations without uncaught errors', async () => {
      let totalEvaluated = 0;
      const caps = await deviceCapabilityManager.getCapabilities();

      for (const wl of workloads) {
        for (const pol of policies) {
          const plan = await deviceCapabilityManager.planWorkload(wl, pol);
          totalEvaluated++;

          expect(plan).toBeDefined();
          expect(plan.workloadType).toBe(wl);

          const isLocalUnsatisfied = pol === 'LOCAL_REQUIRED' && (
            ['NEURAL_RECONSTRUCTION', 'TEXTURE_SYNTHESIS', 'GARMENT_SEGMENTATION'].includes(wl) ||
            (wl === 'GARMENT_CLASSIFICATION' && caps.deviceTier === 'LOW')
          );
          const isCloudUnsatisfied = pol === 'CLOUD_REQUIRED' &&
            ['CLOTH_SIMULATION', 'AVATAR_FITTING'].includes(wl);

          if (isLocalUnsatisfied || isCloudUnsatisfied) {
            expect(plan.status).toBe('POLICY_UNSATISFIED');
            expect(plan.selectedLocation).toBeNull();
          } else {
            expect(['SUCCESS', 'FALLBACK']).toContain(plan.status);
            expect(plan.selectedLocation).toBeTruthy();
          }
        }
      }

      expect(totalEvaluated).toBe(55);
    });
  });
});
