# Yorvyn Technology Library — Module Boundaries & Interface Standards

To ensure long-term maintainability and prevent vendor lock-in, all capabilities within Yorvyn are decoupled behind explicit interfaces. Third-party or research repositories must sit strictly behind an adapter layer.

---

## Boundary Rules

1. **Zero Provider Leakage into UI**:
   The frontend UI (`AvatarStudio.tsx`, `AraAvatarViewer.tsx`) must never reference provider-specific SDKs or research internal classes directly. All interactions flow through standard contracts defined in `packages/`.
2. **Pluggable AI Workers**:
   The core application must function reliably on local CPU resources (parametric manifold pipeline) while supporting remote GPU acceleration (Garment3DGen / diffusion cluster) via `IAIWorkerAdapter`.
3. **No Non-Commercial Code in Production SaaS**:
   Components with non-commercial or academic licenses (e.g. Garment3DGen CC-BY-NC, ReMu SMPL-X dependencies) must remain quarantined in `research/upstream/` and accessed exclusively via optional external worker microservices.
4. **Mandatory Privacy Cleanup**:
   Any reconstruction interface taking photo input must delete the input files upon completion, failure, or cancellation. Original image paths must never escape the boundary layer into persistent database records.

---

## Key Interface Contracts

### 1. Avatar Generation & Customization
```typescript
interface IAvatarGeneratorProvider {
  initialize(onProgress?: (label: string, percent?: number) => void): Promise<void>;
  buildCharacter(params: AvatarAnthropometry, onStage?: (stage: string) => void): Promise<AvatarCharacterModel>;
  exportGlbBuffer(character: AvatarCharacterModel, includeAnimations?: boolean): Promise<Uint8Array>;
}
```

### 2. Garment Reconstruction
```typescript
interface IGarmentReconstructionEngine {
  analyzeGarmentPhoto(input: TemporaryGarmentInput): Promise<GarmentUnderstandingResult>;
  reconstructGarment(input: TemporaryGarmentInput, analysis: GarmentUnderstandingResult): Promise<Garment3DAsset>;
}
```

### 3. Garment Fitting & Occlusion Masking
```typescript
interface IGarmentFitter {
  fitToAvatar(garment: Garment3DAsset, avatar: AvatarCharacterModel): Promise<FittingResult>;
  computeOcclusionMask(garmentCategory: string, avatar: AvatarCharacterModel): string[];
}
```

### 4. PBR Material & Texture Synthesis
```typescript
interface ITextureSynthesizer {
  synthesizePbrMaps(frontImageBytes: Uint8Array, backImageBytes?: Uint8Array, dominantColor?: string): Promise<TextureAtlasMaps>;
  buildMaterial(name: string, maps: TextureAtlasMaps, urls: MaterialUrls): MaterialDef;
}
```

### 5. Asset Pipeline & Wardrobe Persistence
```typescript
interface IAssetPipeline {
  exportGlb(garment: Garment3DAsset, texturePngBytes: Uint8Array): Promise<Uint8Array>;
  renderThumbnail(garment: Garment3DAsset, texturePngBytes: Uint8Array): Promise<Uint8Array>;
  persistToWardrobe(jobId: string, glb: Uint8Array, thumb: Uint8Array, garment: Garment3DAsset): Promise<SavedWardrobeArtifacts>;
}
```

### 6. AI Inference Worker Adapter
```typescript
interface IAIWorkerAdapter {
  readonly adapterName: string;
  readonly executionTarget: 'local_cpu_worker' | 'remote_gpu_cluster';
  checkHealth(): Promise<{ available: boolean; latencyMs: number; vramMb?: number }>;
  processGenerationJob(input: TemporaryGarmentInput, analysis: GarmentUnderstandingResult): Promise<Garment3DAsset>;
}
```
