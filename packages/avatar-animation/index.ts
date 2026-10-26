/**
 * Yorvyn Technology Library — Avatar Animation
 * Animation clip registry, track blending, and state machine controller.
 */

import type { AnimationClipDef } from '../shared-types/index.ts';

export interface PlaybackOptions {
  loop?: boolean;
  crossfadeDuration?: number;
  timeScale?: number;
}

export interface IAnimationController {
  /** Register or update available animation clips */
  registerClips(clips: AnimationClipDef[]): void;

  /** Play a continuous looping state (e.g. 'Idle') */
  play(clipName: string, options?: PlaybackOptions): void;

  /** Play a gesture one-shot (e.g. 'Wave', 'Cheer', 'Turn') and smoothly return to base */
  playOneShot(actionName: string, returnToBaseName?: string, blendSeconds?: number): void;

  /** Update playback delta time (in seconds) on animation tick */
  update(deltaSeconds: number): void;

  /** Get current active playing clip name */
  getCurrentClipName(): string | null;
}

export function createStandardActionClips(): AnimationClipDef[] {
  return [
    {
      name: 'Idle',
      durationSeconds: 3.5,
      boneTrackCount: 22,
      isLooping: true
    },
    {
      name: 'Wave',
      durationSeconds: 2.2,
      boneTrackCount: 28,
      isLooping: false
    },
    {
      name: 'Cheer',
      durationSeconds: 3.0,
      boneTrackCount: 32,
      isLooping: false
    },
    {
      name: 'Turn',
      durationSeconds: 2.0,
      boneTrackCount: 20,
      isLooping: false
    }
  ];
}

export class StandardAnimationController implements IAnimationController {
  private clips = new Map<string, AnimationClipDef>();
  private currentClipName: string | null = null;
  private previousClipName: string | null = null;
  private currentClipTime = 0;
  private blendProgress = 1.0;
  private blendDuration = 0.3;
  private isOneShotActive = false;
  private oneShotReturnBase = 'Idle';
  private timeScale = 1.0;

  constructor(initialClips?: AnimationClipDef[]) {
    if (initialClips) {
      this.registerClips(initialClips);
    }
  }

  public registerClips(clips: AnimationClipDef[]): void {
    for (const clip of clips) {
      this.clips.set(clip.name.toLowerCase(), clip);
    }
  }

  public play(clipName: string, options?: PlaybackOptions): void {
    const key = clipName.toLowerCase();
    if (!this.clips.has(key)) {
      throw new Error(`Animation clip '${clipName}' is not registered`);
    }

    if (this.currentClipName === clipName) {
      return;
    }

    this.previousClipName = this.currentClipName;
    this.currentClipName = clipName;
    this.currentClipTime = 0;
    this.blendDuration = options?.crossfadeDuration ?? 0.3;
    this.blendProgress = this.previousClipName ? 0.0 : 1.0;
    this.timeScale = options?.timeScale ?? 1.0;
    this.isOneShotActive = false;
  }

  public playOneShot(
    actionName: string,
    returnToBaseName: string = 'Idle',
    blendSeconds: number = 0.25
  ): void {
    const key = actionName.toLowerCase();
    if (!this.clips.has(key)) {
      throw new Error(`One-shot action '${actionName}' is not registered`);
    }

    this.previousClipName = this.currentClipName;
    this.currentClipName = actionName;
    this.currentClipTime = 0;
    this.blendDuration = blendSeconds;
    this.blendProgress = 0.0;
    this.isOneShotActive = true;
    this.oneShotReturnBase = returnToBaseName;
  }

  public update(deltaSeconds: number): void {
    if (!this.currentClipName) return;

    const currentClip = this.clips.get(this.currentClipName.toLowerCase());
    if (!currentClip) return;

    const effectiveDt = deltaSeconds * this.timeScale;
    this.currentClipTime += effectiveDt;

    // Advance crossfade blend
    if (this.blendProgress < 1.0) {
      this.blendProgress = Math.min(1.0, this.blendProgress + effectiveDt / this.blendDuration);
    }

    // Check one-shot completion
    if (this.isOneShotActive && this.currentClipTime >= currentClip.durationSeconds) {
      this.play(this.oneShotReturnBase, { crossfadeDuration: this.blendDuration });
    } else if (currentClip.isLooping && this.currentClipTime >= currentClip.durationSeconds) {
      this.currentClipTime %= currentClip.durationSeconds;
    }
  }

  public getCurrentClipName(): string | null {
    return this.currentClipName;
  }

  public getBlendWeight(): number {
    return this.blendProgress;
  }
}
