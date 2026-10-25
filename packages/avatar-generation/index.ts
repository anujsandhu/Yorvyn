/**
 * Yorvyn Technology Library — Avatar Generation
 * Stable provider interface for procedural morphing and generative character synthesis.
 */

import { AvatarAnthropometry, AvatarCharacterModel } from '../avatar-core';

export interface IAvatarGeneratorProvider {
  readonly providerId: string;
  readonly providerName: string;
  readonly supportedExportFormats: ('glb' | 'obj')[];

  /** Initialize library catalog and precompute morph matrices */
  initialize(onProgress?: (label: string, percent?: number) => void): Promise<void>;

  /** Synthesize or morph character mesh based on anthropometry parameters */
  buildCharacter(
    params: AvatarAnthropometry,
    onStage?: (stageName: string) => void
  ): Promise<AvatarCharacterModel>;

  /** Export binary GLB byte buffer with optional baked skeletal animations */
  exportGlbBuffer(
    character: AvatarCharacterModel,
    includeAnimations?: boolean
  ): Promise<Uint8Array>;
}
