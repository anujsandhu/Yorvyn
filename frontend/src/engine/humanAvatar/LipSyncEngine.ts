/**
 * Yorvyn — Real-Time Lip Synchronization Engine
 * 
 * Drives natural mouth and jaw articulation synchronized with audio playback.
 * Supports:
 * - Timestamped Viseme Cues (exact speech alignment)
 * - Real-time Web Audio Analyser (RMS volume + formant frequency energy)
 * - Viseme-to-Blendshape Mapping (Oculus / ARKit standards)
 * - Coarticulation smoothing (attack/decay curve)
 * - Natural lip closure during pauses
 * - Immediate speech interruption handling with graceful return-to-rest (<80ms)
 * - Fallback to jawOpen or procedural bone rotation when visemes are missing
 */

import * as THREE from 'three';

export interface TimestampedViseme {
  viseme: string;
  startTime: number;
  duration: number;
  weight?: number;
}

export interface LipSyncOptions {
  audioElement?: HTMLAudioElement | null;
  audioBuffer?: AudioBuffer | null;
  visemeCues?: TimestampedViseme[];
  onPlaybackComplete?: () => void;
}

export class LipSyncEngine {
  private targetMeshes: THREE.Mesh[] = [];
  private jawBone: THREE.Bone | null = null;
  private hasVisemes = false;
  private hasJawBlendshape = false;

  // Active viseme blend weights (viseme -> weight 0..1)
  private currentVisemeWeights: Map<string, number> = new Map();
  private targetVisemeWeights: Map<string, number> = new Map();

  // Playback & Timing
  private isSpeaking = false;
  private playbackTimeSeconds = 0.0;
  private audioDuration = 0;
  private visemeQueue: TimestampedViseme[] = [];
  private onCompleteCallback: (() => void) | null = null;

  // Web Audio Frequency Analyzer
  private audioContext: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private frequencyData: Uint8Array | null = null;

  // Coarticulation Tuning
  private readonly ATTACK_SPEED = 28.0;  // Rapid lip opening
  private readonly RELEASE_SPEED = 24.0; // Smooth natural closure (<80ms)

  getHasVisemes(): boolean {
    return this.hasVisemes;
  }

  getAudioContext(): AudioContext | null {
    return this.audioContext;
  }

  init(root: THREE.Object3D): void {
    this.targetMeshes = [];
    this.jawBone = null;
    this.hasVisemes = false;
    this.hasJawBlendshape = false;
    this.currentVisemeWeights.clear();
    this.targetVisemeWeights.clear();

    root.traverse((obj) => {
      if ((obj as THREE.Bone).isBone && obj.name === 'Jaw') {
        this.jawBone = obj as THREE.Bone;
      }

      if ((obj as THREE.Mesh).isMesh) {
        const mesh = obj as THREE.Mesh;
        if (mesh.morphTargetDictionary && mesh.morphTargetInfluences) {
          this.targetMeshes.push(mesh);
          if (mesh.morphTargetDictionary['viseme_aa'] !== undefined) {
            this.hasVisemes = true;
          }
          if (mesh.morphTargetDictionary['jawOpen'] !== undefined) {
            this.hasJawBlendshape = true;
          }
        }
      }
    });
  }

  /**
   * Starts a synchronized speech lip-sync performance.
   */
  startSpeech(durationSeconds: number, cues: TimestampedViseme[] = [], onComplete?: () => void): void {
    this.isSpeaking = true;
    this.playbackTimeSeconds = 0.0;
    this.audioDuration = durationSeconds;
    this.visemeQueue = [...cues].sort((a, b) => a.startTime - b.startTime);
    this.onCompleteCallback = onComplete || null;

    // Reset weights
    this.targetVisemeWeights.clear();
  }

  /**
   * Attaches an active Web Audio AnalyserNode for real-time acoustic lip-sync.
   */
  attachAudioAnalyser(analyserNode: AnalyserNode, audioCtx: AudioContext): void {
    this.analyser = analyserNode;
    this.audioContext = audioCtx;
    this.analyser.fftSize = 512;
    this.frequencyData = new Uint8Array(this.analyser.frequencyBinCount);
  }

  /**
   * Immediately halts speech and smoothly closes the mouth (<80ms).
   */
  interruptSpeech(): void {
    this.isSpeaking = false;
    this.visemeQueue = [];
    this.targetVisemeWeights.clear();

    // Set zero target on all active visemes
    for (const key of Array.from(this.currentVisemeWeights.keys())) {
      this.targetVisemeWeights.set(key, 0.0);
    }

    if (this.jawBone) {
      this.jawBone.rotation.x = 0;
    }
  }

  getIsSpeaking(): boolean {
    return this.isSpeaking;
  }

  /**
   * Main per-frame lip-sync update loop.
   * @param delta Delta time in seconds.
   */
  update(delta: number): void {
    if (this.isSpeaking) {
      this.playbackTimeSeconds += delta;
      // Check completion
      if (this.playbackTimeSeconds >= this.audioDuration) {
        this.interruptSpeech();
        if (this.onCompleteCallback) {
          this.onCompleteCallback();
          this.onCompleteCallback = null;
        }
      }
    }

    const elapsedSeconds = this.playbackTimeSeconds;

    // 1. Evaluate Target Visemes from Timestamp Queue or Analyser
    if (this.isSpeaking) {
      if (this.visemeQueue.length > 0) {
        this.evaluateTimestampedCues(elapsedSeconds);
      } else if (this.analyser && this.frequencyData) {
        this.evaluateAcousticAnalyser();
      } else {
        // Fallback procedural cadence based on elapsed time
        this.evaluateProceduralCadence(elapsedSeconds);
      }
    }

    // 2. Coarticulation Smoothing & Interpolation
    const allVisemes = new Set([
      ...Array.from(this.currentVisemeWeights.keys()),
      ...Array.from(this.targetVisemeWeights.keys()),
    ]);

    for (const vName of allVisemes) {
      const cur = this.currentVisemeWeights.get(vName) || 0;
      const tgt = this.targetVisemeWeights.get(vName) || 0;

      const rate = tgt > cur ? this.ATTACK_SPEED : this.RELEASE_SPEED;
      const blend = Math.min(delta * rate, 1.0);
      let next = cur + (tgt - cur) * blend;

      if (Math.abs(next - tgt) < 0.005) {
        next = tgt;
      }

      this.currentVisemeWeights.set(vName, next);
      this.applyVisemeWeight(vName, next);
    }
  }

  /**
   * Evaluates timestamped viseme cues with smooth overlap blending.
   */
  private evaluateTimestampedCues(elapsedSeconds: number): void {
    this.targetVisemeWeights.clear();

    let activeVisemeFound = false;

    for (const cue of this.visemeQueue) {
      const start = cue.startTime;
      const end = cue.startTime + cue.duration;

      if (elapsedSeconds >= start && elapsedSeconds <= end) {
        const peakWeight = cue.weight ?? 0.85;
        const progress = (elapsedSeconds - start) / cue.duration;
        // Natural speech attack-sustain-decay envelope
        let envelope = 1.0;
        if (progress < 0.2) {
          envelope = Math.sin((progress / 0.2) * (Math.PI / 2));
        } else if (progress > 0.8) {
          envelope = Math.cos(((progress - 0.8) / 0.2) * (Math.PI / 2));
        }
        const weight = Math.max(0.1, peakWeight * envelope);

        this.targetVisemeWeights.set(cue.viseme, weight);
        activeVisemeFound = true;
      }
    }

    // Natural lip closure during pauses
    if (!activeVisemeFound) {
      this.targetVisemeWeights.set('viseme_PP', 0.15); // gentle resting seal
    }
  }

  /**
   * Evaluates real-time audio formant energy for live streaming speech.
   */
  private evaluateAcousticAnalyser(): void {
    if (!this.analyser || !this.frequencyData) return;

    this.analyser.getByteFrequencyData(this.frequencyData as any);

    // Compute RMS Energy
    let sum = 0;
    for (let i = 0; i < this.frequencyData.length; i++) {
      sum += this.frequencyData[i] * this.frequencyData[i];
    }
    const rms = Math.sqrt(sum / this.frequencyData.length) / 255.0;

    // Formant energy bands
    // Low band (100Hz - 600Hz): F1, jaw opening /aa/, /O/
    let lowEnergy = 0;
    for (let i = 2; i < 12; i++) lowEnergy += this.frequencyData[i];
    lowEnergy = (lowEnergy / 10.0) / 255.0;

    // Mid band (800Hz - 2200Hz): F2, vowel distinction /E/, /I/
    let midEnergy = 0;
    for (let i = 16; i < 45; i++) midEnergy += this.frequencyData[i];
    midEnergy = (midEnergy / 29.0) / 255.0;

    // High band (3000Hz - 8000Hz): Sibilants /SS/, /CH/, /FF/
    let highEnergy = 0;
    for (let i = 60; i < 160; i++) highEnergy += this.frequencyData[i];
    highEnergy = (highEnergy / 100.0) / 255.0;

    this.targetVisemeWeights.clear();

    if (rms > 0.04) {
      if (highEnergy > 0.35 && highEnergy > lowEnergy) {
        this.targetVisemeWeights.set('viseme_SS', Math.min(1.0, highEnergy * 1.2));
      } else if (lowEnergy > 0.4) {
        this.targetVisemeWeights.set('viseme_aa', Math.min(1.0, lowEnergy * 1.3));
      } else if (midEnergy > 0.35) {
        this.targetVisemeWeights.set('viseme_E', Math.min(1.0, midEnergy * 1.1));
      } else {
        this.targetVisemeWeights.set('viseme_O', Math.min(1.0, rms * 1.4));
      }

      if (this.hasJawBlendshape) {
        this.targetVisemeWeights.set('jawOpen', Math.min(0.85, rms * 1.2));
      }
    } else {
      // Resting closure
      this.targetVisemeWeights.set('viseme_PP', 0.1);
    }
  }

  /**
   * Procedural cadence simulation when audio is playing without granular phoneme data.
   */
  private evaluateProceduralCadence(elapsed: number): void {
    const cycle = elapsed * 14.0;
    const syllabicRhythm = Math.sin(cycle) * Math.sin(cycle * 0.4);

    this.targetVisemeWeights.clear();

    if (syllabicRhythm > 0.1) {
      const visemes = ['viseme_aa', 'viseme_E', 'viseme_O', 'viseme_DD'];
      const chosen = visemes[Math.floor(elapsed * 4.5) % visemes.length];
      const weight = Math.min(0.8, syllabicRhythm * 0.9);
      this.targetVisemeWeights.set(chosen, weight);

      if (this.hasJawBlendshape) {
        this.targetVisemeWeights.set('jawOpen', weight * 0.7);
      }
    } else {
      this.targetVisemeWeights.set('viseme_PP', 0.15);
    }
  }

  /**
   * Applies the calculated weight to mesh blendshapes or falls back to Jaw bone rotation.
   */
  private applyVisemeWeight(visemeName: string, weight: number): void {
    let appliedToMesh = false;

    for (const mesh of this.targetMeshes) {
      if (mesh.morphTargetDictionary && mesh.morphTargetInfluences) {
        const idx = mesh.morphTargetDictionary[visemeName];
        if (idx !== undefined) {
          mesh.morphTargetInfluences[idx] = weight;
          appliedToMesh = true;
        } else if (visemeName.startsWith('viseme_') && mesh.morphTargetDictionary['jawOpen'] !== undefined) {
          // Fallback: drive jawOpen from viseme weight
          const jawIdx = mesh.morphTargetDictionary['jawOpen'];
          mesh.morphTargetInfluences[jawIdx] = Math.max(mesh.morphTargetInfluences[jawIdx] || 0, weight * 0.65);
          appliedToMesh = true;
        }
      }
    }

    // Fallback to Jaw bone rotation if no mesh blendshapes exist
    if (!appliedToMesh && this.jawBone && (visemeName === 'viseme_aa' || visemeName === 'jawOpen')) {
      this.jawBone.rotation.x = -weight * 0.28; // subtle downward jaw rotation
    }
  }

  getCurrentWeights(): Record<string, number> {
    const res: Record<string, number> = {};
    for (const [k, v] of this.currentVisemeWeights.entries()) {
      if (v > 0.01) res[k] = Math.round(v * 100) / 100;
    }
    return res;
  }

  dispose(): void {
    this.interruptSpeech();
    this.targetMeshes = [];
    this.jawBone = null;
    this.currentVisemeWeights.clear();
    this.targetVisemeWeights.clear();
  }
}
