import { describe, it, expect, beforeEach, vi } from 'vitest';
import * as THREE from 'three';
import { GarmentAvatarFittingEngine } from '../GarmentAvatarFittingEngine';
import { studio3DAssetManager } from '../../ara/Studio3DAssetManager';
import { supabase } from '../../../utils/supabase';

function createMockAvatar(opts: { heightScale?: number; widthScale?: number; withSkeleton?: boolean } = {}): THREE.Group {
  const { heightScale = 1.0, widthScale = 1.0, withSkeleton = true } = opts;
  const root = new THREE.Group();
  root.name = 'avatar_root';

  const hips = new THREE.Bone();
  hips.name = 'Hips';
  hips.position.set(0, 0.95 * heightScale, 0);

  const spine = new THREE.Bone();
  spine.name = 'Spine';
  spine.position.set(0, 0.14 * heightScale, 0);
  hips.add(spine);

  const spine2 = new THREE.Bone();
  spine2.name = 'Spine2';
  spine2.position.set(0, 0.24 * heightScale, 0);
  spine.add(spine2);

  const neck = new THREE.Bone();
  neck.name = 'Neck';
  neck.position.set(0, 0.18 * heightScale, 0);
  spine2.add(neck);

  const leftShoulder = new THREE.Bone();
  leftShoulder.name = 'LeftShoulder';
  leftShoulder.position.set(0.16 * widthScale, 0.12 * heightScale, 0);
  spine2.add(leftShoulder);

  const rightShoulder = new THREE.Bone();
  rightShoulder.name = 'RightShoulder';
  rightShoulder.position.set(-0.16 * widthScale, 0.12 * heightScale, 0);
  spine2.add(rightShoulder);

  const leftFoot = new THREE.Bone();
  leftFoot.name = 'LeftFoot';
  leftFoot.position.set(0.1 * widthScale, -0.92 * heightScale, 0);
  hips.add(leftFoot);

  const rightFoot = new THREE.Bone();
  rightFoot.name = 'RightFoot';
  rightFoot.position.set(-0.1 * widthScale, -0.92 * heightScale, 0);
  hips.add(rightFoot);

  root.add(hips);
  root.updateMatrixWorld(true);

  const bodyGeo = new THREE.CylinderGeometry(0.18 * widthScale, 0.16 * widthScale, 1.72 * heightScale, 16, 12);
  bodyGeo.translate(0, 0.86 * heightScale, 0);
  const vCount = bodyGeo.attributes.position.count;
  bodyGeo.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(new Uint16Array(vCount * 4), 4));
  const weights = new Float32Array(vCount * 4);
  for (let i = 0; i < vCount; i++) weights[i * 4] = 1.0;
  bodyGeo.setAttribute('skinWeight', new THREE.Float32BufferAttribute(weights, 4));

  const bodyMat = new THREE.MeshStandardMaterial({ name: 'body_skin', color: 0xf1c27d });
  const bodyMesh = new THREE.SkinnedMesh(bodyGeo, bodyMat);
  bodyMesh.name = 'Alex_1';

  const bones = [hips, spine, spine2, neck, leftShoulder, rightShoulder, leftFoot, rightFoot];
  const skeleton = new THREE.Skeleton(bones);
  if (withSkeleton) {
    bodyMesh.bind(skeleton);
  } else {
    (bodyMesh as any).skeleton = undefined;
  }

  // Base default clothing mesh to test visibility toggling
  const baseTop = new THREE.Mesh(
    new THREE.BoxGeometry(0.38, 0.48, 0.22),
    new THREE.MeshStandardMaterial({ name: 'uniform_shirt', color: 0xffffff })
  );
  baseTop.name = 'base_uniform_shirt';
  const baseBottom = new THREE.Mesh(
    new THREE.BoxGeometry(0.36, 0.85, 0.22),
    new THREE.MeshStandardMaterial({ name: 'uniform_trousers', color: 0x1e293b })
  );
  baseBottom.name = 'base_uniform_trousers';

  root.add(bodyMesh, baseTop, baseBottom);
  root.updateMatrixWorld(true);
  return root;
}

function createMockGarment(name: string, height = 0.62, width = 0.44, yCenter = 1.25): THREE.Group {
  const group = new THREE.Group();
  const geo = new THREE.BoxGeometry(width, height, 0.24, 6, 8, 4);
  geo.translate(0, yCenter, 0);
  const mat = new THREE.MeshStandardMaterial({ color: 0x2563eb });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.name = name;
  group.add(mesh);
  return group;
}

describe('Wear on Character Full-Stack Fitting Pipeline', () => {
  beforeEach(() => {
    studio3DAssetManager.clearAllCaches();
  });

  it('fits a basic T-shirt onto the upper torso region of the avatar', () => {
    const avatar = createMockAvatar();
    const tshirt = createMockGarment('tshirt_torso', 0.58, 0.44, 1.28);

    const res = GarmentAvatarFittingEngine.fitAndAttachGarment(tshirt, avatar, { category: 'top' });
    expect(res.success).toBe(true);
    expect(res.attachedMesh.visible).toBe(true);
    expect(res.attachmentType).toBe('skinned');

    const box = new THREE.Box3().setFromObject(res.attachedMesh);
    const center = new THREE.Vector3();
    box.getCenter(center);
    expect(center.y).toBeGreaterThan(0.8);
    expect(center.y).toBeLessThan(1.7);
  });

  it('fits a jacket (outerwear) onto the avatar', () => {
    const avatar = createMockAvatar();
    const jacket = createMockGarment('denim_jacket', 0.64, 0.48, 1.28);

    const res = GarmentAvatarFittingEngine.fitAndAttachGarment(jacket, avatar, { category: 'outerwear' });
    expect(res.success).toBe(true);
    expect(avatar.getObjectById(res.attachedMesh.id)).toBeDefined();
  });

  it('fits jeans (bottom) onto the lower body below waist', () => {
    const avatar = createMockAvatar();
    const jeans = createMockGarment('straight_jeans', 0.92, 0.42, 0.55);

    const res = GarmentAvatarFittingEngine.fitAndAttachGarment(jeans, avatar, { category: 'bottom' });
    expect(res.success).toBe(true);
    const box = new THREE.Box3().setFromObject(res.attachedMesh);
    expect(box.min.y).toBeLessThan(0.5);
  });

  it('falls back to bone_parented attachment when avatar skeleton is missing', () => {
    const avatarNoSkel = createMockAvatar({ withSkeleton: false });
    const tshirt = createMockGarment('tshirt_no_skel', 0.58, 0.44, 1.28);

    const res = GarmentAvatarFittingEngine.fitAndAttachGarment(tshirt, avatarNoSkel, {
      category: 'top',
      attachmentMode: 'auto',
    });
    expect(res.success).toBe(true);
    expect(res.attachmentType).toBe('bone_parented');
  });

  it('throws diagnostic error on invalid/empty GLB hierarchy without corrupting avatar', () => {
    const avatar = createMockAvatar();
    const emptyGroup = new THREE.Group();

    expect(() => GarmentAvatarFittingEngine.fitAndAttachGarment(emptyGroup, avatar, { category: 'top' })).toThrow(
      /No mesh found/i
    );
    expect(avatar.getObjectByName('Alex_1')).toBeDefined();
  });

  it('adapts proportionally to short, tall, and wide avatar body proportions', () => {
    const shortAvatar = createMockAvatar({ heightScale: 0.85, widthScale: 0.95 });
    const tallAvatar = createMockAvatar({ heightScale: 1.15, widthScale: 1.0 });
    const wideAvatar = createMockAvatar({ heightScale: 1.0, widthScale: 1.25 });

    const rShort = GarmentAvatarFittingEngine.fitAndAttachGarment(
      createMockGarment('tee_short'),
      shortAvatar,
      { category: 'top' }
    );
    const rTall = GarmentAvatarFittingEngine.fitAndAttachGarment(
      createMockGarment('tee_tall'),
      tallAvatar,
      { category: 'top' }
    );
    const rWide = GarmentAvatarFittingEngine.fitAndAttachGarment(
      createMockGarment('tee_wide'),
      wideAvatar,
      { category: 'top' }
    );

    expect(rShort.diagnostics.avatarTorsoHeight).toBeLessThan(rTall.diagnostics.avatarTorsoHeight);
    expect(rWide.diagnostics.appliedScale[0]).toBeGreaterThan(rShort.diagnostics.appliedScale[0]);
  });

  it('prevents duplicate meshes across repeated Wear on Character and garment switching', () => {
    const avatar = createMockAvatar();

    GarmentAvatarFittingEngine.fitAndAttachGarment(createMockGarment('tee_1'), avatar, { category: 'top' });
    GarmentAvatarFittingEngine.fitAndAttachGarment(createMockGarment('jeans_1'), avatar, { category: 'bottom' });
    GarmentAvatarFittingEngine.fitAndAttachGarment(createMockGarment('jacket_1'), avatar, { category: 'outerwear' });

    let fittedCount = 0;
    avatar.traverse((obj) => {
      if (obj.name === 'custom_ai_garment_fitted') fittedCount++;
    });
    expect(fittedCount).toBe(1);
  });

  it('attaches Supabase Bearer token when loading internal /api/ garment GLBs', async () => {
    const sessionSpy = vi.spyOn(supabase.auth, 'getSession').mockResolvedValue({
      data: { session: { access_token: 'test-jwt-token-xyz' } as any },
      error: null,
    });
    const headerSpy = vi.spyOn((studio3DAssetManager as any).gltfLoader, 'setRequestHeader');
    const fakeScene = new THREE.Group();
    const loadSpy = vi.spyOn((studio3DAssetManager as any).gltfLoader, 'load').mockImplementation((...args: any[]) => {
      args[1]({ scene: fakeScene, scenes: [fakeScene], animations: [], cameras: [], asset: {} });
    });

    await studio3DAssetManager.loadGLB('/api/fashion/garment-gen/assets/job_123/garment.glb', 'high').promise;

    expect(headerSpy).toHaveBeenCalledWith({ Authorization: 'Bearer test-jwt-token-xyz' });
    sessionSpy.mockRestore();
    headerSpy.mockRestore();
    loadSpy.mockRestore();
  });
});
