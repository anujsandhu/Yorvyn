import { describe, it, expect, beforeEach, vi } from 'vitest';
import * as THREE from 'three';
import { studio3DAssetManager } from '../Studio3DAssetManager';
import { fashionApi, getApiCacheStats, invalidateApiCache } from '../../../services/fashionApi';

describe('Phase 17.6 Multi-Layer Frontend, 3D Asset & SW Caching', () => {
  beforeEach(() => {
    studio3DAssetManager.clearAllCaches();
    invalidateApiCache();
  });

  it('tracks fashionApi hit/miss telemetry and deduplicates reads', async () => {
    const before = getApiCacheStats();
    const healthSpy = vi.spyOn(fashionApi, 'getKnowledge').mockResolvedValue({ status: 'ok' } as any);
    await fashionApi.getKnowledge();
    await fashionApi.getKnowledge();
    healthSpy.mockRestore();
    expect(before).toHaveProperty('hitRatio');
  });

  it('tracks 3D GLB cache hits/misses and selectively clears private /api/ assets on logout', async () => {
    const fakeScene = new THREE.Group();
    const loadSpy = vi.spyOn((studio3DAssetManager as any).gltfLoader, 'load').mockImplementation((...args: any[]) => {
      args[1]({ scene: fakeScene, scenes: [fakeScene], animations: [], cameras: [], asset: {} });
    });

    // Load 1 public + 1 private GLB, then repeat private load for cache hit
    await studio3DAssetManager.loadGLB('/ara-assets/mannequin.glb', 'normal').promise;
    await studio3DAssetManager.loadGLB('/api/fashion/garment-gen/assets/job_1/garment.glb', 'high').promise;
    await studio3DAssetManager.loadGLB('/api/fashion/garment-gen/assets/job_1/garment.glb', 'high').promise;

    const statsBeforeClear = studio3DAssetManager.getCacheStats();
    expect(statsBeforeClear.gltfEntries).toBe(2);
    expect(statsBeforeClear.hits).toBeGreaterThanOrEqual(1);

    const removed = studio3DAssetManager.clearPrivateAssets();
    expect(removed).toBe(1);
    const statsAfterClear = studio3DAssetManager.getCacheStats();
    expect(statsAfterClear.gltfEntries).toBe(1); // public mannequin preserved

    loadSpy.mockRestore();
  });

  it('enforces network-only bypass for /api/, /auth/, and Authorization requests in sw.js', async () => {
    const fsMod: any = await import(/* @vite-ignore */ ('node:fs' as string));
    const pathMod: any = await import(/* @vite-ignore */ ('node:path' as string));
    const proc: any = (globalThis as any).process;
    const swPath = pathMod.resolve(proc.cwd(), 'public/sw.js');
    const swSrc = fsMod.readFileSync(swPath, 'utf8');

    expect(swSrc).toContain("'/api/'");
    expect(swSrc).toContain("'/auth/'");
    expect(swSrc).toContain("request.headers.has('Authorization')");
    expect(swSrc).toContain('yorvyn-static-v4');
    expect(swSrc).toContain('yorvyn-swr-v4');
  });
});
