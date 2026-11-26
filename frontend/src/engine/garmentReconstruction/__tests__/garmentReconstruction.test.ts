/**
 * YORVYN — PHASE 3: Advanced AI Garment Reconstruction Test Suite
 * 
 * Verifies:
 * 1. GarmentImageProcessor: Multi-view validation, HEIC format, auxiliary detail angles
 * 2. GarmentSegmentationService: Background removal, transparent PNG, rich dark brown palette preservation
 * 3. GarmentIntelligenceService: Subcategory understanding, hoodie components, observed vs inferred provenance
 * 4. MultiImageGarmentMatcher: Multi-view consistency validation and conflict detection
 * 5. GarmentGeometryProcessor: Hoodie 3D manifold geometry, connected sleeves, hood cowl, kangaroo pocket, drawstrings
 * 6. GarmentTextureProcessor: Fleece fabric PBR properties, normal map synthesis, diffuse atlas
 * 7. GarmentTopologyValidator: Manifold checks, flat card firewall, GarmentQualityReport generation
 * 8. GarmentAssetExporter: glTF 2.0 binary container (.glb) generation with embedded diffuse textures
 * 9. LocalParametricReconstructionAdapter: Full end-to-end multi-view reconstruction
 * 10. GarmentReconstructionJobManager: Asynchronous job lifecycle and cancellation
 * 11. GarmentFittingEngine Integration: Target slot mapping, body occlusion masking, collision mitigation
 */

import { describe, it, expect, beforeEach } from 'vitest';
import {
  GarmentImageProcessor,
  GarmentSegmentationService,
  GarmentIntelligenceService,
  MultiImageGarmentMatcher,
  GarmentGeometryProcessor,
  GarmentTextureProcessor,
  GarmentTopologyValidator,
  GarmentAssetExporter,
  LocalParametricReconstructionAdapter,
  GarmentReconstructionJobManager,
  GarmentMannequinPreviewRenderer,
  ReconstructedMeshGeometry
} from '../index';
import { GARMENT_UV_ISLANDS } from '../garmentReconstructionTypes';

describe('YORVYN — Advanced AI Garment Reconstruction Engine (Phase 3)', () => {
  let mockFrontFile: File;
  let mockBackFile: File;
  let mockDetailFile: File;
  let mockBrownHoodieFile: File;

  beforeEach(() => {
    // 2KB mock valid JPEG binary
    const bytes = new Uint8Array(2048);
    bytes[0] = 0xff;
    bytes[1] = 0xd8; // JPEG magic
    mockFrontFile = new File([bytes], 'brown_hoodie_front.jpg', { type: 'image/jpeg' });
    mockBackFile = new File([bytes], 'brown_hoodie_back.jpg', { type: 'image/jpeg' });
    mockDetailFile = new File([bytes], 'hood_detail.jpg', { type: 'image/jpeg' });
    mockBrownHoodieFile = new File([bytes], 'dark_brown_hoodie.png', { type: 'image/png' });
  });

  // ── 1. IMAGE UPLOAD & MULTI-VIEW VALIDATION ──
  describe('GarmentImageProcessor', () => {
    it('validates standard front, back, and detail photographic inputs', async () => {
      const res = await GarmentImageProcessor.validateInput(
        { 
          front: mockFrontFile, 
          back: mockBackFile,
          hoodDetail: mockDetailFile
        },
        'top'
      );
      expect(res.isValid).toBe(true);
      expect(res.issues.length).toBe(0);
      expect(res.hasCompleteGarment).toBe(true);
    });

    it('supports HEIC/HEIF image formats with proper detection', async () => {
      const heicBytes = new Uint8Array(2048);
      const heicFile = new File([heicBytes], 'photo.heic', { type: 'image/heic' });
      const res = await GarmentImageProcessor.validateInput({ front: heicFile }, 'top');
      expect(res.isValid).toBe(true);
      expect(res.detectedFormat).toBe('HEIC');
    });

    it('rejects missing front reference photograph', async () => {
      const res = await GarmentImageProcessor.validateInput(
        { front: null as any },
        'top'
      );
      expect(res.isValid).toBe(false);
      expect(res.issues[0]).toContain('Primary front reference');
    });

    it('rejects unsupported file formats and empty files', async () => {
      const badFile = new File([new Uint8Array(2000)], 'garment.exe', { type: 'application/x-msdownload' });
      const badRes = await GarmentImageProcessor.validateInput({ front: badFile }, 'top');
      expect(badRes.isValid).toBe(false);
      expect(badRes.issues.some(i => i.includes('unsupported file type'))).toBe(true);

      const emptyFile = new File([new Uint8Array(50)], 'empty.jpg', { type: 'image/jpeg' });
      const emptyRes = await GarmentImageProcessor.validateInput({ front: emptyFile }, 'top');
      expect(emptyRes.isValid).toBe(false);
      expect(emptyRes.issues.some(i => i.includes('empty or corrupted'))).toBe(true);
    });

    it('generates honest guidance when back view is missing on complex garments', async () => {
      const outerwearRes = await GarmentImageProcessor.validateInput(
        { front: mockFrontFile },
        'outerwear'
      );
      expect(outerwearRes.isValid).toBe(true);
      expect(outerwearRes.requiresAdditionalView).toBe(true);
      expect(outerwearRes.recommendedViewReason).toContain('Back view photograph is strongly recommended');
      expect(outerwearRes.warnings.some(w => w.includes('Single-view'))).toBe(true);
    });
  });

  // ── 2. GARMENT SEGMENTATION & BACKGROUND REMOVAL ──
  describe('GarmentSegmentationService', () => {
    it('isolates foreground clothing item and extracts rich brown color palette', async () => {
      const res = await GarmentSegmentationService.segmentGarment(mockBrownHoodieFile);
      expect(res).toBeDefined();
      expect(res.dominantColorHex).toMatch(/^#[0-9a-fA-F]{6}$/);
      expect(res.dominantColorHex).toBe('#4a2e18'); // Preserves rich dark brown, not crude black!
      expect(res.palette.length).toBeGreaterThanOrEqual(4);
      expect(res.hasInternalOpenings).toBe(true);
      expect(res.boundingBox.width).toBeGreaterThan(0);
      expect(res.boundingBox.height).toBeGreaterThan(0);
    });

    it('supports interactive manual mask correction without crashing', () => {
      const mockResult = GarmentSegmentationService.generateMockSegmentation();
      const updated = GarmentSegmentationService.applyMaskCorrection(
        mockResult.maskDataUrl,
        mockResult.segmentedDataUrl,
        { x: 100, y: 100, radius: 15, mode: 'erase' }
      );
      expect(updated.updatedMaskUrl).toBeDefined();
      expect(updated.updatedTransparentUrl).toBeDefined();
    });
  });

  // ── 3. GARMENT INTELLIGENCE & COMPONENT UNDERSTANDING ──
  describe('GarmentIntelligenceService', () => {
    it('identifies hoodie construction and itemizes detailed components', () => {
      const seg = GarmentSegmentationService.generateMockSegmentation();
      const intelligence = GarmentIntelligenceService.analyzeGarment(seg, 'top', 'hoodie');

      expect(intelligence.subcategory).toBe('hoodie');
      expect(intelligence.hasHood).toBe(true);
      expect(intelligence.hasKangarooPocket).toBe(true);
      expect(intelligence.hasDrawstrings).toBe(true);
      expect(intelligence.hasRibbedTrim).toBe(true);
      expect(intelligence.materialHint).toBe('fleece');

      // Check provenance breakdown
      const compTypes = intelligence.components.map(c => c.type);
      expect(compTypes).toContain('hood');
      expect(compTypes).toContain('kangaroo_pocket');
      expect(compTypes).toContain('drawstrings');
      expect(compTypes).toContain('left_sleeve');
      expect(compTypes).toContain('right_sleeve');
      expect(compTypes).toContain('ribbed_cuffs');
      expect(compTypes).toContain('ribbed_waistband');

      // Check observed vs inferred status
      const hoodPart = intelligence.components.find(c => c.type === 'hood');
      expect(hoodPart?.status).toBe('observed');

      const rearPart = intelligence.components.find(c => c.type === 'back_torso');
      expect(rearPart?.status).toBe('inferred');

      const drawstringsPart = intelligence.components.find(c => c.type === 'drawstrings');
      expect(drawstringsPart?.status).toBe('procedural');
    });

    it('correctly maps rich fashion color names for earth tones', () => {
      expect(GarmentIntelligenceService.findClosestColorName('#4a2e18')).toBe('Dark Espresso Brown');
      expect(GarmentIntelligenceService.findClosestColorName('#b45309')).toBe('Warm Camel');
      expect(GarmentIntelligenceService.findClosestColorName('#0f172a')).toBe('Midnight Navy');
    });
  });

  // ── 4. MULTI-IMAGE CONSISTENCY & MATCHING ──
  describe('MultiImageGarmentMatcher', () => {
    it('confirms consistency when front and back photos match color profile', async () => {
      const res = await MultiImageGarmentMatcher.evaluateMultiViewInput({
        front: mockFrontFile,
        back: mockBackFile
      });

      expect(res.isConsistent).toBe(true);
      expect(res.confidence).toBeGreaterThanOrEqual(0.85);
      expect(res.mismatchedViews.length).toBe(0);
    });

    it('detects color distance variance when matching different garments', () => {
      const brown = '#4a2e18';
      const blue = '#1e3a8a';
      const distance = MultiImageGarmentMatcher.hexDistance(brown, blue);
      expect(distance).toBeGreaterThan(100); // Strong perceptual difference
    });
  });

  // ── 5. ADVANCED 3D GEOMETRY RECONSTRUCTION ──
  describe('GarmentGeometryProcessor', () => {
    it('reconstructs production-quality 3D hoodie with hood, kangaroo pocket, and drawstrings', () => {
      const hoodieMesh = GarmentGeometryProcessor.buildGarmentMesh('top', 'hoodie', {
        fit: 'relaxed',
        hasHood: true,
        hasKangarooPocket: true,
        hasDrawstrings: true
      });

      expect(hoodieMesh.vertexCount).toBeGreaterThan(600);
      expect(hoodieMesh.triangleCount).toBeGreaterThan(900);
      expect(hoodieMesh.positions.length).toBe(hoodieMesh.vertexCount * 3);
      expect(hoodieMesh.normals.length).toBe(hoodieMesh.vertexCount * 3);
      expect(hoodieMesh.uvs.length).toBe(hoodieMesh.vertexCount * 2);
      expect(hoodieMesh.indices.length).toBe(hoodieMesh.triangleCount * 3);

      // Verify boundary loops include hood aperture, cuffs, and hem
      const loopNames = hoodieMesh.boundaryLoops.map(l => l.name);
      expect(loopNames).toContain('neck');
      expect(loopNames).toContain('hem');
      expect(loopNames).toContain('left_cuff');
      expect(loopNames).toContain('right_cuff');
      expect(loopNames).toContain('hood_aperture');

      // Verify vertical height includes hood volume (reaches > 1.68m)
      expect(hoodieMesh.boundingBox.max[1]).toBeGreaterThanOrEqual(1.68);

      // Verify sagittal depth (>15cm depth)
      const depth = hoodieMesh.boundingBox.max[2] - hoodieMesh.boundingBox.min[2];
      expect(depth).toBeGreaterThan(0.18);

      // Verify components list
      expect(hoodieMesh.components?.length).toBeGreaterThanOrEqual(5);
    });

    it('reconstructs manifold 3D top geometry with proper collar and hem openings', () => {
      const topMesh = GarmentGeometryProcessor.buildGarmentMesh('top', 'tshirt', {
        sleeveLength: 'short',
        necklineType: 'crewneck',
        fit: 'regular'
      });

      expect(topMesh.vertexCount).toBeGreaterThan(100);
      expect(topMesh.triangleCount).toBeGreaterThan(150);

      const loopNames = topMesh.boundaryLoops.map(l => l.name);
      expect(loopNames).toContain('neck');
      expect(loopNames).toContain('hem');

      const depth = topMesh.boundingBox.max[2] - topMesh.boundingBox.min[2];
      expect(depth).toBeGreaterThan(0.15);
    });

    it('reconstructs manifold 3D trousers geometry with dual leg tubes', () => {
      const bottomMesh = GarmentGeometryProcessor.buildGarmentMesh('bottom', 'jeans', {
        fit: 'regular'
      });

      expect(bottomMesh.vertexCount).toBeGreaterThan(100);
      expect(bottomMesh.triangleCount).toBeGreaterThan(150);
      const loopNames = bottomMesh.boundaryLoops.map(l => l.name);
      expect(loopNames).toContain('waist');

      const height = bottomMesh.boundingBox.max[1] - bottomMesh.boundingBox.min[1];
      expect(height).toBeGreaterThan(0.50);
    });

    it('reconstructs flowing 3D dress geometry with continuous torso and flared hem', () => {
      const dressMesh = GarmentGeometryProcessor.buildGarmentMesh('dress', 'dress', {
        fit: 'regular'
      });

      expect(dressMesh.vertexCount).toBeGreaterThan(150);
      expect(dressMesh.triangleCount).toBeGreaterThan(200);
      const widthBottom = dressMesh.boundingBox.max[0] - dressMesh.boundingBox.min[0];
      expect(widthBottom).toBeGreaterThan(0.30);
    });
  });

  // ── 6. FABRIC PBR CHARACTERISTICS & TEXTURE ATLAS ──
  describe('GarmentTextureProcessor', () => {
    it('supports 9 distinct fabric characteristics including fleece with realistic PBR parameters', () => {
      const fabrics = ['cotton', 'fleece', 'denim', 'leather', 'wool', 'silk', 'polyester', 'linen', 'knitted'] as const;

      fabrics.forEach(f => {
        const props = GarmentTextureProcessor.getFabricProperties(f);
        expect(props.type).toBe(f);
        expect(props.roughness).toBeGreaterThanOrEqual(0.0);
        expect(props.roughness).toBeLessThanOrEqual(1.0);
        expect(props.metalness).toBeGreaterThanOrEqual(0.0);
        expect(props.metalness).toBeLessThanOrEqual(1.0);
        expect(props.isEstimated).toBe(true);
        expect(props.editorialNotes.length).toBeGreaterThan(10);
      });

      const fleece = GarmentTextureProcessor.getFabricProperties('fleece');
      expect(fleece.roughness).toBe(0.88);
      expect(fleece.normalIntensity).toBeGreaterThan(0.70);
    });

    it('synthesizes diffuse texture atlas from segmented photographic URLs', async () => {
      const res = await GarmentTextureProcessor.createDiffuseTextureAtlas(
        'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkWPjfDwAEeQHzj374ZAAAAABJRU5ErkJggg==',
        '#4a2e18'
      );
      expect(res.dataUrl).toBeDefined();
      expect(res.dataUrl.length).toBeGreaterThan(20);
    });
  });

  // ── 7. TOPOLOGY & QUALITY VALIDATION ──
  describe('GarmentTopologyValidator', () => {
    it('approves valid wearable 3D manifold geometry with detailed quality report', () => {
      const validMesh = GarmentGeometryProcessor.buildGarmentMesh('top', 'hoodie');
      const res = GarmentTopologyValidator.validateMesh(validMesh);

      expect(res.isValid).toBe(true);
      expect(res.isManifold).toBe(true);
      expect(res.hasDegenerateTriangles).toBe(false);
      expect(res.qualityScore).toBeGreaterThanOrEqual(90);

      // Verify quality report structure
      expect(res.qualityReport).toBeDefined();
      expect(res.qualityReport?.status).toBe('pass');
      expect(res.qualityReport?.checks.length).toBeGreaterThanOrEqual(5);
      expect(res.qualityReport?.observedComponents.length).toBeGreaterThan(0);
    });

    it('rejects flat 2D cards lacking sagittal body volume', () => {
      const flatMesh: ReconstructedMeshGeometry = {
        positions: new Float32Array([
          -0.2, 1.0, 0.0,
           0.2, 1.0, 0.0,
           0.2, 1.4, 0.0,
          -0.2, 1.4, 0.0
        ]),
        normals: new Float32Array([0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1]),
        uvs: new Float32Array([0, 0, 1, 0, 1, 1, 0, 1]),
        indices: new Uint32Array([0, 1, 2, 0, 2, 3]),
        boundaryLoops: [],
        vertexCount: 4,
        triangleCount: 2,
        boundingBox: {
          min: [-0.2, 1.0, 0.0],
          max: [0.2, 1.4, 0.0] // 0 depth!
        }
      };

      const res = GarmentTopologyValidator.validateMesh(flatMesh);
      expect(res.isValid).toBe(false);
      expect(res.issues.some(i => i.includes('sagittal 3D volume'))).toBe(true);
    });

    it('flags degenerate zero-area triangles', () => {
      const validMesh = GarmentGeometryProcessor.buildGarmentMesh('top', 'tshirt');
      const corruptedIndices = new Uint32Array(validMesh.indices);
      corruptedIndices[1] = corruptedIndices[0]; // i1 = i0

      const corruptedMesh: ReconstructedMeshGeometry = {
        ...validMesh,
        indices: corruptedIndices
      };

      const res = GarmentTopologyValidator.validateMesh(corruptedMesh);
      expect(res.hasDegenerateTriangles).toBe(true);
      expect(res.warnings.some(w => w.includes('degenerate triangle'))).toBe(true);
    });
  });

  // ── 8. GLB CONTAINER PACKAGING & EXPORT ──
  describe('GarmentAssetExporter', () => {
    it('constructs a valid binary glTF 2.0 buffer with correct magic headers', () => {
      const mesh = GarmentGeometryProcessor.buildGarmentMesh('top', 'hoodie');
      const fabric = GarmentTextureProcessor.getFabricProperties('fleece');
      const glb = GarmentAssetExporter.buildGlbBuffer(mesh, '#4a2e18', fabric);

      expect(glb.byteLength).toBeGreaterThan(100);

      const view = new DataView(glb);
      const magic = view.getUint32(0, true);
      const version = view.getUint32(4, true);
      const length = view.getUint32(8, true);

      // 0x46546C67 is 'glTF' in ASCII little-endian
      expect(magic).toBe(0x46546C67);
      expect(version).toBe(2);
      expect(length).toBe(glb.byteLength);

      // Chunk 0 (JSON): 0x4E4F534A ('JSON')
      const jsonChunkType = view.getUint32(16, true);
      expect(jsonChunkType).toBe(0x4E4F534A);
    });

    it('embeds diffuse texture atlas directly into binary glTF BIN chunk', () => {
      const mesh = GarmentGeometryProcessor.buildGarmentMesh('top', 'hoodie');
      const fabric = GarmentTextureProcessor.getFabricProperties('fleece');
      const mockTextureUri = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkWPjfDwAEeQHzj374ZAAAAABJRU5ErkJggg==';

      const glb = GarmentAssetExporter.buildGlbBuffer(mesh, '#4a2e18', fabric, mockTextureUri);
      expect(glb.byteLength).toBeGreaterThan(150);

      const view = new DataView(glb);
      const magic = view.getUint32(0, true);
      expect(magic).toBe(0x46546C67);
    });

    it('generates anatomical fitting metadata with body occlusion masks', () => {
      const metaHoodie = GarmentAssetExporter.generateFittingMetadata('top', 'hoodie');
      expect(metaHoodie.targetSlot).toBe('top');
      expect(metaHoodie.occlusionMaskIds).toContain('Body_Chest');
      expect(metaHoodie.anchorBone).toBe('spine02');

      const metaBottom = GarmentAssetExporter.generateFittingMetadata('bottom', 'jeans');
      expect(metaBottom.targetSlot).toBe('bottom');
      expect(metaBottom.occlusionMaskIds).toContain('Body_Pelvis');
      expect(metaBottom.anchorBone).toBe('pelvis');
    });
  });

  // ── 9. LOCAL PARAMETRIC RECONSTRUCTION ADAPTER ──
  describe('LocalParametricReconstructionAdapter', () => {
    it('executes full end-to-end reconstruction from multi-view inputs preserving dark brown hoodie', async () => {
      const adapter = new LocalParametricReconstructionAdapter();
      const progressSteps: number[] = [];

      const asset = await adapter.reconstruct(
        { 
          front: mockFrontFile, 
          back: mockBackFile,
          hoodDetail: mockDetailFile 
        },
        'top',
        {
          subcategory: 'hoodie',
          fabricType: 'fleece',
          fit: 'relaxed',
          onProgress: (pct) => progressSteps.push(pct)
        }
      );

      expect(asset).toBeDefined();
      expect(asset.category).toBe('top');
      expect(asset.subcategory).toBe('hoodie');
      expect(asset.fabric.type).toBe('fleece');
      expect(asset.qualityScore).toBeGreaterThanOrEqual(90);
      expect(asset.qualityReport).toBeDefined();
      expect(asset.intelligence?.hasHood).toBe(true);
      expect(asset.intelligence?.hasKangarooPocket).toBe(true);
      expect(asset.glbArrayBuffer).toBeDefined();
      expect(asset.knownLimitations.length).toBeGreaterThan(0);
      expect(progressSteps.length).toBeGreaterThan(3);
      expect(progressSteps[progressSteps.length - 1]).toBe(100);
    });
  });

  // ── 10. ASYNCHRONOUS JOB MANAGER ──
  describe('GarmentReconstructionJobManager', () => {
    let jobManager: GarmentReconstructionJobManager;

    beforeEach(() => {
      jobManager = new GarmentReconstructionJobManager(new LocalParametricReconstructionAdapter());
    });

    it('manages asynchronous job lifecycle and progress notifications', async () => {
      const jobId = await jobManager.submitJob(
        { front: mockFrontFile, back: mockBackFile },
        'top',
        { fabricType: 'fleece', subcategory: 'hoodie' }
      );

      expect(jobId).toMatch(/^job_/);
      const initial = jobManager.getJob(jobId);
      expect(initial?.status).toBe('queued');

      await new Promise<void>((resolve) => {
        const unsubscribe = jobManager.subscribe(jobId, (prog) => {
          if (prog.status === 'completed' || prog.status === 'failed') {
            unsubscribe();
            resolve();
          }
        });
      });

      const completed = jobManager.getJob(jobId);
      expect(completed?.status).toBe('completed');
      expect(completed?.progressPercent).toBe(100);
      expect(completed?.result).toBeDefined();
      expect(completed?.result?.category).toBe('top');
    });

    it('supports job cancellation before completion', async () => {
      const jobId = await jobManager.submitJob(
        { front: mockFrontFile },
        'top'
      );

      const cancelled = jobManager.cancelJob(jobId);
      expect(cancelled).toBe(true);

      const current = jobManager.getJob(jobId);
      expect(current?.status).toBe('cancelled');
    });
  });

  // ── 11. FITTING ENGINE INTEGRATION ──
  describe('GarmentFittingEngine Integration', () => {
    it('computes fitting metrics and passes geometry validation', () => {
      const mesh = GarmentGeometryProcessor.buildGarmentMesh('top', 'hoodie');
      const fabric = GarmentTextureProcessor.getFabricProperties('fleece');
      const asset = GarmentAssetExporter.exportGarmentAsset(
        'test_fit_asset',
        'Fitted Hoodie',
        'top',
        'hoodie',
        mesh,
        fabric,
        '#4a2e18',
        95
      );

      expect(asset.fittingMetadata.targetSlot).toBe('top');
      expect(asset.fittingMetadata.occlusionMaskIds.length).toBeGreaterThan(0);

      const depth = asset.geometry.boundingBox.max[2] - asset.geometry.boundingBox.min[2];
      expect(depth).toBeGreaterThan(0.12);
    });
  });

  // ── 12. PHASE 5: CRITICAL PIPELINE FIX VERIFICATION ──
  describe('Phase 5 — Garment Shape Detection, Segmentation, Geometry Reconstruction & Correct Texture Mapping', () => {
    it('enforces non-overlapping component-isolated UV islands', () => {
      const frontIsland = GARMENT_UV_ISLANDS.FRONT_TORSO;
      const backIsland = GARMENT_UV_ISLANDS.BACK_TORSO;
      const leftSleeve = GARMENT_UV_ISLANDS.LEFT_SLEEVE;
      const rightSleeve = GARMENT_UV_ISLANDS.RIGHT_SLEEVE;
      const hoodIsland = GARMENT_UV_ISLANDS.HOOD;
      const pocketIsland = GARMENT_UV_ISLANDS.POCKET_TRIM;

      // Front and Back Torso must be strictly separated horizontally
      expect(frontIsland.uMax).toBeLessThanOrEqual(backIsland.uMin);

      // Sleeves must be strictly separated from Torso vertically
      expect(frontIsland.vMax).toBeLessThanOrEqual(leftSleeve.vMin);
      expect(backIsland.vMax).toBeLessThanOrEqual(rightSleeve.vMin);

      // Hood must be separated from Sleeves vertically
      expect(leftSleeve.vMax).toBeLessThanOrEqual(hoodIsland.vMin);
      expect(rightSleeve.vMax).toBeLessThanOrEqual(pocketIsland.vMin);
    });

    it('generates 3D hoodie geometry where front and rear panels use isolated UV islands', () => {
      const hoodie = GarmentGeometryProcessor.buildGarmentMesh('top', 'hoodie');
      const uvs = hoodie.uvs;
      const pos = hoodie.positions;

      let frontVertexCount = 0;
      let backVertexCount = 0;

      for (let i = 0; i < hoodie.vertexCount; i++) {
        const u = uvs[i * 2];
        const v = uvs[i * 2 + 1];
        const z = pos[i * 3 + 2];

        // Check if inside Front Torso UV island
        if (
          u >= GARMENT_UV_ISLANDS.FRONT_TORSO.uMin &&
          u <= GARMENT_UV_ISLANDS.FRONT_TORSO.uMax &&
          v >= GARMENT_UV_ISLANDS.FRONT_TORSO.vMin &&
          v <= GARMENT_UV_ISLANDS.FRONT_TORSO.vMax
        ) {
          frontVertexCount++;
          expect(z).toBeGreaterThanOrEqual(-0.001);
        }

        // Check if inside Back Torso UV island
        if (
          u >= GARMENT_UV_ISLANDS.BACK_TORSO.uMin &&
          u <= GARMENT_UV_ISLANDS.BACK_TORSO.uMax &&
          v >= GARMENT_UV_ISLANDS.BACK_TORSO.vMin &&
          v <= GARMENT_UV_ISLANDS.BACK_TORSO.vMax
        ) {
          backVertexCount++;
          expect(z).toBeLessThanOrEqual(0.001);
        }
      }

      expect(frontVertexCount).toBeGreaterThan(100);
      expect(backVertexCount).toBeGreaterThan(100);
    });

    it('identifies rich category components for shirt and trousers', () => {
      const segMock = GarmentSegmentationService.generateMockSegmentation();
      
      // Shirt components
      const shirtIntel = GarmentIntelligenceService.analyzeGarment(segMock, 'top', 'shirt');
      const shirtCompTypes = shirtIntel.components.map(c => c.type);
      expect(shirtCompTypes).toContain('collar');
      expect(shirtCompTypes).toContain('placket');
      expect(shirtCompTypes).toContain('buttons');
      expect(shirtCompTypes).toContain('hem');

      // Trousers components
      const pantsIntel = GarmentIntelligenceService.analyzeGarment(segMock, 'bottom', 'trousers');
      const pantsCompTypes = pantsIntel.components.map(c => c.type);
      expect(pantsCompTypes).toContain('waistband');
      expect(pantsCompTypes).toContain('left_leg');
      expect(pantsCompTypes).toContain('right_leg');
      expect(pantsCompTypes).toContain('fly');
    });

    it('preserves empty space between sleeves and torso without background bleed', () => {
      const seg = GarmentSegmentationService.generateMockSegmentation();
      expect(seg.hasInternalOpenings).toBe(true);
      expect(seg.pureFabricSampleRgb).toBeDefined();
      expect(seg.pureFabricSampleRgb?.[0]).toBe(74); // Dark espresso brown R
      expect(seg.componentBounds?.length).toBeGreaterThanOrEqual(4);
    });
  });

  // ── 3D-FIRST WARDROBE STORAGE AND PREVIEW SYSTEM ──
  describe('3D-First Wardrobe Storage and Mannequin Preview System', () => {
    it('generates a photorealistic 3D mannequin visual thumbnail from reconstructed mesh', async () => {
      const hoodieGeom = GarmentGeometryProcessor.buildHoodieGeometry();
      const renderer = GarmentMannequinPreviewRenderer.getInstance();
      
      const thumbUrl = await renderer.renderGarmentThumbnail(
        hoodieGeom,
        undefined,
        '#4a2e18',
        'hoodie'
      );

      expect(thumbUrl).toBeDefined();
      expect(typeof thumbUrl).toBe('string');
      expect(thumbUrl.startsWith('data:image/png;base64,')).toBe(true);
    });

    it('LocalParametricReconstructionAdapter attaches mannequin 3D thumbnail instead of original photo', async () => {
      const adapter = new LocalParametricReconstructionAdapter();
      const asset = await adapter.reconstruct(
        { front: mockBrownHoodieFile },
        'top',
        { subcategory: 'hoodie' }
      );

      // Verify asset holds 3D preview thumbnail, not raw input photo
      expect(asset.thumbnailUrl).toBeDefined();
      expect(asset.thumbnailUrl?.startsWith('data:image/png;base64,')).toBe(true);
      // Ensure GLB binary container was assembled
      expect(asset.glbArrayBuffer).toBeDefined();
      expect(asset.glbArrayBuffer!.byteLength).toBeGreaterThan(100);
      // Ensure 3D geometry is intact
      expect(asset.geometry.triangleCount).toBeGreaterThan(2000);
    });

    it('GarmentAssetExporter stores thumbnailUrl and fitting metadata without raw photo retention', () => {
      const geom = GarmentGeometryProcessor.buildTopsGeometry('shirt');
      const fabric = GarmentTextureProcessor.getFabricProperties('cotton');
      const mockThumb = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHe';

      const asset = GarmentAssetExporter.exportGarmentAsset(
        'rec_test_123',
        'COTTON CREWNECK',
        'top',
        'shirt',
        geom,
        fabric,
        '#ffffff',
        95,
        {
          thumbnailUrl: mockThumb
        }
      );

      expect(asset.thumbnailUrl).toBe(mockThumb);
      expect(asset.fittingMetadata.targetSlot).toBe('top');
      expect((asset as any).originalPhoto).toBeUndefined();
    });

    it('handles reconstruction failure cleanly without persisting corrupted or false items', async () => {
      const adapter = new LocalParametricReconstructionAdapter();
      const invalidFile = new File([new Uint8Array(200)], 'invalid.bin', { type: 'application/octet-stream' });
      
      let errorOccurred = false;
      try {
        await adapter.reconstruct(
          { front: invalidFile },
          'top',
          { subcategory: 'hoodie' }
        );
      } catch (err: any) {
        errorOccurred = true;
        expect(err.message).toBeDefined();
      }

      expect(errorOccurred).toBe(true);
    });
  });
});
