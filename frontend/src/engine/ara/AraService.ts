/**
 * Yorvyn Ara 3D Avatar Engine Service
 * Integrates Ara 3D Gen (MIT License / CC0 MakeHuman) character engine
 * for real-time 3D generation, morphing, and GLB export.
 */

import { AssetLibrary, fetchSource, Catalog } from './core/assets';
import { buildHuman, Character } from './core/human';
import { HumanParams } from './core/params';
import { exportGLB } from './export/glb';
import { clipById } from './core/anim/clips';
import { Animator, type BakedClip } from './core/anim/evaluate';
import { type Rig } from './core/rig/rig';

export function bakeCharacterClips(rig: Rig, face?: { names: string[]; defaults: number[] }): BakedClip[] {
  const animator = new Animator(rig, face);
  const clipSpecs = [
    { id: 'idle', name: 'Idle' },
    { id: 'wave', name: 'Wave' },
    { id: 'cheer', name: 'Cheer' },
    { id: 'turn_360', name: 'Turn' }
  ];

  const baked: BakedClip[] = [];
  for (const spec of clipSpecs) {
    const clip = clipById.get(spec.id);
    if (!clip) {
      console.warn(`[AraService] Clip "${spec.id}" not found in Ara 3D Gen catalog`);
      continue;
    }
    const bakedData = animator.bake(clip, 30, { rootMotion: false });
    baked.push({
      name: spec.name,
      loop: clip.loop,
      times: bakedData.times,
      frames: bakedData.frames
    });
  }
  return baked;
}

export interface AvatarStudioState {
  params: HumanParams;
  catalog: Catalog | null;
  loading: boolean;
  loadingProgress: { label: string; percent?: number };
  error: string | null;
  unsavedChanges: boolean;
}

export class AraEngineBridge {
  private lib: AssetLibrary | null = null;
  private currentCharacter: Character | null = null;
  private isBuilding = false;
  private pendingParams: HumanParams | null = null;

  // Uses local public/ara-assets/ with Vite reverse proxy fallback to prevent CORS errors
  private assetBaseUrl = '/ara-assets/';

  constructor() {
    this.lib = new AssetLibrary(fetchSource(this.assetBaseUrl));
  }

  async init(onProgress?: (label: string, percent?: number) => void): Promise<Catalog> {
    if (!this.lib) {
      this.lib = new AssetLibrary(fetchSource(this.assetBaseUrl));
    }

    if (onProgress) onProgress('Loading 3D Anatomy Catalog...', 20);
    try {
      await this.lib.init();
      if (onProgress) onProgress('3D Engine Ready', 100);
      return this.lib.catalog;
    } catch (err: any) {
      console.warn('Full pack prefetch error, initializing catalog fallback:', err);
      try {
        await this.lib.initCatalog();
        return this.lib.catalog;
      } catch (catErr: any) {
        throw new Error(`Failed to load avatar catalog: ${catErr.message || err.message}`);
      }
    }
  }

  getLibrary(): AssetLibrary | null {
    return this.lib;
  }

  getCatalog(): Catalog | null {
    return this.lib?.catalog || null;
  }

  async generateCharacter(
    params: HumanParams,
    onProgress?: (stage: string) => void
  ): Promise<Character> {
    if (!this.lib) throw new Error('Ara Engine not initialized');

    if (this.isBuilding) {
      this.pendingParams = params;
      return new Promise((resolve, reject) => {
        const interval = setInterval(() => {
          if (!this.isBuilding) {
            clearInterval(interval);
            if (this.currentCharacter) resolve(this.currentCharacter);
            else reject(new Error('Generation cancelled'));
          }
        }, 80);
      });
    }

    this.isBuilding = true;
    try {
      const character = await buildHuman(this.lib, params, {
        onStage: (stage: string) => {
          if (onProgress) onProgress(stage);
        }
      });
      this.currentCharacter = character;
      return character;
    } finally {
      this.isBuilding = false;
      if (this.pendingParams) {
        const next = this.pendingParams;
        this.pendingParams = null;
        return this.generateCharacter(next, onProgress);
      }
    }
  }

  async exportCharacterGlb(character?: Character, includeAnimations = true): Promise<Uint8Array> {
    const ch = character || this.currentCharacter;
    if (!ch || !this.lib) throw new Error('No character built for export');
    const textures = new Map<string, Uint8Array>();
    const clips = (includeAnimations && ch.rig) ? bakeCharacterClips(ch.rig, ch.face) : [];
    return exportGLB(ch.mesh, ch.params.name || 'yorvyn_avatar', textures, ch.rig, clips, { meshless: false });
  }
}

/** Singleton instance for the Yorvyn App */
export const araEngine = new AraEngineBridge();
