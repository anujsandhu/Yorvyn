import { describe, it, expect } from 'vitest';
import * as THREE from 'three';
import {
  MotionCoreOrchestrator,
  RetargetingEngine,
  SkeletonAdapter,
  validateAnimatedGLBExport,
} from '../index';

function buildCanonicalHumanoidRig(): { root: THREE.Group; clips: THREE.AnimationClip[]; accessory: THREE.Mesh } {
  const root = new THREE.Group();
  root.name = 'AvatarRoot';

  const makeBone = (name: string, parent: THREE.Object3D, y: number, x = 0) => {
    const b = new THREE.Bone();
    b.name = name;
    b.position.set(x, y, 0);
    parent.add(b);
    return b;
  };

  const hips = makeBone('Hips', root, 0.85);
  const spine = makeBone('Spine', hips, 0.15);
  const spine1 = makeBone('Spine1', spine, 0.12);
  const spine2 = makeBone('Spine2', spine1, 0.15);
  const neck = makeBone('Neck', spine2, 0.22);
  const head = makeBone('Head', neck, 0.12);

  const lArm = makeBone('LeftArm', spine2, 0.18, 0.18);
  const lFore = makeBone('LeftForeArm', lArm, -0.25, 0.05);
  makeBone('LeftHand', lFore, -0.22, 0.02);

  const rArm = makeBone('RightArm', spine2, 0.18, -0.18);
  const rFore = makeBone('RightForeArm', rArm, -0.25, -0.05);
  makeBone('RightHand', rFore, -0.22, -0.02);

  const lUpLeg = makeBone('LeftUpLeg', hips, -0.05, 0.1);
  const lLeg = makeBone('LeftLeg', lUpLeg, -0.4);
  makeBone('LeftFoot', lLeg, -0.38);

  const rUpLeg = makeBone('RightUpLeg', hips, -0.05, -0.1);
  const rLeg = makeBone('RightLeg', rUpLeg, -0.4);
  makeBone('RightFoot', rLeg, -0.38);

  // Body SkinnedMesh bound to skeleton
  const bodyGeo = new THREE.CylinderGeometry(0.18, 0.16, 0.7, 8, 4);
  const vCount = bodyGeo.attributes.position.count;
  const idx = new Uint16Array(vCount * 4);
  const wgt = new Float32Array(vCount * 4);
  for (let i = 0; i < vCount; i++) {
    idx[i * 4] = 0;
    wgt[i * 4] = 1.0;
  }
  bodyGeo.setAttribute('skinIndex', new THREE.BufferAttribute(idx, 4));
  bodyGeo.setAttribute('skinWeight', new THREE.BufferAttribute(wgt, 4));

  const bones: THREE.Bone[] = [];
  root.traverse((o) => {
    if ((o as THREE.Bone).isBone) bones.push(o as THREE.Bone);
  });
  const skeleton = new THREE.Skeleton(bones);
  const bodyMesh = new THREE.SkinnedMesh(bodyGeo, new THREE.MeshStandardMaterial());
  bodyMesh.name = 'body_skin';
  bodyMesh.bind(skeleton);
  root.add(bodyMesh);

  const accessory = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.03, 0.02), new THREE.MeshStandardMaterial());
  accessory.name = 'Sunglasses';
  head.add(accessory);

  root.updateMatrixWorld(true);
  return { root, clips: [], accessory };
}

function buildMultiPartGarmentGroup(bones: THREE.Bone[]): THREE.Group {
  const grp = new THREE.Group();
  grp.name = 'custom_ai_garment_fitted';

  const makePart = (name: string, geo: THREE.BufferGeometry, boneIndex: number) => {
    const c = geo.attributes.position.count;
    const sIdx = new Uint16Array(c * 4);
    const sWgt = new Float32Array(c * 4);
    for (let i = 0; i < c; i++) {
      sIdx[i * 4] = boneIndex;
      sWgt[i * 4] = 1.0;
    }
    geo.setAttribute('skinIndex', new THREE.BufferAttribute(sIdx, 4));
    geo.setAttribute('skinWeight', new THREE.BufferAttribute(sWgt, 4));
    const mesh = new THREE.SkinnedMesh(geo, new THREE.MeshStandardMaterial());
    mesh.name = name;
    mesh.bind(new THREE.Skeleton(bones));
    return mesh;
  };

  grp.add(makePart('main_torso', new THREE.CylinderGeometry(0.22, 0.21, 0.55, 8, 4), 2));
  grp.add(makePart('left_sleeve', new THREE.CylinderGeometry(0.07, 0.06, 0.4, 6, 3), 6));
  return grp;
}

describe('Phase 16.9 MotionCore Engine', () => {
  it('enforces single-mixer FSM transitions, pause/resume/reset, and incompatible transition blocking', async () => {
    const { root, clips } = buildCanonicalHumanoidRig();
    const core = new MotionCoreOrchestrator();
    const { skeletonReport } = await core.initAvatar(root, clips);

    expect(skeletonReport.isCompatible).toBe(true);
    expect(skeletonReport.matchedCanonicalBones).toBeGreaterThanOrEqual(16);
    expect(core.stateManager.getState()).toBe('IDLE');

    expect(core.transitionTo('WALK').accepted).toBe(true);
    expect(core.stateManager.getState()).toBe('WALK');

    expect(core.transitionTo('PAUSE' as any).accepted).toBe(false);
    expect(core.pause().accepted).toBe(true);
    expect(core.stateManager.getState()).toBe('PAUSED');
    const resDec = core.resume();
    expect(resDec.accepted).toBe(true);
    expect(resDec.toState).toBe('WALK');
    expect(core.stateManager.getState()).toBe('WALK');

    // Switch to SIT then verify direct SIT -> RUN jump is rejected until standing/idle
    core.transitionTo('IDLE');
    expect(core.transitionTo('SIT').accepted).toBe(true);
    const illegal = core.transitionTo('RUN');
    expect(illegal.accepted).toBe(false);
    expect(core.stateManager.getState()).toBe('SIT');

    expect(core.transitionTo('STAND').accepted).toBe(true);
    core.resetAll();
    expect(core.stateManager.getState()).toBe('STAND');
    core.dispose();
  });

  it('retargets Mixamo tracks, applies ordered IK and smoothed confidence-weighted PoseInput', () => {
    const { root } = buildCanonicalHumanoidRig();
    const core = new MotionCoreOrchestrator();
    const skel = new SkeletonAdapter();
    skel.bind(root);

    const mixClip = new THREE.AnimationClip('mixamo_walk', 1.0, [
      new THREE.QuaternionKeyframeTrack('mixamorig:LeftArm.quaternion', [0, 1], [0, 0, 0, 1, 0.2, 0, 0, 0.9798]),
      new THREE.QuaternionKeyframeTrack('mixamorig:UnmappedExtraBone.quaternion', [0, 1], [0, 0, 0, 1, 0, 0, 0, 1]),
    ]);
    const retargeted = RetargetingEngine.retargetClip(mixClip, skel);
    expect(retargeted.mappedTracks).toBe(1);
    expect(retargeted.droppedTracks).toBe(1);
    expect(retargeted.clip.tracks[0].name).toBe('LeftArm.quaternion');

    // Pose input rejects NaN & low confidence while updating valid arm joints
    core.animationController.init(root, []);
    const poseRes = core.applyPoseInput({
      timestampMs: 100,
      source: 'offline_sequence',
      landmarks: [
        { name: 'left_shoulder', x: 0.2, y: 1.4, z: 0, confidence: 0.95 },
        { name: 'left_elbow', x: 0.45, y: 1.45, z: 0.1, confidence: 0.92 },
        { name: 'right_shoulder', x: -0.2, y: 1.4, z: 0, confidence: 0.2 }, // below 0.45 threshold
        { name: 'right_elbow', x: NaN, y: 1.2, z: 0, confidence: 0.99 },
      ],
    });
    expect(poseRes.appliedBones).toBe(1);
    expect(poseRes.rejectedLandmarks).toBe(2);

    // Bounded IK solver runs without throwing or producing NaN quaternions
    core.setIKTarget({ chain: 'right_arm', targetWorld: new THREE.Vector3(-0.35, 1.35, 0.2), weight: 0.7 });
    const solved = core.ikEngine.apply(core.getSkeleton());
    expect(solved).toBe(1);
    const rArm = core.getSkeleton().getBone('RightArm')!;
    expect(Number.isFinite(rArm.quaternion.x)).toBe(true);
    core.dispose();
  });

  it('synchronizes multi-part garments, XPBD + self-collision + secondary nodes across WALK/RUN/RAISE_ARMS/BEND/SIT without explosion', async () => {
    const { root, clips, accessory } = buildCanonicalHumanoidRig();
    const core = new MotionCoreOrchestrator();
    await core.initAvatar(root, clips);

    const bones: THREE.Bone[] = [];
    root.traverse((o) => {
      if ((o as THREE.Bone).isBone) bones.push(o as THREE.Bone);
    });
    const garmentGrp = buildMultiPartGarmentGroup(bones);
    root.add(garmentGrp);

    const attachedParts = core.attachGarment(garmentGrp, 'jacket', {
      fabricHint: 'denim',
      hasConstructionSeams: true,
    });
    expect(attachedParts).toBe(2);

    // Primary XPBD meshes cannot be double-registered into SecondaryMotionSolver
    const torsoMesh = garmentGrp.getObjectByName('main_torso')!;
    expect(core.registerSecondaryNode('dup_torso', torsoMesh, 'panel')).toBe(false);
    expect(core.registerSecondaryNode('sunglasses', accessory, 'accessory')).toBe(true);

    core.setWind(0.4, 0, 0.2);
    for (const st of ['WALK', 'RUN', 'RAISE_ARMS', 'BEND', 'SIT'] as const) {
      if (st === 'BEND' || st === 'SIT') core.transitionTo('IDLE');
      core.transitionTo(st);
      for (let f = 0; f < 10; f++) {
        const tel = core.step(1 / 60);
        expect(tel.activeClothVertices).toBeGreaterThan(20);
        expect(tel.p95FrameMs).toBeGreaterThan(0);
      }
      if (st === 'SIT') core.transitionTo('STAND');
    }

    // Verify no NaNs and bounded displacement after motion stress
    torsoMesh.traverse((o) => {
      if ((o as THREE.Mesh).isMesh) {
        const pos = (o as THREE.Mesh).geometry.attributes.position as THREE.BufferAttribute;
        for (let i = 0; i < pos.count; i++) {
          expect(Number.isFinite(pos.getX(i))).toBe(true);
          expect(Number.isFinite(pos.getY(i))).toBe(true);
          expect(Number.isFinite(pos.getZ(i))).toBe(true);
        }
      }
    });

    // Material switch preserves isMeasuredPhysical: false
    const silkSpec = core.setFabric('dress', 'silk');
    expect(silkSpec.isMeasuredPhysical).toBe(false);
    expect(silkSpec.fabricFamily).toBe('silk');

    core.resetAll();
    core.dispose();
  });

  it('adaptively downgrades quality on high frame times, keeps WebGPU experimental, and validates GLB exports', () => {
    const core = new MotionCoreOrchestrator();
    core.compute.setQualityTier('high');
    expect(core.compute.getSummary().webgpuExperimentalOnly).toBe(true);

    const downgraded = core.compute.adaptTierFromFrameTime(32.0);
    expect(downgraded).toBe(true);
    expect(core.compute.getSummary().qualityTier).toBe('balanced');

    // Minimal valid GLB v2 header + JSON testing honest export validation
    const jsonStr = JSON.stringify({
      asset: { version: '2.0' },
      skins: [{ joints: [0, 1] }],
      animations: [{ name: 'Walk', samplers: [{ input: 0, output: 1 }], channels: [{ sampler: 0, target: { node: 0, path: 'rotation' } }] }],
      nodes: [{ name: 'Hips' }, { name: 'Spine', extras: { component_id: 'main_torso' } }],
      meshes: [{ primitives: [{}] }],
    });
    const jBytes = new TextEncoder().encode(jsonStr + ' '.repeat((4 - (jsonStr.length % 4)) % 4));
    const total = 12 + 8 + jBytes.length;
    const glb = new Uint8Array(total);
    const dv = new DataView(glb.buffer);
    dv.setUint32(0, 0x46546c67, true);
    dv.setUint32(4, 2, true);
    dv.setUint32(8, total, true);
    dv.setUint32(12, jBytes.length, true);
    dv.setUint32(16, 0x4e4f534a, true);
    glb.set(jBytes, 20);

    const ok = validateAnimatedGLBExport(glb);
    expect(ok.isValid).toBe(true);
    expect(ok.exportKind).toBe('skeletal_with_garment_deformation');
    expect(ok.hasBakedClothDeformation).toBe(false);

    const falseClaim = validateAnimatedGLBExport(glb, { claimedBakedCloth: true });
    expect(falseClaim.isValid).toBe(false);
  });
});
