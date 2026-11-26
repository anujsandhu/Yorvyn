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
    { id: 'walk', name: 'Walk' },
    { id: 'run', name: 'Run' },
    { id: 'sit_down', name: 'Sit Down' },
    { id: 'sit_idle', name: 'Sit' },
    { id: 'stand_up', name: 'Stand Up' },
    { id: 'crouch', name: 'Bend' },
    { id: 'thumbs_up', name: 'Thumbs Up' },
    { id: 'thumbs_down', name: 'Thumbs Down' },
    { id: 'wave', name: 'Wave' },
    { id: 'cheer', name: 'Cheer' },
    { id: 'nod', name: 'Nod' },
    { id: 'head_shake', name: 'Head Shake' },
    { id: 'thinking', name: 'Thinking' },
    { id: 'curious', name: 'Curious' },
    { id: 'present_single', name: 'Present Outfit' },
    { id: 'present_both', name: 'Present Both' },
    { id: 'point_outfit', name: 'Point at Outfit' },
    { id: 'look_garment', name: 'Look at Garment' },
    { id: 'inspect_outfit', name: 'Inspect Outfit' },
    { id: 'suggest_alt', name: 'Suggest Alternative' },
    { id: 'welcome', name: 'Welcome' },
    { id: 'listening', name: 'Listening' },
    { id: 'excited', name: 'Excited' },
    { id: 'confused', name: 'Confused' },
    { id: 'turn_360', name: 'Turn' },
    { id: 'talk', name: 'Talk' },
    { id: 'laugh', name: 'Laugh' },
  ];

  const baked: BakedClip[] = [];
  for (const spec of clipSpecs) {
    const clip = clipById.get(spec.id);
    if (!clip) {
      console.warn(`[AraService] Clip "${spec.id}" not found in Ara 3D Gen catalog`);
      continue;
    }
    const bakedData = animator.bake(clip, 60, { rootMotion: false });
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

    // Embed all available diffuse and normal maps into the GLB container
    const promises: Promise<void>[] = [];
    for (const m of ch.mesh.materials) {
      if (m.map && !textures.has(m.map)) {
        promises.push(
          this.lib.texture(m.map)
            .then((data) => {
              if (data) textures.set(m.map!, data);
            })
            .catch(() => {})
        );
      }
      if (m.normalMap && !textures.has(m.normalMap)) {
        promises.push(
          this.lib.texture(m.normalMap)
            .then((data) => {
              if (data) textures.set(m.normalMap!, data);
            })
            .catch(() => {})
        );
      }
    }
    if (promises.length > 0) {
      await Promise.all(promises);
    }

    const clips = (includeAnimations && ch.rig) ? bakeCharacterClips(ch.rig, ch.face) : [];
    return exportGLB(ch.mesh, ch.params.name || 'yorvyn_avatar', textures, ch.rig, clips, { meshless: false });
  }
}

/** Singleton instance for the Yorvyn App */
export const araEngine = new AraEngineBridge();
export const avatarEngine = araEngine;
