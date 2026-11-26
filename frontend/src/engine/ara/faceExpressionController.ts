/**
 * Yorvyn — Face Expression & Morph Target Controller (Phase 4)
 * 
 * Manages smooth ARKit facial blend shapes, natural blinking cycles,
 * and emotional expressions (Happy, Thinking, Surprised, Confident/Determined, Neutral)
 * with continuous interpolation and zero mesh corruption.
 */

import * as THREE from 'three';
import { EXPRESSION_WEIGHTS, ExpressionId, FaceWeights } from './core/face';

export interface ExpressionTransitionOptions {
  durationSeconds?: number;
  intensity?: number;
}

export class FaceExpressionController {
  private targetMeshes: THREE.Mesh[] = [];
  private currentWeights: Map<string, number> = new Map();
  private targetWeights: Map<string, number> = new Map();
  private transitionSpeed = 5.0; // Higher = faster transition (~250-300ms)
  
  // Natural Blinking State
  private blinkPhase: 'idle' | 'closing' | 'opening' = 'idle';
  private blinkProgress = 0;
  private nextBlinkTime = 0;
  private readonly BLINK_CLOSE_SPEED = 14.0;
  private readonly BLINK_OPEN_SPEED = 10.0;

  // Active Expression
  private currentExpression: ExpressionId = 'neutral';

  /**
   * Scans an Object3D hierarchy and caches all meshes containing morphTargetDictionary.
   */
  init(root: THREE.Object3D): void {
    this.targetMeshes = [];
    this.currentWeights.clear();
    this.targetWeights.clear();

    root.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        if (mesh.morphTargetDictionary && mesh.morphTargetInfluences) {
          this.targetMeshes.push(mesh);
        }
      }
    });

    this.nextBlinkTime = performance.now() + 2500 + Math.random() * 2000;
  }

  /**
   * Sets target expression with smooth interpolation.
   */
  setExpression(expr: ExpressionId, options: ExpressionTransitionOptions = {}): void {
    this.currentExpression = expr;
    const duration = options.durationSeconds || 0.3;
    this.transitionSpeed = 1.0 / Math.max(duration, 0.05);

    const weights: FaceWeights = EXPRESSION_WEIGHTS[expr] || EXPRESSION_WEIGHTS.neutral;
    const intensity = options.intensity ?? 1.0;

    // Clear targets and set new ones
    this.targetWeights.clear();
    for (const [shape, weight] of Object.entries(weights)) {
      if (typeof weight === 'number') {
        this.targetWeights.set(shape, weight * intensity);
      }
    }

    // Default gentle resting atelier micro-smile for approachable premium editorial aesthetic
    if (!this.targetWeights.has('mouthSmile') && expr === 'neutral') {
      this.targetWeights.set('mouthSmile', 0.08);
    }
  }

  /**
   * Direct manual morph target adjustment (e.g. for custom sliders).
   */
  setShapeWeight(shapeName: string, weight: number): void {
    this.targetWeights.set(shapeName, weight);
    this.currentWeights.set(shapeName, weight);
    this.applyWeightToMeshes(shapeName, weight);
  }

  /**
   * Updates blend shapes and blinking per frame.
   * @param delta Delta time in seconds.
   */
  update(delta: number): void {
    if (this.targetMeshes.length === 0) return;

    // 1. Natural Eyelid Blinking State Machine
    const now = performance.now();
    if (this.blinkPhase === 'idle') {
      if (now >= this.nextBlinkTime) {
        this.blinkPhase = 'closing';
      }
    } else if (this.blinkPhase === 'closing') {
      this.blinkProgress += delta * this.BLINK_CLOSE_SPEED;
      if (this.blinkProgress >= 1.0) {
        this.blinkProgress = 1.0;
        this.blinkPhase = 'opening';
      }
    } else if (this.blinkPhase === 'opening') {
      this.blinkProgress -= delta * this.BLINK_OPEN_SPEED;
      if (this.blinkProgress <= 0.0) {
        this.blinkProgress = 0.0;
        this.blinkPhase = 'idle';
        this.nextBlinkTime = now + 2800 + Math.random() * 3200;
      }
    }

    // 2. Smoothly Lerp Morph Target Influences
    const blendFactor = Math.min(delta * this.transitionSpeed, 1.0);

    // Track all active shapes
    const allShapes = new Set<string>([
      ...Array.from(this.currentWeights.keys()),
      ...Array.from(this.targetWeights.keys())
    ]);

    for (const shape of allShapes) {
      const current = this.currentWeights.get(shape) || 0;
      const target = this.targetWeights.get(shape) || 0;

      let nextVal = current + (target - current) * blendFactor;
      if (Math.abs(nextVal - target) < 0.001) {
        nextVal = target;
      }

      this.currentWeights.set(shape, nextVal);

      // Layer blinking on top of eye blink targets
      if (shape === 'eyeBlinkLeft' || shape === 'eyeBlinkRight') {
        const combinedBlink = Math.min(1.0, nextVal + this.blinkProgress);
        this.applyWeightToMeshes(shape, combinedBlink);
      } else {
        this.applyWeightToMeshes(shape, nextVal);
      }
    }

    // Ensure eyelids blink even when no explicit blink target exists in expression
    if (!allShapes.has('eyeBlinkLeft')) {
      this.applyWeightToMeshes('eyeBlinkLeft', this.blinkProgress);
      this.applyWeightToMeshes('eyeBlinkRight', this.blinkProgress);
    }
  }

  private applyWeightToMeshes(shapeName: string, weight: number): void {
    for (const mesh of this.targetMeshes) {
      if (mesh.morphTargetDictionary && mesh.morphTargetInfluences) {
        const idx = mesh.morphTargetDictionary[shapeName];
        if (idx !== undefined) {
          mesh.morphTargetInfluences[idx] = weight;
        }
      }
    }
  }

  getCurrentExpression(): ExpressionId {
    return this.currentExpression;
  }

  attachModel(root: THREE.Object3D): void {
    this.init(root);
  }

  triggerBlink(): void {
    this.blinkPhase = 'closing';
    this.blinkProgress = 0;
  }

  getCurrentWeights(): Record<string, number> {
    const res: Record<string, number> = {};
    for (const [k, v] of this.currentWeights.entries()) {
      res[k] = v;
    }
    return res;
  }

  getMorphTargetDictionary(): Record<string, number> {
    if (this.targetMeshes.length > 0 && this.targetMeshes[0].morphTargetDictionary) {
      return this.targetMeshes[0].morphTargetDictionary;
    }
    return {};
  }

  dispose(): void {
    this.targetMeshes = [];
    this.currentWeights.clear();
    this.targetWeights.clear();
  }
}

export const faceExpressionController = new FaceExpressionController();
