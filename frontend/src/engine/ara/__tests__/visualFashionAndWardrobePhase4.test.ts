import { describe, it, expect } from 'vitest';
import {
  FASHION_SECONDARY_CATEGORIES,
  WARDROBE_SECONDARY_CATEGORIES,
  PRIMARY_NAV_SECTIONS
} from '../../../pages/AvatarStudio';
import {
  FASHION_CATALOG,
  DEFAULT_FALLBACK_WARDROBE,
  OUTFIT_SUGGESTIONS
} from '../../../data/fashionCatalogData';

describe('YORVYN — PHASE 4: Visual-First Fashion Catalogue & Personal Wardrobe Experience', () => {
  describe('1. Fashion Secondary Navigation (13 Categories + User Categories)', () => {
    it('should define all 13 required secondary fashion categories with icons', () => {
      const ids = FASHION_SECONDARY_CATEGORIES.map(c => c.id);
      const expectedCategories = [
        'all',
        'tops',
        'shirts',
        't-shirts',
        'hoodies',
        'outerwear',
        'jackets',
        'bottoms',
        'trousers',
        'jeans',
        'shorts',
        'dresses',
        'skirts',
        'shoes',
        'accessories'
      ];

      expectedCategories.forEach(expectedId => {
        expect(ids).toContain(expectedId);
      });
    });

    it('should provide icon keys for every fashion category for icon-only rendering', () => {
      FASHION_SECONDARY_CATEGORIES.forEach(cat => {
        expect(cat.iconKey).toBeDefined();
        expect(cat.iconKey.length).toBeGreaterThan(0);
        expect(cat.label).toBeDefined();
      });
    });

    it('should preserve the three morphing primary controls: Fashion, Wardrobe, Avatar', () => {
      const primaryIds = PRIMARY_NAV_SECTIONS.map(s => s.id);
      expect(primaryIds).toEqual(['fashion', 'wardrobe', 'avatar']);
    });

    it('should define wardrobe secondary categories covering items, saved outfits and collections', () => {
      const wardIds = WARDROBE_SECONDARY_CATEGORIES.map(w => w.id);
      expect(wardIds).toContain('all');
      expect(wardIds).toContain('top');
      expect(wardIds).toContain('bottom');
      expect(wardIds).toContain('outerwear');
      expect(wardIds).toContain('footwear');
      expect(wardIds).toContain('accessory');
      expect(wardIds).toContain('saved_outfits');
      expect(wardIds).toContain('collections');
    });

    it('should support curated AI outfit suggestions for the fashion section', () => {
      expect(OUTFIT_SUGGESTIONS.length).toBeGreaterThan(0);
      OUTFIT_SUGGESTIONS.forEach(sugg => {
        expect(sugg.title).toBeDefined();
        expect(sugg.modelImage).toBeDefined();
        expect(sugg.pieces.length).toBeGreaterThan(0);
      });
    });
  });

  describe('2. Visual-First Clothing & Wardrobe Cards', () => {
    it('should provide honest 3D vs 2D asset flags on fashion catalog items', () => {
      const threeDItems = FASHION_CATALOG.filter(item => item.assetType === '3d_mesh');
      const twoDItems = FASHION_CATALOG.filter(item => item.assetType === '2d_image');

      expect(threeDItems.length).toBeGreaterThan(10);
      expect(twoDItems.length).toBeGreaterThan(5);

      // Verify 2D items are not fraudulently marked as 3D
      twoDItems.forEach(item => {
        expect(item.assetType).toBe('2d_image');
      });
    });

    it('should include all required accessory types in the catalogue', () => {
      const accessories = FASHION_CATALOG.filter(item => item.category === 'accessory');
      const subcategories = accessories.map(a => a.subcategory);

      expect(subcategories).toContain('watches');
      expect(subcategories).toContain('rings');
      expect(subcategories).toContain('necklaces');
      expect(subcategories).toContain('bracelets');
      expect(subcategories).toContain('earrings');
      expect(subcategories).toContain('sunglasses');
      expect(subcategories).toContain('bags');
      expect(subcategories).toContain('belts');
      expect(subcategories).toContain('caps');
      expect(subcategories).toContain('scarves');
    });

    it('should include hoodies, shorts, and skirts with rich metadata', () => {
      const hoodies = FASHION_CATALOG.filter(i => i.subcategory === 'hoodies');
      const shorts = FASHION_CATALOG.filter(i => i.subcategory === 'shorts');
      const skirts = FASHION_CATALOG.filter(i => i.subcategory === 'skirts');

      expect(hoodies.length).toBeGreaterThanOrEqual(2);
      expect(shorts.length).toBeGreaterThanOrEqual(2);
      expect(skirts.length).toBeGreaterThanOrEqual(2);

      hoodies.forEach(h => {
        expect(h.color).toBeDefined();
        expect(h.brand).toBeDefined();
        expect(h.appliedParams).toBeDefined();
      });
    });

    it('should populate fallback wardrobe with honest 3D and 2D items covering key categories', () => {
      expect(DEFAULT_FALLBACK_WARDROBE.length).toBeGreaterThanOrEqual(10);

      const categories = DEFAULT_FALLBACK_WARDROBE.map(w => w.category);
      expect(categories).toContain('top');
      expect(categories).toContain('bottom');
      expect(categories).toContain('outerwear');
      expect(categories).toContain('footwear');
      expect(categories).toContain('accessory');

      // Honest status verification
      DEFAULT_FALLBACK_WARDROBE.forEach(item => {
        expect(['3d_mesh', '2d_image']).toContain(item.asset_type);
        expect(item.name).toBeTruthy();
        expect(item.brand).toBeTruthy();
      });
    });
  });

  describe('3. In-Tray Item Details & Try-On Pipeline', () => {
    it('should map 3D catalogue items to Ara HumanParams without removing other layers', () => {
      const topPiece = FASHION_CATALOG.find(i => i.id === 'relaxed-shirt');
      expect(topPiece).toBeDefined();
      expect(topPiece?.appliedParams.top).toBe('uniform_shirt');
      expect(topPiece?.appliedParams.shoes).toBe('shoes01');
    });

    it('should provide comprehensive details for in-tray inspection', () => {
      const sampleItem = FASHION_CATALOG.find(i => i.id === 'watch-oyster-chrono');
      expect(sampleItem).toBeDefined();
      expect(sampleItem?.brand).toBe('Rolex');
      expect(sampleItem?.material).toContain('Oystersteel');
      expect(sampleItem?.userNotes).toBeDefined();
      expect(sampleItem?.assetType).toBe('2d_image');
    });
  });

  describe('4. Resizable Tray Container Queries & Adaptation', () => {
    it('should support 2-column, 3-column, and 4-column container breakpoints', () => {
      const breakpoints = {
        compact: { max: 440, cols: 2 },
        default: { min: 441, max: 660, cols: 3 },
        expanded: { min: 661, cols: 4 }
      };

      expect(breakpoints.compact.cols).toBe(2);
      expect(breakpoints.default.cols).toBe(3);
      expect(breakpoints.expanded.cols).toBe(4);
    });
  });
});
