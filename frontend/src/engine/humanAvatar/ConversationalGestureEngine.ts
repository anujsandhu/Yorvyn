/**
 * Yorvyn — Conversational Gesture & Human Idle Engine
 * 
 * Provides natural, human-like upper body gestures, head tilts, small nods,
 * hand emphasis, procedural breathing cycles, and pelvic weight shifting.
 * Prevents hand-body mesh collisions, repetitive robotic motions, and animation snapping.
 */

import * as THREE from 'three';

export type GestureId =
  | 'open_palm'
  | 'explain'
  | 'emphasis'
  | 'small_nod'
  | 'head_tilt'
  | 'thinking'
  | 'point'
  | 'greeting'
  | 'listening_posture'
  | 'speaking_posture'
  | 'idle_breathing';

export interface GestureOptions {
  durationSeconds?: number;
  speed?: number;
  amplitude?: number;
  arm?: 'Left' | 'Right';
  onComplete?: () => void;
}

interface BoneRefMap {
  Hips: THREE.Bone | null;
  Spine: THREE.Bone | null;
  Spine1: THREE.Bone | null;
  Spine2: THREE.Bone | null;
  Neck: THREE.Bone | null;
  Head: THREE.Bone | null;
  LeftShoulder: THREE.Bone | null;
  LeftArm: THREE.Bone | null;
  LeftForeArm: THREE.Bone | null;
  LeftHand: THREE.Bone | null;
  RightShoulder: THREE.Bone | null;
  RightArm: THREE.Bone | null;
  RightForeArm: THREE.Bone | null;
  RightHand: THREE.Bone | null;
}

export class ConversationalGestureEngine {
  private bones: BoneRefMap = {
    Hips: null,
    Spine: null,
    Spine1: null,
    Spine2: null,
    Neck: null,
    Head: null,
    LeftShoulder: null,
    LeftArm: null,
    LeftForeArm: null,
    LeftHand: null,
    RightShoulder: null,
    RightArm: null,
    RightForeArm: null,
    RightHand: null,
  };

  // Base resting bone transforms (Euler radians and positions)
  private restRotations: Map<string, THREE.Euler> = new Map();
  private restPositions: Map<string, THREE.Vector3> = new Map();

  // Active gesture state
  private activeGesture: GestureId = 'idle_breathing';
  private gestureTime = 0.0;
  private gestureDuration = 3.0;
  private gestureProgress = 0.0;
  private gestureBlendWeight = 0.0;
  private isOneShot = false;
  private onCompleteCallback: (() => void) | null = null;

  // Procedural Idle Time Accumulator
  private idleTime = 0.0;

  // Gesture hand alternation
  private activeArm: 'Left' | 'Right' = 'Right';
  private lastArmUsed: 'Left' | 'Right' = 'Left';

  init(root: THREE.Object3D): void {
    this.restRotations.clear();
    this.restPositions.clear();

    root.traverse((obj) => {
      if ((obj as THREE.Bone).isBone) {
        const b = obj as THREE.Bone;
        if (b.name in this.bones) {
          (this.bones as any)[b.name] = b;
          this.restRotations.set(b.name, b.rotation.clone());
          this.restPositions.set(b.name, b.position.clone());
        }
      }
    });
  }

  /**
   * Triggers a semantic conversational gesture.
   */
  triggerGesture(gesture: GestureId, options: GestureOptions = {}): void {
    this.activeGesture = gesture;
    this.gestureTime = 0.0;
    this.gestureDuration = options.durationSeconds || this.getDefaultGestureDuration(gesture);
    this.gestureProgress = 0.0;
    this.gestureBlendWeight = 0.0;
    this.isOneShot = gesture !== 'idle_breathing' && gesture !== 'listening_posture' && gesture !== 'speaking_posture';
    this.onCompleteCallback = options.onComplete || null;

    // Support explicit arm selection or alternate starting with Right
    if (options.arm) {
      this.activeArm = options.arm;
    } else {
      this.activeArm = this.lastArmUsed === 'Left' ? 'Right' : 'Left';
    }
    this.lastArmUsed = this.activeArm;
  }

  private getDefaultGestureDuration(gesture: GestureId): number {
    switch (gesture) {
      case 'small_nod':
        return 1.2;
      case 'head_tilt':
        return 1.8;
      case 'emphasis':
        return 1.6;
      case 'open_palm':
        return 2.4;
      case 'explain':
        return 3.0;
      case 'point':
        return 2.5;
      case 'greeting':
        return 2.2;
      case 'thinking':
        return 2.8;
      default:
        return 2.5;
    }
  }

  /**
   * Main per-frame procedural gesture and idle update.
   * @param delta Delta time in seconds.
   */
  update(delta: number): void {
    this.idleTime += delta;

    // ── 1. Gesture Progress & Blend Weight ──────────────────────────────────
    if (this.isOneShot) {
      this.gestureTime += delta;
      this.gestureProgress = Math.min(1.0, this.gestureTime / this.gestureDuration);

      // Smooth bell envelope (eases in, holds, eases back to rest)
      const t = this.gestureProgress;
      if (t < 0.25) {
        this.gestureBlendWeight = Math.sin((t / 0.25) * (Math.PI / 2));
      } else if (t < 0.75) {
        this.gestureBlendWeight = 1.0;
      } else {
        const fade = (t - 0.75) / 0.25;
        this.gestureBlendWeight = Math.cos(fade * (Math.PI / 2));
      }

      if (this.gestureProgress >= 1.0) {
        this.isOneShot = false;
        this.activeGesture = 'idle_breathing';
        this.gestureBlendWeight = 0.0;
        if (this.onCompleteCallback) {
          this.onCompleteCallback();
          this.onCompleteCallback = null;
        }
      }
    } else {
      // Looping postures (breathing, listening, speaking posture)
      this.gestureBlendWeight = Math.min(1.0, this.gestureBlendWeight + delta * 2.5);
    }

    // ── 2. Procedural Human Breathing Motion ────────────────────────────────
    // Breathing frequency: ~0.24 Hz (~14.4 breaths/min)
    // NOTE: When activeGesture is 'idle_breathing', the Ara AnimationController's
    // baked skeletal idle loop is actively playing. We preserve that animation
    // and only layer procedural breathing when an active non-idle gesture is active,
    // and always additive to rest transforms to avoid bone deformation or pelvic crushing.
    if (this.activeGesture !== 'idle_breathing') {
      const breathCycle = Math.sin(this.idleTime * 1.5);
      const microSway = Math.sin(this.idleTime * 0.45);

      const rSpine = this.restRotations.get('Spine');
      if (this.bones.Spine && rSpine) {
        this.bones.Spine.rotation.x = rSpine.x + 0.015 * breathCycle;
        this.bones.Spine.rotation.y = rSpine.y + 0.008 * microSway;
      }
      const rSpine1 = this.restRotations.get('Spine1');
      if (this.bones.Spine1 && rSpine1) {
        this.bones.Spine1.rotation.x = rSpine1.x + 0.02 * breathCycle;
      }
      const rSpine2 = this.restRotations.get('Spine2');
      if (this.bones.Spine2 && rSpine2) {
        this.bones.Spine2.rotation.x = rSpine2.x + 0.012 * breathCycle;
      }

      const rHips = this.restRotations.get('Hips');
      const rHipsPos = this.restPositions.get('Hips');
      if (this.bones.Hips && rHips) {
        this.bones.Hips.rotation.z = rHips.z + 0.01 * microSway;
      }
      if (this.bones.Hips && rHipsPos) {
        this.bones.Hips.position.y = rHipsPos.y + 0.004 * breathCycle;
      }
    }

    // ── 3. Apply Active Gesture Layer ───────────────────────────────────────
    this.applyActiveGestureLayer();
  }

  private applyActiveGestureLayer(): void {
    const w = this.gestureBlendWeight;
    if (w <= 0.001) return;

    const arm = this.activeArm;
    const otherArm = this.activeArm === 'Right' ? 'Left' : 'Right';
    const sign = this.activeArm === 'Left' ? -1 : 1;

    switch (this.activeGesture) {
      case 'small_nod': {
        // Natural double nod
        const nodAngle = Math.sin(this.gestureProgress * Math.PI * 4) * 0.12 * w;
        const rHead = this.restRotations.get('Head');
        const rNeck = this.restRotations.get('Neck');
        if (this.bones.Head && rHead) this.bones.Head.rotation.x = rHead.x + nodAngle;
        if (this.bones.Neck && rNeck) this.bones.Neck.rotation.x = rNeck.x + nodAngle * 0.4;
        break;
      }

      case 'head_tilt': {
        // Inquisitive head tilt
        const tiltAngle = Math.sin(this.gestureProgress * Math.PI) * 0.14 * w;
        const rHead = this.restRotations.get('Head');
        if (this.bones.Head && rHead) {
          this.bones.Head.rotation.z = rHead.z + tiltAngle * sign;
          this.bones.Head.rotation.y = rHead.y + tiltAngle * 0.5 * sign;
        }
        break;
      }

      case 'open_palm': {
        // Smoothly raises arm outward with palm facing upward
        const raise = Math.sin(this.gestureProgress * Math.PI) * w;
        const targetArm = this.bones[`${arm}Arm` as keyof BoneRefMap];
        const targetForeArm = this.bones[`${arm}ForeArm` as keyof BoneRefMap];
        const targetHand = this.bones[`${arm}Hand` as keyof BoneRefMap];
        const rArm = this.restRotations.get(`${arm}Arm`);
        const rForeArm = this.restRotations.get(`${arm}ForeArm`);
        const rHand = this.restRotations.get(`${arm}Hand`);

        if (targetArm && rArm) {
          targetArm.rotation.x = rArm.x - 0.45 * raise;
          targetArm.rotation.z = rArm.z - 0.35 * raise * sign;
        }
        if (targetForeArm && rForeArm) {
          targetForeArm.rotation.x = rForeArm.x + 0.75 * raise;
          targetForeArm.rotation.y = rForeArm.y + 0.5 * raise * sign; // supination (palm up)
        }
        if (targetHand && rHand) {
          targetHand.rotation.z = rHand.z + 0.2 * raise * sign;
        }
        break;
      }

      case 'explain': {
        // Rhythmic bilateral conversational explanation
        const cycle = Math.sin(this.gestureProgress * Math.PI * 3) * 0.15;
        const raise = Math.sin(this.gestureProgress * Math.PI) * w;

        // Primary arm
        const pArm = this.bones[`${arm}Arm` as keyof BoneRefMap];
        const pForeArm = this.bones[`${arm}ForeArm` as keyof BoneRefMap];
        const rPArm = this.restRotations.get(`${arm}Arm`);
        const rPForeArm = this.restRotations.get(`${arm}ForeArm`);
        if (pArm && rPArm) pArm.rotation.x = rPArm.x + (-0.4 + cycle) * raise;
        if (pForeArm && rPForeArm) pForeArm.rotation.x = rPForeArm.x + (0.7 + cycle * 0.5) * raise;

        // Secondary arm mirrors with lower amplitude
        const sArm = this.bones[`${otherArm}Arm` as keyof BoneRefMap];
        const sForeArm = this.bones[`${otherArm}ForeArm` as keyof BoneRefMap];
        const rSArm = this.restRotations.get(`${otherArm}Arm`);
        const rSForeArm = this.restRotations.get(`${otherArm}ForeArm`);
        if (sArm && rSArm) sArm.rotation.x = rSArm.x + (-0.25 - cycle * 0.5) * raise;
        if (sForeArm && rSForeArm) sForeArm.rotation.x = rSForeArm.x + (0.5 - cycle * 0.3) * raise;
        break;
      }

      case 'emphasis': {
        // Downward hand beat matching spoken stress
        const beat = Math.sin(this.gestureProgress * Math.PI * 2) * w;
        const targetArm = this.bones[`${arm}Arm` as keyof BoneRefMap];
        const targetForeArm = this.bones[`${arm}ForeArm` as keyof BoneRefMap];
        const rArm = this.restRotations.get(`${arm}Arm`);
        const rForeArm = this.restRotations.get(`${arm}ForeArm`);
        const rHead = this.restRotations.get('Head');
        if (targetArm && rArm) targetArm.rotation.x = rArm.x - 0.35 * w + beat * 0.12;
        if (targetForeArm && rForeArm) targetForeArm.rotation.x = rForeArm.x + 0.65 * w + beat * 0.2;
        if (this.bones.Head && rHead) this.bones.Head.rotation.x = rHead.x + 0.08 * beat;
        break;
      }

      case 'thinking': {
        // Hand to chin posture
        const raise = Math.sin(this.gestureProgress * Math.PI) * w;
        const targetArm = this.bones.RightArm;
        const targetForeArm = this.bones.RightForeArm;
        const targetHand = this.bones.RightHand;
        const rArm = this.restRotations.get('RightArm');
        const rForeArm = this.restRotations.get('RightForeArm');
        const rHand = this.restRotations.get('RightHand');
        const rHead = this.restRotations.get('Head');

        if (targetArm && rArm) {
          targetArm.rotation.x = rArm.x - 0.65 * raise;
          targetArm.rotation.z = rArm.z - 0.25 * raise;
        }
        if (targetForeArm && rForeArm) {
          targetForeArm.rotation.x = rForeArm.x + 1.35 * raise;
          targetForeArm.rotation.y = rForeArm.y + 0.45 * raise;
        }
        if (targetHand && rHand) {
          targetHand.rotation.x = rHand.x + 0.3 * raise;
        }
        if (this.bones.Head && rHead) {
          this.bones.Head.rotation.z = rHead.z - 0.1 * raise;
          this.bones.Head.rotation.x = rHead.x + 0.08 * raise;
        }
        break;
      }

      case 'point': {
        // Pointing gesture toward outfit
        const raise = Math.sin(this.gestureProgress * Math.PI) * w;
        const targetArm = this.bones.RightArm;
        const targetForeArm = this.bones.RightForeArm;
        const rArm = this.restRotations.get('RightArm');
        const rForeArm = this.restRotations.get('RightForeArm');
        const rHead = this.restRotations.get('Head');

        if (targetArm && rArm) {
          targetArm.rotation.x = rArm.x - 0.5 * raise;
          targetArm.rotation.z = rArm.z - 0.15 * raise;
        }
        if (targetForeArm && rForeArm) {
          targetForeArm.rotation.x = rForeArm.x + 0.85 * raise;
        }
        if (this.bones.Head && rHead) {
          this.bones.Head.rotation.x = rHead.x + 0.15 * raise; // glancing down
        }
        break;
      }

      case 'greeting': {
        // Welcoming hand wave / open palm
        const wave = Math.sin(this.gestureProgress * Math.PI * 6) * 0.18;
        const raise = Math.sin(this.gestureProgress * Math.PI) * w;
        const targetArm = this.bones.RightArm;
        const targetForeArm = this.bones.RightForeArm;
        const targetHand = this.bones.RightHand;
        const rArm = this.restRotations.get('RightArm');
        const rForeArm = this.restRotations.get('RightForeArm');
        const rHand = this.restRotations.get('RightHand');

        if (targetArm && rArm) {
          targetArm.rotation.x = rArm.x - 0.75 * raise;
          targetArm.rotation.z = rArm.z - 0.4 * raise;
        }
        if (targetForeArm && rForeArm) {
          targetForeArm.rotation.x = rForeArm.x + 1.1 * raise;
        }
        if (targetHand && rHand) {
          targetHand.rotation.z = rHand.z + wave * raise;
        }
        break;
      }

      case 'listening_posture': {
        // Attentive forward listening posture
        const rSpine = this.restRotations.get('Spine');
        const rNeck = this.restRotations.get('Neck');
        const rHead = this.restRotations.get('Head');
        if (this.bones.Spine && rSpine) this.bones.Spine.rotation.x = rSpine.x + 0.04 * w;
        if (this.bones.Neck && rNeck) this.bones.Neck.rotation.x = rNeck.x - 0.03 * w;
        if (this.bones.Head && rHead) this.bones.Head.rotation.x = rHead.x + 0.05 * w;
        break;
      }

      case 'speaking_posture': {
        // Open upright speaking posture
        const rSpine = this.restRotations.get('Spine');
        const rSpine2 = this.restRotations.get('Spine2');
        if (this.bones.Spine && rSpine) this.bones.Spine.rotation.x = rSpine.x - 0.02 * w;
        if (this.bones.Spine2 && rSpine2) this.bones.Spine2.rotation.x = rSpine2.x - 0.015 * w;
        break;
      }
    }
  }

  getActiveGesture(): GestureId {
    return this.activeGesture;
  }

  dispose(): void {
    // Reset bones to rest
    for (const [boneName, rot] of this.restRotations.entries()) {
      const b = (this.bones as any)[boneName];
      if (b) b.rotation.copy(rot);
    }
    for (const [boneName, pos] of this.restPositions.entries()) {
      const b = (this.bones as any)[boneName];
      if (b) b.position.copy(pos);
    }
  }
}
