import { describe, it, expect } from 'vitest';
import * as THREE from 'three';
import {
  GarmentCategoryRegistry,
  GarmentAssetInspector,
  UniversalGarmentFittingOrchestrator,
  GarmentAvatarFittingEngine,
} from '../index';

function buildDetailedAvatar(): THREE.Group {
  const root = new THREE.Group();
  root.name = 'avatar_detailed';

  const hips = new THREE.Bone();
  hips.name = 'Hips';
  hips.position.set(0, 0.94, 0);

  const spine = new THREE.Bone();
  spine.name = 'Spine';
  spine.position.set(0, 0.14, 0);
  hips.add(spine);

  const spine2 = new THREE.Bone();
  spine2.name = 'Spine2';
  spine2.position.set(0, 0.24, 0);
  spine.add(spine2);

  const neck = new THREE.Bone();
  neck.name = 'Neck';
  neck.position.set(0, 0.17, 0);
  spine2.add(neck);

  const head = new THREE.Bone();
  head.name = 'Head';
  head.position.set(0, 0.15, 0);
  neck.add(head);

  const lShoulder = new THREE.Bone();
  lShoulder.name = 'LeftShoulder';
  lShoulder.position.set(0.10, 0.12, 0);
  spine2.add(lShoulder);

  const lArm = new THREE.Bone();
  lArm.name = 'LeftArm';
  lArm.position.set(0.08, 0, 0);
  lShoulder.add(lArm);

  const lFore = new THREE.Bone();
  lFore.name = 'LeftForeArm';
  lFore.position.set(0.06, -0.22, 0);
  lArm.add(lFore);

  const lHand = new THREE.Bone();
  lHand.name = 'LeftHand';
  lHand.position.set(0.04, -0.20, 0);
  lFore.add(lHand);

  const rShoulder = new THREE.Bone();
  rShoulder.name = 'RightShoulder';
  rShoulder.position.set(-0.10, 0.12, 0);
  spine2.add(rShoulder);

  const rArm = new THREE.Bone();
  rArm.name = 'RightArm';
  rArm.position.set(-0.08, 0, 0);
  rShoulder.add(rArm);

  const lUpLeg = new THREE.Bone();
  lUpLeg.name = 'LeftUpLeg';
  lUpLeg.position.set(0.09, -0.06, 0);
  hips.add(lUpLeg);

  const lLeg = new THREE.Bone();
  lLeg.name = 'LeftLeg';
  lLeg.position.set(0, -0.40, 0);
  lUpLeg.add(lLeg);

  const lFoot = new THREE.Bone();
  lFoot.name = 'LeftFoot';
  lFoot.position.set(0, -0.42, 0);
  lLeg.add(lFoot);

  root.add(hips);
  root.updateMatrixWorld(true);

  const bodyGeo = new THREE.CylinderGeometry(0.175, 0.16, 1.72, 20, 14);
  bodyGeo.translate(0, 0.86, 0);
  const vCount = bodyGeo.attributes.position.count;
  bodyGeo.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(new Uint16Array(vCount * 4), 4));
  const w = new Float32Array(vCount * 4);
  for (let i = 0; i < vCount; i++) w[i * 4] = 1.0;
  bodyGeo.setAttribute('skinWeight', new THREE.Float32BufferAttribute(w, 4));

  const bodyMesh = new THREE.SkinnedMesh(bodyGeo, new THREE.MeshStandardMaterial({ name: 'body_skin' }));
  bodyMesh.name = 'Alex_1';
  const skeleton = new THREE.Skeleton([hips, spine, spine2, neck, head, lShoulder, lArm, lFore, lHand, rShoulder, rArm, lUpLeg, lLeg, lFoot]);
  bodyMesh.bind(skeleton);
  root.add(bodyMesh);
  root.updateMatrixWorld(true);
  return root;
}

function makeMesh(name: string, w: number, h: number, d: number, yCenter = 1.25): THREE.Group {
  const g = new THREE.Group();
  g.name = name;
  const geo = new THREE.BoxGeometry(w, h, d, 6, 8, 4);
  geo.translate(0, yCenter, 0);
  const mat = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.7 });
  const m = new THREE.Mesh(geo, mat);
  m.name = name;
  g.add(m);
  return g;
}

describe('Phase 17.5 Universal Garment & Accessory Fitting Orchestrator', () => {
  it('resolves all taxonomy domains with honest capability states', () => {
    expect(GarmentCategoryRegistry.resolve('tops', 'tshirt').capabilityState).toBe('VERIFIED');
    expect(GarmentCategoryRegistry.resolve('full_body', 'saree').capabilityState).toBe('DECLARED');
    expect(GarmentCategoryRegistry.resolve('footwear', 'sneakers').fittingStrategy).toBe('footwear');
    expect(GarmentCategoryRegistry.resolve('accessory', 'sunglasses').layerSlot).toBe('eyewear');
    expect(GarmentCategoryRegistry.resolve('accessory', 'watch').layerSlot).toBe('jewelry');
  });

  it('prevents phantom-hood slicing and oversized shoulders on single-mesh T-shirt tops', () => {
    const avatar = buildDetailedAvatar();
    const singleTshirt = makeMesh('single_tshirt', 0.42, 0.56, 0.24, 1.26);
    const stages: string[] = [];

    const res = UniversalGarmentFittingOrchestrator.fitAndAttach(singleTshirt, avatar, {
      category: 'top',
      onStageChange: (s) => stages.push(s),
    });

    expect(res.success).toBe(true);
    expect(stages).toContain('inspecting_garment');
    expect(stages).toContain('evaluating_quality');
    // Bounds scale must stay tightly controlled (no 1.4x-1.6x shoulder ballooning)
    expect(res.diagnostics.appliedScale[0]).toBeLessThanOrEqual(1.25);
    expect(res.diagnostics.appliedScale[2]).toBeLessThanOrEqual(1.25);

    // Top of the T-shirt should stay near neck (~1.49-1.56m), NOT ripped 19cm upward as a phantom hood (~1.72m+)
    const fittedBox = new THREE.Box3().setFromObject(res.attachedObject!);
    expect(fittedBox.max.y).toBeLessThan(1.62);
    expect(res.sourceSnapshot.fingerprint).toMatch(/^v175_/);
  });

  it('preserves immutable source geometry snapshot untouched after fitting', () => {
    const avatar = buildDetailedAvatar();
    const src = makeMesh('kurta_top', 0.44, 0.78, 0.25, 1.15);
    const srcMesh = src.children[0] as THREE.Mesh;
    const origY0 = srcMesh.geometry.attributes.position.getY(0);

    const res = UniversalGarmentFittingOrchestrator.fitAndAttach(src, avatar, {
      category: 'top',
      subcategory: 'kurta',
    });

    expect(res.success).toBe(true);
    expect(srcMesh.geometry.attributes.position.getY(0)).toBe(origY0);
    expect(GarmentAssetInspector.inspect(src).sourceFingerprint).toBe(res.sourceSnapshot.fingerprint);
  });

  it('supports multi-garment layering with footwear, headwear, belt, eyewear, bag, and watch coexisting', () => {
    const avatar = buildDetailedAvatar();

    const topRes = UniversalGarmentFittingOrchestrator.fitAndAttach(
      makeMesh('tshirt', 0.42, 0.56, 0.24, 1.25),
      avatar,
      { category: 'top', preserveOtherLayers: true }
    );
    const shoesRes = UniversalGarmentFittingOrchestrator.fitAndAttach(
      makeMesh('sneakers', 0.11, 0.10, 0.27, 0.05),
      avatar,
      { category: 'footwear', subcategory: 'sneakers', preserveOtherLayers: true }
    );
    const capRes = UniversalGarmentFittingOrchestrator.fitAndAttach(
      makeMesh('baseball_cap', 0.20, 0.14, 0.24, 0),
      avatar,
      { category: 'headwear', subcategory: 'cap', preserveOtherLayers: true }
    );
    const beltRes = UniversalGarmentFittingOrchestrator.fitAndAttach(
      makeMesh('leather_belt', 0.34, 0.04, 0.22, 0),
      avatar,
      { category: 'accessory', subcategory: 'belt', preserveOtherLayers: true }
    );
    const glassesRes = UniversalGarmentFittingOrchestrator.fitAndAttach(
      makeMesh('sunglasses', 0.14, 0.05, 0.15, 0),
      avatar,
      { category: 'accessory', subcategory: 'sunglasses', preserveOtherLayers: true }
    );
    const bagRes = UniversalGarmentFittingOrchestrator.fitAndAttach(
      makeMesh('backpack', 0.30, 0.40, 0.16, 0),
      avatar,
      { category: 'accessory', subcategory: 'backpack', preserveOtherLayers: true }
    );
    const watchRes = UniversalGarmentFittingOrchestrator.fitAndAttach(
      makeMesh('wrist_watch', 0.06, 0.02, 0.06, 0),
      avatar,
      { category: 'accessory', subcategory: 'watch', preserveOtherLayers: true }
    );

    expect(topRes.success).toBe(true);
    expect(shoesRes.success).toBe(true);
    expect(capRes.success).toBe(true);
    expect(beltRes.success).toBe(true);
    expect(glassesRes.success).toBe(true);
    expect(bagRes.success).toBe(true);
    expect(watchRes.success).toBe(true);

    // Every item must remain attached simultaneously in the avatar scene graph
    expect(avatar.getObjectByName('custom_ai_garment_fitted')).toBeDefined();
    expect(avatar.getObjectByName('custom_ai_accessory_footwear')).toBeDefined();
    expect(avatar.getObjectByName('custom_ai_accessory_headwear')).toBeDefined();
    expect(avatar.getObjectByName('custom_ai_accessory_belt')).toBeDefined();
    expect(avatar.getObjectByName('custom_ai_accessory_eyewear')).toBeDefined();
    expect(avatar.getObjectByName('custom_ai_accessory_bag')).toBeDefined();
    expect(avatar.getObjectByName('custom_ai_accessory_jewelry')).toBeDefined();

    // Replacing eyewear must not remove fitted garment or shoes
    const sunglasses2 = UniversalGarmentFittingOrchestrator.fitAndAttach(
      makeMesh('aviators', 0.14, 0.05, 0.15, 0),
      avatar,
      { category: 'accessory', subcategory: 'glasses', preserveOtherLayers: true }
    );
    expect(sunglasses2.success).toBe(true);
    expect(avatar.getObjectByName('custom_ai_garment_fitted')).toBeDefined();
    expect(avatar.getObjectByName('custom_ai_accessory_footwear')).toBeDefined();
    let eyewearCount = 0;
    avatar.traverse((o) => {
      if (o.name === 'custom_ai_accessory_eyewear') eyewearCount++;
    });
    expect(eyewearCount).toBe(1);
  });

  it('rejects empty/corrupted garment assets with 10-domain quality failure report and leaves avatar clean', () => {
    const avatar = buildDetailedAvatar();
    const empty = new THREE.Group();
    const res = UniversalGarmentFittingOrchestrator.fitAndAttach(empty, avatar, { category: 'top' });

    expect(res.success).toBe(false);
    expect(res.stageReached).toBe('failed');
    expect(res.qualityReport.overallStatus).toBe('FAILED');
    expect(res.qualityReport.domains).toHaveLength(10);
    expect(res.error).toMatch(/validation failed/i);
    GarmentAvatarFittingEngine.detachGarment(avatar);
  });

  it('fits real reconstructed GLB asset (job_e2e_18bfee08.glb) without phantom hood or shoulder inflation', async () => {
    const fsMod: any = await import(/* @vite-ignore */ ('node:fs' as string));
    const pathMod: any = await import(/* @vite-ignore */ ('node:path' as string));
    const proc: any = (globalThis as any).process;
    const glbPath = pathMod.resolve(proc.cwd(), '../models/generated_3d/job_e2e_18bfee08.glb');
    if (!fsMod.existsSync(glbPath)) return;

    const raw = fsMod.readFileSync(glbPath);
    const dv = new DataView(raw.buffer, raw.byteOffset, raw.byteLength);
    const c0Len = dv.getUint32(12, true);
    const gltf = JSON.parse(raw.subarray(20, 20 + c0Len).toString('utf8'));
    const binOffset = 20 + c0Len + 8;
    const bin = raw.subarray(binOffset);

    const prim = gltf.meshes[0].primitives[0];
    const readAcc = (idx: number) => {
      const acc = gltf.accessors[idx];
      const bv = gltf.bufferViews[acc.bufferView];
      const start = (bv.byteOffset || 0) + (acc.byteOffset || 0);
      const compCount = acc.type === 'VEC3' ? 3 : acc.type === 'VEC2' ? 2 : 1;
      const bytes = bin.subarray(start, start + acc.count * compCount * 4);
      if (acc.componentType === 5126) {
        return new Float32Array(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
      }
      if (acc.componentType === 5125) {
        return new Uint32Array(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
      }
      const u16 = new Uint16Array(
        bin.subarray(start, start + acc.count * compCount * 2).buffer.slice(
          bin.subarray(start, start + acc.count * compCount * 2).byteOffset,
          bin.subarray(start, start + acc.count * compCount * 2).byteOffset + acc.count * compCount * 2
        )
      );
      return u16;
    };

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(readAcc(prim.attributes.POSITION) as Float32Array, 3));
    if (prim.attributes.TEXCOORD_0 !== undefined) {
      geo.setAttribute('uv', new THREE.BufferAttribute(readAcc(prim.attributes.TEXCOORD_0) as Float32Array, 2));
    }
    if (prim.indices !== undefined) {
      geo.setIndex(new THREE.BufferAttribute(readAcc(prim.indices), 1));
    }
    geo.computeVertexNormals();

    const realScene = new THREE.Group();
    const realMesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: 0xffffff }));
    realMesh.name = gltf.nodes?.[0]?.name || 'yorvyn_tops_tshirt';
    realScene.add(realMesh);

    const avatar = buildDetailedAvatar();
    const res = UniversalGarmentFittingOrchestrator.fitAndAttach(realScene, avatar, {
      category: 'tops',
      preserveOtherLayers: true,
    });

    expect(res.success).toBe(true);
    expect(res.inspection.valid).toBe(true);
    expect(res.inspection.vertexCount).toBe(1088);
    expect(res.diagnostics.appliedScale[0]).toBeLessThanOrEqual(1.24);
    expect(res.diagnostics.appliedScale[2]).toBeLessThanOrEqual(1.22);

    const box = new THREE.Box3().setFromObject(res.attachedObject!);
    expect(box.max.y).toBeLessThan(1.60);
    expect(box.min.y).toBeGreaterThan(0.65);
  });
});
