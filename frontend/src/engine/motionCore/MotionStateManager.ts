/**
 * YORVYN MotionCore — Deterministic 12-State Animation State Machine
 * Prevents competing actions from updating the same skeleton simultaneously.
 */

import type { MotionState, MotionTransitionPolicy } from './MotionTypes';

export const LEGAL_STATE_TRANSITIONS: Record<MotionState, ReadonlyArray<MotionState>> = {
  IDLE: ['IDLE', 'WALK', 'RUN', 'TURN', 'RAISE_ARMS', 'BEND', 'SIT', 'CUSTOM', 'PAUSED', 'RESETTING', 'ERROR'],
  WALK: ['IDLE', 'WALK', 'RUN', 'TURN', 'RAISE_ARMS', 'BEND', 'PAUSED', 'RESETTING', 'ERROR'],
  RUN: ['IDLE', 'WALK', 'RUN', 'TURN', 'PAUSED', 'RESETTING', 'ERROR'],
  TURN: ['IDLE', 'WALK', 'RUN', 'TURN', 'PAUSED', 'RESETTING', 'ERROR'],
  RAISE_ARMS: ['IDLE', 'WALK', 'BEND', 'TURN', 'PAUSED', 'RESETTING', 'ERROR'],
  BEND: ['IDLE', 'STAND', 'RAISE_ARMS', 'PAUSED', 'RESETTING', 'ERROR'],
  SIT: ['STAND', 'IDLE', 'PAUSED', 'RESETTING', 'ERROR'],
  STAND: ['IDLE', 'WALK', 'TURN', 'SIT', 'PAUSED', 'RESETTING', 'ERROR'],
  CUSTOM: ['IDLE', 'CUSTOM', 'PAUSED', 'RESETTING', 'ERROR'],
  PAUSED: ['IDLE', 'WALK', 'RUN', 'TURN', 'RAISE_ARMS', 'BEND', 'SIT', 'STAND', 'CUSTOM', 'RESETTING', 'ERROR'],
  RESETTING: ['IDLE', 'ERROR'],
  ERROR: ['RESETTING', 'IDLE'],
};

const DEFAULT_POLICIES: Record<MotionState, MotionTransitionPolicy> = {
  IDLE: { blendDurationSeconds: 0.3, priority: 10, loop: true },
  WALK: { blendDurationSeconds: 0.25, priority: 20, loop: true },
  RUN: { blendDurationSeconds: 0.22, priority: 40, loop: true },
  TURN: { blendDurationSeconds: 0.28, priority: 25, loop: false, returnToState: 'IDLE' },
  RAISE_ARMS: { blendDurationSeconds: 0.3, priority: 30, loop: false, returnToState: 'IDLE' },
  BEND: { blendDurationSeconds: 0.3, priority: 30, loop: false, returnToState: 'IDLE' },
  SIT: { blendDurationSeconds: 0.4, priority: 35, loop: true },
  STAND: { blendDurationSeconds: 0.35, priority: 35, loop: false, returnToState: 'IDLE' },
  CUSTOM: { blendDurationSeconds: 0.3, priority: 15, loop: false, returnToState: 'IDLE' },
  PAUSED: { blendDurationSeconds: 0.1, priority: 80, loop: false },
  RESETTING: { blendDurationSeconds: 0.1, priority: 90, loop: false, returnToState: 'IDLE' },
  ERROR: { blendDurationSeconds: 0.1, priority: 100, loop: false },
};

export interface TransitionDecision {
  accepted: boolean;
  fromState: MotionState;
  toState: MotionState;
  policy: MotionTransitionPolicy;
  interrupted: boolean;
  reason: string;
}

export class MotionStateManager {
  private currentState: MotionState = 'IDLE';
  private stateBeforePause: MotionState = 'IDLE';
  private customClipName: string | null = null;
  private timeScale = 1.0;

  public getState(): MotionState {
    return this.currentState;
  }

  public getStateBeforePause(): MotionState {
    return this.stateBeforePause;
  }

  public getCustomClipName(): string | null {
    return this.customClipName;
  }

  public getTimeScale(): number {
    return this.timeScale;
  }

  public setTimeScale(scale: number): void {
    this.timeScale = Math.max(0.0, Math.min(3.0, Number.isFinite(scale) ? scale : 1.0));
  }

  public requestTransition(target: MotionState, customClip?: string): TransitionDecision {
    const allowed = LEGAL_STATE_TRANSITIONS[this.currentState] || [];
    if (!allowed.includes(target)) {
      return {
        accepted: false,
        fromState: this.currentState,
        toState: this.currentState,
        policy: DEFAULT_POLICIES[this.currentState],
        interrupted: false,
        reason: `Transition ${this.currentState} -> ${target} blocked by FSM rules.`,
      };
    }

    const from = this.currentState;
    const interrupted = from !== 'IDLE' && from !== 'PAUSED' && target !== from;
    if (target === 'PAUSED' && from !== 'PAUSED') {
      this.stateBeforePause = from;
    }
    this.currentState = target;
    this.customClipName = target === 'CUSTOM' ? customClip || null : null;

    return {
      accepted: true,
      fromState: from,
      toState: target,
      policy: { ...DEFAULT_POLICIES[target] },
      interrupted,
      reason: `Transitioned cleanly ${from} -> ${target}.`,
    };
  }

  public pause(): TransitionDecision {
    return this.requestTransition('PAUSED');
  }

  public resume(): TransitionDecision {
    if (this.currentState !== 'PAUSED') {
      return {
        accepted: false,
        fromState: this.currentState,
        toState: this.currentState,
        policy: DEFAULT_POLICIES[this.currentState],
        interrupted: false,
        reason: 'Not paused.',
      };
    }
    const target = this.stateBeforePause === 'PAUSED' ? 'IDLE' : this.stateBeforePause;
    return this.requestTransition(target, this.customClipName || undefined);
  }

  public reset(): TransitionDecision {
    this.requestTransition('RESETTING');
    this.timeScale = 1.0;
    this.stateBeforePause = 'IDLE';
    return this.requestTransition('IDLE');
  }
}
