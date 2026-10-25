/**
 * Yorvyn Technology Library — Avatar Animation
 * Animation clip registry, track blending, and state machine controller.
 */

import { AnimationClipDef } from '../shared-types';

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
