/**
 * Yorvyn — Animation Intent Interpreter
 * 
 * Validates animation intent payloads received from the LLM or stylist backend,
 * strictly enforces the allowlist to block arbitrary code or bone transformations,
 * and translates validated semantic actions into AvatarPerformanceController commands.
 */

import { EmotionType, GazeTarget } from './FacialAnimationController';
import { GestureId } from './ConversationalGestureEngine';
import { TimestampedViseme } from './LipSyncEngine';

export interface RawAnimationIntent {
  spoken_response?: string;
  emotion?: string;
  expression_intensity?: number;
  gaze_target?: string;
  gesture_id?: string;
  gesture_timing?: number;
  speaking_state?: string;
  conversational_emphasis?: string[];
  viseme_cues?: Array<{
    viseme: string;
    start_time: number;
    duration: number;
    weight?: number;
  }>;
}

export interface ValidatedPerformanceCommand {
  spokenResponse: string;
  emotion: EmotionType;
  intensity: number;
  gazeTarget: GazeTarget;
  gestureId: GestureId;
  gestureTiming: number;
  speakingState: 'speaking' | 'listening' | 'thinking' | 'idle';
  visemeCues: TimestampedViseme[];
}

const ALLOWED_EMOTIONS: Set<EmotionType> = new Set([
  'neutral',
  'happy',
  'frown',
  'surprise',
  'confusion',
  'curiosity',
  'thinking',
  'empathy',
  'serious',
  'speaking',
]);

const ALLOWED_GESTURES: Set<GestureId> = new Set([
  'open_palm',
  'explain',
  'emphasis',
  'small_nod',
  'head_tilt',
  'thinking',
  'point',
  'greeting',
  'listening_posture',
  'speaking_posture',
  'idle_breathing',
]);

const ALLOWED_GAZES: Set<GazeTarget> = new Set([
  'user',
  'camera',
  'thoughtful_away',
  'garment',
  'down',
]);

export class AnimationIntentInterpreter {
  /**
   * Sanitizes, validates, and decodes an animation intent payload.
   */
  static interpret(raw: RawAnimationIntent | null | undefined): ValidatedPerformanceCommand {
    if (!raw) {
      return {
        spokenResponse: '',
        emotion: 'neutral',
        intensity: 0.8,
        gazeTarget: 'user',
        gestureId: 'idle_breathing',
        gestureTiming: 0.0,
        speakingState: 'idle',
        visemeCues: [],
      };
    }

    // 1. Emotion validation
    const rawEmotion = (raw.emotion || 'neutral').toLowerCase().trim() as EmotionType;
    const emotion: EmotionType = ALLOWED_EMOTIONS.has(rawEmotion) ? rawEmotion : 'neutral';

    // 2. Gesture validation
    const rawGesture = (raw.gesture_id || 'open_palm').toLowerCase().trim() as GestureId;
    const gestureId: GestureId = ALLOWED_GESTURES.has(rawGesture) ? rawGesture : 'open_palm';

    // 3. Gaze target validation
    const rawGaze = (raw.gaze_target || 'user').toLowerCase().trim() as GazeTarget;
    const gazeTarget: GazeTarget = ALLOWED_GAZES.has(rawGaze) ? rawGaze : 'user';

    // 4. Intensity clamp (0.0 to 1.0)
    const intensity = Math.max(0.0, Math.min(1.0, raw.expression_intensity ?? 0.85));

    // 5. Speaking state
    const rawState = (raw.speaking_state || 'speaking').toLowerCase();
    const speakingState = ['speaking', 'listening', 'thinking', 'idle'].includes(rawState)
      ? (rawState as 'speaking' | 'listening' | 'thinking' | 'idle')
      : 'speaking';

    // 6. Viseme Cues mapping
    const visemeCues: TimestampedViseme[] = (raw.viseme_cues || []).map((c) => ({
      viseme: c.viseme,
      startTime: Math.max(0.0, c.start_time),
      duration: Math.max(0.04, c.duration),
      weight: Math.max(0.1, Math.min(1.0, c.weight ?? 0.85)),
    }));

    return {
      spokenResponse: raw.spoken_response || '',
      emotion,
      intensity,
      gazeTarget,
      gestureId,
      gestureTiming: Math.max(0.0, raw.gesture_timing ?? 0.0),
      speakingState,
      visemeCues,
    };
  }
}

