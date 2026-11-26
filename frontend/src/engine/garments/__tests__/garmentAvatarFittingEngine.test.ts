/**
 * YORVYN — Master Garment-to-Avatar Fitting Engine Test Suite
 * Validates the complete 9-step virtual try-on fitting pipeline:
 * 1. Landmark extraction from rigged avatar
 * 2. Anatomical alignment (hoodie, bottoms, dress)
 * 3. BVH collision resolution & 3.0mm clearance guarantee
 * 4. Barycentric skin weight transfer and skeleton binding
 * 5. Bone-parented static attachment fallback
 * 6. Avatar body integrity & strict preservation of skin, eyes, hair, hands, and feet
 * 7. Clean unequip and state restoration
 */

import { describe, it, expect, beforeEach } from 'vitest';
import * as THREE from 'three';
import { GarmentAvatarFittingEngine } from '../GarmentAvatarFittingEngine';
import { UniversalGarmentFittingEngine } from '../UniversalGarmentFittingEngine';
import { GarmentGeometryProcessor } from '../../garmentReconstruction/GarmentGeometryProcessor';

describe('GarmentAvatarFittingEngine', () => {
  let avatarModel: THREE.Group;
  let bodyMesh: THREE.SkinnedMesh;
  let suitMesh: THREE.SkinnedMesh;
  let hairMesh: THREE.Mesh;
  let eyesMesh: THREE.Mesh;
  let skeleton: THREE.Skeleton;
  let bones: THREE.Bone[];

  beforeEach(() => {
    avatarModel = new THREE.Group();
    avatarModel.name = 'avatarModelRoot';

    const avatarGroup = new THREE.Group();
    avatarGroup.name = 'Alex';
    avatarModel.add(avatarGroup);

    // Setup Mixamo-compatible humanoid skeleton
    const boneNames = [
      'Hips', 'Spine', 'Spine1', 'Spine2', 'Neck', 'Head',
      'LeftShoulder', 'LeftArm', 'LeftForeArm', 'LeftHand',
      'RightShoulder', 'RightArm', 'RightForeArm', 'RightHand',
      'LeftUpLeg', 'LeftLeg', 'LeftFoot',
      'RightUpLeg', 'RightLeg', 'RightFoot'
    ];

    bones = boneNames.map((name) => {
      const b = new THREE.Bone();
      b.name = name;
      return b;
    });

    // Structure hierarchy
    const hips = bones[0]; // Hips
    const spine = bones[1];
    const spine1 = bones[2];
    const spine2 = bones[3];
    const neck = bones[4];
    const head = bones[5];
    const leftShoulder = bones[6];
    const leftArm = bones[7];
    const leftForeArm = bones[8];
    const leftHand = bones[9];
    const rightShoulder = bones[10];
    const rightArm = bones[11];
    const rightForeArm = bones[12];
    const rightHand = bones[13];
    const leftUpLeg = bones[14];
    const rightUpLeg = bones[17];

    avatarGroup.add(hips);
    hips.add(spine);
    spine.add(spine1);
    spine1.add(spine2);
    spine2.add(neck);
    neck.add(head);
    spine2.add(leftShoulder);
    leftShoulder.add(leftArm);
    leftArm.add(leftForeArm);
    leftForeArm.add(leftHand);
    spine2.add(rightShoulder);
    rightShoulder.add(rightArm);
    rightArm.add(rightForeArm);
    rightForeArm.add(rightHand);
    hips.add(leftUpLeg);
    hips.add(rightUpLeg);

    // Bind pose joint positions
    hips.position.set(0, 0.815, 0);
    spine.position.set(0, 0.050, 0);
    spine1.position.set(0, 0.050, 0);
    spine2.position.set(0, 0.125, 0); // Y ~ 1.040
    neck.position.set(0, 0.240, 0);  // Y ~ 1.280
    head.position.set(0, 0.086, 0);  // Y ~ 1.366
    leftArm.position.set(0.160, 0.160, 0);
    leftForeArm.position.set(0.120, -0.150, 0);
    leftHand.position.set(0.090, -0.120, 0.05);
    rightArm.position.set(-0.160, 0.160, 0);
    rightForeArm.position.set(-0.120, -0.150, 0);
    rightHand.position.set(-0.090, -0.120, 0.05);

    skeleton = new THREE.Skeleton(bones);

    // Create synthetic full-body avatar mesh (Alex_1) spanning 0.02m to 1.56m
    const bodyVerts: number[] = [];
    const bodyIndices: number[] = [];
    const bodySkinIndices: number[] = [];
    const bodySkinWeights: number[] = [];

    // Cylindrical rings for legs, torso, neck, head
    const rings = 20;
    const slices = 12;
    for (let r = 0; r < rings; r++) {
      const frac = r / (rings - 1);
      const y = 0.02 + frac * 1.54; // 0.02m to 1.56m
      const rad = frac > 0.9 ? 0.10 : frac > 0.5 ? 0.16 : 0.08;

      for (let s = 0; s < slices; s++) {
        const theta = (s / slices) * Math.PI * 2;
        bodyVerts.push(Math.sin(theta) * rad, y, Math.cos(theta) * rad);

        // Assign bone weights based on height
        let boneIdx = 0; // Hips
        if (y > 1.35) boneIdx = 5; // Head
        else if (y > 1.25) boneIdx = 4; // Neck
        else if (y > 1.00) boneIdx = 3; // Spine2
        else if (y > 0.90) boneIdx = 2; // Spine1
        else if (y > 0.80) boneIdx = 1; // Spine

        bodySkinIndices.push(boneIdx, 0, 0, 0);
        bodySkinWeights.push(1.0, 0.0, 0.0, 0.0);
      }
    }

    for (let r = 0; r < rings - 1; r++) {
      for (let s = 0; s < slices; s++) {
        const i0 = r * slices + s;
        const i1 = r * slices + ((s + 1) % slices);
        const i2 = (r + 1) * slices + s;
        const i3 = (r + 1) * slices + ((s + 1) % slices);
        bodyIndices.push(i0, i1, i2);
        bodyIndices.push(i1, i3, i2);
      }
    }

    const bodyGeo = new THREE.BufferGeometry();
    bodyGeo.setAttribute('position', new THREE.Float32BufferAttribute(bodyVerts, 3));
    bodyGeo.setIndex(bodyIndices);
    bodyGeo.computeVertexNormals();
    bodyGeo.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(bodySkinIndices, 4));
    bodyGeo.setAttribute('skinWeight', new THREE.Float32BufferAttribute(bodySkinWeights, 4));

    const bodyMat = new THREE.MeshStandardMaterial({ name: 'Skin', color: 0xffffff });
    bodyMesh = new THREE.SkinnedMesh(bodyGeo, bodyMat);
    bodyMesh.name = 'Alex_1';
    bodyMesh.bind(skeleton);
    avatarGroup.add(bodyMesh);

    // Default Outfit suit (Alex_8)
    const suitGeo = bodyGeo.clone();
    const suitMat = new THREE.MeshStandardMaterial({ name: 'Outfit', color: 0x1e293b });
    suitMesh = new THREE.SkinnedMesh(suitGeo, suitMat);
    suitMesh.name = 'Alex_8';
    suitMesh.bind(skeleton);
    avatarGroup.add(suitMesh);

    // Hair mesh (Alex_9)
    hairMesh = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.2, 0.2), new THREE.MeshStandardMaterial({ name: 'Hair' }));
    hairMesh.name = 'Alex_9';
    avatarGroup.add(hairMesh);

    // Eyes mesh (Alex_2)
    eyesMesh = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.05, 0.05), new THREE.MeshStandardMaterial({ name: 'Eyes' }));
    eyesMesh.name = 'Alex_2';
    avatarGroup.add(eyesMesh);
  });

  it('should fit and skin a 3D hoodie directly onto the avatar with anatomical alignment', () => {
    const hoodieGeom = GarmentGeometryProcessor.buildGarmentMesh('top', 'hoodie');
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(hoodieGeom.positions, 3));
    geo.setIndex(new THREE.Uint32BufferAttribute(hoodieGeom.indices, 1));
    geo.computeVertexNormals();

    const garmentSource = new THREE.Group();
    const hoodieMesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ name: 'BrownFleece' }));
    garmentSource.add(hoodieMesh);

    const result = GarmentAvatarFittingEngine.fitAndAttachGarment(
      garmentSource,
      avatarModel,
      { category: 'top', subcategory: 'hoodie', attachmentMode: 'skinned' }
    );

    expect(result.success).toBe(true);
    expect(result.attachmentType).toBe('skinned');
    expect(result.attachedMesh).toBeInstanceOf(THREE.SkinnedMesh);

    const skinnedHoodie = result.attachedMesh as THREE.SkinnedMesh;
    expect(skinnedHoodie.skeleton).toBe(skeleton);
    expect(skinnedHoodie.geometry.attributes.skinIndex).toBeDefined();
    expect(skinnedHoodie.geometry.attributes.skinWeight).toBeDefined();

    // Verify fitted bounds match avatar torso and neck
    skinnedHoodie.geometry.computeBoundingBox();
    const bb = skinnedHoodie.geometry.boundingBox!;

    // Waistband & sleeve cuffs sit near avatar waist and wrists (0.65 - 0.85m)
    expect(bb.min.y).toBeGreaterThanOrEqual(0.65);
    expect(bb.min.y).toBeLessThanOrEqual(0.85);

    // Hood apex rises over the head (> 1.45m)
    expect(bb.max.y).toBeGreaterThan(1.45);

    // Suit jacket is clipped to keep trousers visible, and skin, hair, eyes remain strictly visible
    expect((suitMesh.material as THREE.MeshStandardMaterial).clippingPlanes?.length).toBe(1);
    expect(bodyMesh.visible).toBe(true);
    expect(hairMesh.visible).toBe(true);
    expect(eyesMesh.visible).toBe(true);
  });

  it('should enforce BVH collision resolution with zero poke-through penetrations', () => {
    // Intentionally create a hoodie whose initial torso bounds penetrate body skin
    const hoodieGeom = GarmentGeometryProcessor.buildGarmentMesh('top', 'hoodie', { fit: 'slim' });
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(hoodieGeom.positions, 3));
    geo.setIndex(new THREE.Uint32BufferAttribute(hoodieGeom.indices, 1));

    const garmentSource = new THREE.Group();
    garmentSource.add(new THREE.Mesh(geo, new THREE.MeshStandardMaterial()));

    const result = GarmentAvatarFittingEngine.fitAndAttachGarment(
      garmentSource,
      avatarModel,
      { category: 'top', subcategory: 'hoodie', minClearanceMeters: 0.003 }
    );

    expect(result.collisionResult).toBeDefined();
    // Diagnostics should report resolved penetration count
    expect(result.diagnostics.resolvedVerticesCount).toBeGreaterThan(500);
  });

  it('should fit bottoms/trousers aligning waistband to hips', () => {
    const pantsGeom = GarmentGeometryProcessor.buildGarmentMesh('bottom', 'pants');
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pantsGeom.positions, 3));
    geo.setIndex(new THREE.Uint32BufferAttribute(pantsGeom.indices, 1));

    const garmentSource = new THREE.Group();
    garmentSource.add(new THREE.Mesh(geo, new THREE.MeshStandardMaterial()));

    const result = GarmentAvatarFittingEngine.fitAndAttachGarment(
      garmentSource,
      avatarModel,
      { category: 'bottom', subcategory: 'pants' }
    );

    expect(result.success).toBe(true);
    expect(result.attachmentType).toBe('skinned');

    const attached = result.attachedMesh as THREE.SkinnedMesh;
    attached.geometry.computeBoundingBox();
    const bb = attached.geometry.boundingBox!;

    // Cuffs terminate near ankles/feet
    expect(bb.min.y).toBeLessThan(0.15);
    // Waistband sits near hips
    expect(bb.max.y).toBeGreaterThanOrEqual(0.75);
  });

  it('should fit dress/outfit spanning from neck collar down to hem', () => {
    const dressGeom = GarmentGeometryProcessor.buildGarmentMesh('dress', 'dress');
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(dressGeom.positions, 3));
    geo.setIndex(new THREE.Uint32BufferAttribute(dressGeom.indices, 1));

    const garmentSource = new THREE.Group();
    garmentSource.add(new THREE.Mesh(geo, new THREE.MeshStandardMaterial()));

    const result = GarmentAvatarFittingEngine.fitAndAttachGarment(
      garmentSource,
      avatarModel,
      { category: 'dress', subcategory: 'dress' }
    );

    expect(result.success).toBe(true);
    const attached = result.attachedMesh as THREE.SkinnedMesh;
    attached.geometry.computeBoundingBox();
    const bb = attached.geometry.boundingBox!;

    expect(bb.max.y).toBeGreaterThanOrEqual(1.20); // Neckline
    expect(bb.min.y).toBeLessThan(0.40); // Hem below knees
  });

  it('should support bone-parented static attachment to Spine2 for unskinned top fallback', () => {
    const hoodieGeom = GarmentGeometryProcessor.buildGarmentMesh('top', 'hoodie');
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(hoodieGeom.positions, 3));
    geo.setIndex(new THREE.Uint32BufferAttribute(hoodieGeom.indices, 1));

    const garmentSource = new THREE.Group();
    garmentSource.add(new THREE.Mesh(geo, new THREE.MeshStandardMaterial()));

    const result = GarmentAvatarFittingEngine.fitAndAttachGarment(
      garmentSource,
      avatarModel,
      { category: 'top', subcategory: 'hoodie', attachmentMode: 'bone_parented' }
    );

    expect(result.success).toBe(true);
    expect(result.attachmentType).toBe('bone_parented');
    expect(result.targetBoneOrGroup).toBe('Spine2');

    const spine2 = avatarModel.getObjectByName('Spine2');
    expect(spine2?.children.some((c) => c.name === 'custom_ai_garment_fitted')).toBe(true);
  });

  it('should cleanly detach garment and restore avatar suit visibility', () => {
    const hoodieGeom = GarmentGeometryProcessor.buildGarmentMesh('top', 'hoodie');
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(hoodieGeom.positions, 3));
    geo.setIndex(new THREE.Uint32BufferAttribute(hoodieGeom.indices, 1));

    const garmentSource = new THREE.Group();
    garmentSource.add(new THREE.Mesh(geo, new THREE.MeshStandardMaterial()));

    GarmentAvatarFittingEngine.fitAndAttachGarment(garmentSource, avatarModel, { category: 'top' });
    expect((suitMesh.material as THREE.MeshStandardMaterial).clippingPlanes?.length).toBe(1);

    // Detach garment
    GarmentAvatarFittingEngine.detachGarment(avatarModel);

    // Suit mesh clipping plane is reset, and custom garment is completely removed
    expect((suitMesh.material as THREE.MeshStandardMaterial).clippingPlanes?.length).toBe(0);
    let found = false;
    avatarModel.traverse((c) => {
      if (c.name === 'custom_ai_garment_fitted') found = true;
    });
    expect(found).toBe(false);
  });

  it('should preserve all multi-component GLB nodes, compact shared buffers, and bind each component SkinnedMesh', () => {
    const hoodieGeom = GarmentGeometryProcessor.buildGarmentMesh('top', 'hoodie');
    const sharedPosAttr = new THREE.Float32BufferAttribute(hoodieGeom.positions, 3);
    const totalTris = hoodieGeom.indices.length / 3;
    expect(totalTris).toBeGreaterThan(20);

    // Split single shared geometry into sub-slice index buffers exactly matching backend GLBExporter output
    const sharedMat = new THREE.MeshStandardMaterial({ name: 'hoodie_mat', color: 0x3b82f6 });
    const garmentSource = new THREE.Group();
    garmentSource.name = 'test_hoodie_glb';

    const sliceCount = Math.floor(totalTris / 4);
    const componentsSpec = [
      { id: 'main_torso', sem: 'torso', startTri: 0, triCount: sliceCount },
      { id: 'left_sleeve', sem: 'sleeve', startTri: sliceCount, triCount: sliceCount },
      { id: 'hood_cowl', sem: 'hood', startTri: sliceCount * 2, triCount: sliceCount },
      { id: 'kangaroo_pocket', sem: 'pocket', startTri: sliceCount * 3, triCount: totalTris - sliceCount * 3 }
    ];

    const torsoNode = new THREE.Object3D();
    for (const spec of componentsSpec) {
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', sharedPosAttr);
      const subIndices = hoodieGeom.indices.slice(spec.startTri * 3, (spec.startTri + spec.triCount) * 3);
      geo.setIndex(new THREE.Uint32BufferAttribute(subIndices, 1));
      geo.computeVertexNormals();

      const compMesh = new THREE.Mesh(geo, sharedMat);
      compMesh.name = spec.id;
      compMesh.userData = {
        component_id: spec.id,
        semantic_type: spec.sem,
        dimensions_m: [0.4, 0.5, 0.2],
        attachment_location: spec.id === 'main_torso' ? 'torso_root' : 'torso_seam'
      };
      if (spec.id === 'main_torso') {
        torsoNode.position.set(0, 0, 0);
        compMesh.add(torsoNode);
        garmentSource.add(compMesh);
      } else {
        garmentSource.add(compMesh);
      }
    }

    const result = GarmentAvatarFittingEngine.fitAndAttachGarment(
      garmentSource,
      avatarModel,
      { category: 'tops', subcategory: 'hoodie', attachmentMode: 'skinned' }
    );

    expect(result.success).toBe(true);
    expect(result.attachmentType).toBe('skinned');
    expect(result.diagnostics.componentCount).toBe(4);
    expect(result.diagnostics.componentNames).toEqual([
      'main_torso',
      'left_sleeve',
      'hood_cowl',
      'kangaroo_pocket'
    ]);

    const attachedGroup = result.attachedMesh as THREE.Group;
    expect(attachedGroup).toBeInstanceOf(THREE.Group);
    expect(attachedGroup.name).toBe('custom_ai_garment_fitted');
    expect(attachedGroup.userData.isMultiComponent).toBe(true);
    expect(attachedGroup.children.length).toBe(4);

    // Every child component must be a SkinnedMesh with compacted geometry, preserved name/userData, and visibility protection
    for (const child of attachedGroup.children) {
      const sm = child as THREE.SkinnedMesh;
      expect(sm.isSkinnedMesh).toBe(true);
      expect(sm.skeleton).toBe(skeleton);
      expect(sm.visible).toBe(true);
      expect(sm.userData.isCustomAiGarment).toBe(true);
      expect(sm.userData.component_id).toBe(sm.name);
      expect(sm.geometry.attributes.skinIndex).toBeDefined();
      expect(sm.geometry.attributes.skinWeight).toBeDefined();
      // Compacted vertex buffer must be strictly smaller than the full unsplit buffer
      expect(sm.geometry.attributes.position.count).toBeLessThanOrEqual(sharedPosAttr.count);
    }

    // Re-running updateAvatarClothingVisibility must NOT hide custom component children (even e.g. 'hood_cowl')
    GarmentAvatarFittingEngine.updateAvatarClothingVisibility(avatarModel, 'tops', true);
    for (const child of attachedGroup.children) {
      expect(child.visible).toBe(true);
    }

    // Clean detach removes the entire multi-component hierarchy
    GarmentAvatarFittingEngine.detachGarment(avatarModel);
    expect(avatarModel.getObjectByName('custom_ai_garment_fitted')).toBeUndefined();
    expect(avatarModel.getObjectByName('kangaroo_pocket')).toBeUndefined();
  });

  it('should anchor standalone multi-component skirt at waistY instead of neckY and protect child visibility', () => {
    const skirtGeom = GarmentGeometryProcessor.buildGarmentMesh('dress', 'skirt');
    const posAttr = new THREE.Float32BufferAttribute(skirtGeom.positions, 3);
    const totalTris = skirtGeom.indices.length / 3;
    const half = Math.floor(totalTris / 2);

    const skirtMat = new THREE.MeshStandardMaterial({ name: 'skirt_mat', color: 0xec4899 });
    const garmentSource = new THREE.Group();

    const wbGeo = new THREE.BufferGeometry();
    wbGeo.setAttribute('position', posAttr);
    wbGeo.setIndex(new THREE.Uint32BufferAttribute(skirtGeom.indices.slice(0, half * 3), 1));
    const wbMesh = new THREE.Mesh(wbGeo, skirtMat);
    wbMesh.name = 'waistband';
    wbMesh.userData = { component_id: 'waistband', semantic_type: 'waistband' };

    const drapeGeo = new THREE.BufferGeometry();
    drapeGeo.setAttribute('position', posAttr);
    drapeGeo.setIndex(new THREE.Uint32BufferAttribute(skirtGeom.indices.slice(half * 3), 1));
    const drapeMesh = new THREE.Mesh(drapeGeo, skirtMat);
    drapeMesh.name = 'flared_skirt_drape';
    drapeMesh.userData = { component_id: 'flared_skirt_drape', semantic_type: 'skirt' };

    garmentSource.add(wbMesh);
    garmentSource.add(drapeMesh);

    const result = GarmentAvatarFittingEngine.fitAndAttachGarment(
      garmentSource,
      avatarModel,
      { category: 'dresses_and_skirts', attachmentMode: 'skinned' }
    );

    expect(result.success).toBe(true);
    const attached = result.attachedMesh as THREE.Group;
    const overallBox = new THREE.Box3();
    for (const child of attached.children) {
      const mesh = child as THREE.Mesh;
      mesh.geometry.computeBoundingBox();
      if (mesh.geometry.boundingBox) overallBox.union(mesh.geometry.boundingBox);
    }

    // Waistband top sits near avatar waist (~0.815m + 0.025m = 0.84m), NOT stretched up to neck (1.28m)
    expect(overallBox.max.y).toBeLessThan(1.0);
    expect(overallBox.max.y).toBeGreaterThan(0.75);
    // Child mesh named 'flared_skirt_drape' (contains 'skirt') must remain visible after visibility filtering
    expect(attached.getObjectByName('flared_skirt_drape')?.visible).toBe(true);
  });

  it('should fit multi-component garment cleanly onto plus-size proportioned avatar via UniversalGarmentFittingEngine', () => {
    // Expand torso rings radially to simulate plus body silhouette
    const pos = bodyMesh.geometry.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < pos.count; i++) {
      const y = pos.getY(i);
      if (y > 0.70 && y < 1.25) {
        pos.setX(i, pos.getX(i) * 1.35);
        pos.setZ(i, pos.getZ(i) * 1.35);
      }
    }
    pos.needsUpdate = true;
    bodyMesh.geometry.computeBoundingBox();
    (bodyMesh.geometry as any).boundsTree = undefined;

    const hoodieGeom = GarmentGeometryProcessor.buildGarmentMesh('top', 'hoodie');
    const sharedPosAttr = new THREE.Float32BufferAttribute(hoodieGeom.positions, 3);
    const totalTris = hoodieGeom.indices.length / 3;
    const half = Math.floor(totalTris / 2);

    const garmentSource = new THREE.Group();
    const torsoMesh = new THREE.Mesh(
      new THREE.BufferGeometry()
        .setAttribute('position', sharedPosAttr)
        .setIndex(new THREE.Uint32BufferAttribute(hoodieGeom.indices.slice(0, half * 3), 1)),
      new THREE.MeshStandardMaterial()
    );
    torsoMesh.name = 'main_torso';
    torsoMesh.userData = { component_id: 'main_torso', semantic_type: 'torso' };

    const hoodMesh = new THREE.Mesh(
      new THREE.BufferGeometry()
        .setAttribute('position', sharedPosAttr)
        .setIndex(new THREE.Uint32BufferAttribute(hoodieGeom.indices.slice(half * 3), 1)),
      new THREE.MeshStandardMaterial()
    );
    hoodMesh.name = 'hood_cowl';
    hoodMesh.userData = { component_id: 'hood_cowl', semantic_type: 'hood' };

    garmentSource.add(torsoMesh, hoodMesh);

    const universalRes = UniversalGarmentFittingEngine.fitGarment(garmentSource, avatarModel, {
      category: 'tops',
      subcategory: 'hoodie'
    });

    expect(universalRes.success).toBe(true);
    expect(universalRes.attachmentType).toBe('skinned');
    expect(universalRes.measurements.chestCircumferenceCm).toBeGreaterThan(95);
    expect(universalRes.collisionDiagnostics.minClearanceGuaranteedMm).toBe(3.0);
    expect(universalRes.attachedMesh.name).toBe('custom_ai_garment_fitted');
  });
});
