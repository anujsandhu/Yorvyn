/**
 * Yorvyn — Avatar Model Capability Checker
 * 
 * Inspects any loaded 3D avatar (Object3D, SkinnedMesh, or GLTF hierarchy),
 * audits skeleton availability, bone presence, ARKit/Oculus facial blendshapes,
 * eye/jaw controls, and finger articulation.
 * Classifies the model into a Capability Tier and configures graceful fallbacks.
 */

import * as THREE from 'three';

export type CapabilityTier = 1 | 2 | 3 | 4;

export interface CapabilityReport {
  tier: CapabilityTier;
  tierName: string;
  hasSkeleton: boolean;
  bonesFound: string[];
  missingEssentialBones: string[];
  hasFacialBlendshapes: boolean;
  blendshapesFound: string[];
  missingBlendshapes: string[];
  hasVisemes: boolean;
  visemesFound: string[];
  hasEyeControl: boolean;
  hasJawControl: boolean;
  hasHandFingers: boolean;
  animationClipsFound: string[];
  fallbackMappings: Record<string, string>;
  warnings: string[];
}

const ESSENTIAL_BONES = [
  'Hips',
  'Spine',
  'Neck',
  'Head',
  'LeftArm',
  'RightArm',
  'LeftForeArm',
  'RightForeArm',
  'LeftHand',
  'RightHand',
];

const STANDARD_VISEMES = [
  'viseme_PP',
  'viseme_FF',
  'viseme_TH',
  'viseme_DD',
  'viseme_kk',
  'viseme_CH',
  'viseme_SS',
  'viseme_nn',
  'viseme_RR',
  'viseme_aa',
  'viseme_E',
  'viseme_I',
  'viseme_O',
  'viseme_U',
];

const STANDARD_EXPRESSIONS = [
  'mouthSmile',
  'mouthFrown',
  'eyeBlinkLeft',
  'eyeBlinkRight',
  'browInnerUp',
  'browDownLeft',
  'browDownRight',
  'jawOpen',
];

export class AvatarCapabilityChecker {
  /**
   * Inspects a Three.js hierarchy and returns an exhaustive capability audit.
   */
  static audit(root: THREE.Object3D, animationClips: THREE.AnimationClip[] = []): CapabilityReport {
    const bonesFound = new Set<string>();
    const blendshapesFound = new Set<string>();
    const warnings: string[] = [];
    const fallbackMappings: Record<string, string> = {};

    root.traverse((obj) => {
      // Check bone names
      if ((obj as THREE.Bone).isBone || obj.type === 'Bone') {
        bonesFound.add(obj.name);
      }

      if ((obj as THREE.Mesh).isMesh) {
        const mesh = obj as THREE.Mesh;
        if (mesh.morphTargetDictionary) {
          Object.keys(mesh.morphTargetDictionary).forEach((shapeName) => {
            blendshapesFound.add(shapeName);
          });
        }
      }
    });

    // Check essential bones
    const missingEssentialBones = ESSENTIAL_BONES.filter((b) => !bonesFound.has(b));

    // Check visemes
    const visemesFound = STANDARD_VISEMES.filter((v) => blendshapesFound.has(v));
    const hasVisemes = visemesFound.length >= 8;

    // Check eye controls
    const hasEyeBones = bonesFound.has('LeftEye') && bonesFound.has('RightEye');
    const hasEyeBlendshapes =
      blendshapesFound.has('eyeLookUpLeft') || blendshapesFound.has('eyeBlinkLeft');
    const hasEyeControl = hasEyeBones || hasEyeBlendshapes;

    // Check jaw control
    const hasJawBone = bonesFound.has('Jaw');
    const hasJawBlendshape = blendshapesFound.has('jawOpen');
    const hasJawControl = hasJawBone || hasJawBlendshape;

    // Check fingers
    const hasHandFingers =
      bonesFound.has('LeftHandIndex1') || bonesFound.has('RightHandThumb1');

    // Establish fallbacks if visemes are missing
    if (!hasVisemes) {
      if (hasJawBlendshape) {
        fallbackMappings['speech_visemes'] = 'jawOpen';
        warnings.push('Oculus visemes missing; falling back to jawOpen blendshape.');
      } else if (hasJawBone) {
        fallbackMappings['speech_visemes'] = 'bone_Jaw_rotation';
        warnings.push('Facial blendshapes missing; falling back to procedural Jaw bone rotation.');
      } else {
        fallbackMappings['speech_visemes'] = 'subtle_head_nod_cadence';
        warnings.push('No jaw or viseme controls found; speech will use subtle conversational head cadence.');
      }
    }

    if (!hasEyeControl) {
      fallbackMappings['gaze_tracking'] = 'procedural_head_orientation';
      warnings.push('Eye controls missing; gaze direction will be driven via neck/head orientation.');
    }

    // Determine Capability Tier
    let tier: CapabilityTier = 4;
    let tierName = 'Tier 4: Static / Unrigged Fallback';

    const hasSkeleton = bonesFound.size >= 10 && missingEssentialBones.length === 0;
    const hasFacialBlendshapes = blendshapesFound.size >= 6;

    if (hasSkeleton && hasFacialBlendshapes && hasVisemes && hasHandFingers) {
      tier = 1;
      tierName = 'Tier 1: Full Conversational Digital Human';
    } else if (hasSkeleton && (hasJawControl || hasFacialBlendshapes)) {
      tier = 2;
      tierName = 'Tier 2: Skeletal Expressive Human';
    } else if (hasSkeleton) {
      tier = 3;
      tierName = 'Tier 3: Basic Upper Body Rig';
    } else {
      tier = 4;
      tierName = 'Tier 4: Unrigged / Minimal Mesh';
    }

    return {
      tier,
      tierName,
      hasSkeleton,
      bonesFound: Array.from(bonesFound),
      missingEssentialBones,
      hasFacialBlendshapes,
      blendshapesFound: Array.from(blendshapesFound),
      missingBlendshapes: STANDARD_EXPRESSIONS.filter((e) => !blendshapesFound.has(e)),
      hasVisemes,
      visemesFound,
      hasEyeControl,
      hasJawControl,
      hasHandFingers,
      animationClipsFound: animationClips.map((c) => c.name),
      fallbackMappings,
      warnings,
    };
  }
}

