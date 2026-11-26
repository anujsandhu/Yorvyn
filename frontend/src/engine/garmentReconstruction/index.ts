/**
 * YORVYN — ADVANCED AI GARMENT RECONSTRUCTION ENGINE (Phase 3)
 * 
 * Central module exporting:
 * - garmentReconstructionTypes: Data contracts, fabric PBR schemas, boundary loops, quality reports
 * - GarmentImageProcessor: Universal multi-view validation, resolution check, format guardrails
 * - GarmentSegmentationService: Background removal, transparent PNG generation, mask touchup
 * - GarmentIntelligenceService: Subcategory understanding, component breakdown, provenance tracking
 * - MultiImageGarmentMatcher: Cross-image consistency matching and view classification
 * - GarmentGeometryProcessor: 3D manifold geometry builders (hoodie, tops, bottoms, dress), connected seams
 * - GarmentTextureProcessor: Physical PBR properties for 9 fabrics, albedo atlas, normal map synthesis
 * - GarmentTopologyValidator: Manifold checks, non-degenerate triangles, quality report generation
 * - GarmentAssetExporter: glTF 2.0 binary container (.glb) builder with embedded textures
 * - GarmentReconstructionAdapter: Local parametric & backend worker reconstruction adapters
 * - GarmentReconstructionJobManager: Async job lifecycle, progress notifications, cancellation
 */

export * from './garmentReconstructionTypes';
export * from './GarmentImageProcessor';
export * from './GarmentSegmentationService';
export * from './GarmentIntelligenceService';
export * from './MultiImageGarmentMatcher';
export * from './GarmentGeometryProcessor';
export * from './GarmentTextureProcessor';
export * from './GarmentTopologyValidator';
export * from './GarmentAssetExporter';
export * from './GarmentReconstructionAdapter';
export * from './GarmentReconstructionJobManager';
export * from './GarmentMannequinPreviewRenderer';
