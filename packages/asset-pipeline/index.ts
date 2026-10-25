/**
 * Yorvyn Technology Library — Asset Pipeline
 * GLB binary assembly, software 3D thumbnail rendering, and privacy-safe persistence.
 */

import { Garment3DAsset } from '../garment-core';

export interface SavedWardrobeArtifacts {
  wardrobeItemId: string;
  glbRelativeUrl: string;
  thumbnailRelativeUrl: string;
  fileSizeBytes: number;
  createdAt: string;
}

export interface IAssetPipeline {
  /** Encode separable garment mesh and embedded PBR textures into binary glTF 2.0 (.glb) */
  exportGlb(garment: Garment3DAsset, texturePngBytes: Uint8Array): Promise<Uint8Array>;

  /** Render software depth-buffered 3D studio preview PNG directly from 3D geometry */
  renderThumbnail(garment: Garment3DAsset, texturePngBytes: Uint8Array): Promise<Uint8Array>;

  /**
   * Persist generated 3D assets to storage, enforce strict privacy by purging
   * any temporary input photos, and register in My Wardrobe.
   */
  persistToWardrobe(
    jobId: string,
    glbBytes: Uint8Array,
    thumbnailBytes: Uint8Array,
    garment: Garment3DAsset
  ): Promise<SavedWardrobeArtifacts>;
}
