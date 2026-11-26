/**
 * YORVYN — Edge Model & Artifact Cache Manager (Phase 13)
 * Provides robust IndexedDB-backed caching for verified edge AI model checkpoints,
 * metadata, and temporary preprocessing artifacts.
 */

export interface CachedModelEntry {
  modelId: string;
  version: string;
  sha256: string;
  weightsBuffer: ArrayBuffer;
  metadata: Record<string, any>;
  cachedAt: number;
  lastUsedAt: number;
  sizeBytes: number;
}

export class EdgeModelCacheManager {
  private static instance: EdgeModelCacheManager;
  private readonly dbName = 'yorvyn_edge_ai_cache_v13';
  private readonly modelStoreName = 'models';
  private readonly artifactStoreName = 'temporary_artifacts';
  private readonly maxStorageQuotaBytes = 150 * 1024 * 1024; // 150MB safety ceiling
  private readonly ttlMs = 7 * 24 * 60 * 60 * 1000; // 7 days

  private dbPromise: Promise<IDBDatabase> | null = null;

  private constructor() {}

  public static getInstance(): EdgeModelCacheManager {
    if (!EdgeModelCacheManager.instance) {
      EdgeModelCacheManager.instance = new EdgeModelCacheManager();
    }
    return EdgeModelCacheManager.instance;
  }

  private getDB(): Promise<IDBDatabase> {
    if (this.dbPromise) return this.dbPromise;

    if (typeof indexedDB === 'undefined') {
      return Promise.reject(new Error('IndexedDB is not supported in this environment.'));
    }

    this.dbPromise = new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, 1);

      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(this.modelStoreName)) {
          const store = db.createObjectStore(this.modelStoreName, { keyPath: 'modelId' });
          store.createIndex('lastUsedAt', 'lastUsedAt', { unique: false });
        }
        if (!db.objectStoreNames.contains(this.artifactStoreName)) {
          db.createObjectStore(this.artifactStoreName, { keyPath: 'id' });
        }
      };

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });

    return this.dbPromise;
  }

  /**
   * Retrieves a cached model entry if present and not expired.
   */
  public async getModel(modelId: string, expectedVersion?: string): Promise<CachedModelEntry | null> {
    try {
      const db = await this.getDB();
      return new Promise((resolve) => {
        const tx = db.transaction(this.modelStoreName, 'readonly');
        const store = tx.objectStore(this.modelStoreName);
        const req = store.get(modelId);

        req.onsuccess = () => {
          const entry: CachedModelEntry | undefined = req.result;
          if (!entry) {
            resolve(null);
            return;
          }

          // Check version and TTL
          const now = Date.now();
          if (expectedVersion && entry.version !== expectedVersion) {
            resolve(null);
            return;
          }
          if (now - entry.cachedAt > this.ttlMs) {
            // Expired: delete asynchronously
            this.deleteModel(modelId).catch(() => {});
            resolve(null);
            return;
          }

          // Update last used timestamp in background
          this.touchModel(modelId).catch(() => {});
          resolve(entry);
        };

        req.onerror = () => resolve(null);
      });
    } catch {
      return null;
    }
  }

  /**
   * Stores verified model weights in IndexedDB.
   */
  public async storeModel(entry: Omit<CachedModelEntry, 'cachedAt' | 'lastUsedAt' | 'sizeBytes'>): Promise<void> {
    try {
      if (entry.weightsBuffer.byteLength > this.maxStorageQuotaBytes) {
        console.warn(`[EdgeModelCacheManager] Model ${entry.modelId} exceeds maxStorageQuotaBytes ceiling of ${this.maxStorageQuotaBytes}`);
        return;
      }
      const db = await this.getDB();
      const now = Date.now();
      const fullEntry: CachedModelEntry = {
        ...entry,
        cachedAt: now,
        lastUsedAt: now,
        sizeBytes: entry.weightsBuffer.byteLength
      };

      return new Promise((resolve, reject) => {
        const tx = db.transaction(this.modelStoreName, 'readwrite');
        const store = tx.objectStore(this.modelStoreName);
        const req = store.put(fullEntry);

        req.onsuccess = () => resolve();
        req.onerror = () => reject(req.error);
      });
    } catch (e) {
      console.warn('[EdgeModelCacheManager] Failed to cache model in IndexedDB:', e);
    }
  }

  public async deleteModel(modelId: string): Promise<void> {
    try {
      const db = await this.getDB();
      return new Promise((resolve, reject) => {
        const tx = db.transaction(this.modelStoreName, 'readwrite');
        const store = tx.objectStore(this.modelStoreName);
        const req = store.delete(modelId);
        req.onsuccess = () => resolve();
        req.onerror = () => reject(req.error);
      });
    } catch {
      // Ignore cleanup error
    }
  }

  private async touchModel(modelId: string): Promise<void> {
    try {
      const db = await this.getDB();
      const tx = db.transaction(this.modelStoreName, 'readwrite');
      const store = tx.objectStore(this.modelStoreName);
      const req = store.get(modelId);
      req.onsuccess = () => {
        if (req.result) {
          req.result.lastUsedAt = Date.now();
          store.put(req.result);
        }
      };
    } catch {
      // Ignore touch error
    }
  }

  /**
   * Explicit user-initiated cache purge for privacy and storage reclamation.
   */
  public async purgeAllCache(): Promise<void> {
    try {
      const db = await this.getDB();
      return new Promise((resolve, reject) => {
        const tx = db.transaction([this.modelStoreName, this.artifactStoreName], 'readwrite');
        tx.objectStore(this.modelStoreName).clear();
        tx.objectStore(this.artifactStoreName).clear();
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
      });
    } catch {
      // Ignore purge error
    }
  }
}

export const edgeModelCacheManager = EdgeModelCacheManager.getInstance();
