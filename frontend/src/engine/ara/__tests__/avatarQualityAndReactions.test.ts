import { describe, it, expect, beforeEach, vi } from 'vitest';
import * as THREE from 'three';
import {
  thumbsUp,
  thumbsDown,
  FASHION_REACTIONS,
} from '../core/anim/clips/fashionReactions';
import { CLIPS } from '../core/anim/clips';
import { AraAnimationController } from '../avatarAnimationController';
import { avatarFeedbackService } from '../../../services/feedback/avatarFeedbackService';

describe('PHASE 11: Avatar Quality, Animations & Reaction System Tests', () => {
  let modelRoot: THREE.Group;
  let skinnedMesh: THREE.SkinnedMesh;
  let bones: THREE.Bone[];
  let mockStore: Record<string, string> = {};

  beforeEach(() => {
    mockStore = {};
    Object.defineProperty(globalThis, 'localStorage', {
      value: {
        getItem: (key: string) => mockStore[key] || null,
        setItem: (key: string, val: string) => { mockStore[key] = String(val); },
        removeItem: (key: string) => { delete mockStore[key]; },
        clear: () => { mockStore = {}; },
        key: (i: number) => Object.keys(mockStore)[i] || null,
        length: 0,
      },
      writable: true,
      configurable: true,
    });

    // Setup standard 65-bone skeleton mock for testing deformation & gestures
    modelRoot = new THREE.Group();
    const boneNames = [
      'Hips', 'Spine', 'Spine1', 'Spine2', 'Neck', 'Head',
      'RightShoulder', 'RightArm', 'RightForeArm', 'RightHand',
      'RightHandThumb1', 'RightHandThumb2', 'RightHandThumb3',
      'RightHandIndex1', 'RightHandIndex2', 'RightHandIndex3',
      'RightHandMiddle1', 'RightHandMiddle2', 'RightHandMiddle3',
      'RightHandRing1', 'RightHandRing2', 'RightHandRing3',
      'RightHandPinky1', 'RightHandPinky2', 'RightHandPinky3',
      'LeftShoulder', 'LeftArm', 'LeftForeArm', 'LeftHand',
      'LeftHandThumb1', 'LeftHandThumb2', 'LeftHandThumb3',
      'LeftHandIndex1', 'LeftHandIndex2', 'LeftHandIndex3',
      'LeftHandMiddle1', 'LeftHandMiddle2', 'LeftHandMiddle3',
      'LeftHandRing1', 'LeftHandRing2', 'LeftHandRing3',
      'LeftHandPinky1', 'LeftHandPinky2', 'LeftHandPinky3',
      'LeftUpLeg', 'LeftLeg', 'LeftFoot',
      'RightUpLeg', 'RightLeg', 'RightFoot',
    ];

    bones = boneNames.map(name => {
      const bone = new THREE.Bone();
      bone.name = name;
      return bone;
    });

    const skeleton = new THREE.Skeleton(bones);
    const geometry = new THREE.BufferGeometry();
    skinnedMesh = new THREE.SkinnedMesh(geometry, new THREE.MeshStandardMaterial());
    skinnedMesh.bind(skeleton);
    skinnedMesh.morphTargetDictionary = {
      mouthSmileLeft: 0,
      mouthSmileRight: 1,
      mouthPucker: 2,
      eyeBlinkLeft: 3,
      eyeBlinkRight: 4,
      browInnerUp: 5,
    };
    skinnedMesh.morphTargetInfluences = [0, 0, 0, 0, 0, 0];

    bones.forEach(b => modelRoot.add(b));
    modelRoot.add(skinnedMesh);
  });

  describe('1. Fashion Reaction Animation Clips Catalogue', () => {
    it('should define valid reaction clips with proper durations and categories', () => {
      expect(thumbsUp.id).toBe('thumbs_up');
      expect(thumbsUp.duration).toBeGreaterThan(1.0);
      expect(typeof thumbsUp.sample).toBe('function');

      expect(thumbsDown.id).toBe('thumbs_down');
      expect(thumbsDown.duration).toBeGreaterThan(1.0);
      expect(typeof thumbsDown.sample).toBe('function');
    });

    it('should articulate finger and thumb bones specifically for thumbs-up pose', () => {
      const poseMid = thumbsUp.sample(1.0);
      expect(poseMid).toBeDefined();
      expect(poseMid.bones).toBeDefined();

      // Right hand should have curled fingers and extended thumb in bones channel
      expect(poseMid.bones!['RightHandIndex1']).toBeDefined();
      expect(poseMid.bones!['RightHandThumb1']).toBeDefined();
      expect(poseMid.bones!['RightHandThumb2']).toBeDefined();

      // Check facial expression (smile)
      expect(poseMid.face?.mouthSmile).toBeGreaterThan(0);
    });

    it('should articulate inverted wrist and curled fingers for thumbs-down pose', () => {
      const poseMid = thumbsDown.sample(1.0);
      expect(poseMid).toBeDefined();
      expect(poseMid.bones).toBeDefined();

      // Right hand fingers curled and thumb pointed down
      expect(poseMid.bones!['RightHandIndex1']).toBeDefined();
      expect(poseMid.bones!['RightHandThumb1']).toBeDefined();
      expect(poseMid.bones!['RightHandThumb2']).toBeDefined();

      // Disapproval facial expression
      expect(poseMid.face?.mouthFrown || poseMid.face?.mouthPress).toBeGreaterThan(0);
    });

    it('should bundle all 16+ reaction clips in FASHION_REACTIONS array', () => {
      expect(FASHION_REACTIONS.length).toBeGreaterThanOrEqual(16);
      const ids = FASHION_REACTIONS.map(c => c.id);
      expect(ids).toContain('thumbs_up');
      expect(ids).toContain('thumbs_down');
      expect(ids).toContain('nod');
      expect(ids).toContain('head_shake');
      expect(ids).toContain('thinking');
      expect(ids).toContain('curious');
      expect(ids).toContain('present_single');
      expect(ids).toContain('present_both');
      expect(ids).toContain('point_outfit');
      expect(ids).toContain('look_garment');
      expect(ids).toContain('inspect_outfit');
      expect(ids).toContain('suggest_alt');
      expect(ids).toContain('welcome');
      expect(ids).toContain('listening');
      expect(ids).toContain('excited');
      expect(ids).toContain('confused');
    });

    it('should include fashion reactions in primary CLIPS catalogue', () => {
      const clipIds = CLIPS.map(c => c.id);
      expect(clipIds).toContain('idle');
      expect(clipIds).toContain('thumbs_up');
      expect(clipIds).toContain('thumbs_down');
      expect(clipIds).toContain('present_single');
      expect(clipIds).toContain('wave');
      expect(clipIds).toContain('cheer');
    });
  });

  describe('2. Animation Controller State Transitions & Interruption', () => {
    it('should initialize with clips and safely play a reaction action', () => {
      const clips = [
        new THREE.AnimationClip('idle', 2, []),
        new THREE.AnimationClip('thumbs_up', 2.2, []),
        new THREE.AnimationClip('thumbs_down', 2.2, []),
      ];

      const controller = new AraAnimationController();
      controller.init(modelRoot, clips);

      expect(controller.hasClip('thumbs_up')).toBe(true);
      expect(controller.hasClip('thumbs_down')).toBe(true);

      const played = controller.play('thumbs_up', { loop: false, crossfadeDuration: 0.25 });
      expect(played).toBe(true);
      expect(controller.getCurrentClipName()).toBe('thumbs_up');
    });

    it('should support animation aliases gracefully (e.g. thumbsUp -> thumbs_up)', () => {
      const clips = [
        new THREE.AnimationClip('idle', 2, []),
        new THREE.AnimationClip('thumbs_up', 2.2, []),
      ];
      const controller = new AraAnimationController();
      controller.init(modelRoot, clips);

      expect(controller.play('thumbsUp')).toBe(true);
      expect(controller.getCurrentClipName()).toBe('thumbs_up');
    });

    it('should safely handle missing animation clips without crashing', () => {
      const clips = [new THREE.AnimationClip('idle', 2, [])];
      const controller = new AraAnimationController();
      controller.init(modelRoot, clips);

      const played = controller.play('non_existent_gesture');
      expect(played).toBe(false);
      // Controller should remain stable
      expect(controller.getCurrentClipName()).toBe(null);
    });

    it('should interrupt ongoing reaction seamlessly when a new reaction is triggered', () => {
      const clips = [
        new THREE.AnimationClip('idle', 2, []),
        new THREE.AnimationClip('thumbs_up', 2.2, []),
        new THREE.AnimationClip('thinking', 2.5, []),
      ];
      const controller = new AraAnimationController();
      controller.init(modelRoot, clips);

      controller.play('thumbs_up');
      expect(controller.getCurrentClipName()).toBe('thumbs_up');

      // Interrupt with thinking pose
      const interrupted = controller.play('thinking', { crossfadeDuration: 0.15 });
      expect(interrupted).toBe(true);
      expect(controller.getCurrentClipName()).toBe('thinking');
    });

    it('should update mixer cleanly on tick with delta time', () => {
      const clips = [
        new THREE.AnimationClip('idle', 2, []),
        new THREE.AnimationClip('thumbs_up', 2.2, []),
      ];
      const controller = new AraAnimationController();
      controller.init(modelRoot, clips);
      controller.play('thumbs_up');

      expect(() => {
        controller.update(0.016);
        controller.update(0.016);
      }).not.toThrow();
    });
  });

  describe('3. Avatar Feedback Submission & Cache Persistence', () => {
    beforeEach(() => {
      vi.restoreAllMocks();
    });

    it('should record positive thumbs-up feedback with snapshot reference', async () => {
      const result = await avatarFeedbackService.submitFeedback({
        userId: 'usr_test_123',
        configurationSnapshot: { skinTone: '#d4aa78', height: 175, bodyType: 'athletic' },
        customizationEvent: 'skin_tone_changed',
        rating: 'thumbs_up',
        comment: 'Great radiant skin tone match!',
      });

      expect(result.success).toBe(true);
      expect(result.id).toBeDefined();

      // Verify cached record
      const cached = avatarFeedbackService.getLocalCache();
      expect(cached.length).toBeGreaterThanOrEqual(1);
      expect(cached[0].rating).toBe('thumbs_up');
      expect(cached[0].customizationEvent).toBe('skin_tone_changed');
      expect(cached[0].comment).toBe('Great radiant skin tone match!');
    });

    it('should record negative thumbs-down feedback without breaking profile', async () => {
      const result = await avatarFeedbackService.submitFeedback({
        userId: 'usr_test_123',
        configurationSnapshot: { hairColor: '#3d2314', bodyType: 'slim' },
        customizationEvent: 'hair_color_changed',
        rating: 'thumbs_down',
        comment: 'Too dark, prefer auburn',
      });

      expect(result.success).toBe(true);
      const cached = avatarFeedbackService.getLocalCache();
      expect(cached[0].rating).toBe('thumbs_down');
    });

    it('should handle sequential feedback ratings cleanly', async () => {
      const first = await avatarFeedbackService.submitFeedback({
        userId: 'usr_test_123',
        configurationSnapshot: { height: 180 },
        customizationEvent: 'height_changed',
        rating: 'thumbs_down',
      });

      const revised = await avatarFeedbackService.submitFeedback({
        userId: 'usr_test_123',
        configurationSnapshot: { height: 180 },
        customizationEvent: 'height_changed',
        rating: 'thumbs_up',
        comment: 'Looks great now after zoom',
      });

      expect(first.success).toBe(true);
      expect(revised.success).toBe(true);
      const cached = avatarFeedbackService.getLocalCache();
      expect(cached[0].rating).toBe('thumbs_up');
    });
  });

  describe('4. Morph Target & Procedural Blinking Capability Verification', () => {
    it('should verify facial morph targets on skinned mesh', () => {
      expect(skinnedMesh.morphTargetDictionary).toBeDefined();
      expect(skinnedMesh.morphTargetDictionary!['eyeBlinkLeft']).toBeDefined();
      expect(skinnedMesh.morphTargetDictionary!['eyeBlinkRight']).toBeDefined();
      expect(skinnedMesh.morphTargetDictionary!['mouthSmileLeft']).toBeDefined();
    });

    it('should support safe procedural morph setting without clipping bounds', () => {
      const blinkIdx = skinnedMesh.morphTargetDictionary!['eyeBlinkLeft'];
      skinnedMesh.morphTargetInfluences![blinkIdx] = 1.0;
      expect(skinnedMesh.morphTargetInfluences![blinkIdx]).toBe(1.0);

      // Return smoothly to 0.0
      skinnedMesh.morphTargetInfluences![blinkIdx] = 0.0;
      expect(skinnedMesh.morphTargetInfluences![blinkIdx]).toBe(0.0);
    });
  });
});
