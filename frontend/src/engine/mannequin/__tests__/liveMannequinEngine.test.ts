/**
 * YORVYN — Phase 6 Test Suite: Live 3D Fashion Mannequin Engine
 * Verifies live mannequin motion, idle breathing, camera director transitions,
 * stature scaling, and persistent base body integrity.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import * as THREE from 'three';
import {
  LiveMannequinEngine,
  LiveMannequinCameraDirector
} from '../index';

describe('LiveMannequinCameraDirector', () => {
  const target = new THREE.Vector3(0, 0.9, 0);
  const distance = 4.0;

  it('should compute front inspection position at 0 rad azimuth', () => {
    const pos = LiveMannequinCameraDirector.computeInspectionPosition(target, distance, 0, 0.05);
    expect(pos.x).toBeCloseTo(0, 3);
    expect(pos.z).toBeCloseTo(4.0, 3);
    expect(pos.y).toBeCloseTo(0.95, 3);
  });

  it('should compute side inspection position at 90 deg (PI/2 rad) azimuth', () => {
    const pos = LiveMannequinCameraDirector.computeInspectionPosition(target, distance, Math.PI / 2, 0.05);
    expect(pos.x).toBeCloseTo(4.0, 3);
    expect(pos.z).toBeCloseTo(0, 3);
  });

  it('should compute rear inspection position at 180 deg (PI rad) azimuth', () => {
    const pos = LiveMannequinCameraDirector.computeInspectionPosition(target, distance, Math.PI, 0.05);
    expect(pos.x).toBeCloseTo(0, 3);
    expect(pos.z).toBeCloseTo(-4.0, 3);
  });

  it('should generate portrait and full-body framing configurations', () => {
    const full = LiveMannequinCameraDirector.getFraming('full', 1.80);
    const portrait = LiveMannequinCameraDirector.getFraming('portrait', 1.80);

    expect(full.target.y).toBeCloseTo(0.828, 2);
    expect(portrait.target.y).toBeCloseTo(1.296, 2);
    expect(portrait.distance).toBeLessThan(full.distance);
  });

  it('should smoothly interpolate camera vectors using cubic ease-out', () => {
    const trans = {
      startTime: 1000,
      durationMs: 500,
      startPos: new THREE.Vector3(0, 1, 4),
      targetPos: new THREE.Vector3(4, 1, 0),
      startTarget: new THREE.Vector3(0, 1, 0),
      endTarget: new THREE.Vector3(0, 1, 0),
      isTransitioning: true
    };

    // At 50% elapsed time (1250ms), cubic ease-out progress = 1 - (1 - 0.5)^3 = 0.875
    const step = LiveMannequinCameraDirector.interpolateStep(trans, 1250);
    expect(step.completed).toBe(false);
    expect(step.position.x).toBeCloseTo(3.5, 1);

    // At 100% elapsed time (1500ms)
    const endStep = LiveMannequinCameraDirector.interpolateStep(trans, 1500);
    expect(endStep.completed).toBe(true);
    expect(endStep.position.x).toBeCloseTo(4.0, 3);
  });
});

describe('LiveMannequinEngine', () => {
  let engine: LiveMannequinEngine;
  let model: THREE.Group;
  let clips: THREE.AnimationClip[];

  beforeEach(() => {
    engine = new LiveMannequinEngine();
    model = new THREE.Group();

    // Create synthetic Three.js animation clips matching Ara 3D Gen clips
    const track = new THREE.VectorKeyframeTrack('.position', [0, 1, 2], [0, 0, 0, 0, 0.02, 0, 0, 0, 0]);
    clips = [
      new THREE.AnimationClip('Idle', 2.0, [track]),
      new THREE.AnimationClip('Turn', 2.5, [track]),
      new THREE.AnimationClip('Present Outfit', 2.0, [track]),
      new THREE.AnimationClip('Look at Garment', 1.8, [track]),
      new THREE.AnimationClip('Thumbs Up', 2.2, [track]),
      new THREE.AnimationClip('Present Both', 2.0, [track]),
      new THREE.AnimationClip('Thinking', 2.0, [track]),
      new THREE.AnimationClip('Curious', 2.0, [track])
    ];

    engine.init(model, clips);
  });

  it('should initialize and start the breathing idle loop as default baseline', () => {
    const anim = engine.getAnimationController();
    expect(anim.getCurrentClipName()).toBe('idle');
    expect(anim.isPlaying()).toBe(true);
  });

  it('should trigger outfit presentation gestures upon garment equip', () => {
    engine.onGarmentEquipped('top');
    expect(engine.getAnimationController().getCurrentClipName()).toBe('present outfit');

    engine.onGarmentEquipped('shoes');
    expect(engine.getAnimationController().getCurrentClipName()).toBe('look at garment');

    engine.onGarmentEquipped('outfit');
    expect(engine.getAnimationController().getCurrentClipName()).toBe('turn');
  });

  it('should support editorial fashion poses', () => {
    engine.setPose('fashion_runway');
    expect(engine.getCurrentPose()).toBe('fashion_runway');
    expect(engine.getAnimationController().getCurrentClipName()).toBe('present both');

    engine.setPose('crossed_arms');
    expect(engine.getCurrentPose()).toBe('crossed_arms');
    expect(engine.getAnimationController().getCurrentClipName()).toBe('thinking');

    engine.setPose('standing');
    expect(engine.getCurrentPose()).toBe('standing');
    expect(engine.getAnimationController().getCurrentClipName()).toBe('idle');
  });

  it('should accurately compute stature and silhouette scaling', () => {
    const slim = LiveMannequinEngine.computeStatureScale({ heightCm: 180, silhouetteId: 'slim' });
    expect(slim.scaleY).toBeCloseTo(1.80 / 1.70, 3);
    expect(slim.scaleX).toBeLessThan(slim.scaleY); // Slim is narrower

    const athletic = LiveMannequinEngine.computeStatureScale({ heightCm: 180, silhouetteId: 'athletic' });
    expect(athletic.scaleX).toBeGreaterThan(slim.scaleX); // Athletic is broader
  });

  it('should advance animation clock cleanly on update', () => {
    expect(() => engine.update(0.016)).not.toThrow();
  });

  it('should verify persistent base body integrity', () => {
    const verts = new Float32Array([
      0, 1.65, 0, // Head
      0, 1.44, 0, // Neck
      0, 1.10, 0, // Torso
      0.3, 1.10, 0, // Arm
      0, 0.50, 0, // Leg
      0, 0.05, 0  // Foot
    ]);
    const idx = new Uint32Array([0, 1, 2, 2, 3, 4, 3, 4, 5]);

    const report = engine.verifyBodyIntegrity(verts, idx);
    expect(report.vertexCount).toBe(6);
    expect(report.hasHoles).toBe(false);
  });

  it('should cleanly dispose of resources without memory leaks', () => {
    expect(() => engine.dispose()).not.toThrow();
    // After disposal, update is safe no-op
    expect(() => engine.update(0.016)).not.toThrow();
  });
});

