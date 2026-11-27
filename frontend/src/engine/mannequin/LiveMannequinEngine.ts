/**
 * YORVYN — Live 3D Fashion Mannequin Engine (Phase 6)
 * Orchestrates a coherent, living 3D fashion mannequin.
 * Coordinates persistent base body integrity, idle breathing, fashion poses,
 * garment reaction sequencing, and smooth cross-fade animation transitions.
 */

import * as THREE from 'three';
import { AraAnimationController, araAnim } from '../ara/avatarAnimationController';
import { BaseBodyController, BaseBodyIntegrityReport } from '../garments/BaseBodyController';
import { OutfitStateManager, PersistentOutfitState } from '../garments/OutfitStateManager';
import { GarmentResourceManager } from '../garments/GarmentResourceManager';
import { GarmentVisibilityManager } from '../garments/GarmentVisibilityManager';
import { HumanParams } from '../ara/core/params';

export type FashionPosePreset = 'standing' | 'fashion_runway' | 'crossed_arms' | 'hands_pockets';

export interface MannequinStatureConfig {
  heightCm: number;
  silhouetteId: 'slim' | 'athletic' | 'regular' | 'curvy';
}

export interface StatureScaleResult {
  scaleX: number;
  scaleY: number;
  scaleZ: number;
  targetCm: number;
}

export class LiveMannequinEngine {
  private animController: AraAnimationController;
  private outfitManager: OutfitStateManager;
  private resourceManager: GarmentResourceManager;
  private currentPose: FashionPosePreset = 'standing';
  private currentModel: THREE.Object3D | null = null;
  private isDisposed: boolean = false;

  constructor(outfitState?: Partial<PersistentOutfitState>, animController?: AraAnimationController) {
    this.animController = animController || araAnim;
    this.outfitManager = new OutfitStateManager(outfitState);
    this.resourceManager = new GarmentResourceManager();
  }

  /**
   * Initializes the live mannequin engine on the Three.js character scene and animation clips.
   */
  public init(modelRoot: THREE.Object3D, clips: THREE.AnimationClip[], params?: HumanParams): void {
    this.currentModel = modelRoot;
    this.isDisposed = false;

    // 1. Initialize skeletal animation controller
    this.animController.init(modelRoot, clips);

    // 2. Start breathing idle loop as default baseline
    this.playIdle();

    // 3. Synchronize mesh visibility with active outfit state
    if (params) {
      this.syncFromHumanParams(params, modelRoot);
    } else {
      GarmentVisibilityManager.syncMeshVisibility(modelRoot, this.outfitManager.getState());
    }
  }

  /**
   * Synchronizes the internal outfit state and 3D mesh visibility from HumanParams.
   */
  public syncFromHumanParams(p: HumanParams, modelRoot?: THREE.Object3D): PersistentOutfitState {
    const hasOutfit = !!(p.outfit && p.outfit !== 'none');
    const hasTop = !!(p.top && p.top !== 'none');
    const hasBottom = !!(p.bottom && p.bottom !== 'none');
    const hasShoes = !!(p.shoes && p.shoes !== 'none');

    const nextState: PersistentOutfitState = {
      version: 1,
      underwear: p.underwear !== false ? {
        id: 'briefs',
        name: 'Neutral Modesty Briefs',
        category: 'underwear',
        hidesSkin: false
      } : null,
      outfit: hasOutfit ? {
        id: p.outfit,
        name: p.outfit,
        category: 'outfit'
      } : null,
      top: hasTop ? {
        id: p.top,
        name: p.top,
        category: 'top'
      } : null,
      bottom: hasBottom ? {
        id: p.bottom,
        name: p.bottom,
        category: 'bottom'
      } : null,
      shoes: hasShoes ? {
        id: p.shoes,
        name: p.shoes,
        category: 'shoes'
      } : null,
      outerwear: null,
      accessories: (p.accessories || []).map((a) => ({
        id: a,
        name: a,
        category: 'accessory'
      })),
      updatedAt: new Date().toISOString()
    };

    this.outfitManager = new OutfitStateManager(nextState);

    const targetModel = modelRoot || this.currentModel;
    if (targetModel) {
      GarmentVisibilityManager.syncMeshVisibility(targetModel, nextState);
    }

    return nextState;
  }

  /**
   * Returns the animation controller.
   */
  public getAnimationController(): AraAnimationController {
    return this.animController;
  }

  /**
   * Returns the outfit state manager.
   */
  public getOutfitStateManager(): OutfitStateManager {
    return this.outfitManager;
  }

  /**
   * Returns the GPU resource manager.
   */
  public getResourceManager(): GarmentResourceManager {
    return this.resourceManager;
  }

  /**
   * Plays the continuous idle breathing motion with natural weight shifts.
   */
  public playIdle(crossfadeSeconds: number = 0.35): void {
    if (this.isDisposed) return;
    this.animController.play('Idle', { loop: true, crossfadeDuration: crossfadeSeconds });
  }

  /**
   * Triggers a fashion reaction emote (e.g. upon equipping a new garment or receiving user feedback),
   * then automatically and smoothly returns to the idle breathing cycle.
   */
  public playReaction(reactionClipName: string, crossfadeSeconds: number = 0.35): boolean {
    if (this.isDisposed) return false;
    return this.animController.playOneShot(reactionClipName, 'Idle', crossfadeSeconds);
  }

  /**
   * Celebrates a newly equipped garment with a fashion presentation sequence
   * (e.g. 360 turn or look-at-garment gesture).
   */
  public onGarmentEquipped(category: string): void {
    if (category === 'shoes' || category === 'bottom') {
      this.playReaction('Look at Garment', 0.4);
    } else if (category === 'outfit' || category === 'outerwear') {
      this.playReaction('Turn', 0.4);
    } else {
      this.playReaction('Present Outfit', 0.4);
    }
  }

  /**
   * Changes the mannequin's editorial fashion posture.
   */
  public setPose(pose: FashionPosePreset): void {
    this.currentPose = pose;
    switch (pose) {
      case 'fashion_runway':
        this.playReaction('Present Both', 0.4);
        break;
      case 'crossed_arms':
        this.playReaction('Thinking', 0.4);
        break;
      case 'hands_pockets':
        this.playReaction('Curious', 0.4);
        break;
      case 'standing':
      default:
        this.playIdle(0.4);
        break;
    }
  }

  public getCurrentPose(): FashionPosePreset {
    return this.currentPose;
  }

  public getCurrentModel(): THREE.Object3D | null {
    return this.currentModel;
  }

  /**
   * Computes instant stature and body silhouette scaling without reconstructing the GLTF mesh.
   */
  public static computeStatureScale(config: MannequinStatureConfig): StatureScaleResult {
    const targetCm = Math.min(210, Math.max(140, config.heightCm || 178));
    const baseHeightMeters = 1.70;
    const targetHeightMeters = targetCm / 100.0;
    const scaleY = targetHeightMeters / baseHeightMeters;

    let widthFactor = 1.0;
    let depthFactor = 1.0;

    switch (config.silhouetteId) {
      case 'slim':
        widthFactor = 0.94;
        depthFactor = 0.93;
        break;
      case 'athletic':
        widthFactor = 1.06;
        depthFactor = 1.03;
        break;
      case 'curvy':
        widthFactor = 1.08;
        depthFactor = 1.06;
        break;
      case 'regular':
      default:
        widthFactor = 1.0;
        depthFactor = 1.0;
        break;
    }

    return {
      scaleX: scaleY * widthFactor,
      scaleY,
      scaleZ: scaleY * depthFactor,
      targetCm
    };
  }

  /**
   * Verifies that the current mannequin body remains continuous and complete.
   */
  public verifyBodyIntegrity(positions: Float32Array, indices: Uint32Array): BaseBodyIntegrityReport {
    return BaseBodyController.verifyIntegrity(positions, indices);
  }

  /**
   * Advances the animation mixer by delta seconds.
   */
  public update(deltaSeconds: number): void {
    if (this.isDisposed) return;
    this.animController.update(deltaSeconds);
  }

  /**
   * Disposes of animation mixer, GPU resources, and event listeners cleanly.
   */
  public dispose(): void {
    this.isDisposed = true;
    this.animController.dispose();
    this.resourceManager.disposeAll();
    this.currentModel = null;
  }
}
