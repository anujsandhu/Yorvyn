/**
 * YORVYN — Garment Reconstruction Adapter (Phase 3)
 * 
 * Provider-independent abstraction isolating model integration from application logic.
 * Exposes:
 * - IGarmentReconstructionAdapter: Standard interface
 * - LocalParametricReconstructionAdapter: Advanced multi-image client-side parametric & understanding pipeline
 * - BackendWorkerReconstructionAdapter: Asynchronous server-side pipeline via FastAPI worker
 */

import { 
  MultiViewInput, 
  GarmentReconstructionCategory, 
  GarmentSubcategory,
  ReconstructedGarmentAsset,
  FabricType 
} from './garmentReconstructionTypes';
import { GarmentImageProcessor } from './GarmentImageProcessor';
import { GarmentSegmentationService } from './GarmentSegmentationService';
import { GarmentIntelligenceService } from './GarmentIntelligenceService';
import { MultiImageGarmentMatcher } from './MultiImageGarmentMatcher';
import { GarmentGeometryProcessor } from './GarmentGeometryProcessor';
import { GarmentTextureProcessor } from './GarmentTextureProcessor';
import { GarmentTopologyValidator } from './GarmentTopologyValidator';
import { GarmentAssetExporter } from './GarmentAssetExporter';
import { GarmentMannequinPreviewRenderer } from './GarmentMannequinPreviewRenderer';

export interface ReconstructionAdapterOptions {
  subcategory?: GarmentSubcategory | string;
  fabricType?: FabricType;
  fit?: 'slim' | 'regular' | 'relaxed' | 'oversized';
  necklineType?: 'crewneck' | 'v_neck' | 'collar' | 'scoop' | 'turtle' | 'hoodie_collar';
  sleeveLength?: 'sleeveless' | 'short' | 'three_quarter' | 'long';
  onProgress?: (progress: number, stage: string) => void;
}

export interface IGarmentReconstructionAdapter {
  readonly providerName: string;
  reconstruct(
    input: MultiViewInput,
    category: GarmentReconstructionCategory,
    options?: ReconstructionAdapterOptions
  ): Promise<ReconstructedGarmentAsset>;
}

/**
 * Local Parametric Reconstruction Adapter
 * Runs entirely on-device without external server round-trips or GPU cloud fees.
 */
export class LocalParametricReconstructionAdapter implements IGarmentReconstructionAdapter {
  public readonly providerName = 'Yorvyn-Advanced-Parametric-Engine-Phase3';

  public async reconstruct(
    input: MultiViewInput,
    category: GarmentReconstructionCategory,
    options: ReconstructionAdapterOptions = {}
  ): Promise<ReconstructedGarmentAsset> {
    const notify = (pct: number, stage: string) => {
      options.onProgress?.(pct, stage);
    };

    // 1. Photographic Validation
    notify(10, 'Validating reference photographs and EXIF dimensions...');
    const validation = await GarmentImageProcessor.validateInput(input, category);
    if (!validation.isValid) {
      throw new Error(`Garment image validation failed: ${validation.issues.join('; ')}`);
    }

    // 2. Multi-Image Consistency & Angle Matching
    notify(22, 'Evaluating multi-view consistency and feature alignment...');
    const matchResult = await MultiImageGarmentMatcher.evaluateMultiViewInput(input);
    if (!matchResult.isConsistent) {
      // Non-fatal warning or error based on mismatch
      options.onProgress?.(25, `Notice: ${matchResult.notes.join(' ')}`);
    }

    // 3. Garment Segmentation & Background Removal
    notify(36, 'Segmenting clothing item and generating transparent PNG mask...');
    const segResult = await GarmentSegmentationService.segmentGarment(input.front);

    // 4. Garment Understanding & Component Intelligence
    notify(48, 'Analyzing garment construction, components, and color profile...');
    const intelligence = GarmentIntelligenceService.analyzeGarment(
      segResult,
      category,
      options.subcategory
    );

    const subcategory = intelligence.subcategory;
    const isHoodie = subcategory === 'hoodie' || intelligence.hasHood;

    // 5. Category-Specific 3D Geometry Reconstruction
    notify(62, `Reconstructing 3D wearable manifold ${subcategory} geometry with connected seams...`);
    const geometry = GarmentGeometryProcessor.buildGarmentMesh(category, subcategory, {
      fit: options.fit || (intelligence.silhouette === 'tailored' ? 'slim' : intelligence.silhouette),
      necklineType: options.necklineType || intelligence.necklineType,
      sleeveLength: options.sleeveLength || intelligence.sleeveLength,
      hasHood: isHoodie,
      hasKangarooPocket: intelligence.hasKangarooPocket,
      hasDrawstrings: intelligence.hasDrawstrings
    });

    // 6. PBR Fabric Setup & Photographic Diffuse Atlas Synthesis
    notify(76, 'Synthesizing photographic albedo atlas and normal maps...');
    const fabricType = options.fabricType || intelligence.materialHint;
    const fabricProps = GarmentTextureProcessor.getFabricProperties(fabricType);

    const backUrl = input.back 
      ? (typeof input.back === 'string' ? input.back : URL.createObjectURL(input.back)) 
      : undefined;

    const { dataUrl: diffuseAtlasUrl } = await GarmentTextureProcessor.createDiffuseTextureAtlas(
      segResult.transparentPngUrl || segResult.segmentedDataUrl,
      intelligence.primaryColorHex,
      backUrl,
      1024,
      segResult.pureFabricSampleRgb,
      segResult.componentBounds
    );

    const normalMapUrl = GarmentTextureProcessor.generateProceduralNormalMap(fabricType);

    // 7. Manifold Topology Validation & Quality Report
    notify(88, 'Validating 3D manifold topology, boundary loops, and component provenance...');
    const topoValidation = GarmentTopologyValidator.validateMesh(geometry);
    if (!topoValidation.isValid) {
      throw new Error(`Reconstructed mesh topology failed manifold validation: ${topoValidation.issues.join('; ')}`);
    }

    // 8. Generate 3D-First Mannequin Visual Preview
    notify(94, 'Rendering catalog-grade 3D mannequin visual thumbnail...');
    let mannequinThumbUrl: string | undefined;
    try {
      mannequinThumbUrl = await GarmentMannequinPreviewRenderer.getInstance().renderGarmentThumbnail(
        geometry,
        diffuseAtlasUrl,
        intelligence.primaryColorHex,
        subcategory
      );
    } catch (renderErr) {
      console.warn('Mannequin preview rendering warning:', renderErr);
    }

    // 9. glTF Binary Container Assembly
    notify(97, 'Assembling binary glTF asset with embedded textures and Ara rig compatibility...');
    const assetId = `rec_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const garmentName = `${intelligence.primaryColorName} ${subcategory.toUpperCase()}`;

    const asset = GarmentAssetExporter.exportGarmentAsset(
      assetId,
      garmentName,
      category,
      subcategory,
      geometry,
      fabricProps,
      intelligence.primaryColorHex,
      topoValidation.qualityScore,
      {
        thumbnailUrl: mannequinThumbUrl,
        textureDataUrl: diffuseAtlasUrl,
        normalMapDataUrl: normalMapUrl,
        qualityReport: topoValidation.qualityReport,
        intelligence
      }
    );

    // 10. Clean up temporary intermediate blob references
    if (backUrl && typeof input.back !== 'string' && backUrl.startsWith('blob:')) {
      try { URL.revokeObjectURL(backUrl); } catch { /* noop */ }
    }
    if (segResult.transparentPngUrl && segResult.transparentPngUrl.startsWith('blob:')) {
      try { URL.revokeObjectURL(segResult.transparentPngUrl); } catch { /* noop */ }
    }

    notify(100, 'Reconstruction complete with 3D mannequin preview ready for fitting review.');
    return asset;
  }
}

/**
 * Backend Worker Reconstruction Adapter
 * Submits multi-view photographs to FastAPI worker pipeline and polls progress.
 */
export class BackendWorkerReconstructionAdapter implements IGarmentReconstructionAdapter {
  public readonly providerName = 'Yorvyn-Backend-Worker-Pipeline';
  private apiBaseUrl: string;

  constructor(apiBaseUrl = '/api/fashion/garment-gen') {
    this.apiBaseUrl = apiBaseUrl;
  }

  public async reconstruct(
    input: MultiViewInput,
    category: GarmentReconstructionCategory,
    options: ReconstructionAdapterOptions = {}
  ): Promise<ReconstructedGarmentAsset> {
    const notify = (pct: number, stage: string) => {
      options.onProgress?.(pct, stage);
    };

    notify(10, 'Submitting photographs to background worker...');

    // Convert front input to File/Blob if needed
    let frontFile: Blob;
    if (input.front instanceof File || input.front instanceof Blob) {
      frontFile = input.front;
    } else {
      const resp = await fetch(input.front);
      frontFile = await resp.blob();
    }

    const formData = new FormData();
    formData.append('front_image', frontFile, 'front.jpg');
    formData.append('category', category);
    if (options.subcategory) formData.append('subcategory', options.subcategory);
    if (options.fabricType) formData.append('material', options.fabricType);
    if (options.fit) formData.append('fit', options.fit);

    if (input.back) {
      let backFile: Blob;
      if (input.back instanceof File || input.back instanceof Blob) {
        backFile = input.back;
      } else {
        const resp = await fetch(input.back);
        backFile = await resp.blob();
      }
      formData.append('back_image', backFile, 'back.jpg');
    }

    // Call canonical endpoint /jobs
    const resp = await fetch(`${this.apiBaseUrl}/jobs`, {
      method: 'POST',
      body: formData
    });

    if (!resp.ok) {
      let errorMsg = `Worker returned HTTP ${resp.status}`;
      try {
        const errJson = await resp.json();
        if (errJson.detail) errorMsg = errJson.detail;
      } catch {
        // use default errorMsg
      }
      throw new Error(`Backend reconstruction failed: ${errorMsg}`);
    }

    const jobData = await resp.json();
    notify(40, 'Garment processing in worker pipeline...');

    return this.pollJobCompletion(jobData.job_id, notify);
  }

  private async pollJobCompletion(
    jobId: string,
    notify: (pct: number, stage: string) => void
  ): Promise<ReconstructedGarmentAsset> {
    for (let attempt = 0; attempt < 30; attempt++) {
      await new Promise(r => setTimeout(r, 1000));
      notify(40 + attempt * 2, 'Reconstructing geometry in worker...');

      const statusResp = await fetch(`${this.apiBaseUrl}/jobs/${jobId}`);
      if (!statusResp.ok) {
        throw new Error(`Worker status check failed: HTTP ${statusResp.status}`);
      }
      const statusData = await statusResp.json();
      if (statusData.status === 'completed' && statusData.result) {
        notify(100, 'Reconstruction completed successfully.');
        const res = statusData.result;
        const cat = (res.category || 'top') as GarmentReconstructionCategory;
        const subcat = (res.subcategory || 'tshirt') as GarmentSubcategory;
        const fabricProps = GarmentTextureProcessor.getFabricProperties((res.features?.material_hint as FabricType) || 'cotton');
        const geometry = GarmentGeometryProcessor.buildGarmentMesh(cat, subcat);
        const fittingMetadata = GarmentAssetExporter.generateFittingMetadata(cat, subcat);

        return {
          id: res.job_id,
          name: res.garment_name,
          category: cat,
          subcategory: subcat,
          fabric: fabricProps,
          geometry: geometry,
          fittingMetadata: fittingMetadata,
          qualityScore: Math.round((res.features?.confidence_score || 0.85) * 100),
          intelligence: {
            category: cat,
            subcategory: subcat,
            silhouette: (res.features?.fit as any) || 'regular',
            hasHood: subcat === 'hoodie',
            hasKangarooPocket: subcat === 'hoodie',
            hasDrawstrings: subcat === 'hoodie',
            hasRibbedTrim: true,
            sleeveStyle: 'set_in',
            sleeveLength: (res.features?.sleeve_length as any) || 'long',
            necklineType: (res.features?.neckline_type as any) || 'crewneck',
            primaryColorName: res.features?.primary_color_name || 'Espresso',
            primaryColorHex: res.features?.primary_color_hex || '#333333',
            palette: res.features?.palette || [],
            pattern: res.features?.pattern || 'solid',
            materialHint: (res.features?.material_hint as FabricType) || 'cotton',
            components: [],
            confidenceScore: res.features?.confidence_score || 0.85,
            qualityNotes: 'Reconstructed via backend FastAPI worker pipeline.'
          },
          glbBlobUrl: res.glb_url,
          thumbnailUrl: res.thumbnail_url,
          textureDataUrl: res.texture_url,
          normalMapDataUrl: res.normal_map_url,
          createdAt: res.created_at || new Date().toISOString(),
          knownLimitations: []
        };
      }
      if (statusData.status === 'failed') {
        throw new Error(statusData.error || 'Worker reconstruction failed.');
      }
    }
    throw new Error('Worker job polling timed out.');
  }
}
