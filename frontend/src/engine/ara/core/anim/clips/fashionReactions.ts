/**
 * Yorvyn — Fashion Stylist Emotional & Gestural Reaction Animations
 * 
 * Provides anatomically accurate, beautifully keyframed skeletal animations and
 * facial blend-shape transitions for Yorvyn's virtual fashion companion:
 * - Thumbs Up & Thumbs Down (Approval / Disapproval with real finger articulation)
 * - Fashion Presentation (Single hand, Both hands runway presentation)
 * - Garment Inspection (Looking down, side profiles, pointing at details)
 * - Social & Styling Responses (Nod, Head Shake, Thinking, Suggest Alternative, Curious, Welcome)
 * - Voice & Chat Reactions (Attentive listening, speaking gestures, excited approval, confused)
 */

import { type Ch, type Clip } from './types';
import { fingers, side, v, track, lerp3, nlerp3, smoother } from './helpers';

/** Eased smootherstep track helper */
const keys = (T: number[], t: number) => (vals: number[]) => track(T, vals)(t);

/** Natural relaxed arm reference points (in neck/chest space) for seamless zero-jerk transitions */
const REST_ARM = {
  Right: {
    pos: v(-0.20, -0.55, 0.08) as [number, number, number],
    pole: v(-0.8, -0.6, -0.4) as [number, number, number],
    dir: v(0, -1, 0.05) as [number, number, number],  // fingers pointing down along gravity
    palm: v(1, 0, 0) as [number, number, number],     // palm facing inward toward thigh
  },
  Left: {
    pos: v(0.20, -0.55, 0.08) as [number, number, number],
    pole: v(0.8, -0.6, -0.4) as [number, number, number],
    dir: v(0, -1, 0.05) as [number, number, number],
    palm: v(-1, 0, 0) as [number, number, number],
  }
};

// ── 1. THUMBS UP (APPROVAL) ──────────────────────────────────────────────────
export const thumbsUp: Clip = {
  id: 'thumbs_up',
  name: 'Thumbs Up',
  category: 'Emotes',
  duration: 2.2,
  loop: false,
  sample: (t) => {
    const k = keys([0, 0.48, 1.48, 2.2], t);
    const raise = k([0, 1, 1, 0]); // raise hand, hold, lower smoothly
    const nodEnv = smoother(raise);
    const nod = Math.sin(Math.min(1, Math.max(0, (t - 0.35) / 0.8)) * Math.PI * 2) * nodEnv;

    const out: Record<string, Ch> = {
      Spine: [-2 * raise, 0, 0],
      Spine1: [-2 * raise, 0, 0],
      Spine2: [-1 * raise, 0, 0],
      Neck: [-4 * raise + 3 * nod, 0, 0],
      Head: [-6 * raise + 6 * nod, -8 * raise, 0],
    };

    // Body posture: left arm stays relaxed at side
    side(out, 'Arm', [0, 0, 3], [0, 0, 0]);
    side(out, 'ForeArm', [12, 0, 0], [0, 0, 0]);
    side(out, 'Leg', [-3, 0, 0], [-3, 0, 0]);
    side(out, 'UpLeg', [0, 0, -3], [0, 0, -3]);

    // Right hand: fingers curl smoothly into fist
    for (const f of ['Index', 'Middle', 'Ring', 'Pinky']) {
      out[`RightHand${f}1`] = [14 + (78 - 14) * raise, 0, 0];
      out[`RightHand${f}2`] = [16 + (88 - 16) * raise, 0, 0];
      out[`RightHand${f}3`] = [12 + (62 - 12) * raise, 0, 0];
      // Left hand fingers relaxed
      out[`LeftHand${f}1`] = [14, 0, 0];
      out[`LeftHand${f}2`] = [16, 0, 0];
      out[`LeftHand${f}3`] = [12, 0, 0];
    }

    // Right thumb: extends straight upward
    out.RightHandThumb1 = [8 + (-18 - 8) * raise, -16 * raise, -12 * raise];
    out.RightHandThumb2 = [8 + (-16 - 8) * raise, -8 * raise, 0];
    out.RightHandThumb3 = [-10 * raise, 0, 0];

    out.LeftHandThumb1 = [8, 0, 0];
    out.LeftHandThumb2 = [8, 0, 0];

    // Right hand IK target: smoothly sweeps from relaxed side to chest
    const targetPos = v(-0.22, -0.04, 0.32);
    const targetPole = v(-0.8, -0.7, -0.3);
    const targetDir = v(0, 1, 0.15);
    const targetPalm = v(1, 0, 0.2);

    return {
      bones: out,
      root: { ground: true },
      ik: {
        Right: {
          pos: lerp3(REST_ARM.Right.pos, targetPos, raise),
          pole: nlerp3(REST_ARM.Right.pole, targetPole, raise),
          dir: nlerp3(REST_ARM.Right.dir, targetDir, raise),
          palm: nlerp3(REST_ARM.Right.palm, targetPalm, raise),
        },
      },
      face: {
        mouthSmile: 0.85 * raise,
        eyeSquintLeft: 0.3 * raise,
        eyeSquintRight: 0.3 * raise,
        browOuterUpLeft: 0.2 * raise,
        browOuterUpRight: 0.2 * raise,
      },
    };
  },
};

// ── 2. THUMBS DOWN (DISAPPROVAL) ─────────────────────────────────────────────
export const thumbsDown: Clip = {
  id: 'thumbs_down',
  name: 'Thumbs Down',
  category: 'Emotes',
  duration: 2.2,
  loop: false,
  sample: (t) => {
    const k = keys([0, 0.48, 1.48, 2.2], t);
    const raise = k([0, 1, 1, 0]); // raise hand, hold, lower smoothly
    const shakeEnv = smoother(raise);
    const shake = Math.sin(Math.min(1, Math.max(0, (t - 0.45) / 0.9)) * Math.PI * 3) * shakeEnv;

    const out: Record<string, Ch> = {
      Spine: [3 * raise, 0, 0],
      Spine1: [2 * raise, 0, 0],
      Neck: [4 * raise, 6 * shake, 0],
      Head: [6 * raise, 12 * shake, 0],
    };

    side(out, 'Arm', [0, 0, 3], [0, 0, 0]);
    side(out, 'ForeArm', [12, 0, 0], [0, 0, 0]);
    side(out, 'Leg', [-3, 0, 0], [-3, 0, 0]);
    side(out, 'UpLeg', [0, 0, -3], [0, 0, -3]);

    // Right hand: fingers curl smoothly into fist
    for (const f of ['Index', 'Middle', 'Ring', 'Pinky']) {
      out[`RightHand${f}1`] = [14 + (80 - 14) * raise, 0, 0];
      out[`RightHand${f}2`] = [16 + (90 - 16) * raise, 0, 0];
      out[`RightHand${f}3`] = [12 + (65 - 12) * raise, 0, 0];
      out[`LeftHand${f}1`] = [14, 0, 0];
      out[`LeftHand${f}2`] = [16, 0, 0];
      out[`LeftHand${f}3`] = [12, 0, 0];
    }

    // Right thumb: extended downward
    out.RightHandThumb1 = [8 + (25 - 8) * raise, 15 * raise, 10 * raise];
    out.RightHandThumb2 = [8 + (22 - 8) * raise, 10 * raise, 0];
    out.RightHandThumb3 = [15 * raise, 0, 0];

    out.LeftHandThumb1 = [8, 0, 0];
    out.LeftHandThumb2 = [8, 0, 0];

    const targetPos = v(-0.22, -0.10, 0.30);
    const targetPole = v(-0.8, -0.6, -0.3);
    const targetDir = v(0, -1, 0.1);
    const targetPalm = v(-1, 0, -0.2);

    return {
      bones: out,
      root: { ground: true },
      ik: {
        Right: {
          pos: lerp3(REST_ARM.Right.pos, targetPos, raise),
          pole: nlerp3(REST_ARM.Right.pole, targetPole, raise),
          dir: nlerp3(REST_ARM.Right.dir, targetDir, raise),
          palm: nlerp3(REST_ARM.Right.palm, targetPalm, raise),
        },
      },
      face: {
        mouthFrown: 0.65 * raise,
        browInnerUp: 0.5 * raise,
        mouthPress: 0.35 * raise,
      },
    };
  },
};

// ── 3. NOD (APPROVAL & AFFIRMATION) ───────────────────────────────────────────
export const nod: Clip = {
  id: 'nod',
  name: 'Nod',
  category: 'Emotes',
  duration: 1.6,
  loop: false,
  sample: (t) => {
    const env = smoother(Math.sin((t / 1.6) * Math.PI));
    const nodCycle = Math.sin((t / 1.6) * Math.PI * 4) * env; // two smooth affirmative nods
    const out: Record<string, Ch> = {
      Spine: [0.8 * nodCycle, 0, 0],
      Neck: [6 * nodCycle, 0, 0],
      Head: [14 * nodCycle, 0, 0],
    };
    fingers(out, 14);
    side(out, 'Arm', [0, 0, 3], [0, 0, 3]);
    side(out, 'ForeArm', [12, 0, 0], [12, 0, 0]);
    return {
      bones: out,
      root: { ground: true },
      face: {
        mouthSmile: 0.55 * env,
        eyeSquintLeft: 0.2 * env,
        eyeSquintRight: 0.2 * env,
      },
    };
  },
};

// ── 4. HEAD SHAKE (DISAGREEMENT / UNCERTAINTY) ────────────────────────────────
export const headShake: Clip = {
  id: 'head_shake',
  name: 'Head Shake',
  category: 'Emotes',
  duration: 1.8,
  loop: false,
  sample: (t) => {
    const env = smoother(Math.sin((t / 1.8) * Math.PI));
    const shake = Math.sin((t / 1.8) * Math.PI * 5) * env;
    const out: Record<string, Ch> = {
      Neck: [2 * env, 10 * shake, 0],
      Head: [4 * env, 18 * shake, -3 * shake],
    };
    fingers(out, 14);
    side(out, 'Arm', [0, 0, 3], [0, 0, 3]);
    side(out, 'ForeArm', [12, 0, 0], [12, 0, 0]);
    return {
      bones: out,
      root: { ground: true },
      face: {
        mouthPress: 0.4 * env,
        browDownLeft: 0.3 * env,
        browDownRight: 0.3 * env,
      },
    };
  },
};

// ── 5. THINKING POSE (CONTEMPLATION) ──────────────────────────────────────────
export const thinking: Clip = {
  id: 'thinking',
  name: 'Thinking',
  category: 'Emotes',
  duration: 2.8,
  loop: false,
  sample: (t) => {
    const k = keys([0, 0.55, 2.15, 2.8], t);
    const pose = k([0, 1, 1, 0]);
    const breathe = Math.sin((t / 2.8) * Math.PI * 2) * smoother(pose);

    const out: Record<string, Ch> = {
      Spine: [2 * pose + 0.8 * breathe, 0, 0],
      Neck: [2 * pose, -10 * pose, -6 * pose],
      Head: [4 * pose, -16 * pose, -10 * pose],
      RightArm: [0, 0, 0],
      RightForeArm: [0, 0, 0],
    };

    side(out, 'Arm', [0, 0, 3], [0, 0, 0]);
    side(out, 'ForeArm', [12, 0, 0], [0, 0, 0]);

    // Hand to chin: fingers transition smoothly from relaxed to contemplative curl
    for (const f of ['Middle', 'Ring', 'Pinky']) {
      out[`RightHand${f}1`] = [14 + (60 - 14) * pose, 0, 0];
      out[`RightHand${f}2`] = [16 + (70 - 16) * pose, 0, 0];
      out[`RightHand${f}3`] = [12 + (50 - 12) * pose, 0, 0];
    }
    out.RightHandIndex1 = [14 + (30 - 14) * pose, 0, 0];
    out.RightHandIndex2 = [16 + (25 - 16) * pose, 0, 0];
    out.RightHandThumb1 = [8 + (-5 - 8) * pose, -10 * pose, 0];

    const targetPos = v(-0.10, 0.08, 0.24);
    const targetPole = v(-0.7, -0.6, -0.4);
    const targetDir = v(0.2, 0.9, 0.2);
    const targetPalm = v(0.8, -0.2, 0.5);

    return {
      bones: out,
      root: { ground: true },
      ik: {
        Right: {
          pos: lerp3(REST_ARM.Right.pos, targetPos, pose),
          pole: nlerp3(REST_ARM.Right.pole, targetPole, pose),
          dir: nlerp3(REST_ARM.Right.dir, targetDir, pose),
          palm: nlerp3(REST_ARM.Right.palm, targetPalm, pose),
        },
      },
      face: {
        browInnerUp: 0.45 * pose,
        eyeSquintLeft: 0.25 * pose,
        mouthPress: 0.3 * pose,
      },
      gaze: [12 * pose, 8 * pose],
    };
  },
};

// ── 6. CURIOUS HEAD TILT ──────────────────────────────────────────────────────
export const curious: Clip = {
  id: 'curious',
  name: 'Curious',
  category: 'Emotes',
  duration: 2.0,
  loop: false,
  sample: (t) => {
    const k = keys([0, 0.45, 1.55, 2.0], t);
    const tilt = k([0, 1, 1, 0]);
    const out: Record<string, Ch> = {
      Neck: [0, 8 * tilt, 8 * tilt],
      Head: [2 * tilt, 14 * tilt, 16 * tilt],
    };
    fingers(out, 14);
    side(out, 'Arm', [0, 0, 3], [0, 0, 3]);
    side(out, 'ForeArm', [12, 0, 0], [12, 0, 0]);
    return {
      bones: out,
      root: { ground: true },
      face: {
        browOuterUpLeft: 0.65 * tilt,
        browInnerUp: 0.25 * tilt,
        mouthSmile: 0.35 * tilt,
        eyeWideLeft: 0.3 * tilt,
      },
      gaze: [-6 * tilt, 4 * tilt],
    };
  },
};

// ── 7. PRESENT OUTFIT (SINGLE HAND) ───────────────────────────────────────────
export const presentSingle: Clip = {
  id: 'present_single',
  name: 'Present Outfit',
  category: 'Emotes',
  duration: 2.5,
  loop: false,
  sample: (t) => {
    const k = keys([0, 0.55, 1.85, 2.5], t);
    const extend = k([0, 1, 1, 0]);
    const out: Record<string, Ch> = {
      Spine: [-2 * extend, 0, 0],
      Neck: [-2 * extend, -12 * extend, 0],
      Head: [-4 * extend, -16 * extend, 0],
    };

    side(out, 'Arm', [0, 0, 3], [0, 0, 0]);
    side(out, 'ForeArm', [12, 0, 0], [0, 0, 0]);

    // Open elegant presentation hand: fingers lightly extended and tapered
    for (const f of ['Index', 'Middle', 'Ring', 'Pinky']) {
      out[`RightHand${f}1`] = [14 + (6 - 14) * extend, 0, 0];
      out[`RightHand${f}2`] = [16 + (8 - 16) * extend, 0, 0];
      out[`RightHand${f}3`] = [12 + (6 - 12) * extend, 0, 0];
    }
    out.RightHandThumb1 = [8 + (-10 - 8) * extend, 0, 0];

    const targetPos = v(-0.38, -0.25, 0.28);
    const targetPole = v(-0.9, -0.6, -0.2);
    const targetDir = v(-0.4, 0.6, 0.6);
    const targetPalm = v(0.3, 0.8, -0.4);

    return {
      bones: out,
      root: { ground: true },
      ik: {
        Right: {
          pos: lerp3(REST_ARM.Right.pos, targetPos, extend),
          pole: nlerp3(REST_ARM.Right.pole, targetPole, extend),
          dir: nlerp3(REST_ARM.Right.dir, targetDir, extend),
          palm: nlerp3(REST_ARM.Right.palm, targetPalm, extend),
        },
      },
      face: {
        mouthSmile: 0.75 * extend,
        eyeSquintLeft: 0.25 * extend,
        eyeSquintRight: 0.25 * extend,
      },
    };
  },
};

// ── 8. PRESENT OUTFIT (BOTH HANDS) ────────────────────────────────────────────
export const presentBoth: Clip = {
  id: 'present_both',
  name: 'Present Both Hands',
  category: 'Emotes',
  duration: 2.8,
  loop: false,
  sample: (t) => {
    const k = keys([0, 0.65, 2.05, 2.8], t);
    const extend = k([0, 1, 1, 0]);
    const out: Record<string, Ch> = {
      Spine: [-3 * extend, 0, 0],
      Neck: [-4 * extend, 0, 0],
      Head: [-6 * extend, 0, 0],
    };

    fingers(out, 14 + (6 - 14) * extend);

    const targetPosL = v(0.38, -0.24, 0.26);
    const targetPoleL = v(0.9, -0.6, -0.2);
    const targetDirL = v(0.4, 0.5, 0.6);
    const targetPalmL = v(-0.3, 0.8, -0.4);

    const targetPosR = v(-0.38, -0.24, 0.26);
    const targetPoleR = v(-0.9, -0.6, -0.2);
    const targetDirR = v(-0.4, 0.5, 0.6);
    const targetPalmR = v(0.3, 0.8, -0.4);

    return {
      bones: out,
      root: { ground: true },
      ik: {
        Left: {
          pos: lerp3(REST_ARM.Left.pos, targetPosL, extend),
          pole: nlerp3(REST_ARM.Left.pole, targetPoleL, extend),
          dir: nlerp3(REST_ARM.Left.dir, targetDirL, extend),
          palm: nlerp3(REST_ARM.Left.palm, targetPalmL, extend),
        },
        Right: {
          pos: lerp3(REST_ARM.Right.pos, targetPosR, extend),
          pole: nlerp3(REST_ARM.Right.pole, targetPoleR, extend),
          dir: nlerp3(REST_ARM.Right.dir, targetDirR, extend),
          palm: nlerp3(REST_ARM.Right.palm, targetPalmR, extend),
        },
      },
      face: {
        mouthSmile: 0.8 * extend,
        eyeSquintLeft: 0.3 * extend,
        eyeSquintRight: 0.3 * extend,
      },
    };
  },
};

// ── 9. POINT AT OUTFIT DETAILS ───────────────────────────────────────────────
export const pointOutfit: Clip = {
  id: 'point_outfit',
  name: 'Point at Outfit',
  category: 'Emotes',
  duration: 2.4,
  loop: false,
  sample: (t) => {
    const k = keys([0, 0.5, 1.8, 2.4], t);
    const point = k([0, 1, 1, 0]);

    const out: Record<string, Ch> = {
      Neck: [4 * point, -10 * point, 0],
      Head: [8 * point, -14 * point, 0],
    };

    side(out, 'Arm', [0, 0, 3], [0, 0, 0]);
    side(out, 'ForeArm', [12, 0, 0], [0, 0, 0]);

    // Index finger pointing toward chest/lapel; other fingers curled
    for (const f of ['Middle', 'Ring', 'Pinky']) {
      out[`RightHand${f}1`] = [14 + (75 - 14) * point, 0, 0];
      out[`RightHand${f}2`] = [16 + (85 - 16) * point, 0, 0];
      out[`RightHand${f}3`] = [12 + (60 - 12) * point, 0, 0];
    }
    out.RightHandIndex1 = [14 + (6 - 14) * point, 0, 0];
    out.RightHandIndex2 = [16 + (4 - 16) * point, 0, 0];
    out.RightHandThumb1 = [8 + (10 - 8) * point, 0, 0];

    const targetPos = v(-0.12, -0.20, 0.26);
    const targetPole = v(-0.8, -0.5, -0.3);
    const targetDir = v(0.2, 0.8, -0.3);
    const targetPalm = v(0.5, 0.1, 0.8);

    return {
      bones: out,
      root: { ground: true },
      ik: {
        Right: {
          pos: lerp3(REST_ARM.Right.pos, targetPos, point),
          pole: nlerp3(REST_ARM.Right.pole, targetPole, point),
          dir: nlerp3(REST_ARM.Right.dir, targetDir, point),
          palm: nlerp3(REST_ARM.Right.palm, targetPalm, point),
        },
      },
      face: {
        mouthSmile: 0.6 * point,
      },
      gaze: [-8 * point, -12 * point],
    };
  },
};

// ── 10. LOOK AT GARMENT (FABRIC & FIT INSPECTION) ─────────────────────────────
export const lookGarment: Clip = {
  id: 'look_garment',
  name: 'Look at Garment',
  category: 'Emotes',
  duration: 2.6,
  loop: false,
  sample: (t) => {
    const k = keys([0, 0.5, 2.0, 2.6], t);
    const inspect = k([0, 1, 1, 0]);
    const sway = Math.sin((t / 2.6) * Math.PI * 2) * smoother(inspect);

    const out: Record<string, Ch> = {
      Spine: [4 * inspect, 0, 0],
      Neck: [8 * inspect, 6 * sway, 0],
      Head: [16 * inspect, 10 * sway, 0],
    };

    side(out, 'Arm', [2, 0, 4 + 2 * inspect], [2, 0, 4 + 2 * inspect]);
    side(out, 'ForeArm', [14 + 10 * inspect, 0, 0], [14 + 10 * inspect, 0, 0]);
    fingers(out, 12);

    return {
      bones: out,
      root: { ground: true },
      face: {
        mouthPress: 0.25 * inspect,
        browInnerUp: 0.2 * inspect,
      },
      gaze: [6 * sway, -24 * inspect],
    };
  },
};

// ── 11. INSPECT OUTFIT (TORSO TWIST PREVIEW) ──────────────────────────────────
export const inspectOutfit: Clip = {
  id: 'inspect_outfit',
  name: 'Inspect Outfit',
  category: 'Emotes',
  duration: 3.2,
  loop: false,
  sample: (t) => {
    const env = smoother(Math.sin((t / 3.2) * Math.PI));
    const twist = Math.sin((t / 3.2) * Math.PI * 2) * env; // gently turns upper body left and right
    const out: Record<string, Ch> = {
      Spine: [0, 12 * twist, 0],
      Spine1: [0, 10 * twist, 0],
      Neck: [0, 8 * twist, 0],
      Head: [2 * env, 14 * twist, 0],
    };
    side(out, 'Arm', [0, 0, 4], [0, 0, 4]);
    side(out, 'ForeArm', [14, 0, 0], [14, 0, 0]);
    fingers(out, 14);

    return {
      bones: out,
      root: { ground: true },
      face: {
        mouthSmile: 0.65 * env,
        eyeSquintLeft: 0.2 * env,
        eyeSquintRight: 0.2 * env,
      },
      gaze: [10 * twist, -8 * env],
    };
  },
};

// ── 12. SUGGEST ALTERNATIVE (HELPFUL SHRUG & HANDS UP) ───────────────────────
export const suggestAlt: Clip = {
  id: 'suggest_alt',
  name: 'Suggest Alternative',
  category: 'Emotes',
  duration: 2.4,
  loop: false,
  sample: (t) => {
    const k = keys([0, 0.45, 1.8, 2.4], t);
    const shrug = k([0, 1, 1, 0]);

    const out: Record<string, Ch> = {
      Spine: [2 * shrug, 0, 0],
      Neck: [2 * shrug, 6 * shrug, 4 * shrug],
      Head: [4 * shrug, 10 * shrug, 8 * shrug],
    };

    side(out, 'Shoulder', [0, 0, 14 * shrug], [0, 0, 14 * shrug]);
    fingers(out, 14 + (8 - 14) * shrug);

    const targetPosL = v(0.32, -0.32, 0.22);
    const targetPoleL = v(0.8, -0.6, -0.2);
    const targetDirL = v(0.3, 0.6, 0.6);
    const targetPalmL = v(-0.2, 0.9, -0.3);

    const targetPosR = v(-0.32, -0.32, 0.22);
    const targetPoleR = v(-0.8, -0.6, -0.2);
    const targetDirR = v(-0.3, 0.6, 0.6);
    const targetPalmR = v(0.2, 0.9, -0.3);

    return {
      bones: out,
      root: { ground: true },
      ik: {
        Left: {
          pos: lerp3(REST_ARM.Left.pos, targetPosL, shrug),
          pole: nlerp3(REST_ARM.Left.pole, targetPoleL, shrug),
          dir: nlerp3(REST_ARM.Left.dir, targetDirL, shrug),
          palm: nlerp3(REST_ARM.Left.palm, targetPalmL, shrug),
        },
        Right: {
          pos: lerp3(REST_ARM.Right.pos, targetPosR, shrug),
          pole: nlerp3(REST_ARM.Right.pole, targetPoleR, shrug),
          dir: nlerp3(REST_ARM.Right.dir, targetDirR, shrug),
          palm: nlerp3(REST_ARM.Right.palm, targetPalmR, shrug),
        },
      },
      face: {
        browOuterUpLeft: 0.5 * shrug,
        browOuterUpRight: 0.5 * shrug,
        browInnerUp: 0.3 * shrug,
        mouthSmile: 0.45 * shrug,
      },
    };
  },
};

// ── 13. WELCOME USER (OPEN HEART GREETING) ───────────────────────────────────
export const welcome: Clip = {
  id: 'welcome',
  name: 'Welcome',
  category: 'Emotes',
  duration: 2.6,
  loop: false,
  sample: (t) => {
    const k = keys([0, 0.55, 1.95, 2.6], t);
    const open = k([0, 1, 1, 0]);
    const nod = Math.sin(Math.min(1, Math.max(0, (t - 0.25) / 0.8)) * Math.PI * 2) * smoother(open);

    const out: Record<string, Ch> = {
      Spine: [-3 * open, 0, 0],
      Neck: [-2 * open + 3 * nod, 0, 0],
      Head: [-4 * open + 5 * nod, 0, 0],
    };

    fingers(out, 14 + (6 - 14) * open);

    const targetPosL = v(0.36, -0.26, 0.24);
    const targetPoleL = v(0.9, -0.5, -0.2);
    const targetDirL = v(0.3, 0.6, 0.6);
    const targetPalmL = v(-0.3, 0.8, -0.4);

    const targetPosR = v(-0.36, -0.26, 0.24);
    const targetPoleR = v(-0.9, -0.5, -0.2);
    const targetDirR = v(-0.4, 0.6, 0.6);
    const targetPalmR = v(0.3, 0.8, -0.4);

    return {
      bones: out,
      root: { ground: true },
      ik: {
        Left: {
          pos: lerp3(REST_ARM.Left.pos, targetPosL, open),
          pole: nlerp3(REST_ARM.Left.pole, targetPoleL, open),
          dir: nlerp3(REST_ARM.Left.dir, targetDirL, open),
          palm: nlerp3(REST_ARM.Left.palm, targetPalmL, open),
        },
        Right: {
          pos: lerp3(REST_ARM.Right.pos, targetPosR, open),
          pole: nlerp3(REST_ARM.Right.pole, targetPoleR, open),
          dir: nlerp3(REST_ARM.Right.dir, targetDirR, open),
          palm: nlerp3(REST_ARM.Right.palm, targetPalmR, open),
        },
      },
      face: {
        mouthSmile: 0.9 * open,
        eyeSquintLeft: 0.35 * open,
        eyeSquintRight: 0.35 * open,
        browOuterUpLeft: 0.25 * open,
        browOuterUpRight: 0.25 * open,
      },
    };
  },
};

// ── 14. ATTENTIVE LISTENING (VOICE / CHAT LISTENING) ──────────────────────────
export const listening: Clip = {
  id: 'listening',
  name: 'Listening',
  category: 'Emotes',
  duration: 3.2,
  loop: true,
  sample: (t) => {
    const a = (t / 3.2) * Math.PI * 2;
    const breathe = Math.sin(a);
    const out: Record<string, Ch> = {
      Spine: [1.2 * breathe, 0, 0],
      Neck: [2, 6 * Math.sin(a * 0.5), 4],
      Head: [2, 10 * Math.sin(a * 0.5), 6],
    };

    side(out, 'Arm', [1, 0, 4], [1, 0, 4]);
    side(out, 'ForeArm', [14, 0, 0], [14, 0, 0]);
    fingers(out, 12);

    return {
      bones: out,
      root: { ground: true },
      face: {
        browInnerUp: 0.2,
        browOuterUpLeft: 0.15,
        mouthSmile: 0.35,
        eyeWideLeft: 0.1,
        eyeWideRight: 0.1,
      },
      gaze: [0, 4],
    };
  },
};

// ── 15. EXCITED CELEBRATION ───────────────────────────────────────────────────
export const excited: Clip = {
  id: 'excited',
  name: 'Excited',
  category: 'Emotes',
  duration: 1.8,
  loop: false,
  sample: (t) => {
    const k = keys([0, 0.35, 1.45, 1.8], t);
    const joy = k([0, 1, 1, 0]);
    const hop = Math.max(0, Math.sin((t / 1.8) * Math.PI * 4)) * smoother(joy);

    const out: Record<string, Ch> = {
      Spine: [-4 * joy - 3 * hop, 0, 0],
      Neck: [-6 * joy, 0, 0],
      Head: [-10 * joy - 4 * hop, 0, 0],
    };

    side(out, 'Shoulder', [0, 0, 10 * hop], [0, 0, 10 * hop]);
    for (const s of ['Left', 'Right'] as const) {
      for (const f of ['Index', 'Middle', 'Ring', 'Pinky']) {
        out[`${s}Hand${f}1`] = [14 + (80 - 14) * joy, 0, 0];
        out[`${s}Hand${f}2`] = [16 + (100 - 16) * joy, 0, 0];
        out[`${s}Hand${f}3`] = [12 + (65 - 12) * joy, 0, 0];
      }
      out[`${s}HandThumb2`] = [8 + (15 - 8) * joy, 0, 0];
      out[`${s}HandThumb3`] = [25 * joy, 0, 0];
    }

    const up = -0.05 + 0.22 * hop;
    const targetPosL = v(0.32, up, 0.24);
    const targetPoleL = v(0.9, -0.6, -0.3);
    const targetDirL = v(0.2, 1, 0.2);
    const targetPalmL = v(-0.3, 0, 1);

    const targetPosR = v(-0.32, up, 0.24);
    const targetPoleR = v(-0.9, -0.6, -0.3);
    const targetDirR = v(-0.2, 1, 0.2);
    const targetPalmR = v(0.3, 0, 1);

    return {
      bones: out,
      root: { ground: true, lift: 0.04 * hop },
      ik: {
        Left: {
          pos: lerp3(REST_ARM.Left.pos, targetPosL, joy),
          pole: nlerp3(REST_ARM.Left.pole, targetPoleL, joy),
          dir: nlerp3(REST_ARM.Left.dir, targetDirL, joy),
          palm: nlerp3(REST_ARM.Left.palm, targetPalmL, joy),
        },
        Right: {
          pos: lerp3(REST_ARM.Right.pos, targetPosR, joy),
          pole: nlerp3(REST_ARM.Right.pole, targetPoleR, joy),
          dir: nlerp3(REST_ARM.Right.dir, targetDirR, joy),
          palm: nlerp3(REST_ARM.Right.palm, targetPalmR, joy),
        },
      },
      face: {
        mouthSmile: 1.0 * joy,
        jawOpen: 0.35 * hop,
        eyeSquintLeft: 0.3 * joy,
        eyeSquintRight: 0.3 * joy,
      },
    };
  },
};

// ── 16. CONFUSED (QUESTIONING ASYMMETRICAL EXPRESSION) ────────────────────────
export const confused: Clip = {
  id: 'confused',
  name: 'Confused',
  category: 'Emotes',
  duration: 2.2,
  loop: false,
  sample: (t) => {
    const k = keys([0, 0.45, 1.65, 2.2], t);
    const puzzled = k([0, 1, 1, 0]);

    const out: Record<string, Ch> = {
      Neck: [2 * puzzled, 12 * puzzled, 8 * puzzled],
      Head: [4 * puzzled, 16 * puzzled, 12 * puzzled],
    };

    side(out, 'Arm', [0, 0, 3], [0, 0, 0]);
    side(out, 'ForeArm', [12, 0, 0], [0, 0, 0]);
    fingers(out, 14);

    const targetPos = v(-0.26, -0.35, 0.22);
    const targetPole = v(-0.7, -0.6, -0.2);
    const targetDir = v(-0.3, 0.5, 0.6);
    const targetPalm = v(0.2, 0.9, -0.2);

    return {
      bones: out,
      root: { ground: true },
      ik: {
        Right: {
          pos: lerp3(REST_ARM.Right.pos, targetPos, puzzled),
          pole: nlerp3(REST_ARM.Right.pole, targetPole, puzzled),
          dir: nlerp3(REST_ARM.Right.dir, targetDir, puzzled),
          palm: nlerp3(REST_ARM.Right.palm, targetPalm, puzzled),
        },
      },
      face: {
        browOuterUpLeft: 0.75 * puzzled,
        browDownRight: 0.65 * puzzled,
        mouthPress: 0.4 * puzzled,
        mouthStretch: 0.25 * puzzled,
      },
      gaze: [10 * puzzled, 6 * puzzled],
    };
  },
};

/** All curated fashion reaction clips exportable to GLTF */
export const FASHION_REACTIONS: Clip[] = [
  thumbsUp,
  thumbsDown,
  nod,
  headShake,
  thinking,
  curious,
  presentSingle,
  presentBoth,
  pointOutfit,
  lookGarment,
  inspectOutfit,
  suggestAlt,
  welcome,
  listening,
  excited,
  confused,
];
