/**
 * Yorvyn Technology — Studio 3D Asset Loading & Memory Manager
 *
 * Implements centralized, priority-based GLTF/GLB and texture lifecycle management:
 * - Priority Queues: Active Avatar (CRITICAL) -> Worn Outfit (HIGH) -> Visible Preview (NORMAL) -> Idle Prefetch (LOW)
 * - Single shared GLTFLoader & TextureLoader instances
 * - In-flight network request deduplication
 * - Memory-conscious LRU GLTF scene template cache
 * - Request cancellation & race-condition prevention via AbortController tokens
 * - Deep GPU resource disposal (Geometries, Materials, Textures, RenderTargets)
 */

import * as THREE from 'three';
import { GLTF, GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { supabase } from '../../utils/supabase';

export type AssetPriority = 'critical' | 'high' | 'normal' | 'low';

const PRIORITY_SCORES: Record<AssetPriority, number> = {
  critical: 4,
  high: 3,
  normal: 2,
  low: 1
};

interface QueuedTask<T> {
  id: string;
  url: string;
  priority: AssetPriority;
  execute: () => Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: any) => void;
  aborted: boolean;
}

export class Studio3DAssetManager {
  private static instance: Studio3DAssetManager;

  private gltfLoader: GLTFLoader;
  private textureLoader: THREE.TextureLoader;
  private inFlightGLTFs = new Map<string, Promise<GLTF>>();
  private inFlightTextures = new Map<string, Promise<THREE.Texture>>();
  private gltfCache = new Map<string, { gltf: GLTF; timestamp: number }>();
  private textureCache = new Map<string, { texture: THREE.Texture; timestamp: number }>();

  private taskQueue: QueuedTask<any>[] = [];
  private activeConcurrency = 0;
  private maxConcurrency = 3;
  private maxCachedGLTFs = 12;
  private maxCachedTextures = 30;

  private constructor() {
    const loadingManager = new THREE.LoadingManager();
    this.gltfLoader = new GLTFLoader(loadingManager);
    this.textureLoader = new THREE.TextureLoader(loadingManager);
  }

  public static getInstance(): Studio3DAssetManager {
    if (!Studio3DAssetManager.instance) {
      Studio3DAssetManager.instance = new Studio3DAssetManager();
    }
    return Studio3DAssetManager.instance;
  }

  /**
   * Enqueue or directly execute an asset task based on priority and concurrency limits
   */
  private scheduleTask<T>(
    id: string,
    url: string,
    priority: AssetPriority,
    execute: () => Promise<T>
  ): { promise: Promise<T>; abort: () => void } {
    let taskRef: QueuedTask<T>;

    const promise = new Promise<T>((resolve, reject) => {
      taskRef = {
        id,
        url,
        priority,
        execute,
        resolve,
        reject,
        aborted: false
      };

      // Insert task in priority order
      const insertIdx = this.taskQueue.findIndex(
        t => PRIORITY_SCORES[t.priority] < PRIORITY_SCORES[priority]
      );
      if (insertIdx === -1) {
        this.taskQueue.push(taskRef);
      } else {
        this.taskQueue.splice(insertIdx, 0, taskRef);
      }

      this.pumpQueue();
    });

    const abort = () => {
      if (taskRef) {
        taskRef.aborted = true;
        const qIdx = this.taskQueue.indexOf(taskRef);
        if (qIdx !== -1) {
          this.taskQueue.splice(qIdx, 1);
        }
        taskRef.reject(new Error(`[Studio3DAssetManager] Task ${id} aborted`));
      }
    };

    return { promise, abort };
  }

  private async pumpQueue(): Promise<void> {
    if (this.activeConcurrency >= this.maxConcurrency || this.taskQueue.length === 0) {
      return;
    }

    const task = this.taskQueue.shift();
    if (!task) return;

    if (task.aborted) {
      this.pumpQueue();
      return;
    }

    this.activeConcurrency++;
    try {
      const result = await task.execute();
      if (!task.aborted) {
        task.resolve(result);
      }
    } catch (err) {
      if (!task.aborted) {
        task.reject(err);
      }
    } finally {
      this.activeConcurrency--;
      this.pumpQueue();
    }
  }

  /**
   * Parse in-memory ArrayBuffer (e.g. from Ara character export) using the shared GLTFLoader
   */
  public async parseGLB(buffer: ArrayBuffer, path = ''): Promise<GLTF> {
    return this.gltfLoader.parseAsync(buffer, path);
  }

  /**
   * Load GLTF/GLB with priority, caching, deduplication, and cancellation
   */
  public loadGLB(
    url: string,
    priority: AssetPriority = 'normal',
    signal?: AbortSignal
  ): { promise: Promise<GLTF>; abort: () => void } {
    // 1. Check in-memory cache
    const cached = this.gltfCache.get(url);
    if (cached) {
      cached.timestamp = Date.now();
      // Return cloneable replica so multiple callers don't mutate the same scene graph
      const clonedScene = cached.gltf.scene.clone(true);
      return {
        promise: Promise.resolve({
          ...cached.gltf,
          scene: clonedScene
        }),
        abort: () => {}
      };
    }

    // 2. Check in-flight duplicate requests
    const inFlight = this.inFlightGLTFs.get(url);
    if (inFlight) {
      return {
        promise: inFlight.then(gltf => ({
          ...gltf,
          scene: gltf.scene.clone(true)
        })),
        abort: () => {}
      };
    }

    // 3. Schedule task through priority queue
    const taskId = `glb:${url}:${Date.now()}`;
    const loader = this.gltfLoader;

    const execute = () => {
      const loadPromise = new Promise<GLTF>(async (resolve, reject) => {
        try {
          const isInternalApiUrl = url.startsWith('/api/') || url.includes('/api/fashion/garment-gen/assets/');
          if (isInternalApiUrl) {
            try {
              const {
                data: { session },
              } = await supabase.auth.getSession();
              if (session?.access_token) {
                loader.setRequestHeader({ Authorization: `Bearer ${session.access_token}` });
              } else {
                loader.setRequestHeader({});
              }
            } catch {
              loader.setRequestHeader({});
            }
          } else {
            loader.setRequestHeader({});
          }

          loader.load(
            url,
            (gltf) => {
              // Keep pristine master copy in cache; return independent clone to caller
              this.gltfCache.set(url, { gltf, timestamp: Date.now() });
              this.evictCacheIfNeeded();
              resolve({
                ...gltf,
                scene: gltf.scene.clone(true)
              });
            },
            undefined,
            (err) => {
              const msg = err instanceof Error ? err.message : String(err || 'Failed to load GLB asset');
              reject(new Error(`GLB load failed for ${url}: ${msg}`));
            }
          );
        } catch (err) {
          reject(err);
        }
      });

      this.inFlightGLTFs.set(url, loadPromise);
      loadPromise.finally(() => {
        this.inFlightGLTFs.delete(url);
      });

      return loadPromise;
    };

    const scheduled = this.scheduleTask(taskId, url, priority, execute);

    if (signal) {
      signal.addEventListener('abort', () => scheduled.abort(), { once: true });
    }

    return scheduled;
  }

  /**
   * Load Texture with caching and deduplication
   */
  public loadTexture(url: string, isSRGB = true): Promise<THREE.Texture> {
    const cached = this.textureCache.get(url);
    if (cached) {
      cached.timestamp = Date.now();
      return Promise.resolve(cached.texture);
    }

    const inFlight = this.inFlightTextures.get(url);
    if (inFlight) {
      return inFlight;
    }

    const loadPromise = new Promise<THREE.Texture>((resolve, reject) => {
      this.textureLoader.load(
        url,
        (tex) => {
          tex.colorSpace = isSRGB ? THREE.SRGBColorSpace : THREE.NoColorSpace;
          tex.flipY = false;
          tex.needsUpdate = true;
          this.textureCache.set(url, { texture: tex, timestamp: Date.now() });
          this.evictTextureCacheIfNeeded();
          resolve(tex);
        },
        undefined,
        (err) => reject(err)
      );
    });

    this.inFlightTextures.set(url, loadPromise);
    loadPromise.finally(() => {
      this.inFlightTextures.delete(url);
    });

    return loadPromise;
  }

  /**
   * Deep recursive GPU resource disposal
   */
  public disposeObject3D(root: THREE.Object3D | null | undefined, forceDisposeCustomGarments = false): void {
    if (!root) return;

    root.traverse((child) => {
      // Strictly protect custom AI fitted garments from accidental disposal during avatar rebuilds
      if (
        !forceDisposeCustomGarments &&
        (child.name === 'custom_ai_garment' ||
          child.name === 'custom_ai_garment_fitted' ||
          child.userData?.isCustomAiGarment)
      ) {
        return;
      }

      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        if (mesh.geometry) {
          mesh.geometry.dispose();
        }
        if (Array.isArray(mesh.material)) {
          mesh.material.forEach((mat) => this.disposeMaterial(mat));
        } else if (mesh.material) {
          this.disposeMaterial(mesh.material);
        }
      }
    });

    if (root.parent) {
      root.parent.remove(root);
    }
  }

  public disposeMaterial(material: THREE.Material): void {
    if (!material) return;
    material.dispose();

    const mat = material as any;
    const textureProperties = ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'aoMap', 'bumpMap', 'displacementMap', 'emissiveMap', 'alphaMap'];
    for (const prop of textureProperties) {
      if (mat[prop] && mat[prop].isTexture) {
        // If it's a blob url or procedural texture, dispose of it
        const tex = mat[prop] as THREE.Texture;
        const imgSrc = (tex.image as any)?.src;
        if (typeof imgSrc === 'string' && imgSrc.startsWith('blob:')) {
          tex.dispose();
        }
      }
    }
  }

  private evictCacheIfNeeded(): void {
    if (this.gltfCache.size <= this.maxCachedGLTFs) return;
    // Evict oldest
    let oldestKey: string | null = null;
    let oldestTime = Infinity;
    for (const [key, val] of this.gltfCache.entries()) {
      if (val.timestamp < oldestTime) {
        oldestTime = val.timestamp;
        oldestKey = key;
      }
    }
    if (oldestKey) {
      const entry = this.gltfCache.get(oldestKey);
      if (entry) {
        this.disposeObject3D(entry.gltf.scene);
      }
      this.gltfCache.delete(oldestKey);
    }
  }

  private evictTextureCacheIfNeeded(): void {
    if (this.textureCache.size <= this.maxCachedTextures) return;
    let oldestKey: string | null = null;
    let oldestTime = Infinity;
    for (const [key, val] of this.textureCache.entries()) {
      if (val.timestamp < oldestTime) {
        oldestTime = val.timestamp;
        oldestKey = key;
      }
    }
    if (oldestKey) {
      const entry = this.textureCache.get(oldestKey);
      entry?.texture.dispose();
      this.textureCache.delete(oldestKey);
    }
  }

  public clearAllCaches(): void {
    for (const [, val] of this.gltfCache) {
      this.disposeObject3D(val.gltf.scene);
    }
    this.gltfCache.clear();

    for (const [, val] of this.textureCache) {
      val.texture.dispose();
    }
    this.textureCache.clear();

    this.inFlightGLTFs.clear();
    this.inFlightTextures.clear();
    this.taskQueue.length = 0;
  }
}

export const studio3DAssetManager = Studio3DAssetManager.getInstance();
