/**
 * YORVYN — PHASE 8: AI Avatar Intelligence & Personalization Engine Types
 * 
 * Provides strongly-typed data contracts for:
 * 1. Conversational intent parsing and command execution
 * 2. Proposal generation, multi-option alternatives, and verification
 * 3. Privacy-conscious reference photo analysis and consent
 * 4. Hairstyle recommendation and face-shape matrix
 * 5. Preview orchestration and before/after comparison
 */

import { AvatarProfile, FaceShapePreset, BodySilhouetteType } from '../../types/avatarProfile';
import { AvatarCreatorCategory } from '../avatarCreator/avatarCreatorTypes';

export type AvatarCommandAction = 
  | 'set_slider'
  | 'set_preset'
  | 'set_color'
  | 'set_garment'
  | 'set_expression'
  | 'composite';

export interface AvatarCommandOperation {
  action: AvatarCommandAction;
  category: AvatarCreatorCategory;
  targetKey: string;      // e.g. 'jawWidth', 'proportions.shoulderWidth', 'appearance.hairStyleId'
  targetValue: any;       // e.g. 0.35, 'short02', '#1e3a8a'
  displayLabel: string;   // e.g. 'Broaden shoulders (+35%)'
  previousValue?: any;
}

export type ProposalStatus = 'pending' | 'previewing' | 'accepted' | 'rejected' | 'modified';

export interface AvatarCustomizationProposal {
  id: string;
  title: string;
  summary: string;
  category: AvatarCreatorCategory;
  confidence: number; // 0.0 - 1.0
  operations: AvatarCommandOperation[];
  profilePatch: Partial<AvatarProfile>;
  explanation: string;
  createdAt: string;
  source: 'conversational' | 'photo_analysis' | 'recommendation' | 'occasion';
  status: ProposalStatus;
  alternatives?: AvatarCustomizationProposal[];
}

export interface UserPhotoConsent {
  hasConsented: boolean;
  consentTimestamp: string;
  privacyPolicyVersion: string;
  acceptedTerms: string[];
}

export interface PhotoDetectedTraits {
  faceShape: {
    value: FaceShapePreset;
    confidence: number;
    description: string;
  };
  skinTone: {
    hex: string;
    undertone: 'warm' | 'cool' | 'neutral';
    confidence: number;
    description: string;
  };
  hair: {
    styleId: string;
    styleName: string;
    colorHex: string;
    length: 'short' | 'medium' | 'long';
    confidence: number;
  };
  facialHair: {
    styleId: string;
    styleName: string;
    confidence: number;
  };
  proportions: {
    estimatedSilhouette: BodySilhouetteType;
    confidence: number;
    disclaimer: string;
  };
}

export interface PhotoAnalysisResult {
  detectedTraits: PhotoDetectedTraits;
  privacyNotice: string;
  retentionPolicy: string;
  generatedProposal: AvatarCustomizationProposal;
}

export interface HairstyleRecommendationItem {
  styleId: string;
  name: string;
  category: 'short' | 'medium' | 'long' | 'textured';
  faceShapeCompatibility: FaceShapePreset[];
  matchScore: number; // 0 to 100
  editorialReason: string;
  isFavorite?: boolean;
}

export interface OccasionStylingProposal {
  occasionId: string;
  occasionTitle: string;
  weatherContext?: string;
  paletteName: string;
  paletteHexes: string[];
  recommendedOutfit: {
    outfitId?: string;
    topId?: string;
    bottomId?: string;
    shoesId?: string;
    name: string;
    editorialReason: string;
  };
  recommendedHairstyleId?: string;
  recommendedExpression?: string;
}

export interface AIMessage {
  id: string;
  sender: 'user' | 'assistant' | 'system';
  text: string;
  timestamp: string;
  proposal?: AvatarCustomizationProposal;
  quickActions?: string[];
}

