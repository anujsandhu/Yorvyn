/**
 * YORVYN — PHASE 7: Complete Modular Avatar Asset Registry
 * 
 * Central catalog of all 13 customization categories,
 * visual preset definitions, fine adjustment sliders, and color palettes.
 * Every option maps directly to supported 3D geometry, MakeHuman targets,
 * or Ara engine deformation parameters.
 */

import { 
  AvatarCreatorCategory, 
  CategoryTabMeta, 
  AvatarSliderDef, 
  AvatarPresetDef, 
  AvatarColorSwatch 
} from './avatarCreatorTypes';
import { 
  BodySilhouetteType, 
  FaceShapePreset 
} from '../../types/avatarProfile';

// =============================================================================
// 1. CATEGORY TABS CONFIGURATION (13 BITMOJI/SNAP-STYLE CATEGORIES)
// =============================================================================

export const CATEGORY_TABS: CategoryTabMeta[] = [
  { id: 'body', label: 'Body', iconName: 'User', cameraFocus: 'full', subViews: ['presets', 'sliders'] },
  { id: 'face', label: 'Face', iconName: 'Smiley', cameraFocus: 'head', subViews: ['presets', 'sliders'] },
  { id: 'eyes', label: 'Eyes', iconName: 'Eye', cameraFocus: 'head', subViews: ['presets', 'sliders', 'colors'] },
  { id: 'eyebrows', label: 'Brows', iconName: 'Eyebrows', cameraFocus: 'head', subViews: ['presets', 'sliders', 'colors'] },
  { id: 'nose', label: 'Nose', iconName: 'Nose', cameraFocus: 'head', subViews: ['presets', 'sliders'] },
  { id: 'mouth', label: 'Mouth', iconName: 'Mouth', cameraFocus: 'head', subViews: ['presets', 'sliders', 'colors'] },
  { id: 'ears', label: 'Ears', iconName: 'Ears', cameraFocus: 'head', subViews: ['presets', 'sliders'] },
  { id: 'hair', label: 'Hair', iconName: 'Scissors', cameraFocus: 'head', subViews: ['presets', 'sliders', 'colors'] },
  { id: 'facial_hair', label: 'Beard', iconName: 'Beard', cameraFocus: 'head', subViews: ['presets', 'sliders', 'colors'] },
  { id: 'skin', label: 'Skin', iconName: 'Palette', cameraFocus: 'head', subViews: ['presets', 'colors', 'styling'] },
  { id: 'clothing', label: 'Clothing', iconName: 'TShirt', cameraFocus: 'full', subViews: ['presets', 'colors', 'styling'] },
  { id: 'accessories', label: 'Accs', iconName: 'Glasses', cameraFocus: 'torso', subViews: ['presets'] },
  { id: 'expressions', label: 'Emotes', iconName: 'Sparkle', cameraFocus: 'full', subViews: ['presets', 'styling'] },
];

// =============================================================================
// 2. FINE ADJUSTMENT SLIDERS (CATEGORIZED & MAPPED TO 3D TARGETS)
// =============================================================================

export const AVATAR_SLIDERS: Record<AvatarCreatorCategory, AvatarSliderDef[]> = {
  body: [
    { id: 'heightCm', category: 'body', label: 'Stature Height', min: 145, max: 205, step: 1, defaultValue: 178, unit: 'cm', profilePath: 'proportions.heightCm' },
    { id: 'muscleDefinition', category: 'body', label: 'Muscle Tone', min: 0, max: 1, step: 0.02, defaultValue: 0.55, unit: '%', profilePath: 'proportions.muscleDefinition' },
    { id: 'shoulderWidth', category: 'body', label: 'Shoulder Breadth', min: -1, max: 1, step: 0.05, defaultValue: 0.1, bipolar: true, modifierKey: 'shoulder/shoulder-scale-horiz', profilePath: 'proportions.shoulderWidth' },
    { id: 'chestSize', category: 'body', label: 'Chest Breadth / Volume', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'breast/breast-volume-vert', profilePath: 'proportions.chestSize' },
    { id: 'waistWidth', category: 'body', label: 'Waist Taper', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'waist/waist-width', profilePath: 'proportions.waistWidth' },
    { id: 'hipWidth', category: 'body', label: 'Hip Width', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'hips/hip-scale-horiz', profilePath: 'proportions.hipWidth' },
    { id: 'torsoLength', category: 'body', label: 'Torso Length', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'torso/torso-scale-vert', profilePath: 'proportions.torsoLength' },
    { id: 'neckLength', category: 'body', label: 'Neck Length', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'neck/neck-scale-vert', profilePath: 'proportions.neckLength' },
    { id: 'armLength', category: 'body', label: 'Arm Length', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'armslegs/upperarm-scale-horiz', profilePath: 'proportions.armLength' },
    { id: 'armThickness', category: 'body', label: 'Arm Thickness', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'armslegs/upperarm-scale-depth', profilePath: 'proportions.armThickness' },
    { id: 'handSize', category: 'body', label: 'Hand Scale', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'armslegs/hand-scale', profilePath: 'proportions.handSize' },
    { id: 'legLength', category: 'body', label: 'Leg Stride Length', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'armslegs/upperlegs-height', profilePath: 'proportions.legLength' },
    { id: 'thighThickness', category: 'body', label: 'Thigh Proportions', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'armslegs/upperleg-scale-depth', profilePath: 'proportions.thighThickness' },
    { id: 'calfThickness', category: 'body', label: 'Calf Proportions', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'armslegs/lowerleg-scale-depth', profilePath: 'proportions.calfThickness' },
    { id: 'footSize', category: 'body', label: 'Foot Scale', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'armslegs/foot-scale', profilePath: 'proportions.footSize' },
  ],

  face: [
    { id: 'faceWidth', category: 'face', label: 'Face Width', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'head/head-scale-horiz', profilePath: 'face.faceWidth' },
    { id: 'faceHeight', category: 'face', label: 'Face Length', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'head/head-scale-vert', profilePath: 'face.faceHeight' },
    { id: 'foreheadHeight', category: 'face', label: 'Forehead Height', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'forehead/forehead-scale-vert', profilePath: 'face.foreheadHeight' },
    { id: 'jawWidth', category: 'face', label: 'Jaw Width', min: -1, max: 1, step: 0.05, defaultValue: 0.05, bipolar: true, modifierKey: 'chin/jaw-width', profilePath: 'face.jawWidth' },
    { id: 'jawAngle', category: 'face', label: 'Jaw Angle / Chiseled', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'head/head-angle', profilePath: 'face.jawAngle' },
    { id: 'chinShape', category: 'face', label: 'Chin Bone Shape', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'chin/chin-bone', profilePath: 'face.chinShape' },
    { id: 'chinProjection', category: 'face', label: 'Chin Projection', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'chin/chin-prominent', profilePath: 'face.chinProjection' },
    { id: 'cheekFullness', category: 'face', label: 'Cheek Fullness', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'cheek/cheek-prominence', profilePath: 'face.cheekFullness' },
    { id: 'cheekboneProminence', category: 'face', label: 'Cheekbone Definition', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'cheek/cheek-bones', profilePath: 'face.cheekboneProminence' },
    { id: 'facialSymmetry', category: 'face', label: 'Facial Balance & Alignment', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, profilePath: 'face.facialSymmetry' }
  ],

  eyes: [
    { id: 'eyeSize', category: 'eyes', label: 'Eye Scale', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'eyes/eye-scale', profilePath: 'face.eyeSize' },
    { id: 'eyeSpacing', category: 'eyes', label: 'Eye Spacing / Distance', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'eyes/eye-trans', profilePath: 'face.eyeSpacing' },
    { id: 'eyeAngle', category: 'eyes', label: 'Canthal Tilt / Eye Angle', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'eyes/eye-eyefold-angle', profilePath: 'face.eyeAngle' },
    { id: 'eyelidShape', category: 'eyes', label: 'Eyelid Fold Depth', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'eyes/eye-eyefold', profilePath: 'face.eyelidShape' },
    { id: 'eyeHighlights', category: 'eyes', label: 'Catchlight Highlights', min: 0, max: 1, step: 0.05, defaultValue: 0.85, profilePath: 'face.eyeHighlights' }
  ],

  eyebrows: [
    { id: 'eyebrowPosition', category: 'eyebrows', label: 'Vertical Position', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'eyebrows/eyebrows-trans:down|up', profilePath: 'face.eyebrowPosition' },
    { id: 'eyebrowArch', category: 'eyebrows', label: 'Brow Arch & Angle', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'eyebrows/eyebrows-angle', profilePath: 'face.eyebrowArch' },
    { id: 'eyebrowThickness', category: 'eyebrows', label: 'Brow Density', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, profilePath: 'face.eyebrowThickness' },
    { id: 'eyebrowSpacing', category: 'eyebrows', label: 'Brow Center Spacing', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, profilePath: 'face.eyebrowSpacing' }
  ],

  nose: [
    { id: 'noseLength', category: 'nose', label: 'Nose Length', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'nose/nose-scale-vert', profilePath: 'face.noseLength' },
    { id: 'noseWidth', category: 'nose', label: 'Nose Width', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'nose/nose-scale-horiz', profilePath: 'face.noseWidth' },
    { id: 'noseBridgeWidth', category: 'nose', label: 'Bridge Width', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'nose/nose-width1', profilePath: 'face.noseBridgeWidth' },
    { id: 'noseTipShape', category: 'nose', label: 'Tip Width & Point', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'nose/nose-point-width', profilePath: 'face.noseTipShape' },
    { id: 'nostrilWidth', category: 'nose', label: 'Nostril Width', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'nose/nose-nostrils-width', profilePath: 'face.nostrilWidth' },
    { id: 'nostrilShape', category: 'nose', label: 'Nostril Flare / Compression', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'nose/nose-compression', profilePath: 'face.nostrilShape' },
    { id: 'noseAngle', category: 'nose', label: 'Nose Profile Projection', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'nose/nose-trans:backward|forward', profilePath: 'face.noseAngle' }
  ],

  mouth: [
    { id: 'upperLipFullness', category: 'mouth', label: 'Upper Lip Fullness', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'mouth/mouth-upperlip-volume', profilePath: 'face.upperLipFullness' },
    { id: 'lowerLipFullness', category: 'mouth', label: 'Lower Lip Fullness', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'mouth/mouth-lowerlip-volume', profilePath: 'face.lowerLipFullness' },
    { id: 'mouthWidth', category: 'mouth', label: 'Mouth Breadth', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'mouth/mouth-scale-horiz', profilePath: 'face.mouthWidth' },
    { id: 'mouthPosition', category: 'mouth', label: 'Vertical Placement', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'mouth/mouth-trans:down|up', profilePath: 'face.mouthPosition' }
  ],

  ears: [
    { id: 'earSize', category: 'ears', label: 'Ear Scale', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'ears/ear-scale', profilePath: 'face.earSize' },
    { id: 'earPosition', category: 'ears', label: 'Ear Vertical Position', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'ears/ear-trans', profilePath: 'face.earPosition' },
    { id: 'earShape', category: 'ears', label: 'Ear Angle / Flappiness', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'ears/ear-rot-flapp', profilePath: 'face.earShape' },
    { id: 'earlobeVariation', category: 'ears', label: 'Earlobe Size & Attachment', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, modifierKey: 'ears/ear-lobe', profilePath: 'face.earlobeVariation' }
  ],

  hair: [
    { id: 'hairLength', category: 'hair', label: 'Hair Length Factor', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, profilePath: 'appearance.hairLength' },
    { id: 'hairVolume', category: 'hair', label: 'Hair Volume & Lift', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, profilePath: 'appearance.hairVolume' },
    { id: 'hairline', category: 'hair', label: 'Hairline Contour', min: -1, max: 1, step: 0.05, defaultValue: 0.0, bipolar: true, profilePath: 'appearance.hairline' }
  ],

  facial_hair: [
    { id: 'facialHairDensity', category: 'facial_hair', label: 'Beard Density & Stubble Trim', min: 0, max: 1, step: 0.05, defaultValue: 0.65, profilePath: 'appearance.facialHairDensity' },
    { id: 'facialHairLength', category: 'facial_hair', label: 'Beard Trim Length', min: 0, max: 1, step: 0.05, defaultValue: 0.50, profilePath: 'appearance.facialHairLength' }
  ],

  skin: [],
  clothing: [],
  accessories: [],
  expressions: []
};

// =============================================================================
// 3. VISUAL PRESET CARDS (MAPPED TO REAL 3D ASSETS & MORPHS)
// =============================================================================

export const AVATAR_PRESETS: Record<AvatarCreatorCategory, AvatarPresetDef[]> = {
  body: [
    {
      id: 'athletic',
      category: 'body',
      name: 'Athletic V-Taper',
      description: 'Sculpted shoulders, narrow waist, toned athletic build',
      badge: 'Popular',
      apply: (p) => ({
        proportions: {
          ...p.proportions,
          silhouette: 'athletic' as BodySilhouetteType,
          shoulderWidth: 0.25,
          waistWidth: -0.10,
          hipWidth: -0.05,
          muscleDefinition: 0.70
        }
      })
    },
    {
      id: 'slender',
      category: 'body',
      name: 'Slender Runway',
      description: 'Elongated silhouette, streamlined haute couture proportions',
      badge: 'Editorial',
      apply: (p) => ({
        proportions: {
          ...p.proportions,
          silhouette: 'slender' as BodySilhouetteType,
          shoulderWidth: -0.10,
          waistWidth: -0.18,
          hipWidth: -0.12,
          muscleDefinition: 0.40
        }
      })
    },
    {
      id: 'curvy',
      category: 'body',
      name: 'Curvy Hourglass',
      description: 'Defined waist with accentuated hips and feminine contours',
      apply: (p) => ({
        proportions: {
          ...p.proportions,
          silhouette: 'curvy' as BodySilhouetteType,
          shoulderWidth: -0.05,
          waistWidth: -0.15,
          hipWidth: 0.32,
          muscleDefinition: 0.45
        }
      })
    },
    {
      id: 'broad',
      category: 'body',
      name: 'Broad & Powerful',
      description: 'Expansive shoulder span and sturdy athletic posture',
      apply: (p) => ({
        proportions: {
          ...p.proportions,
          silhouette: 'broad' as BodySilhouetteType,
          shoulderWidth: 0.35,
          waistWidth: 0.05,
          hipWidth: 0.15,
          muscleDefinition: 0.80
        }
      })
    },
    {
      id: 'natural',
      category: 'body',
      name: 'Natural Balanced',
      description: 'Balanced everyday human anatomy proportions',
      apply: (p) => ({
        proportions: {
          ...p.proportions,
          silhouette: 'natural' as BodySilhouetteType,
          shoulderWidth: 0.0,
          waistWidth: 0.0,
          hipWidth: 0.0,
          muscleDefinition: 0.50
        }
      })
    }
  ],

  face: [
    {
      id: 'oval',
      category: 'face',
      name: 'Classic Oval',
      description: 'Harmonious balanced proportions with gently curved jawline',
      badge: 'Balanced',
      apply: (p) => ({
        face: {
          ...p.face,
          faceShapePreset: 'oval' as FaceShapePreset,
          faceWidth: 0.0,
          faceHeight: 0.05,
          jawWidth: -0.05,
          chinWidth: -0.05
        }
      })
    },
    {
      id: 'square',
      category: 'face',
      name: 'Sculpted Square',
      description: 'Prominent jawline, strong angular corners and wide forehead',
      badge: 'Chiseled',
      apply: (p) => ({
        face: {
          ...p.face,
          faceShapePreset: 'square' as FaceShapePreset,
          faceWidth: 0.15,
          jawWidth: 0.30,
          jawAngle: 0.25,
          chinWidth: 0.20
        }
      })
    },
    {
      id: 'round',
      category: 'face',
      name: 'Youthful Round',
      description: 'Soft curved cheeks, friendly contours and smooth jawline',
      apply: (p) => ({
        face: {
          ...p.face,
          faceShapePreset: 'round' as FaceShapePreset,
          faceWidth: 0.20,
          faceHeight: -0.10,
          cheekFullness: 0.25,
          jawWidth: 0.0
        }
      })
    },
    {
      id: 'diamond',
      category: 'face',
      name: 'High-Fashion Diamond',
      description: 'High prominent cheekbones with sculpted chin taper',
      badge: 'Editorial',
      apply: (p) => ({
        face: {
          ...p.face,
          faceShapePreset: 'diamond' as FaceShapePreset,
          cheekboneProminence: 0.35,
          jawWidth: -0.10,
          chinProjection: 0.15
        }
      })
    },
    {
      id: 'triangular',
      category: 'face',
      name: 'Inverted Triangle',
      description: 'Broader forehead tapering into a refined pointed chin',
      apply: (p) => ({
        face: {
          ...p.face,
          faceShapePreset: 'triangular' as FaceShapePreset,
          foreheadHeight: 0.15,
          jawWidth: -0.20,
          chinWidth: -0.15
        }
      })
    },
    {
      id: 'rectangular',
      category: 'face',
      name: 'Editorial Oblong',
      description: 'Distinguished vertical length with refined straight jawline',
      apply: (p) => ({
        face: {
          ...p.face,
          faceShapePreset: 'rectangular' as FaceShapePreset,
          faceHeight: 0.25,
          faceWidth: -0.05,
          jawAngle: 0.15
        }
      })
    }
  ],

  eyes: [
    {
      id: 'almond',
      category: 'eyes',
      name: 'Almond Eyes',
      description: 'Slightly upturned outer corners with balanced natural symmetry',
      badge: 'Classic',
      apply: (p) => ({
        face: {
          ...p.face,
          eyeSize: 0.05,
          eyeAngle: 0.12,
          eyelidShape: 0.0
        }
      })
    },
    {
      id: 'deepset',
      category: 'eyes',
      name: 'Deep-Set Eyes',
      description: 'Intense editorial gaze with defined brow bone prominence',
      apply: (p) => ({
        face: {
          ...p.face,
          eyeSize: 0.0,
          eyeAngle: -0.05,
          eyelidShape: 0.25
        }
      })
    },
    {
      id: 'round_eyes',
      category: 'eyes',
      name: 'Open Radiant',
      description: 'Large expressive irises with rounded open eyelids',
      apply: (p) => ({
        face: {
          ...p.face,
          eyeSize: 0.25,
          eyeAngle: 0.0,
          eyelidShape: -0.15
        }
      })
    },
    {
      id: 'monolid',
      category: 'eyes',
      name: 'Smooth Epicanthic',
      description: 'Elegant epicanthic fold with seamless sleek eyelid contour',
      apply: (p) => ({
        face: {
          ...p.face,
          eyeSize: 0.0,
          eyeAngle: 0.15,
          eyelidShape: -0.35
        }
      })
    }
  ],

  eyebrows: [
    {
      id: 'eyebrow001',
      category: 'eyebrows',
      name: 'Natural Arch',
      description: 'Softly tailored arch with balanced everyday density',
      apply: (p) => ({
        face: { ...p.face, eyebrowShapeId: 'eyebrow001' },
        appearance: { ...p.appearance, eyebrowStyleId: 'eyebrow001' }
      })
    },
    {
      id: 'eyebrow002',
      category: 'eyebrows',
      name: 'Bold Structured',
      description: 'Full masculine density with defined straight trajectory',
      badge: 'Bold',
      apply: (p) => ({
        face: { ...p.face, eyebrowShapeId: 'eyebrow002', eyebrowThickness: 0.3 },
        appearance: { ...p.appearance, eyebrowStyleId: 'eyebrow002' }
      })
    },
    {
      id: 'eyebrow003',
      category: 'eyebrows',
      name: 'Strong Runway',
      description: 'Dense dark brows designed for high contrast styling',
      apply: (p) => ({
        face: { ...p.face, eyebrowShapeId: 'eyebrow003' },
        appearance: { ...p.appearance, eyebrowStyleId: 'eyebrow003' }
      })
    },
    {
      id: 'eyebrow010',
      category: 'eyebrows',
      name: 'Sleek Editorial',
      description: 'Fine contoured arch designed for high-fashion elegance',
      badge: 'Refined',
      apply: (p) => ({
        face: { ...p.face, eyebrowShapeId: 'eyebrow010', eyebrowArch: 0.25 },
        appearance: { ...p.appearance, eyebrowStyleId: 'eyebrow010' }
      })
    },
    {
      id: 'eyebrow011',
      category: 'eyebrows',
      name: 'Feathered Delicate',
      description: 'Soft brushed-up hairs with natural tapering tail',
      apply: (p) => ({
        face: { ...p.face, eyebrowShapeId: 'eyebrow011' },
        appearance: { ...p.appearance, eyebrowStyleId: 'eyebrow011' }
      })
    },
    {
      id: 'eyebrow012',
      category: 'eyebrows',
      name: 'High Fashion Wing',
      description: 'Lifted arch creating an awake, confident editorial gaze',
      apply: (p) => ({
        face: { ...p.face, eyebrowShapeId: 'eyebrow012', eyebrowPosition: 0.15 },
        appearance: { ...p.appearance, eyebrowStyleId: 'eyebrow012' }
      })
    }
  ],

  nose: [
    {
      id: 'straight_atelier',
      category: 'nose',
      name: 'Straight Atelier',
      description: 'Clean straight bridge with refined tip symmetry',
      badge: 'Balanced',
      apply: (p) => ({
        face: {
          ...p.face,
          noseLength: 0.0,
          noseWidth: 0.0,
          noseBridgeWidth: 0.0,
          noseTipShape: 0.0
        }
      })
    },
    {
      id: 'aquiline_roman',
      category: 'nose',
      name: 'Aquiline Roman',
      description: 'Strong elevated bridge with distinguished high dorsal ridge',
      badge: 'Distinguished',
      apply: (p) => ({
        face: {
          ...p.face,
          noseLength: 0.20,
          noseBridgeWidth: 0.15,
          noseAngle: 0.25
        }
      })
    },
    {
      id: 'button_upturned',
      category: 'nose',
      name: 'Upturned Button',
      description: 'Gentle concave curve with a delicate lifted tip',
      apply: (p) => ({
        face: {
          ...p.face,
          noseLength: -0.15,
          noseTipShape: 0.10,
          noseAngle: -0.20
        }
      })
    },
    {
      id: 'wide_structured',
      category: 'nose',
      name: 'Wide Structured',
      description: 'Broad bridge with grounded natural nostril flare',
      apply: (p) => ({
        face: {
          ...p.face,
          noseWidth: 0.25,
          nostrilWidth: 0.30,
          noseBridgeWidth: 0.20
        }
      })
    },
    {
      id: 'slender_sculpted',
      category: 'nose',
      name: 'Slender Sculpted',
      description: 'Narrow bridge with crisp chiseling and compact tip',
      apply: (p) => ({
        face: {
          ...p.face,
          noseWidth: -0.20,
          nostrilWidth: -0.15,
          noseBridgeWidth: -0.25
        }
      })
    }
  ],

  mouth: [
    {
      id: 'natural_plush',
      category: 'mouth',
      name: 'Natural Plush',
      description: 'Balanced upper and lower fullness with approachable curve',
      badge: 'Popular',
      apply: (p) => ({
        face: {
          ...p.face,
          upperLipFullness: 0.10,
          lowerLipFullness: 0.15,
          mouthWidth: 0.0
        }
      })
    },
    {
      id: 'cupids_bow',
      category: 'mouth',
      name: 'Defined Cupid\'s Bow',
      description: 'Sculpted upper peaks with sharp vermilion border',
      badge: 'Editorial',
      apply: (p) => ({
        face: {
          ...p.face,
          upperLipFullness: 0.25,
          lowerLipFullness: 0.05,
          mouthWidth: -0.05
        }
      })
    },
    {
      id: 'full_volume',
      category: 'mouth',
      name: 'Full Glamour Volume',
      description: 'Generous volume on both lips with soft pillow contour',
      apply: (p) => ({
        face: {
          ...p.face,
          upperLipFullness: 0.35,
          lowerLipFullness: 0.40,
          mouthWidth: 0.08
        }
      })
    },
    {
      id: 'subtle_minimal',
      category: 'mouth',
      name: 'Subtle Minimal',
      description: 'Slim refined lips with understated natural grace',
      apply: (p) => ({
        face: {
          ...p.face,
          upperLipFullness: -0.15,
          lowerLipFullness: -0.10,
          mouthWidth: -0.05
        }
      })
    }
  ],

  ears: [
    {
      id: 'classic_ears',
      category: 'ears',
      name: 'Classic Proportions',
      description: 'Flush to head with standard anatomical lobes',
      apply: (p) => ({
        face: {
          ...p.face,
          earSize: 0.0,
          earShape: 0.0,
          earlobeVariation: 0.0
        }
      })
    },
    {
      id: 'sculpted_ears',
      category: 'ears',
      name: 'Compact Sculpted',
      description: 'Compact outline with neatly tucked upper helix',
      apply: (p) => ({
        face: {
          ...p.face,
          earSize: -0.15,
          earShape: -0.10
        }
      })
    },
    {
      id: 'piercing_studs',
      category: 'ears',
      name: 'Gold Studs Piercing',
      description: 'Luxury gold studs fitted to both earlobes',
      badge: 'Jewelry',
      apply: (p) => ({
        face: { ...p.face, piercingStyleId: 'studs' }
      })
    },
    {
      id: 'piercing_hoops',
      category: 'ears',
      name: 'Silver Hoops Piercing',
      description: 'Sleek polished silver hoop earrings',
      badge: 'Jewelry',
      apply: (p) => ({
        face: { ...p.face, piercingStyleId: 'small_hoops' }
      })
    },
    {
      id: 'piercing_none',
      category: 'ears',
      name: 'Unpierced Lobes',
      description: 'Clean earlobes without jewelry',
      apply: (p) => ({
        face: { ...p.face, piercingStyleId: 'none' }
      })
    }
  ],

  hair: [
    {
      id: 'short02',
      category: 'hair',
      name: 'Classic Side Part',
      description: 'Tailored executive taper with neat side part',
      badge: 'Timeless',
      apply: (p) => ({
        appearance: { ...p.appearance, hairStyleId: 'short02' }
      })
    },
    {
      id: 'short01',
      category: 'hair',
      name: 'Textured Crop',
      description: 'Modern forward texture with faded temple lines',
      badge: 'Modern',
      apply: (p) => ({
        appearance: { ...p.appearance, hairStyleId: 'short01' }
      })
    },
    {
      id: 'short03',
      category: 'hair',
      name: 'Modern Spikes',
      description: 'Sculpted dynamic crown with crisp silhouette',
      apply: (p) => ({
        appearance: { ...p.appearance, hairStyleId: 'short03' }
      })
    },
    {
      id: 'short04',
      category: 'hair',
      name: 'Layered Taper',
      description: 'Refined layered texture with clean neckline transition',
      apply: (p) => ({
        appearance: { ...p.appearance, hairStyleId: 'short04' }
      })
    },
    {
      id: 'bob01',
      category: 'hair',
      name: 'Sleek French Bob',
      description: 'Jaw-length razor cut with Parisian chic precision',
      badge: 'Editorial',
      apply: (p) => ({
        appearance: { ...p.appearance, hairStyleId: 'bob01' }
      })
    },
    {
      id: 'bob02',
      category: 'hair',
      name: 'Wavy Shoulder Lob',
      description: 'Soft undulating waves falling gently past the clavicle',
      apply: (p) => ({
        appearance: { ...p.appearance, hairStyleId: 'bob02' }
      })
    },
    {
      id: 'long01',
      category: 'hair',
      name: 'Cascading Waves',
      description: 'Luxurious long flowing layers with natural body',
      badge: 'Luxury',
      apply: (p) => ({
        appearance: { ...p.appearance, hairStyleId: 'long01' }
      })
    },
    {
      id: 'ponytail01',
      category: 'hair',
      name: 'High Sleek Ponytail',
      description: 'Architectural high ponytail with lifted crown tension',
      apply: (p) => ({
        appearance: { ...p.appearance, hairStyleId: 'ponytail01' }
      })
    },
    {
      id: 'afro01',
      category: 'hair',
      name: 'Natural Afro',
      description: 'Voluminous textured afro celebrating natural coils',
      badge: 'Signature',
      apply: (p) => ({
        appearance: { ...p.appearance, hairStyleId: 'afro01' }
      })
    },
    {
      id: 'braid01',
      category: 'hair',
      name: 'Crown Braided Bun',
      description: 'Intricately woven braided updo with regal atelier presence',
      apply: (p) => ({
        appearance: { ...p.appearance, hairStyleId: 'braid01' }
      })
    },
    {
      id: 'buzz',
      category: 'hair',
      name: 'Ultra Clean Buzz',
      description: 'Minimalist shaved texture hugging the cranial geometry',
      apply: (p) => ({
        appearance: { ...p.appearance, hairStyleId: 'buzz' }
      })
    },
    {
      id: 'cornrows',
      category: 'hair',
      name: 'Geometric Cornrows',
      description: 'Precision scalp braids following cranial contour lines',
      badge: 'Artisanal',
      apply: (p) => ({
        appearance: { ...p.appearance, hairStyleId: 'cornrows' }
      })
    },
    {
      id: 'box_braids',
      category: 'hair',
      name: 'Flowing Box Braids',
      description: 'Cascading individual braids draped over the shoulders',
      apply: (p) => ({
        appearance: { ...p.appearance, hairStyleId: 'box_braids' }
      })
    },
    {
      id: 'mohawk',
      category: 'hair',
      name: 'Punk Edge Mohawk',
      description: 'Bold central crest with shaved lateral temples',
      apply: (p) => ({
        appearance: { ...p.appearance, hairStyleId: 'mohawk' }
      })
    }
  ],

  facial_hair: [
    {
      id: 'none',
      category: 'facial_hair',
      name: 'Clean Shaven',
      description: 'Smooth complexion without facial hair',
      apply: (p) => ({
        appearance: { ...p.appearance, facialHairId: 'none' }
      })
    },
    {
      id: 'stubble',
      category: 'facial_hair',
      name: '5 O\'Clock Shadow',
      description: 'Subtle rugged stubble accentuating the jawline',
      badge: 'Rugged',
      apply: (p) => ({
        appearance: { ...p.appearance, facialHairId: 'stubble', facialHairDensity: 0.5 }
      })
    },
    {
      id: 'short_beard',
      category: 'facial_hair',
      name: 'Tailored Short Beard',
      description: 'Neatly groomed full beard contoured along the cheeklines',
      badge: 'Refined',
      apply: (p) => ({
        appearance: { ...p.appearance, facialHairId: 'short_beard', facialHairDensity: 0.75 }
      })
    },
    {
      id: 'full_beard',
      category: 'facial_hair',
      name: 'Full Stature Beard',
      description: 'Dense substantial beard extending down the neck',
      apply: (p) => ({
        appearance: { ...p.appearance, facialHairId: 'full_beard', facialHairDensity: 1.0 }
      })
    },
    {
      id: 'goatee',
      category: 'facial_hair',
      name: 'Sculpted Goatee',
      description: 'Crisp circle goatee framing the lips and chin',
      apply: (p) => ({
        appearance: { ...p.appearance, facialHairId: 'goatee' }
      })
    },
    {
      id: 'mustache',
      category: 'facial_hair',
      name: 'Classic Mustache',
      description: 'Traditional upper lip mustache with neat borders',
      apply: (p) => ({
        appearance: { ...p.appearance, facialHairId: 'mustache' }
      })
    }
  ],

  skin: [
    {
      id: 'porcelain',
      category: 'skin',
      name: 'Porcelain Fair',
      description: 'Luminous ivory tone with soft rose undertone',
      previewColor: '#fdf2f0',
      apply: (p) => ({
        appearance: {
          ...p.appearance,
          skinToneId: 'porcelain',
          skinToneHex: '#fdf2f0',
          skinModel: p.genderPresentation === 'feminine' ? 'young_caucasian_female' : 'young_caucasian_male',
          skinUndertone: 'cool'
        }
      })
    },
    {
      id: 'ivory',
      category: 'skin',
      name: 'Ivory Natural',
      description: 'Balanced neutral tone with radiant clarity',
      previewColor: '#fbe8d3',
      badge: 'Neutral',
      apply: (p) => ({
        appearance: {
          ...p.appearance,
          skinToneId: 'ivory',
          skinToneHex: '#fbe8d3',
          skinModel: p.genderPresentation === 'feminine' ? 'young_asian_female' : 'young_asian_male',
          skinUndertone: 'neutral'
        }
      })
    },
    {
      id: 'sand',
      category: 'skin',
      name: 'Warm Golden Sand',
      description: 'Warm golden hue inspired by Mediterranean light',
      previewColor: '#e5b894',
      badge: 'Warm',
      apply: (p) => ({
        appearance: {
          ...p.appearance,
          skinToneId: 'sand',
          skinToneHex: '#e5b894',
          skinModel: p.genderPresentation === 'feminine' ? 'young_caucasian_female2' : 'young_caucasian_male2',
          skinUndertone: 'warm'
        }
      })
    },
    {
      id: 'amber',
      category: 'skin',
      name: 'Rich Amber',
      description: 'Deep sun-kissed warmth with olive undertone',
      previewColor: '#c68642',
      badge: 'Olive',
      apply: (p) => ({
        appearance: {
          ...p.appearance,
          skinToneId: 'amber',
          skinToneHex: '#c68642',
          skinModel: p.genderPresentation === 'feminine' ? 'middleage_caucasian_female' : 'middleage_caucasian_male',
          skinUndertone: 'olive'
        }
      })
    },
    {
      id: 'bronze',
      category: 'skin',
      name: 'Luminous Bronze',
      description: 'Radiant bronze complexion with warm golden undertone',
      previewColor: '#a66838',
      apply: (p) => ({
        appearance: {
          ...p.appearance,
          skinToneId: 'bronze',
          skinToneHex: '#a66838',
          skinModel: p.genderPresentation === 'feminine' ? 'young_african_female' : 'young_african_male',
          skinUndertone: 'warm'
        }
      })
    },
    {
      id: 'almond',
      category: 'skin',
      name: 'Golden Almond',
      description: 'Deep golden brown with rich terracotta warmth',
      previewColor: '#8d5524',
      apply: (p) => ({
        appearance: {
          ...p.appearance,
          skinToneId: 'almond',
          skinToneHex: '#8d5524',
          skinModel: p.genderPresentation === 'feminine' ? 'young_african_female' : 'young_african_male',
          skinUndertone: 'warm'
        }
      })
    },
    {
      id: 'espresso',
      category: 'skin',
      name: 'Deep Espresso',
      description: 'Rich dark espresso complexion with cool undertone',
      previewColor: '#3d2314',
      badge: 'Deep',
      apply: (p) => ({
        appearance: {
          ...p.appearance,
          skinToneId: 'espresso',
          skinToneHex: '#3d2314',
          skinModel: p.genderPresentation === 'feminine' ? 'young_african_female' : 'young_african_male',
          skinUndertone: 'cool'
        }
      })
    }
  ],

  clothing: [
    {
      id: 'undress_mannequin',
      category: 'clothing',
      name: 'Bare Atelier Mannequin',
      description: 'Complete base body inspection in neutral modesty briefs',
      badge: 'Mannequin',
      apply: (p) => ({
        wardrobe: {
          ...p.wardrobe,
          isBareMannequin: true,
          outfitId: 'none',
          topId: 'none',
          bottomId: 'none',
          shoesId: 'none',
          outerwearId: 'none'
        }
      })
    },
    {
      id: 'male_elegantsuit01',
      category: 'clothing',
      name: 'Bespoke Tuxedo Suit',
      description: 'Tailored black evening suit with satin peak lapels',
      badge: 'Formal',
      apply: (p) => ({
        wardrobe: {
          ...p.wardrobe,
          isBareMannequin: false,
          outfitId: 'male_elegantsuit01',
          topId: 'none',
          bottomId: 'none',
          shoesId: 'shoes01'
        }
      })
    },
    {
      id: 'female_elegantsuit01',
      category: 'clothing',
      name: 'Haute Couture Suit',
      description: 'Feminine structured evening suit with tailored silhouette',
      badge: 'Formal',
      apply: (p) => ({
        wardrobe: {
          ...p.wardrobe,
          isBareMannequin: false,
          outfitId: 'female_elegantsuit01',
          topId: 'none',
          bottomId: 'none',
          shoesId: 'shoes02'
        }
      })
    },
    {
      id: 'streetwear_layers',
      category: 'clothing',
      name: 'Cyberpunk Techwear',
      description: 'High-tech hooded jacket with tactical modular trousers',
      badge: 'Streetwear',
      apply: (p) => ({
        wardrobe: {
          ...p.wardrobe,
          isBareMannequin: false,
          outfitId: 'none',
          topId: 'techwear_jacket',
          bottomId: 'techwear_pants',
          shoesId: 'shoes04'
        }
      })
    },
    {
      id: 'casual_tunic',
      category: 'clothing',
      name: 'Artisanal Woven Buba',
      description: 'Traditional woven tunic paired with loose sokoto trousers',
      badge: 'Heritage',
      apply: (p) => ({
        wardrobe: {
          ...p.wardrobe,
          isBareMannequin: false,
          outfitId: 'none',
          topId: 'long_tunic',
          bottomId: 'trousers',
          shoesId: 'shoes05'
        }
      })
    },
    {
      id: 'fatigue_casual',
      category: 'clothing',
      name: 'Utility Military Shirt',
      description: 'Rugged buttoned fatigue shirt with matching cargo pants',
      badge: 'Utility',
      apply: (p) => ({
        wardrobe: {
          ...p.wardrobe,
          isBareMannequin: false,
          outfitId: 'none',
          topId: 'fatigue_shirt',
          bottomId: 'cargo_shorts',
          shoesId: 'shoes03'
        }
      })
    },
    {
      id: 'female_casualsuit01',
      category: 'clothing',
      name: 'Casual Power Blazer',
      description: 'Relaxed tailored blazer with tapered ankle trousers',
      badge: 'Smart Casual',
      apply: (p) => ({
        wardrobe: {
          ...p.wardrobe,
          isBareMannequin: false,
          outfitId: p.genderPresentation === 'feminine' ? 'female_casualsuit01' : 'male_casualsuit01',
          topId: 'none',
          bottomId: 'none',
          shoesId: 'shoes05'
        }
      })
    },
    {
      id: 'female_sportsuit01',
      category: 'clothing',
      name: 'Athletic Tracksuit',
      description: 'Dynamic performance sportswear tracksuit with sleek runners',
      badge: 'Sportswear',
      apply: (p) => ({
        wardrobe: {
          ...p.wardrobe,
          isBareMannequin: false,
          outfitId: p.genderPresentation === 'feminine' ? 'female_sportsuit01' : 'male_casualsuit04',
          topId: 'none',
          bottomId: 'none',
          shoesId: 'shoes04'
        }
      })
    },
    {
      id: 'summer_linen',
      category: 'clothing',
      name: 'Summer Breeze Tank & Linen',
      description: 'Lightweight breathable tank top with relaxed trousers and sandals',
      badge: 'Summer',
      apply: (p) => ({
        wardrobe: {
          ...p.wardrobe,
          isBareMannequin: false,
          outfitId: 'none',
          topId: 'tank_top',
          bottomId: 'trousers',
          shoesId: 'sandals'
        }
      })
    },
    {
      id: 'traditional_drape',
      category: 'clothing',
      name: 'Heritage Wrapper & Tunic',
      description: 'Sleeveless woven tunic paired with a sweeping long wrapper skirt',
      badge: 'Heritage',
      apply: (p) => ({
        wardrobe: {
          ...p.wardrobe,
          isBareMannequin: false,
          outfitId: 'none',
          topId: 'tunic',
          bottomId: 'wrapper_long',
          shoesId: 'sandals'
        }
      })
    },
    {
      id: 'vintage_workwear',
      category: 'clothing',
      name: 'Denim Utility Worksuit',
      description: 'Heavyweight indigo denim workwear suit with durable oxfords',
      badge: 'Workwear',
      apply: (p) => ({
        wardrobe: {
          ...p.wardrobe,
          isBareMannequin: false,
          outfitId: 'male_worksuit01',
          topId: 'none',
          bottomId: 'none',
          shoesId: 'shoes06'
        }
      })
    }
  ],

  accessories: [
    {
      id: 'sunglasses',
      category: 'accessories',
      name: 'Dark Aviator Sunglasses',
      description: 'Chic designer sunglasses with tinted polarized lenses',
      badge: 'Eyewear',
      apply: (p) => {
        const has = p.wardrobe.sunglasses;
        return {
          wardrobe: {
            ...p.wardrobe,
            sunglasses: !has
          }
        };
      }
    },
    {
      id: 'watch',
      category: 'accessories',
      name: 'Luxury Chronograph Watch',
      description: 'Stainless steel wrist chronograph on left forearm',
      badge: 'Timepiece',
      apply: (p) => {
        const accs = p.wardrobe.accessories || [];
        const has = accs.includes('watch');
        return {
          wardrobe: {
            ...p.wardrobe,
            accessories: has ? accs.filter(a => a !== 'watch') : [...accs, 'watch']
          }
        };
      }
    },
    {
      id: 'cowrie_necklace',
      category: 'accessories',
      name: 'Cowrie-Shell Necklace',
      description: 'Natural polished cowrie shells strung along the collarbone',
      apply: (p) => {
        const accs = p.wardrobe.accessories || [];
        const has = accs.includes('cowrie_necklace');
        return {
          wardrobe: {
            ...p.wardrobe,
            accessories: has ? accs.filter(a => a !== 'cowrie_necklace') : [...accs, 'cowrie_necklace']
          }
        };
      }
    },
    {
      id: 'shoulder_drape',
      category: 'accessories',
      name: 'Royal Shuka Drape',
      description: 'Regal woven shoulder cloth draped gracefully across torso',
      badge: 'Heritage',
      apply: (p) => {
        const accs = p.wardrobe.accessories || [];
        const has = accs.includes('shoulder_drape');
        return {
          wardrobe: {
            ...p.wardrobe,
            accessories: has ? accs.filter(a => a !== 'shoulder_drape') : [...accs, 'shoulder_drape']
          }
        };
      }
    },
    {
      id: 'fila_cap',
      category: 'accessories',
      name: 'Woven Fila Cap',
      description: 'Handcrafted luxury cap folded on crown',
      apply: (p) => {
        const accs = p.wardrobe.accessories || [];
        const has = accs.includes('fila_cap');
        return {
          wardrobe: {
            ...p.wardrobe,
            accessories: has ? accs.filter(a => a !== 'fila_cap') : [...accs, 'fila_cap']
          }
        };
      }
    },
    {
      id: 'beret',
      category: 'accessories',
      name: 'Atelier French Beret',
      description: 'Classic wool beret tilted at an elegant angle',
      apply: (p) => {
        const accs = p.wardrobe.accessories || [];
        const has = accs.includes('beret');
        return {
          wardrobe: {
            ...p.wardrobe,
            accessories: has ? accs.filter(a => a !== 'beret') : [...accs, 'beret']
          }
        };
      }
    }
  ],

  expressions: [
    {
      id: 'neutral',
      category: 'expressions',
      name: 'Relaxed Atelier',
      description: 'Poised editorial confidence with soft relaxed mouth',
      badge: 'Default',
      apply: (p) => ({
        face: { ...p.face, restingExpression: 'neutral' }
      })
    },
    {
      id: 'happy',
      category: 'expressions',
      name: 'Approachable Smile',
      description: 'Warm friendly smile with genuine eye crinkling',
      badge: 'Friendly',
      apply: (p) => ({
        face: { ...p.face, restingExpression: 'happy' }
      })
    },
    {
      id: 'laughing',
      category: 'expressions',
      name: 'Radiant Joy',
      description: 'Full open laugh radiating vibrant charm',
      apply: (p) => ({
        face: { ...p.face, restingExpression: 'laughing' }
      })
    },
    {
      id: 'determined',
      category: 'expressions',
      name: 'Runway Focus',
      description: 'Focused intense editorial gaze with sculpted brow tension',
      badge: 'Runway',
      apply: (p) => ({
        face: { ...p.face, restingExpression: 'determined' }
      })
    },
    {
      id: 'thinking',
      category: 'expressions',
      name: 'Thoughtful Contemplation',
      description: 'Slightly raised brow with reflective fashion consideration',
      apply: (p) => ({
        face: { ...p.face, restingExpression: 'surprised' }
      })
    },
    {
      id: 'surprised',
      category: 'expressions',
      name: 'Delighted Surprise',
      description: 'Wide expressive eyes celebrating a stunning new outfit',
      apply: (p) => ({
        face: { ...p.face, restingExpression: 'surprised' }
      })
    }
  ]
};

// =============================================================================
// 4. COLOR PALETTES (HAIR, EYES, LIPS, MAKEUP, ACCENTS)
// =============================================================================

export const HAIR_COLOR_SWATCHES: AvatarColorSwatch[] = [
  { id: 'jetblack', name: 'Jet Black', hex: '#111010', group: 'dark' },
  { id: 'espresso', name: 'Dark Espresso', hex: '#261b14', group: 'dark' },
  { id: 'chestnut', name: 'Warm Chestnut', hex: '#4d3221', group: 'brown' },
  { id: 'chocolate', name: 'Milk Chocolate', hex: '#63432b', group: 'brown' },
  { id: 'auburn', name: 'Auburn Copper', hex: '#873a1d', group: 'red' },
  { id: 'burgundy', name: 'Burgundy Wine', hex: '#4f1422', group: 'red' },
  { id: 'honey_blonde', name: 'Honey Blonde', hex: '#d6b372', group: 'blonde' },
  { id: 'platinum', name: 'Platinum Silver', hex: '#cbd5e1', group: 'blonde' },
  { id: 'charcoal', name: 'Charcoal Ash', hex: '#4b5563', group: 'grey' },
  { id: 'cobalt', name: 'Electric Cobalt', hex: '#1e40af', group: 'vibrant' },
  { id: 'amethyst', name: 'Soft Lavender', hex: '#a855f7', group: 'vibrant' },
  { id: 'emerald', name: 'Deep Emerald', hex: '#065f46', group: 'vibrant' }
];

export const EYE_COLOR_SWATCHES: AvatarColorSwatch[] = [
  { id: 'brownlight', name: 'Warm Hazel', hex: '#6b4423' },
  { id: 'brown', name: 'Deep Amber Brown', hex: '#3d2514' },
  { id: 'blue', name: 'Sapphire Blue', hex: '#1e3a8a' },
  { id: 'deepblue', name: 'Ocean Midnight', hex: '#172554' },
  { id: 'bluegreen', name: 'Marine Teal', hex: '#0f766e' },
  { id: 'green', name: 'Emerald Green', hex: '#15803d' },
  { id: 'grey', name: 'Nordic Slate', hex: '#64748b' },
  { id: 'ice', name: 'Arctic Ice', hex: '#38bdf8' },
  { id: 'lightblue', name: 'Sky Cerulean', hex: '#60a5fa' }
];

export const LIP_COLOR_SWATCHES: AvatarColorSwatch[] = [
  { id: 'nude_natural', name: 'Nude Natural', hex: '#d48b76' },
  { id: 'rose_petal', name: 'Rose Petal', hex: '#c06b7a' },
  { id: 'warm_terracotta', name: 'Warm Terracotta', hex: '#b35446' },
  { id: 'classic_red', name: 'Runway Red', hex: '#9e1b24' },
  { id: 'deep_berry', name: 'Deep Berry', hex: '#6a1d3a' },
  { id: 'plum_wine', name: 'Plum Noir', hex: '#421b2d' },
  { id: 'caramel_gloss', name: 'Caramel Honey', hex: '#b06f47' },
  { id: 'soft_coral', name: 'Soft Coral', hex: '#e07a68' }
];

export const CLOTHING_COLOR_SWATCHES: AvatarColorSwatch[] = [
  { id: 'cloth_midnight', name: 'Midnight Onyx', hex: '#0f172a' },
  { id: 'cloth_ivory', name: 'Ivory White', hex: '#f8fafc' },
  { id: 'cloth_charcoal', name: 'Refined Charcoal', hex: '#334155' },
  { id: 'cloth_navy', name: 'Deep Navy', hex: '#1e3a8a' },
  { id: 'cloth_crimson', name: 'Royal Crimson', hex: '#881337' },
  { id: 'cloth_emerald', name: 'Forest Emerald', hex: '#064e3b' },
  { id: 'cloth_camel', name: 'Camel Tan', hex: '#b45309' },
  { id: 'cloth_sage', name: 'Sage Green', hex: '#4d7c0f' },
  { id: 'cloth_terracotta', name: 'Terracotta', hex: '#9a3412' },
  { id: 'cloth_gold', name: 'Atelier Gold', hex: '#ca8a04' }
];
