/**
 * Yorvyn 3D Avatar Profile — Strongly Typed, Versioned Identity Schema (Phase 3)
 * 
 * Acts as the single source of truth for 3D character generation,
 * morphing parameters, clothing state, facial expressions, and Supabase synchronization.
 */

import { HumanParams, DEFAULT_PARAMS } from '../engine/ara/core/params';
import { ExpressionId } from '../engine/ara/core/face';

export const AVATAR_PROFILE_SCHEMA_VERSION = 3;

export type GenderPresentation = 'masculine' | 'feminine' | 'neutral';

export type BodySilhouetteType = 'slender' | 'athletic' | 'curvy' | 'broad' | 'natural';
export type BodyPostureType = 'standing' | 'runway' | 'crossed_arms' | 'hands_pockets';

export interface AvatarProportions {
  heightCm: number;
  weightKg: number;
  silhouette: BodySilhouetteType;
  /** Normalized modifiers (-1.0 to 1.0) */
  shoulderWidth: number;
  torsoLength: number;
  waistWidth: number;
  hipWidth: number;
  armThickness: number;
  legThickness: number;
  muscleDefinition: number; // 0.0 to 1.0

  // Phase 7: Complete Body Customization Controls
  chestSize?: number;       // -1.0 to 1.0 (breast volume / chest breadth)
  neckLength?: number;      // -1.0 to 1.0 (neck scale vert)
  armLength?: number;       // -1.0 to 1.0 (upperarm scale horiz)
  handSize?: number;        // -1.0 to 1.0 (hand scale)
  legLength?: number;       // -1.0 to 1.0 (upperlegs height)
  thighThickness?: number;  // -1.0 to 1.0 (upperleg thickness)
  calfThickness?: number;   // -1.0 to 1.0 (lowerleg thickness)
  footSize?: number;        // -1.0 to 1.0 (foot scale)
  posture?: BodyPostureType;
}

export type FaceShapePreset = 'oval' | 'round' | 'rectangular' | 'square' | 'triangular' | 'invertedtriangular' | 'diamond' | 'default';

export interface AvatarFacialFeatures {
  headShape: number; // -1.0 to 1.0
  jawWidth: number;  // -1.0 to 1.0
  chinWidth: number; // -1.0 to 1.0
  cheekFullness: number; // -1.0 to 1.0
  noseWidth: number; // -1.0 to 1.0
  restingExpression: ExpressionId;

  // Phase 7: Detailed Face Customization
  faceShapePreset?: FaceShapePreset;
  faceWidth?: number;       // -1.0 to 1.0 (head scale horiz)
  faceHeight?: number;      // -1.0 to 1.0 (head scale vert)
  foreheadHeight?: number;  // -1.0 to 1.0 (forehead scale vert)
  jawAngle?: number;        // -1.0 to 1.0 (head angle)
  chinShape?: number;       // -1.0 to 1.0 (chin bone)
  chinProjection?: number;  // -1.0 to 1.0 (chin prominent)
  cheekboneProminence?: number; // -1.0 to 1.0 (cheek bones)
  facialProportions?: number;   // 0.0 to 1.0
  facialSymmetry?: number;      // -1.0 to 1.0

  // Phase 7: Eyes
  eyeShape?: string;
  eyeSize?: number;         // -1.0 to 1.0 (eye scale)
  eyeSpacing?: number;      // -1.0 to 1.0 (eye trans)
  eyePosition?: number;     // -1.0 to 1.0
  eyeAngle?: number;        // -1.0 to 1.0 (eye eyefold angle)
  eyelidShape?: number;     // -1.0 to 1.0 (eye eyefold)
  eyelashStyleId?: string;  // eyelashes01..04
  eyeHighlights?: number;   // 0.0 to 1.0

  // Phase 7: Eyebrows
  eyebrowShapeId?: string;  // eyebrow001..012
  eyebrowThickness?: number;// -1.0 to 1.0
  eyebrowLength?: number;   // -1.0 to 1.0
  eyebrowSpacing?: number;  // -1.0 to 1.0
  eyebrowPosition?: number; // -1.0 to 1.0 (eyebrows-trans:down|up)
  eyebrowArch?: number;     // -1.0 to 1.0 (eyebrows angle)
  eyebrowColorHex?: string;

  // Phase 7: Nose
  noseBridgeShape?: string;
  noseBridgeWidth?: number; // -1.0 to 1.0 (nose width 1)
  noseLength?: number;      // -1.0 to 1.0 (nose scale vert)
  noseTipShape?: number;    // -1.0 to 1.0 (nose point width)
  nostrilWidth?: number;    // -1.0 to 1.0 (nose nostrils width)
  nostrilShape?: number;    // -1.0 to 1.0 (nose compression)
  noseAngle?: number;       // -1.0 to 1.0 (nose trans:backward|forward)

  // Phase 7: Lips and Mouth
  lipShape?: string;
  upperLipFullness?: number;// -1.0 to 1.0 (mouth upperlip volume)
  lowerLipFullness?: number;// -1.0 to 1.0 (mouth lowerlip volume)
  mouthWidth?: number;      // -1.0 to 1.0 (mouth scale horiz)
  mouthPosition?: number;   // -1.0 to 1.0 (mouth trans:down|up)
  lipColorHex?: string;

  // Phase 7: Ears
  earSize?: number;         // -1.0 to 1.0 (ear scale)
  earPosition?: number;     // -1.0 to 1.0 (ear trans)
  earShape?: number;        // -1.0 to 1.0 (ear flapp rotation)
  earlobeVariation?: number;// -1.0 to 1.0 (earlobe)
  piercingStyleId?: string; // 'none' | 'studs' | 'small_hoops' | 'large_hoops' | 'drop_earrings'
}

export interface AvatarAppearance {
  skinToneId: string;
  skinToneHex: string;
  skinModel: string;
  hairStyleId: string;
  hairColorHex: string;
  facialHairId: string;
  facialHairColorHex: string;
  eyebrowStyleId: string;
  eyeColorId: string;

  // Phase 7: Skin & Makeup
  skinUndertone?: 'cool' | 'warm' | 'neutral' | 'olive';
  skinDetails?: {
    freckles?: number;
    beautyMarks?: boolean;
    moles?: boolean;
    scars?: string;
  };
  makeup?: {
    lipColor?: string;
    blushColor?: string;
    blushIntensity?: number;
    eyeshadowColor?: string;
  };

  // Phase 7: Hair Finetuning
  hairLength?: number;
  hairVolume?: number;
  hairline?: number;
  hairTexture?: string;
  hairHighlightHex?: string;
  hairRootHex?: string;
  hairGradientHex?: string;

  // Phase 7: Facial Hair Finetuning
  facialHairDensity?: number;
  facialHairLength?: number;
}

export interface AvatarWardrobeState {
  isBareMannequin: boolean;
  outfitId: string; // 'none' | proxy id (e.g. 'male_elegantsuit01')
  topId: string;    // 'none' | garment id
  bottomId: string; // 'none' | garment id
  outerwearId: string; // 'none' | garment id
  shoesId: string;  // 'none' | 'shoes01'..'shoes06'
  accessories: string[];
  sunglasses: boolean;
  garmentStyles: Record<string, { color?: string; color2?: string; pattern?: string }>;
}

export interface AvatarProfile {
  version: number;
  id: string;
  userId: string;
  updatedAt: string;
  name: string;
  genderPresentation: GenderPresentation;
  proportions: AvatarProportions;
  face: AvatarFacialFeatures;
  appearance: AvatarAppearance;
  wardrobe: AvatarWardrobeState;
}

export const DEFAULT_AVATAR_PROPORTIONS_MASCULINE: AvatarProportions = {
  heightCm: 180,
  weightKg: 75,
  silhouette: 'athletic',
  shoulderWidth: 0.15,
  torsoLength: 0.0,
  waistWidth: -0.05,
  hipWidth: -0.05,
  armThickness: 0.10,
  legThickness: 0.05,
  muscleDefinition: 0.60
};

export const DEFAULT_AVATAR_PROPORTIONS_FEMININE: AvatarProportions = {
  heightCm: 168,
  weightKg: 58,
  silhouette: 'natural',
  shoulderWidth: -0.10,
  torsoLength: 0.0,
  waistWidth: -0.15,
  hipWidth: 0.15,
  armThickness: -0.05,
  legThickness: 0.0,
  muscleDefinition: 0.40
};

export const DEFAULT_AVATAR_PROFILE: AvatarProfile = {
  version: AVATAR_PROFILE_SCHEMA_VERSION,
  id: 'default_atelier_profile',
  userId: '',
  updatedAt: new Date().toISOString(),
  name: 'Aarav (Masculine Avatar)',
  genderPresentation: 'masculine',
  proportions: DEFAULT_AVATAR_PROPORTIONS_MASCULINE,
  face: {
    headShape: 0.0,
    jawWidth: 0.05,
    chinWidth: 0.0,
    cheekFullness: 0.0,
    noseWidth: 0.0,
    restingExpression: 'neutral'
  },
  appearance: {
    skinToneId: 'amber',
    skinToneHex: '#f3c299',
    skinModel: 'young_caucasian_male',
    hairStyleId: 'short02',
    hairColorHex: '#1e293b',
    facialHairId: 'none',
    facialHairColorHex: '#1e293b',
    eyebrowStyleId: 'eyebrow001',
    eyeColorId: 'brownlight'
  },
  wardrobe: {
    isBareMannequin: false,
    outfitId: 'male_elegantsuit01',
    topId: 'none',
    bottomId: 'none',
    outerwearId: 'none',
    shoesId: 'shoes01',
    accessories: [],
    sunglasses: false,
    garmentStyles: {}
  }
};

/**
 * Maps BodySilhouette presets to concrete morph modifiers and scales.
 */
export function silhouetteToModifiers(silhouette: BodySilhouetteType): Record<string, number> {
  switch (silhouette) {
    case 'slender':
      return {
        'torso/torso-scale-vert': 0.12,
        'hips/hip-scale-horiz': -0.22,
        'shoulder/shoulder-scale-horiz': -0.18,
        'arms/arm-scale-horiz': -0.15,
        'legs/leg-scale-horiz': -0.15
      };
    case 'athletic':
      return {
        'torso/torso-scale-vert': 0.06,
        'hips/hip-scale-horiz': -0.08,
        'shoulder/shoulder-scale-horiz': 0.32,
        'arms/arm-scale-horiz': 0.20,
        'legs/leg-scale-horiz': 0.12
      };
    case 'curvy':
      return {
        'torso/torso-scale-vert': -0.04,
        'hips/hip-scale-horiz': 0.36,
        'shoulder/shoulder-scale-horiz': -0.05,
        'stomach/stomach-scale-horiz': 0.05
      };
    case 'broad':
      return {
        'torso/torso-scale-vert': 0.02,
        'hips/hip-scale-horiz': 0.18,
        'shoulder/shoulder-scale-horiz': 0.42,
        'arms/arm-scale-horiz': 0.25,
        'legs/leg-scale-horiz': 0.20
      };
    case 'natural':
    default:
      return {
        'torso/torso-scale-vert': 0.0,
        'hips/hip-scale-horiz': 0.0,
        'shoulder/shoulder-scale-horiz': 0.0
      };
  }
}

/**
 * Converts an AvatarProfile into Ara HumanParams for 3D character reconstruction.
 */
export function avatarProfileToHumanParams(profile: AvatarProfile): HumanParams {
  const isMasculine = profile.genderPresentation !== 'feminine';
  const silMods = silhouetteToModifiers(profile.proportions.silhouette);

  // Map Face Shape Preset to targets if defined
  const faceShapeMods: Record<string, number> = {};
  if (profile.face.faceShapePreset) {
    switch (profile.face.faceShapePreset) {
      case 'oval':
        faceShapeMods['head/head-oval'] = 0.7;
        break;
      case 'round':
        faceShapeMods['head/head-round'] = 0.75;
        break;
      case 'rectangular':
        faceShapeMods['head/head-rectangular'] = 0.7;
        break;
      case 'square':
        faceShapeMods['head/head-square'] = 0.75;
        break;
      case 'triangular':
        faceShapeMods['head/head-triangular'] = 0.7;
        break;
      case 'invertedtriangular':
        faceShapeMods['head/head-invertedtriangular'] = 0.7;
        break;
      case 'diamond':
        faceShapeMods['head/head-diamond'] = 0.7;
        break;
    }
  }

  const modifiers: Record<string, number> = {
    ...silMods,
    ...faceShapeMods,
    // Body Proportions
    'shoulder/shoulder-scale-horiz': profile.proportions.shoulderWidth ?? 0.0,
    'torso/torso-scale-vert': profile.proportions.torsoLength ?? 0.0,
    'hips/hip-scale-horiz': profile.proportions.hipWidth ?? 0.0,
    'waist/waist-width': profile.proportions.waistWidth ?? 0.0,
    'neck/neck-scale-vert': profile.proportions.neckLength ?? 0.0,
    'breast/breast-volume-vert': profile.proportions.chestSize ?? (isMasculine ? 0.0 : 0.4),
    'armslegs/upperarm-scale-horiz': profile.proportions.armLength ?? 0.0,
    'armslegs/upperarm-scale-depth': profile.proportions.armThickness ?? 0.0,
    'armslegs/hand-scale': profile.proportions.handSize ?? 0.0,
    'armslegs/upperlegs-height': profile.proportions.legLength ?? 0.0,
    'armslegs/upperleg-scale-depth': profile.proportions.thighThickness ?? 0.0,
    'armslegs/lowerleg-scale-depth': profile.proportions.calfThickness ?? profile.proportions.legThickness ?? 0.0,
    'armslegs/foot-scale': profile.proportions.footSize ?? 0.0,

    // Face & Head
    'head/head-scale-horiz': profile.face.faceWidth ?? profile.face.headShape ?? 0.0,
    'head/head-scale-vert': profile.face.faceHeight ?? 0.0,
    'forehead/forehead-scale-vert': profile.face.foreheadHeight ?? 0.0,
    'head/head-angle': profile.face.jawAngle ?? 0.0,
    'chin/jaw-width': profile.face.jawWidth ?? 0.0,
    'chin/chin-width': profile.face.chinWidth ?? 0.0,
    'chin/chin-bone': profile.face.chinShape ?? 0.0,
    'chin/chin-prominent': profile.face.chinProjection ?? 0.0,
    'cheek/cheek-prominence': profile.face.cheekFullness ?? 0.0,
    'cheek/cheek-bones': profile.face.cheekboneProminence ?? 0.0,

    // Eyes & Eyebrows
    'eyes/eye-scale': profile.face.eyeSize ?? 0.0,
    'eyes/eye-trans': profile.face.eyeSpacing ?? 0.0,
    'eyes/eye-eyefold-angle': profile.face.eyeAngle ?? 0.0,
    'eyes/eye-eyefold': profile.face.eyelidShape ?? 0.0,
    'eyebrows/eyebrows-trans:down|up': profile.face.eyebrowPosition ?? 0.0,
    'eyebrows/eyebrows-angle': profile.face.eyebrowArch ?? 0.0,

    // Nose
    'nose/nose-scale-horiz': profile.face.noseWidth ?? 0.0,
    'nose/nose-scale-vert': profile.face.noseLength ?? 0.0,
    'nose/nose-width1': profile.face.noseBridgeWidth ?? 0.0,
    'nose/nose-nostrils-width': profile.face.nostrilWidth ?? 0.0,
    'nose/nose-point-width': profile.face.noseTipShape ?? 0.0,
    'nose/nose-compression': profile.face.nostrilShape ?? 0.0,
    'nose/nose-trans:backward|forward': profile.face.noseAngle ?? 0.0,

    // Lips & Mouth
    'mouth/mouth-upperlip-volume': profile.face.upperLipFullness ?? 0.0,
    'mouth/mouth-lowerlip-volume': profile.face.lowerLipFullness ?? 0.0,
    'mouth/mouth-scale-horiz': profile.face.mouthWidth ?? 0.0,
    'mouth/mouth-trans:down|up': profile.face.mouthPosition ?? 0.0,

    // Ears
    'ears/ear-scale': profile.face.earSize ?? 0.0,
    'ears/ear-trans': profile.face.earPosition ?? 0.0,
    'ears/ear-rot-flapp': profile.face.earShape ?? 0.0,
    'ears/ear-lobe': profile.face.earlobeVariation ?? 0.0
  };

  const heightParam = Math.max(0, Math.min(1, (profile.proportions.heightCm - 155) / 40));
  const weightParam = Math.max(0, Math.min(1, (profile.proportions.weightKg - 45) / 55));

  // Determine earrings
  const piercing = profile.face.piercingStyleId && profile.face.piercingStyleId !== 'none'
    ? (profile.face.piercingStyleId as any)
    : 'none';

  return {
    ...DEFAULT_PARAMS,
    name: profile.name,
    gender: isMasculine ? 0.95 : 0.05,
    age: 0.25,
    muscle: profile.proportions.muscleDefinition,
    weight: weightParam,
    height: heightParam,
    proportions: 0.85,
    breastSize: isMasculine ? 0.1 : 0.55,
    breastFirmness: 0.6,
    skin: (profile.genderPresentation === 'feminine' && profile.appearance.skinModel === 'young_caucasian_male')
      ? 'young_caucasian_female'
      : (profile.appearance.skinModel || (isMasculine ? 'young_caucasian_male' : 'young_caucasian_female')),
    skinTint: profile.appearance.skinToneHex || '#ffffff',
    eyes: profile.appearance.eyeColorId || 'brownlight',
    eyebrows: profile.face.eyebrowShapeId || profile.appearance.eyebrowStyleId || (isMasculine ? 'eyebrow001' : 'eyebrow010'),
    eyelashes: profile.face.eyelashStyleId || (isMasculine ? 'eyelashes01' : 'eyelashes02'),
    hair: profile.appearance.hairStyleId || (isMasculine ? 'short02' : 'bob01'),
    hairColor: profile.appearance.hairColorHex || '#1e293b',
    hairTint: '#ffffff',
    facialHair: (isMasculine ? profile.appearance.facialHairId : 'none') as any,
    beardColor: profile.appearance.facialHairColorHex || '#1e293b',
    earrings: piercing,
    earringMetal: 'gold',
    expression: profile.face.restingExpression || 'neutral',
    outfit: profile.wardrobe.isBareMannequin ? 'none' : profile.wardrobe.outfitId || 'none',
    outfitTint: profile.wardrobe.garmentStyles?.default?.color || '#ffffff',
    top: profile.wardrobe.isBareMannequin ? 'none' : profile.wardrobe.topId || 'none',
    bottom: profile.wardrobe.isBareMannequin ? 'none' : profile.wardrobe.bottomId || 'none',
    shoes: profile.wardrobe.isBareMannequin ? 'none' : profile.wardrobe.shoesId || 'shoes01',
    underwear: true,
    accessories: profile.wardrobe.accessories || [],
    garmentStyles: profile.wardrobe.garmentStyles || {},
    modifiers
  };
}

/**
 * Serializes live HumanParams into strongly typed AvatarProfile (Schema v3).
 */
export function humanParamsToAvatarProfile(params: HumanParams, userId = ''): AvatarProfile {
  const isMasculine = (params.gender ?? 0.5) >= 0.5;
  const mods = params.modifiers || {};
  return {
    version: AVATAR_PROFILE_SCHEMA_VERSION,
    id: `avatar_${userId || 'current'}`,
    userId,
    updatedAt: new Date().toISOString(),
    name: params.name || (isMasculine ? 'Aarav (Masculine Avatar)' : 'Elena (Feminine Avatar)'),
    genderPresentation: isMasculine ? 'masculine' : 'feminine',
    proportions: {
      heightCm: Math.round(155 + (params.height || 0.6) * 40),
      weightKg: Math.round(45 + (params.weight || 0.5) * 55),
      silhouette: isMasculine ? 'athletic' : 'curvy',
      shoulderWidth: mods['shoulder/shoulder-scale-horiz'] ?? mods['torso/torso-scale-horiz'] ?? 0.0,
      torsoLength: mods['torso/torso-scale-vert'] ?? 0.0,
      waistWidth: mods['waist/waist-width'] ?? 0.0,
      hipWidth: mods['hips/hip-scale-horiz'] ?? 0.0,
      armThickness: mods['armslegs/upperarm-scale-depth'] ?? mods['arms/arm-scale-horiz'] ?? 0.0,
      legThickness: mods['armslegs/lowerleg-scale-depth'] ?? mods['legs/leg-scale-horiz'] ?? 0.0,
      muscleDefinition: params.muscle || 0.5,
      chestSize: mods['breast/breast-volume-vert'] ?? 0.0,
      neckLength: mods['neck/neck-scale-vert'] ?? 0.0,
      armLength: mods['armslegs/upperarm-scale-horiz'] ?? 0.0,
      handSize: mods['armslegs/hand-scale'] ?? 0.0,
      legLength: mods['armslegs/upperlegs-height'] ?? 0.0,
      thighThickness: mods['armslegs/upperleg-scale-depth'] ?? 0.0,
      calfThickness: mods['armslegs/lowerleg-scale-depth'] ?? 0.0,
      footSize: mods['armslegs/foot-scale'] ?? 0.0,
      posture: 'standing'
    },
    face: {
      headShape: mods['head/head-scale-horiz'] ?? 0.0,
      faceWidth: mods['head/head-scale-horiz'] ?? 0.0,
      faceHeight: mods['head/head-scale-vert'] ?? 0.0,
      foreheadHeight: mods['forehead/forehead-scale-vert'] ?? 0.0,
      jawWidth: mods['chin/jaw-width'] ?? 0.0,
      jawAngle: mods['head/head-angle'] ?? 0.0,
      chinWidth: mods['chin/chin-width'] ?? 0.0,
      chinShape: mods['chin/chin-bone'] ?? 0.0,
      chinProjection: mods['chin/chin-prominent'] ?? 0.0,
      cheekFullness: mods['cheek/cheek-prominence'] ?? 0.0,
      cheekboneProminence: mods['cheek/cheek-bones'] ?? 0.0,
      noseWidth: mods['nose/nose-scale-horiz'] ?? 0.0,
      noseLength: mods['nose/nose-scale-vert'] ?? 0.0,
      noseBridgeWidth: mods['nose/nose-width1'] ?? 0.0,
      nostrilWidth: mods['nose/nose-nostrils-width'] ?? 0.0,
      noseTipShape: mods['nose/nose-point-width'] ?? 0.0,
      nostrilShape: mods['nose/nose-compression'] ?? 0.0,
      noseAngle: mods['nose/nose-trans:backward|forward'] ?? 0.0,
      upperLipFullness: mods['mouth/mouth-upperlip-volume'] ?? 0.0,
      lowerLipFullness: mods['mouth/mouth-lowerlip-volume'] ?? 0.0,
      mouthWidth: mods['mouth/mouth-scale-horiz'] ?? 0.0,
      mouthPosition: mods['mouth/mouth-trans:down|up'] ?? 0.0,
      eyeSize: mods['eyes/eye-scale'] ?? 0.0,
      eyeSpacing: mods['eyes/eye-trans'] ?? 0.0,
      eyeAngle: mods['eyes/eye-eyefold-angle'] ?? 0.0,
      eyelidShape: mods['eyes/eye-eyefold'] ?? 0.0,
      eyelashStyleId: params.eyelashes || (isMasculine ? 'eyelashes01' : 'eyelashes02'),
      eyebrowShapeId: params.eyebrows || (isMasculine ? 'eyebrow001' : 'eyebrow010'),
      eyebrowPosition: mods['eyebrows/eyebrows-trans:down|up'] ?? 0.0,
      eyebrowArch: mods['eyebrows/eyebrows-angle'] ?? 0.0,
      earSize: mods['ears/ear-scale'] ?? 0.0,
      earPosition: mods['ears/ear-trans'] ?? 0.0,
      earShape: mods['ears/ear-rot-flapp'] ?? 0.0,
      earlobeVariation: mods['ears/ear-lobe'] ?? 0.0,
      piercingStyleId: (params.earrings as any) || 'none',
      restingExpression: (params.expression as any) || 'neutral'
    },
    appearance: {
      skinToneId: 'natural',
      skinToneHex: params.skinTint || '#ffffff',
      skinModel: params.skin || (isMasculine ? 'young_caucasian_male' : 'young_caucasian_female'),
      hairStyleId: params.hair || (isMasculine ? 'short02' : 'bob01'),
      hairColorHex: params.hairColor || '#1e293b',
      facialHairId: (params.facialHair as any) || 'none',
      facialHairColorHex: params.beardColor || '#1e293b',
      eyebrowStyleId: params.eyebrows || (isMasculine ? 'eyebrow001' : 'eyebrow010'),
      eyeColorId: params.eyes || 'brownlight',
      skinUndertone: 'neutral',
      skinDetails: {
        freckles: 0,
        beautyMarks: false,
        moles: false,
        scars: 'none'
      },
      makeup: {
        lipColor: undefined,
        blushColor: undefined,
        blushIntensity: 0
      }
    },
    wardrobe: {
      isBareMannequin: params.outfit === 'none' && params.top === 'none' && params.bottom === 'none',
      outfitId: params.outfit || 'none',
      topId: params.top || 'none',
      bottomId: params.bottom || 'none',
      outerwearId: 'none',
      shoesId: params.shoes || 'shoes01',
      accessories: params.accessories || [],
      sunglasses: false,
      garmentStyles: params.garmentStyles || {}
    }
  };
}

/**
 * Upgrades legacy or partial profile data to Schema v3 with safe defaults.
 */
export function migrateAvatarProfile(raw: any, userId = ''): AvatarProfile {
  if (!raw || typeof raw !== 'object') {
    return { ...DEFAULT_AVATAR_PROFILE, userId };
  }

  // Already v3
  if (raw.version === AVATAR_PROFILE_SCHEMA_VERSION && raw.proportions && raw.appearance && raw.wardrobe) {
    return {
      ...raw,
      userId: userId || raw.userId || ''
    };
  }

  // Legacy format migration
  const genderPres: GenderPresentation = 
    raw.avatarGenderPresentation === 'feminine' || raw.gender === 'female' ? 'feminine' : 'masculine';
  const defaultProps = genderPres === 'feminine' ? DEFAULT_AVATAR_PROPORTIONS_FEMININE : DEFAULT_AVATAR_PROPORTIONS_MASCULINE;

  const heightVal = Number(raw.heightValue || raw.height_cm || (genderPres === 'feminine' ? 168 : 180));
  const weightVal = Number(raw.weightValue || (genderPres === 'feminine' ? 58 : 75));
  const silhouette: BodySilhouetteType = (['slender', 'athletic', 'curvy', 'broad'].includes(raw.bodyType) 
    ? raw.bodyType 
    : defaultProps.silhouette) as BodySilhouetteType;

  const skinToneHex = raw.skinToneHex || raw.skin_tone_hex || '#f3c299';
  const hairColorHex = raw.hairColourHex || raw.hair_colour_hex || '#1e293b';

  return {
    version: AVATAR_PROFILE_SCHEMA_VERSION,
    id: raw.id || `profile_${Date.now()}`,
    userId: userId || raw.user_id || '',
    updatedAt: new Date().toISOString(),
    name: raw.displayName || raw.name || (genderPres === 'feminine' ? 'Elena' : 'Aarav'),
    genderPresentation: genderPres,
    proportions: {
      heightCm: heightVal,
      weightKg: weightVal,
      silhouette,
      shoulderWidth: raw.shoulderWidth ?? defaultProps.shoulderWidth,
      torsoLength: raw.torsoLength ?? defaultProps.torsoLength,
      waistWidth: raw.waistWidth ?? defaultProps.waistWidth,
      hipWidth: raw.hipWidth ?? defaultProps.hipWidth,
      armThickness: raw.armThickness ?? defaultProps.armThickness,
      legThickness: raw.legThickness ?? defaultProps.legThickness,
      muscleDefinition: raw.muscleDefinition ?? defaultProps.muscleDefinition
    },
    face: {
      headShape: raw.headShape ?? 0.0,
      jawWidth: raw.jawWidth ?? 0.0,
      chinWidth: raw.chinWidth ?? 0.0,
      cheekFullness: raw.cheekFullness ?? 0.0,
      noseWidth: raw.noseWidth ?? 0.0,
      restingExpression: raw.restingExpression || 'neutral'
    },
    appearance: {
      skinToneId: raw.skinToneId || raw.skin_tone_id || 'amber',
      skinToneHex,
      skinModel: raw.skinModel || (genderPres === 'feminine' ? 'young_caucasian_female' : 'young_caucasian_male'),
      hairStyleId: raw.hairStyleId || raw.avatarConfiguration?.hair || (genderPres === 'feminine' ? 'bob01' : 'short02'),
      hairColorHex,
      facialHairId: raw.facialHairId || 'none',
      facialHairColorHex: raw.facialHairColorHex || hairColorHex,
      eyebrowStyleId: raw.eyebrowStyleId || (genderPres === 'feminine' ? 'eyebrow010' : 'eyebrow001'),
      eyeColorId: raw.eyeColorId || 'brownlight'
    },
    wardrobe: {
      isBareMannequin: Boolean(raw.isBareMannequin),
      outfitId: raw.outfitId || (genderPres === 'feminine' ? 'female_casualsuit01' : 'male_elegantsuit01'),
      topId: raw.topId || 'none',
      bottomId: raw.bottomId || 'none',
      outerwearId: raw.outerwearId || 'none',
      shoesId: raw.shoesId || 'shoes01',
      accessories: raw.accessories || [],
      sunglasses: Boolean(raw.sunglasses),
      garmentStyles: raw.garmentStyles || {}
    }
  };
}
