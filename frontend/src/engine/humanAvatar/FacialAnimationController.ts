/**
 * Yorvyn — Comprehensive Facial Animation Controller
 * 
 * Manages human-like facial expressions, eye saccades, gaze orientation,
 * asymmetric eyebrow animation, and natural eyelid blinking cycles.
 * Smoothly blends ARKit/Oculus morph targets with zero mesh distortion.
 */

import * as THREE from 'three';

export type EmotionType =
  | 'neutral'
  | 'happy'
  | 'frown'
  | 'surprise'
  | 'confusion'
  | 'curiosity'
  | 'thinking'
  | 'empathy'
  | 'serious'
  | 'speaking';

export type GazeTarget = 'user' | 'camera' | 'thoughtful_away' | 'garment' | 'down';

export interface FacialTransitionOptions {
  durationSeconds?: number;
  intensity?: number;
}

export const EMOTION_MORPH_PRESETS: Record<EmotionType, Record<string, number>> = {
  neutral: {
    mouthSmile: 0.08,
    browInnerUp: 0.0,
    browDownLeft: 0.0,
    browDownRight: 0.0,
  },
  happy: {
    mouthSmile: 0.85,
    eyeSquintLeft: 0.35,
    eyeSquintRight: 0.35,
    browOuterUpLeft: 0.2,
    browOuterUpRight: 0.2,
  },
  frown: {
    mouthFrown: 0.65,
    browInnerUp: 0.75,
    browDownLeft: 0.2,
    browDownRight: 0.2,
  },
  surprise: {
    eyeWideLeft: 0.8,
    eyeWideRight: 0.8,
    browInnerUp: 0.85,
    browOuterUpLeft: 0.85,
    browOuterUpRight: 0.85,
    jawOpen: 0.25,
  },
  confusion: {
    browDownLeft: 0.7,
    browInnerUp: 0.4,
    browDownRight: 0.1,
    mouthFrown: 0.3,
    eyeSquintLeft: 0.25,
  },
  curiosity: {
    browOuterUpRight: 0.6,
    browInnerUp: 0.35,
    eyeWideRight: 0.3,
    mouthSmile: 0.2,
  },
  thinking: {
    browDownLeft: 0.45,
    browDownRight: 0.45,
    eyeSquintLeft: 0.25,
    eyeSquintRight: 0.25,
    mouthSmile: 0.05,
  },
  empathy: {
    browInnerUp: 0.65,
    mouthSmile: 0.25,
    eyeSquintLeft: 0.2,
    eyeSquintRight: 0.2,
  },
  serious: {
    browDownLeft: 0.35,
    browDownRight: 0.35,
    mouthSmile: 0.0,
    mouthPress: 0.2,
  },
  speaking: {
    mouthSmile: 0.12,
    browOuterUpLeft: 0.1,
    browOuterUpRight: 0.1,
  },
};

export class FacialAnimationController {
  private targetMeshes: THREE.Mesh[] = [];
  private leftEyeBone: THREE.Bone | null = null;
  private rightEyeBone: THREE.Bone | null = null;
  private headBone: THREE.Bone | null = null;

  // Active morph target weights
  private currentWeights: Map<string, number> = new Map();
  private initialWeights: Map<string, number> = new Map();
  private targetWeights: Map<string, number> = new Map();
  private transitionDuration = 0.3;
  private transitionElapsed = 0.3;

  // Clock
  private clockTime = 0.0;

  // Blinking State Machine
  private blinkPhase: 'idle' | 'closing' | 'opening' = 'idle';
  private blinkProgress = 0.0;
  private nextBlinkTime = 0;
  private isDoubleBlink = false;
  private readonly BLINK_CLOSE_RATE = 16.0; // Rapid closure (~60ms)
  private readonly BLINK_OPEN_RATE = 10.0;  // Natural ease-out opening (~100ms)

  // Saccadic Eye Gaze
  private currentGazeTarget: GazeTarget = 'user';
  private eyeRotation = new THREE.Vector2(0, 0); // Yaw, Pitch in radians
  private targetEyeRotation = new THREE.Vector2(0, 0);
  private nextSaccadeTime = 0;

  // Current Emotion State
  private currentEmotion: EmotionType = 'neutral';
  private currentIntensity = 1.0;

  init(root: THREE.Object3D): void {
    this.targetMeshes = [];
    this.leftEyeBone = null;
    this.rightEyeBone = null;
    this.headBone = null;
    this.currentWeights.clear();
    this.initialWeights.clear();
    this.targetWeights.clear();
    this.clockTime = 0.0;

    root.traverse((obj) => {
      if ((obj as THREE.Bone).isBone) {
        const b = obj as THREE.Bone;
        if (b.name === 'LeftEye') this.leftEyeBone = b;
        if (b.name === 'RightEye') this.rightEyeBone = b;
        if (b.name === 'Head') this.headBone = b;
      }

      if ((obj as THREE.Mesh).isMesh) {
        const mesh = obj as THREE.Mesh;
        if (mesh.morphTargetDictionary && mesh.morphTargetInfluences) {
          this.targetMeshes.push(mesh);
        }
      }
    });

    this.nextBlinkTime = 2.5 + Math.random() * 2.5;
    this.nextSaccadeTime = 1.5 + Math.random() * 2.0;
  }

  setEmotion(emotion: EmotionType, options: FacialTransitionOptions = {}): void {
    this.currentEmotion = emotion;
    this.currentIntensity = options.intensity ?? 1.0;
    this.transitionDuration = Math.max(options.durationSeconds || 0.3, 0.05);
    this.transitionElapsed = 0.0;

    // Snapshot current weights to smoothly interpolate from
    this.initialWeights = new Map(this.currentWeights);

    const preset = EMOTION_MORPH_PRESETS[emotion] || EMOTION_MORPH_PRESETS.neutral;

    // Reset target weights and populate
    this.targetWeights.clear();
    for (const [shape, weight] of Object.entries(preset)) {
      this.targetWeights.set(shape, weight * this.currentIntensity);
    }
  }

  setGazeTarget(gaze: GazeTarget): void {
    this.currentGazeTarget = gaze;
    this.updateTargetGazeOrientation();
  }

  triggerBlink(): void {
    this.blinkPhase = 'closing';
    this.blinkProgress = 0.0;
  }

  update(delta: number): void {
    if (this.targetMeshes.length === 0 && !this.leftEyeBone) return;

    this.clockTime += delta;
    const now = this.clockTime;

    // ── 1. Natural Blinking Cycle ───────────────────────────────────────────
    if (this.blinkPhase === 'idle') {
      if (now >= this.nextBlinkTime) {
        this.blinkPhase = 'closing';
        this.isDoubleBlink = Math.random() < 0.15; // 15% probability of double blink
      }
    } else if (this.blinkPhase === 'closing') {
      this.blinkProgress += delta * this.BLINK_CLOSE_RATE;
      if (this.blinkProgress >= 1.0) {
        this.blinkProgress = 1.0;
        this.blinkPhase = 'opening';
      }
    } else if (this.blinkPhase === 'opening') {
      this.blinkProgress -= delta * this.BLINK_OPEN_RATE;
      if (this.blinkProgress <= 0.0) {
        this.blinkProgress = 0.0;
        if (this.isDoubleBlink) {
          this.isDoubleBlink = false;
          this.blinkPhase = 'closing'; // Trigger quick second flutter
        } else {
          this.blinkPhase = 'idle';
          this.nextBlinkTime = now + 2.4 + Math.random() * 3.2;
        }
      }
    }

    // ── 2. Eye Saccades & Gaze Drift ────────────────────────────────────────
    if (now >= this.nextSaccadeTime) {
      this.updateTargetGazeOrientation();
      this.nextSaccadeTime = now + 1.2 + Math.random() * 2.5;
    }

    // Saccade interpolation (rapid micro-snaps)
    this.eyeRotation.x += (this.targetEyeRotation.x - this.eyeRotation.x) * Math.min(delta * 18.0, 1.0);
    this.eyeRotation.y += (this.targetEyeRotation.y - this.eyeRotation.y) * Math.min(delta * 18.0, 1.0);

    if (this.leftEyeBone && this.rightEyeBone) {
      this.leftEyeBone.rotation.y = this.eyeRotation.x;
      this.leftEyeBone.rotation.x = this.eyeRotation.y;
      this.rightEyeBone.rotation.y = this.eyeRotation.x;
      this.rightEyeBone.rotation.x = this.eyeRotation.y;
    }

    // ── 3. Smooth Expression Morph Blending ─────────────────────────────────
    this.transitionElapsed = Math.min(this.transitionElapsed + delta, this.transitionDuration);
    const t = this.transitionElapsed / this.transitionDuration;
    // Cubic Hermite smoothstep for natural organic acceleration & deceleration
    const progress = t * t * (3 - 2 * t);

    const allShapes = new Set([
      ...Array.from(this.initialWeights.keys()),
      ...Array.from(this.currentWeights.keys()),
      ...Array.from(this.targetWeights.keys()),
    ]);

    for (const shape of allShapes) {
      const initial = this.initialWeights.get(shape) || 0.0;
      const target = this.targetWeights.get(shape) || 0.0;
      const next = t >= 1.0 ? target : initial + (target - initial) * progress;
      this.currentWeights.set(shape, next);

      // Layer eyelid blink over eye blendshapes
      if (shape === 'eyeBlinkLeft' || shape === 'eyeBlinkRight') {
        const combined = Math.min(1.0, next + this.blinkProgress);
        this.applyWeight(shape, combined);
      } else {
        this.applyWeight(shape, next);
      }
    }

    // Guarantee eyelids close even if no expression defines eyeBlink
    if (!allShapes.has('eyeBlinkLeft')) {
      this.applyWeight('eyeBlinkLeft', this.blinkProgress);
      this.applyWeight('eyeBlinkRight', this.blinkProgress);
    }
  }

  private updateTargetGazeOrientation(): void {
    const jitterYaw = (Math.random() - 0.5) * 0.04;
    const jitterPitch = (Math.random() - 0.5) * 0.03;

    switch (this.currentGazeTarget) {
      case 'user':
      case 'camera':
        this.targetEyeRotation.set(jitterYaw, jitterPitch);
        break;
      case 'thoughtful_away':
        // Glance up and slightly to the left/right
        this.targetEyeRotation.set(0.18 + jitterYaw, 0.12 + jitterPitch);
        break;
      case 'garment':
        // Glance down toward outfit
        this.targetEyeRotation.set(jitterYaw * 0.5, -0.25 + jitterPitch);
        break;
      case 'down':
        this.targetEyeRotation.set(0.0, -0.32);
        break;
    }
  }

  private applyWeight(shapeName: string, weight: number): void {
    for (const mesh of this.targetMeshes) {
      if (mesh.morphTargetDictionary && mesh.morphTargetInfluences) {
        const idx = mesh.morphTargetDictionary[shapeName];
        if (idx !== undefined) {
          mesh.morphTargetInfluences[idx] = weight;
        }
      }
    }
  }

  getCurrentEmotion(): EmotionType {
    return this.currentEmotion;
  }

  getHeadBone(): THREE.Bone | null {
    return this.headBone;
  }

  dispose(): void {
    this.targetMeshes = [];
    this.leftEyeBone = null;
    this.rightEyeBone = null;
    this.headBone = null;
    this.currentWeights.clear();
    this.targetWeights.clear();
  }
}
