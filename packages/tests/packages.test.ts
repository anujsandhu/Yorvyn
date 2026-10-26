import test from 'node:test';
import assert from 'node:assert/strict';

import {
  // 1. shared-types
  computeBoundingBox,
  // 2. avatar-core
  createDefaultAnthropometry,
  normalizeAnthropometry,
  calculateAnatomicalHeights,
  AVATAR_COORDINATE_CONVENTIONS,
  // 3. avatar-generation
  ParametricAvatarGeneratorProvider,
  // 4. avatar-rigging
  StandardHumanoidRiggingService,
  STANDARD_HUMANOID_65_BONES,
  // 5. avatar-animation
  StandardAnimationController,
  createStandardActionClips,
  // 6. garment-core
  StandardGarmentValidator,
  extractBoundaryLoops,
  GARMENT_CATEGORIES,
  // 7. garment-reconstruction
  ClientGarmentReconstructionService,
  // 8. garment-fitting
  StandardGarmentFitter,
  // 9. materials-textures
  StandardTextureSynthesizer,
  parseHexColor,
  createRgbaPng,
  // 10. three-renderer
  calculateCameraFraming,
  HeadlessStudioRenderer,
  YORVYN_STUDIO_LIGHTING,
  // 11. asset-pipeline
  StandardAssetPipeline,
  // 12. ai-adapters
  LocalCpuWorkerAdapter,
  createAIWorkerAdapter
} from '../index.ts';

test('Package 1: @yorvyn/shared-types — computeBoundingBox & conventions', () => {
  const dummyMesh = {
    positions: new Float32Array([-1, 0, -0.5, 1, 1.8, 0.5]),
    normals: new Float32Array(6),
    uvs: new Float32Array(4),
    indices: new Uint32Array([0, 1, 0])
  };
  const bbox = computeBoundingBox(dummyMesh);
  assert.equal(bbox.min.x, -1);
  assert.equal(bbox.min.y, 0);
  assert.equal(bbox.min.z, -0.5);
  assert.equal(bbox.max.x, 1);
  assert.ok(Math.abs(bbox.max.y - 1.8) < 0.0001);
  assert.equal(bbox.max.z, 0.5);
  assert.equal(bbox.size.x, 2);
  assert.ok(Math.abs(bbox.size.y - 1.8) < 0.0001);
  assert.equal(bbox.size.z, 1);
});

test('Package 2: @yorvyn/avatar-core — anthropometry calculations', () => {
  assert.equal(AVATAR_COORDINATE_CONVENTIONS.axisUp, '+Y');
  assert.equal(AVATAR_COORDINATE_CONVENTIONS.axisFront, '+Z');

  const anthropometry = createDefaultAnthropometry();
  assert.equal(anthropometry.height, 1.70);
  const normalized = normalizeAnthropometry({ ...anthropometry, height: 2.5 });
  assert.equal(normalized.height, 2.15); // clamped

  const heights = calculateAnatomicalHeights(anthropometry);
  assert.ok(heights.headTop > heights.chest);
  assert.ok(heights.chest > heights.waist);
  assert.ok(heights.waist > heights.crotch);
});

test('Package 3: @yorvyn/avatar-generation — parametric avatar synthesis & GLB export', async () => {
  const provider = new ParametricAvatarGeneratorProvider();
  await provider.initialize();
  const character = await provider.buildCharacter(createDefaultAnthropometry());

  assert.ok(character.mesh.positions.length > 0);
  assert.ok(character.mesh.indices.length > 0);
  assert.equal(character.metadata?.rigStandard, 'standard-65-bone');

  const glbBytes = await provider.exportGlbBuffer(character);
  assert.ok(glbBytes.byteLength > 100);
  // Check 'glTF' magic header in little endian (0x46546c67)
  const view = new DataView(glbBytes.buffer);
  assert.equal(view.getUint32(0, true), 0x46546c67);
  assert.equal(view.getUint32(4, true), 2);
});

test('Package 4: @yorvyn/avatar-rigging — 65-bone rig generation & skinning weights', () => {
  const riggingService = new StandardHumanoidRiggingService();
  const rig = riggingService.generateRig(1.75);

  assert.equal(rig.boneNames.length, STANDARD_HUMANOID_65_BONES.length);
  assert.ok(rig.boneNames.includes('Hips'));
  assert.ok(rig.boneNames.includes('Head'));
  assert.ok(rig.boneNames.includes('LeftHandThumb1'));

  const dummyMesh = {
    positions: new Float32Array([0, 1.70, 0, 0, 0.9, 0]),
    normals: new Float32Array(6),
    uvs: new Float32Array(4),
    indices: new Uint32Array([0, 1, 0])
  };
  const weights = riggingService.computeSkinningWeights(dummyMesh, rig);
  assert.equal(weights.jointIndices.length, 8); // 2 vertices * 4 joints
  assert.equal(weights.jointWeights.length, 8);
  // Verify sum of weights for vertex 0 is approx 1.0
  const sum0 = weights.jointWeights[0] + weights.jointWeights[1] + weights.jointWeights[2] + weights.jointWeights[3];
  assert.ok(Math.abs(sum0 - 1.0) < 0.001);
});

test('Package 5: @yorvyn/avatar-animation — clip registry & state controller', () => {
  const clips = createStandardActionClips();
  assert.equal(clips.length, 4);
  const controller = new StandardAnimationController(clips);

  controller.play('Idle');
  assert.equal(controller.getCurrentClipName(), 'Idle');

  controller.update(1.0);
  assert.equal(controller.getCurrentClipName(), 'Idle');

  controller.playOneShot('Wave', 'Idle', 0.2);
  assert.equal(controller.getCurrentClipName(), 'Wave');

  // Advance time past Wave duration (2.2s)
  controller.update(2.5);
  // Should have transitioned back to Idle
  assert.equal(controller.getCurrentClipName(), 'Idle');
});

test('Package 6: @yorvyn/garment-core — garment validation & boundary loops', () => {
  const validator = new StandardGarmentValidator();
  assert.ok(GARMENT_CATEGORIES.includes('t-shirt'));

  const validMesh = {
    positions: new Float32Array([
      -0.2, 0.8, 0,
      0.2, 0.8, 0,
      0, 1.4, 0
    ]),
    normals: new Float32Array([0, 0, 1, 0, 0, 1, 0, 0, 1]),
    uvs: new Float32Array([0, 0, 1, 0, 0.5, 1]),
    indices: new Uint32Array([0, 1, 2])
  };

  const result = validator.validateManifold(validMesh, 't-shirt');
  assert.equal(result.isValid, true);
  assert.equal(result.triangleCount, 1);

  const loops = extractBoundaryLoops(validMesh, 't-shirt');
  assert.ok(loops.length > 0);
});

test('Package 7: @yorvyn/garment-reconstruction — analysis & separable garment synthesis', async () => {
  const reconstructor = new ClientGarmentReconstructionService();
  const input = {
    jobId: 'job-test-101',
    frontImageBytes: new Uint8Array([0x45, 0x82, 0xC3, 0x99]),
    hintCategory: 'hoodie',
    imageMimeType: 'image/jpeg'
  };

  const analysis = await reconstructor.analyzeGarmentPhoto(input);
  assert.equal(analysis.category, 'hoodie');
  assert.ok(analysis.confidence > 0.9);

  let stageLogged = '';
  const garment = await reconstructor.reconstructGarment(input, analysis, p => {
    stageLogged = p.stage;
  });

  assert.equal(stageLogged, 'completed');
  assert.equal(garment.isSeparableGarment, true);
  assert.ok(garment.mesh.positions.length > 0);
  assert.ok(garment.boundaryLoops.length > 0);
});

test('Package 8: @yorvyn/garment-fitting — avatar fitting & occlusion masks', async () => {
  const fitter = new StandardGarmentFitter();
  const avatarGenerator = new ParametricAvatarGeneratorProvider();
  const avatar = await avatarGenerator.buildCharacter(createDefaultAnthropometry());

  const dummyGarment = {
    metadata: {
      id: 'g-1',
      name: 'T-Shirt',
      category: 't-shirt',
      color: '#3B82F6',
      fabricType: 'cotton',
      tags: ['top'],
      createdAt: new Date().toISOString()
    },
    mesh: avatar.mesh,
    materials: [],
    boundaryLoops: [],
    isSeparableGarment: true as const
  };

  const fitResult = await fitter.fitToAvatar(dummyGarment, avatar);
  assert.ok(fitResult.appliedScale[0] > 0);
  assert.ok(fitResult.appliedScale[1] > 0);
  assert.ok(fitResult.maskedBodyMaterialIds.includes('Body_Chest'));
});

test('Package 9: @yorvyn/materials-textures — PBR map synthesis & minimal PNG generation', async () => {
  const hex = '#3B82F6';
  const rgb = parseHexColor(hex);
  assert.equal(rgb.r, 0x3b);
  assert.equal(rgb.g, 0x82);
  assert.equal(rgb.b, 0xf6);

  const pngBytes = createRgbaPng(2, 2, 255, 0, 0, 255);
  // Check PNG magic bytes
  assert.equal(pngBytes[0], 137);
  assert.equal(pngBytes[1], 80); // 'P'
  assert.equal(pngBytes[2], 78); // 'N'
  assert.equal(pngBytes[3], 71); // 'G'

  const synth = new StandardTextureSynthesizer();
  const maps = await synth.synthesizePbrMaps(new Uint8Array(10), undefined, '#3B82F6');
  assert.ok(maps.diffusePngBytes.byteLength > 0);
  assert.ok(maps.normalPngBytes && maps.normalPngBytes.byteLength > 0);
});

test('Package 10: @yorvyn/three-renderer — camera framing & lighting presets', () => {
  const portraitFraming = calculateCameraFraming('portrait', 1.70);
  assert.equal(portraitFraming.fov, 30);
  assert.ok(portraitFraming.position[1] > 1.0); // Head/chest level

  const fullFraming = calculateCameraFraming('full', 1.70);
  assert.equal(fullFraming.fov, 30);
  assert.ok(fullFraming.position[2] > portraitFraming.position[2]); // Camera further back for full body

  assert.ok(YORVYN_STUDIO_LIGHTING.keyLight.intensity > 1.0);

  const renderer = new HeadlessStudioRenderer();
  renderer.initialize({
    container: {} as any,
    canvas: {} as any,
    initialCameraView: 'portrait'
  });
  renderer.setCameraMode('portrait', 1.70);
  assert.equal(renderer.getFraming().fov, 30);
  renderer.toggleWireframe(true);
  assert.equal(renderer.isWireframe(), true);
});

test('Package 11: @yorvyn/asset-pipeline — GLB packaging & wardrobe persistence', async () => {
  const pipeline = new StandardAssetPipeline();
  const avatarGenerator = new ParametricAvatarGeneratorProvider();
  const character = await avatarGenerator.buildCharacter(createDefaultAnthropometry());

  const garment = {
    metadata: {
      id: 'g-test-42',
      name: 'Designer Polo',
      category: 'shirt',
      color: '#10B981',
      fabricType: 'knit',
      tags: ['shirt'],
      createdAt: new Date().toISOString()
    },
    mesh: character.mesh,
    materials: [],
    boundaryLoops: [],
    isSeparableGarment: true as const
  };

  const texturePng = createRgbaPng(2, 2, 16, 185, 129, 255);
  const glbBytes = await pipeline.exportGlb(garment, texturePng);

  assert.ok(glbBytes.byteLength > 100);
  const dv = new DataView(glbBytes.buffer);
  assert.equal(dv.getUint32(0, true), 0x46546c67); // glTF

  const thumbnailBytes = await pipeline.renderThumbnail(garment, texturePng);
  assert.equal(thumbnailBytes[0], 137); // PNG

  const saved = await pipeline.persistToWardrobe('job-42', glbBytes, thumbnailBytes, garment);
  assert.equal(saved.wardrobeItemId, 'item-job-42');
  assert.ok(saved.glbRelativeUrl.endsWith('.glb'));
});

test('Package 12: @yorvyn/ai-adapters — CPU worker execution & GPU adapter factory', async () => {
  const cpuAdapter = new LocalCpuWorkerAdapter();
  assert.equal(cpuAdapter.executionTarget, 'local_cpu_worker');
  assert.equal(cpuAdapter.isAvailable, true);

  const health = await cpuAdapter.checkHealth();
  assert.equal(health.available, true);

  const factoryAdapter = createAIWorkerAdapter('local_cpu_worker');
  assert.equal(factoryAdapter.executionTarget, 'local_cpu_worker');

  const gpuAdapter = createAIWorkerAdapter('remote_gpu_cluster', 'http://127.0.0.1:9999/gpu');
  assert.equal(gpuAdapter.executionTarget, 'remote_gpu_cluster');
});
