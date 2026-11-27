/**
 * YORVYN — PHASE 7: AI-Assisted Personalization Future-Ready Interface
 * 
 * Provides strongly typed contracts and architectural stubs for:
 * 1. Photo-to-Avatar Suggestion Engine (Reference photo -> MakeHuman parameters)
 * 2. Face-Shape Hair & Beard Recommendation Matrix
 * 3. Color Season & Contrast Accessory Matcher
 * 4. Conversational Natural Language Avatar Stylist
 * 
 * NOTE: Architecture is strictly decoupled from core geometry rendering.
 * Stubs return structured mock recommendations or pass through until remote
 * vision/LLM models are deployed.
 */

import { AvatarProfile, FaceShapePreset } from '../../types/avatarProfile';
import { AvatarCreatorCategory } from './avatarCreatorTypes';

export interface PhotoAnalysisRequest {
  imageFileOrBase64: string;
  userGenderHint?: 'masculine' | 'feminine' | 'neutral';
}

export interface PhotoAnalysisResponse {
  detectedFaceShape: FaceShapePreset;
  estimatedSkinToneHex: string;
  recommendedSkinModel: string;
  detectedEyeColorHex: string;
  suggestedHairstyleId: string;
  detectedFacialHairId?: string;
  confidenceScore: number; // 0.0 to 1.0
  suggestedProfileModifiers: Record<string, number>;
}

export interface HairstyleRecommendation {
  hairstyleId: string;
  name: string;
  faceShapeCompatibility: FaceShapePreset[];
  fashionEditorialReason: string;
  score: number; // 0.0 to 1.0
}

export interface ColorSeasonPalette {
  seasonName: 'Warm Autumn' | 'Cool Winter' | 'Fresh Spring' | 'Soft Summer';
  recommendedPaletteHexes: string[];
  recommendedMetal: 'gold' | 'silver' | 'rose_gold';
  recommendedGarmentPatterns: string[];
}

export interface ConversationalCustomizationIntent {
  rawPrompt: string;
  targetCategory?: AvatarCreatorCategory;
  parameterChanges: Partial<AvatarProfile>;
  confidence: number;
  explanation: string;
}

export interface IAIPersonalizationService {
  /**
   * Analyzes an uploaded selfie or reference photo to generate avatar profile suggestions.
   */
  analyzeReferencePhoto(request: PhotoAnalysisRequest): Promise<PhotoAnalysisResponse>;

  /**
   * Recommends hairstyles optimized for the avatar's current face shape.
   */
  recommendHairstyles(faceShape: FaceShapePreset): Promise<HairstyleRecommendation[]>;

  /**
   * Analyzes skin tone & eye color to determine seasonal color palette & accessories.
   */
  determineColorSeason(skinHex: string, eyeColorId: string): Promise<ColorSeasonPalette>;

  /**
   * Parses natural language styling prompt (e.g. "make my jaw more chiseled and give me a taper fade")
   */
  interpretNaturalLanguageStyling(prompt: string, current: AvatarProfile): Promise<ConversationalCustomizationIntent>;
}

/**
 * Concrete client implementation with offline fallback heuristics.
 */
export class AIPersonalizationService implements IAIPersonalizationService {
  async analyzeReferencePhoto(request: PhotoAnalysisRequest): Promise<PhotoAnalysisResponse> {
    // Heuristic baseline until remote vision endpoint is hooked up
    const isMasc = request.userGenderHint !== 'feminine';
    return {
      detectedFaceShape: 'oval',
      estimatedSkinToneHex: '#f3c299',
      recommendedSkinModel: isMasc ? 'young_caucasian_male' : 'young_caucasian_female',
      detectedEyeColorHex: '#452b1b',
      suggestedHairstyleId: isMasc ? 'short02' : 'bob01',
      detectedFacialHairId: isMasc ? 'stubble' : 'none',
      confidenceScore: 0.88,
      suggestedProfileModifiers: {
        'head/head-scale-horiz': 0.02,
        'chin/jaw-width': 0.05,
        'nose/nose-scale-vert': 0.0
      }
    };
  }

  async recommendHairstyles(faceShape: FaceShapePreset): Promise<HairstyleRecommendation[]> {
    const recommendations: Record<FaceShapePreset, HairstyleRecommendation[]> = {
      oval: [
        { hairstyleId: 'short02', name: 'Classic Side Part', faceShapeCompatibility: ['oval', 'square'], fashionEditorialReason: 'Accentuates balanced oval symmetry with clean side silhouette.', score: 0.98 },
        { hairstyleId: 'bob01', name: 'Sleek French Bob', faceShapeCompatibility: ['oval', 'diamond'], fashionEditorialReason: 'Highlights cheekbones without shortening facial height.', score: 0.94 },
        { hairstyleId: 'long01', name: 'Cascading Waves', faceShapeCompatibility: ['oval', 'rectangular'], fashionEditorialReason: 'Adds movement and softness to natural facial proportions.', score: 0.92 }
      ],
      square: [
        { hairstyleId: 'short04', name: 'Layered Taper', faceShapeCompatibility: ['square'], fashionEditorialReason: 'Softens strong angular jawline with textured height.', score: 0.96 },
        { hairstyleId: 'bob02', name: 'Wavy Shoulder Lob', faceShapeCompatibility: ['square', 'round'], fashionEditorialReason: 'Curves break up geometric jaw corners.', score: 0.93 },
        { hairstyleId: 'short01', name: 'Textured Crop', faceShapeCompatibility: ['square'], fashionEditorialReason: 'Complements sharp masculine bone structure.', score: 0.90 }
      ],
      round: [
        { hairstyleId: 'short03', name: 'Modern Spikes', faceShapeCompatibility: ['round'], fashionEditorialReason: 'Adds vertical crown height to lengthen facial profile.', score: 0.97 },
        { hairstyleId: 'ponytail01', name: 'High Sleek Ponytail', faceShapeCompatibility: ['round', 'oval'], fashionEditorialReason: 'Draws eye upwards, slimming the cheek contour.', score: 0.95 },
        { hairstyleId: 'braid01', name: 'Crown Braided Bun', faceShapeCompatibility: ['round'], fashionEditorialReason: 'Vertical architectural balance.', score: 0.91 }
      ],
      diamond: [
        { hairstyleId: 'bob01', name: 'Sleek French Bob', faceShapeCompatibility: ['diamond', 'oval'], fashionEditorialReason: 'Frames cheekbones beautifully with chin-length fullness.', score: 0.98 },
        { hairstyleId: 'short02', name: 'Classic Side Part', faceShapeCompatibility: ['diamond'], fashionEditorialReason: 'Balances temple width with chiseled jaw.', score: 0.94 }
      ],
      triangular: [
        { hairstyleId: 'long01', name: 'Cascading Waves', faceShapeCompatibility: ['triangular'], fashionEditorialReason: 'Wide lower curls balance narrow chin.', score: 0.95 },
        { hairstyleId: 'bob02', name: 'Wavy Shoulder Lob', faceShapeCompatibility: ['triangular'], fashionEditorialReason: 'Softens pointed chin geometry.', score: 0.92 }
      ],
      rectangular: [
        { hairstyleId: 'short01', name: 'Textured Crop', faceShapeCompatibility: ['rectangular'], fashionEditorialReason: 'Horizontal texture minimizes vertical elongation.', score: 0.94 },
        { hairstyleId: 'afro01', name: 'Natural Afro', faceShapeCompatibility: ['rectangular', 'oval'], fashionEditorialReason: 'Volumetric lateral expansion balances long proportions.', score: 0.96 }
      ],
      invertedtriangular: [
        { hairstyleId: 'bob02', name: 'Wavy Shoulder Lob', faceShapeCompatibility: ['invertedtriangular'], fashionEditorialReason: 'Provides fullness around jaw and neck.', score: 0.95 }
      ],
      default: [
        { hairstyleId: 'short02', name: 'Classic Side Part', faceShapeCompatibility: ['oval', 'square'], fashionEditorialReason: 'Universally flattering atelier cut.', score: 0.90 }
      ]
    };

    return recommendations[faceShape] || recommendations.default;
  }

  async determineColorSeason(skinHex: string, eyeColorId: string): Promise<ColorSeasonPalette> {
    // Determine warm vs cool based on skin hex warmth
    const isWarm = skinHex.includes('e') || skinHex.includes('c') || eyeColorId.includes('brown');

    if (isWarm) {
      return {
        seasonName: 'Warm Autumn',
        recommendedPaletteHexes: ['#873a1d', '#d6b372', '#503525', '#15803d', '#3f6b5a'],
        recommendedMetal: 'gold',
        recommendedGarmentPatterns: ['asooke', 'khaki', 'leather']
      };
    } else {
      return {
        seasonName: 'Cool Winter',
        recommendedPaletteHexes: ['#1e3a8a', '#4a1525', '#111010', '#cbd5e1', '#00e5ff'],
        recommendedMetal: 'silver',
        recommendedGarmentPatterns: ['techwear', 'solid', 'camo']
      };
    }
  }

  async interpretNaturalLanguageStyling(prompt: string, current: AvatarProfile): Promise<ConversationalCustomizationIntent> {
    const lower = prompt.toLowerCase();
    const changes: Partial<AvatarProfile> = {};

    if (lower.includes('chiseled') || lower.includes('jaw')) {
      changes.face = {
        ...current.face,
        jawWidth: 0.25,
        jawAngle: 0.20,
        chinProjection: 0.15
      };
      return {
        rawPrompt: prompt,
        targetCategory: 'face',
        parameterChanges: changes,
        confidence: 0.92,
        explanation: 'Sculpted jaw width and elevated chin projection for a chiseled jawline.'
      };
    }

    if (lower.includes('smile') || lower.includes('happy')) {
      changes.face = {
        ...current.face,
        restingExpression: 'happy'
      };
      return {
        rawPrompt: prompt,
        targetCategory: 'expressions',
        parameterChanges: changes,
        confidence: 0.95,
        explanation: 'Applied approachable friendly smile expression.'
      };
    }

    if (lower.includes('shave') || lower.includes('clean shaven')) {
      changes.appearance = {
        ...current.appearance,
        facialHairId: 'none'
      };
      return {
        rawPrompt: prompt,
        targetCategory: 'facial_hair',
        parameterChanges: changes,
        confidence: 0.96,
        explanation: 'Switched facial hair to clean shaven.'
      };
    }

    return {
      rawPrompt: prompt,
      parameterChanges: {},
      confidence: 0.50,
      explanation: 'Prompt received. AI conversational assistant is ready for full LLM connection.'
    };
  }
}

export const aiPersonalizationService = new AIPersonalizationService();

