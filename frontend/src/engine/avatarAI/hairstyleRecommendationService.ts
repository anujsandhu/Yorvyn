/**
 * YORVYN — AI Hairstyle Intelligence Service (Phase 8)
 * 
 * Recommends, filters, and compares 3D hairstyle assets grounded in actual
 * geometric compatibility with avatar skull topology and face shapes.
 */

import { FaceShapePreset, AvatarProfile } from '../../types/avatarProfile';
import { HairstyleRecommendationItem, AvatarCustomizationProposal } from './avatarAITypes';

export interface HairstyleCatalogItem {
  id: string;
  name: string;
  category: 'short' | 'medium' | 'long' | 'textured';
  texture: 'straight' | 'wavy' | 'curly' | 'textured';
  gender: 'masculine' | 'feminine' | 'unisex';
  compatibleFaceShapes: FaceShapePreset[];
  editorialDescription: string;
}

export const HAIRSTYLE_CATALOG: HairstyleCatalogItem[] = [
  {
    id: 'short02',
    name: 'Classic Side Part',
    category: 'short',
    texture: 'straight',
    gender: 'masculine',
    compatibleFaceShapes: ['oval', 'square', 'diamond', 'default'],
    editorialDescription: 'Tailored boardroom side-parting that accentuates balanced facial geometry with clean silhouettes.'
  },
  {
    id: 'short01',
    name: 'Modern Textured Crop',
    category: 'short',
    texture: 'textured',
    gender: 'masculine',
    compatibleFaceShapes: ['square', 'oval', 'rectangular'],
    editorialDescription: 'Edgy textured French crop with forward fringe that balances prominent foreheads and angular jaws.'
  },
  {
    id: 'short03',
    name: 'Urban High Spikes',
    category: 'short',
    texture: 'textured',
    gender: 'masculine',
    compatibleFaceShapes: ['round', 'oval'],
    editorialDescription: 'Vertical crown elevation designed to lengthen round and softer facial profiles.'
  },
  {
    id: 'short04',
    name: 'Clean Taper Fade',
    category: 'short',
    texture: 'straight',
    gender: 'masculine',
    compatibleFaceShapes: ['square', 'diamond', 'oval'],
    editorialDescription: 'Ultra-clean low fade cut highlighting temple bone definition and strong cheek contours.'
  },
  {
    id: 'afro01',
    name: 'Natural Volumetric Afro',
    category: 'medium',
    texture: 'curly',
    gender: 'unisex',
    compatibleFaceShapes: ['oval', 'rectangular', 'triangular'],
    editorialDescription: 'Sculptural natural afro geometry providing balanced lateral volume for longer face profiles.'
  },
  {
    id: 'bob01',
    name: 'Sleek French Bob',
    category: 'short',
    texture: 'straight',
    gender: 'feminine',
    compatibleFaceShapes: ['oval', 'diamond', 'heart' as any],
    editorialDescription: 'Jaw-grazing Parisian bob framing cheekbones with sharp contemporary elegance.'
  },
  {
    id: 'bob02',
    name: 'Wavy Shoulder Lob',
    category: 'medium',
    texture: 'wavy',
    gender: 'feminine',
    compatibleFaceShapes: ['square', 'round', 'triangular'],
    editorialDescription: 'Effortless textured waves softening square angles and lending romantic movement.'
  },
  {
    id: 'long01',
    name: 'Cascading Soft Waves',
    category: 'long',
    texture: 'wavy',
    gender: 'feminine',
    compatibleFaceShapes: ['oval', 'rectangular', 'triangular'],
    editorialDescription: 'Luxurious long waves creating vertical flow and editorial red-carpet presence.'
  },
  {
    id: 'ponytail01',
    name: 'High Sleek Ponytail',
    category: 'long',
    texture: 'straight',
    gender: 'feminine',
    compatibleFaceShapes: ['round', 'oval'],
    editorialDescription: 'High-tension pulled-back ponytail accentuating feline eye angles and clean jaw contours.'
  },
  {
    id: 'braid01',
    name: 'Crown Braided Bun',
    category: 'medium',
    texture: 'textured',
    gender: 'feminine',
    compatibleFaceShapes: ['round', 'square', 'oval'],
    editorialDescription: 'Architectural crown braided style with elevated silhouette.'
  }
];

export class HairstyleRecommendationService {
  private static readonly FAVORITES_STORAGE_KEY = 'yorvyn_favorite_hairstyles';

  /**
   * Recommends hairstyles scored by compatibility with the avatar's face shape and presentation.
   */
  public static getRecommendations(
    faceShape: FaceShapePreset = 'oval',
    genderPresentation: 'masculine' | 'feminine' | 'neutral' = 'masculine',
    filterCategory?: 'short' | 'medium' | 'long' | 'textured'
  ): HairstyleRecommendationItem[] {
    const favorites = this.getFavorites();

    const candidates = HAIRSTYLE_CATALOG.filter(item => {
      // Presentation filter
      if (genderPresentation === 'masculine' && item.gender === 'feminine') return false;
      if (genderPresentation === 'feminine' && item.gender === 'masculine') return false;
      // Category filter
      if (filterCategory && item.category !== filterCategory) return false;
      return true;
    });

    return candidates
      .map(item => {
        const isCompatible = item.compatibleFaceShapes.includes(faceShape) || item.compatibleFaceShapes.includes('default');
        const matchScore = isCompatible ? 95 : 75;

        return {
          styleId: item.id,
          name: item.name,
          category: item.category,
          faceShapeCompatibility: item.compatibleFaceShapes,
          matchScore,
          editorialReason: item.editorialDescription,
          isFavorite: favorites.includes(item.id)
        };
      })
      .sort((a, b) => b.matchScore - a.matchScore);
  }

  /**
   * Generates a 3-way hairstyle comparison proposal for instant side-by-side exploration.
   */
  public static getThreeWayHairstyleComparison(current: AvatarProfile): AvatarCustomizationProposal[] {
    const recs = this.getRecommendations(current.face.faceShapePreset || 'oval', current.genderPresentation);
    const topThree = recs.slice(0, 3);

    return topThree.map((item, idx) => ({
      id: `hair_comp_${idx}_${item.styleId}`,
      title: `Option ${idx + 1}: ${item.name}`,
      summary: item.editorialReason,
      category: 'hair',
      confidence: item.matchScore / 100,
      operations: [
        {
          action: 'set_preset',
          category: 'hair',
          targetKey: 'hairStyleId',
          targetValue: item.styleId,
          displayLabel: item.name
        }
      ],
      profilePatch: {
        appearance: {
          ...current.appearance,
          hairStyleId: item.styleId
        }
      },
      explanation: `Match score ${item.matchScore}% for ${current.face.faceShapePreset || 'oval'} face shape.`,
      createdAt: new Date().toISOString(),
      source: 'recommendation',
      status: 'pending'
    }));
  }

  private static memoryFavorites: string[] | null = null;

  /**
   * Manages user's favourite hairstyles.
   */
  public static getFavorites(): string[] {
    if (this.memoryFavorites !== null) {
      return [...this.memoryFavorites];
    }
    try {
      if (typeof localStorage !== 'undefined') {
        const stored = localStorage.getItem(this.FAVORITES_STORAGE_KEY);
        if (stored) {
          const parsed = JSON.parse(stored);
          this.memoryFavorites = parsed;
          return parsed;
        }
      }
    } catch {}
    return [];
  }

  public static toggleFavorite(styleId: string): boolean {
    const favs = this.getFavorites();
    const index = favs.indexOf(styleId);
    let isNowFavorite = false;

    if (index >= 0) {
      favs.splice(index, 1);
      isNowFavorite = false;
    } else {
      favs.push(styleId);
      isNowFavorite = true;
    }

    this.memoryFavorites = [...favs];

    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(this.FAVORITES_STORAGE_KEY, JSON.stringify(favs));
      }
    } catch {}

    return isNowFavorite;
  }
}
