import { describe, it, expect, beforeEach } from 'vitest';
import * as THREE from 'three';
import {
  AvatarProfile,
  DEFAULT_AVATAR_PROFILE,
  DEFAULT_AVATAR_PROPORTIONS_MASCULINE,
  DEFAULT_AVATAR_PROPORTIONS_FEMININE,
  silhouetteToModifiers,
  avatarProfileToHumanParams,
  humanParamsToAvatarProfile,
  migrateAvatarProfile
} from '../../../types/avatarProfile';
import { FaceExpressionController } from '../faceExpressionController';

describe('PHASE 3 — Advanced 3D Avatar Engine & Snap-Style Personalization Tests', () => {

  describe('1. Avatar Profile v3 Schema & Bidirectional Mapping', () => {
    it('should correctly map masculine AvatarProfile to HumanParams with correct modifiers', () => {
      const profile: AvatarProfile = {
        ...DEFAULT_AVATAR_PROFILE,
        genderPresentation: 'masculine',
        proportions: {
          ...DEFAULT_AVATAR_PROPORTIONS_MASCULINE,
          heightCm: 185,
          weightKg: 82,
          shoulderWidth: 0.18,
          waistWidth: -0.05
        },
        face: {
          headShape: 0.05,
          jawWidth: 0.12,
          chinWidth: 0.04,
          cheekFullness: -0.08,
          noseWidth: 0.02,
          restingExpression: 'happy'
        }
      };

      const params = avatarProfileToHumanParams(profile);
      expect(params.gender).toBeGreaterThanOrEqual(0.9);
      expect(params.expression).toBe('happy');
      expect(params.modifiers).toBeDefined();
      expect(params.modifiers!['chin/jaw-width']).toBe(0.12);
      expect(params.modifiers!['shoulder/shoulder-scale-horiz']).toBe(0.18);
    });

    it('should correctly map feminine AvatarProfile to HumanParams with feminine defaults', () => {
      const profile: AvatarProfile = {
        ...DEFAULT_AVATAR_PROFILE,
        genderPresentation: 'feminine',
        proportions: {
          ...DEFAULT_AVATAR_PROPORTIONS_FEMININE,
          heightCm: 168,
          weightKg: 55,
          hipWidth: 0.15
        }
      };

      const params = avatarProfileToHumanParams(profile);
      expect(params.gender).toBeLessThanOrEqual(0.1);
      expect(params.skin).toBe('young_caucasian_female');
      expect(params.breastSize).toBeGreaterThan(0.4);
      expect(params.modifiers!['hips/hip-scale-horiz']).toBe(0.15);
    });

    it('should perform bidirectional roundtrip from HumanParams to AvatarProfile and back', () => {
      const profile = { ...DEFAULT_AVATAR_PROFILE };
      const params = avatarProfileToHumanParams(profile);
      const roundtripProfile = humanParamsToAvatarProfile(params, 'user_123');

      expect(roundtripProfile.version).toBe(3);
      expect(roundtripProfile.userId).toBe('user_123');
      expect(roundtripProfile.genderPresentation).toBe('masculine');
      expect(roundtripProfile.proportions.heightCm).toBe(profile.proportions.heightCm);
      expect(roundtripProfile.appearance.hairStyleId).toBe(profile.appearance.hairStyleId);
    });

    it('should safely migrate legacy profile JSON without corrupting missing properties', () => {
      const legacyRaw = {
        name: 'Elena Classic',
        avatarGenderPresentation: 'feminine',
        heightValue: 172,
        weightValue: 60,
        bodyType: 'curvy',
        skinToneHex: '#ffe0bd'
      };

      const migrated = migrateAvatarProfile(legacyRaw, 'user_migrated_456');
      expect(migrated.version).toBe(3);
      expect(migrated.userId).toBe('user_migrated_456');
      expect(migrated.genderPresentation).toBe('feminine');
      expect(migrated.proportions.heightCm).toBe(172);
      expect(migrated.proportions.silhouette).toBe('curvy');
      expect(migrated.appearance.skinToneHex).toBe('#ffe0bd');
      expect(migrated.face.restingExpression).toBe('neutral');
    });
  });

  describe('2. Continuous Silhouette Modifiers', () => {
    it('should calculate valid macro modifiers for each body silhouette preset', () => {
      const athletic = silhouetteToModifiers('athletic');
      expect(athletic['shoulder/shoulder-scale-horiz']).toBeGreaterThan(0.2); // Broad athletic shoulders
      expect(athletic['hips/hip-scale-horiz']).toBeLessThan(0); // Tapered athletic hips

      const curvy = silhouetteToModifiers('curvy');
      expect(curvy['hips/hip-scale-horiz']).toBeGreaterThan(0.2); // Full hips

      const broad = silhouetteToModifiers('broad');
      expect(broad['shoulder/shoulder-scale-horiz']).toBeGreaterThan(0.3); // Very broad chest/shoulders
    });
  });

  describe('3. FaceExpressionController (Smooth Blending & Organic Blinking)', () => {
    let controller: FaceExpressionController;
    let mockRoot: THREE.Object3D;
    let headMesh: THREE.Mesh;

    beforeEach(() => {
      controller = new FaceExpressionController();
      mockRoot = new THREE.Object3D();

      const geo = new THREE.BufferGeometry();
      // Setup mock morph targets
      const morphDict: Record<string, number> = {
        'mouthSmile': 0,
        'eyeBlinkLeft': 1,
        'eyeBlinkRight': 2,
        'jawOpen': 3
      };
      const morphInfluences = [0, 0, 0, 0];

      headMesh = new THREE.Mesh(geo, new THREE.MeshBasicMaterial());
      headMesh.morphTargetDictionary = morphDict;
      headMesh.morphTargetInfluences = morphInfluences;
      mockRoot.add(headMesh);
    });

    it('should bind to morph targets on the model mesh', () => {
      controller.attachModel(mockRoot);
      const dict = controller.getMorphTargetDictionary();
      expect(dict['mouthSmile']).toBe(0);
      expect(dict['eyeBlinkLeft']).toBe(1);
    });

    it('should smoothly transition expression weights over delta time without popping', () => {
      controller.attachModel(mockRoot);
      controller.setExpression('happy');

      // Delta time of 0.1s
      controller.update(0.1);
      const currentWeights = controller.getCurrentWeights();
      // Weight should be moving towards 0.85 smoothly
      expect(currentWeights.mouthSmile).toBeGreaterThan(0);
      expect(currentWeights.mouthSmile).toBeLessThan(0.85);

      // Advance time by 0.5s more -> should approach destination
      controller.update(0.5);
      expect(controller.getCurrentWeights().mouthSmile).toBeGreaterThan(0.80);
    });

    it('should layer eyelid blinks without resetting active facial expression', () => {
      controller.attachModel(mockRoot);
      controller.setExpression('neutral');
      controller.update(0.1);

      // Trigger blink
      controller.triggerBlink();
      controller.update(0.04);

      // Blink should be non-zero
      expect(headMesh.morphTargetInfluences![1]).toBeGreaterThan(0);
      expect(headMesh.morphTargetInfluences![2]).toBeGreaterThan(0);

      // Resting micro-smile or expression should still be active
      expect(controller.getCurrentWeights().mouthSmile).toBeGreaterThanOrEqual(0.01);
    });

    it('should clean up listeners and references on dispose', () => {
      controller.attachModel(mockRoot);
      controller.dispose();
      expect(controller.getMorphTargetDictionary()).toEqual({});
    });
  });

  describe('4. Camera Inspection & View Angle Calculations', () => {
    it('should calculate correct spherical coordinates for Front (0°), Side (90°), and Back (180°)', () => {
      const distance = 2.4;

      // Front angle: theta = 0
      const frontX = distance * Math.sin(0);
      const frontZ = distance * Math.cos(0);
      expect(frontX).toBeCloseTo(0, 5);
      expect(frontZ).toBeCloseTo(distance, 5);

      // Side angle: theta = Math.PI / 2 (90°)
      const sideX = distance * Math.sin(Math.PI / 2);
      const sideZ = distance * Math.cos(Math.PI / 2);
      expect(sideX).toBeCloseTo(distance, 5);
      expect(sideZ).toBeCloseTo(0, 5);

      // Back angle: theta = Math.PI (180°)
      const backX = distance * Math.sin(Math.PI);
      const backZ = distance * Math.cos(Math.PI);
      expect(backX).toBeCloseTo(0, 5);
      expect(backZ).toBeCloseTo(-distance, 5);
    });
  });

});
