/**
 * Yorvyn — Central Avatar Performance Controller
 * 
 * Master performance director coordinating:
 * - Real-time lip synchronization (LipSyncEngine)
 * - Facial expressions, eye saccades & blinking (FacialAnimationController)
 * - Conversational arm gestures, small nods & breathing (ConversationalGestureEngine)
 * - Model capability auditing & fallback handling (AvatarCapabilityChecker)
 * - State machine: IDLE <-> LISTENING <-> THINKING <-> SPEAKING
 * - Instantaneous speech interruption handling (<80ms return to rest)
 * - Attentive listening behaviour with eye contact and receptive micro-nods
 */

import * as THREE from 'three';
import { AvatarCapabilityChecker, CapabilityReport } from './AvatarCapabilityChecker';
import { FacialAnimationController } from './FacialAnimationController';
import { LipSyncEngine } from './LipSyncEngine';
import { ConversationalGestureEngine } from './ConversationalGestureEngine';
import { AnimationIntentInterpreter, RawAnimationIntent } from './AnimationIntentInterpreter';

export type PerformanceState = 'idle' | 'listening' | 'thinking' | 'speaking';

export interface PerformanceOptions {
  onSpeechComplete?: () => void;
  onInterrupted?: () => void;
}

export class AvatarPerformanceController {
  private root: THREE.Object3D | null = null;
  private capabilityReport: CapabilityReport | null = null;

  // Sub-engines
  public readonly facial: FacialAnimationController = new FacialAnimationController();
  public readonly lipSync: LipSyncEngine = new LipSyncEngine();
  public readonly gestures: ConversationalGestureEngine = new ConversationalGestureEngine();

  // State Machine
  private currentState: PerformanceState = 'idle';
  private stateTime = 0.0;

  // Listening Behaviour
  private nextReceptiveNodTime = 0;

  // Scheduled Gesture Trigger
  private pendingGestureTimer: any = null;

  init(root: THREE.Object3D, animationClips: THREE.AnimationClip[] = []): CapabilityReport {
    this.root = root;

    // 1. Audit Avatar Model Capabilities
    this.capabilityReport = AvatarCapabilityChecker.audit(root, animationClips);

    // 2. Initialize sub-controllers
    this.facial.init(root);
    this.lipSync.init(root);
    this.gestures.init(root);

    this.currentState = 'idle';
    this.stateTime = 0.0;
    this.nextReceptiveNodTime = performance.now() + 4000 + Math.random() * 3000;

    return this.capabilityReport;
  }

  getRoot(): THREE.Object3D | null {
    return this.root;
  }

  getCapabilityReport(): CapabilityReport | null {
    return this.capabilityReport;
  }

  getState(): PerformanceState {
    return this.currentState;
  }

  /**
   * Sets performance state with appropriate posture and gaze transitions.
   */
  setState(state: PerformanceState): void {
    if (this.currentState === state) return;

    this.currentState = state;
    this.stateTime = 0.0;

    switch (state) {
      case 'idle':
        this.facial.setEmotion('neutral');
        this.facial.setGazeTarget('user');
        this.gestures.triggerGesture('idle_breathing');
        this.lipSync.interruptSpeech();
        break;

      case 'listening':
        // Attentive forward posture, steady eye contact, silence
        this.facial.setEmotion('neutral', { intensity: 0.9 });
        this.facial.setGazeTarget('user');
        this.gestures.triggerGesture('listening_posture');
        this.lipSync.interruptSpeech();
        this.nextReceptiveNodTime = this.stateTime + 3.5 + Math.random() * 3.0;
        break;

      case 'thinking':
        // Glance thoughtfully away, furrowed brows, hand to chin
        this.facial.setEmotion('thinking', { intensity: 0.85 });
        this.facial.setGazeTarget('thoughtful_away');
        this.gestures.triggerGesture('thinking');
        this.lipSync.interruptSpeech();
        break;

      case 'speaking':
        this.facial.setEmotion('speaking', { intensity: 0.85 });
        this.facial.setGazeTarget('user');
        this.gestures.triggerGesture('speaking_posture');
        break;
    }
  }

  /**
   * Executes a complete animated conversational performance from an LLM AnimationIntent.
   */
  playIntent(intent: RawAnimationIntent, durationSeconds: number, options: PerformanceOptions = {}): void {
    // 1. Sanitize and validate intent through allowlist
    const cmd = AnimationIntentInterpreter.interpret(intent);

    // 2. Transition state to speaking
    this.setState('speaking');

    // 3. Set facial emotion & gaze
    this.facial.setEmotion(cmd.emotion, { intensity: cmd.intensity });
    this.facial.setGazeTarget(cmd.gazeTarget);

    // 4. Start synchronized Lip-Sync
    this.lipSync.startSpeech(durationSeconds, cmd.visemeCues, () => {
      this.setState('idle');
      if (options.onSpeechComplete) options.onSpeechComplete();
    });

    // 5. Schedule gesture trigger with offset
    if (this.pendingGestureTimer) {
      clearTimeout(this.pendingGestureTimer);
    }

    if (cmd.gestureTiming > 0.05) {
      this.pendingGestureTimer = setTimeout(() => {
        if (this.currentState === 'speaking') {
          this.gestures.triggerGesture(cmd.gestureId);
        }
      }, cmd.gestureTiming * 1000);
    } else {
      this.gestures.triggerGesture(cmd.gestureId);
    }
  }

  /**
   * Immediately halts current speech and transitions avatar into listening state (<80ms).
   */
  interrupt(options: PerformanceOptions = {}): void {
    if (this.pendingGestureTimer) {
      clearTimeout(this.pendingGestureTimer);
      this.pendingGestureTimer = null;
    }

    this.lipSync.interruptSpeech();
    this.setState('listening');

    if (options.onInterrupted) {
      options.onInterrupted();
    }
  }

  /**
   * Main per-frame tick called by requestAnimationFrame in renderer.
   * @param delta Elapsed time in seconds.
   */
  update(delta: number): void {
    this.stateTime += delta;

    // 1. Update Sub-engines
    this.facial.update(delta);
    this.lipSync.update(delta);
    this.gestures.update(delta);

    // 2. State-Specific Live Behaviors
    if (this.currentState === 'listening') {
      // Periodic subtle receptive nod every 4-8s while user is speaking
      if (this.stateTime >= this.nextReceptiveNodTime) {
        this.gestures.triggerGesture('small_nod', { durationSeconds: 0.9 });
        this.nextReceptiveNodTime = this.stateTime + 4.0 + Math.random() * 4.0;
      }
    }
  }

  dispose(): void {
    if (this.pendingGestureTimer) {
      clearTimeout(this.pendingGestureTimer);
    }
    this.facial.dispose();
    this.lipSync.dispose();
    this.gestures.dispose();
    this.root = null;
    this.capabilityReport = null;
  }
}

// Global Singleton
export const avatarPerformanceController = new AvatarPerformanceController();
