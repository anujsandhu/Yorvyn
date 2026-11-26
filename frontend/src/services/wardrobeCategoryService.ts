/**
 * Wardrobe Category Persistence Service — Yorvyn
 * 
 * Provides customizable category hierarchy, user-controlled order, custom icon handling,
 * and single-screen category management for clothing, accessories, watches, jewelry,
 * perfumes, cosmetics, gadgets, and collectibles.
 */

import { WardrobeCategory } from '../types/fashion';

export const DEFAULT_WARDROBE_CATEGORIES: WardrobeCategory[] = [
  {
    id: 'all',
    label: 'All',
    itemType: 'clothing',
    iconType: 'preset',
    iconKey: 'SquaresFour',
    isDefault: true,
    isVisible: true,
    isPinned: true,
    sortOrder: 0,
    count: 24,
    description: 'All wardrobe and atelier catalog items'
  },
  {
    id: 'tops',
    label: 'Tops',
    itemType: 'clothing',
    iconType: 'preset',
    iconKey: 'CoatHanger',
    isDefault: true,
    isVisible: true,
    isPinned: true,
    sortOrder: 1,
    count: 6,
    description: 'Shirts, t-shirts, polo shirts, sweaters, and knitwear'
  },
  {
    id: 'bottoms',
    label: 'Bottoms',
    itemType: 'clothing',
    iconType: 'preset',
    iconKey: 'Pants',
    isDefault: true,
    isVisible: true,
    isPinned: true,
    sortOrder: 2,
    count: 5,
    description: 'Trousers, pleated pants, denim, and shorts'
  },
  {
    id: 'outerwear',
    label: 'Outerwear',
    itemType: 'clothing',
    iconType: 'preset',
    iconKey: 'CoatHanger',
    isDefault: true,
    isVisible: true,
    isPinned: true,
    sortOrder: 3,
    count: 4,
    description: 'Jackets, blazers, coats, hoodies, and overshirts'
  },
  {
    id: 'shoes',
    label: 'Shoes',
    itemType: 'footwear',
    iconType: 'preset',
    iconKey: 'Sneaker',
    isDefault: true,
    isVisible: true,
    isPinned: true,
    sortOrder: 4,
    count: 4,
    description: 'Sneakers, formal oxfords, loafers, and boots'
  },
  {
    id: 'accessories',
    label: 'Accessories',
    itemType: 'accessory',
    iconType: 'preset',
    iconKey: 'Watch',
    isDefault: true,
    isVisible: true,
    isPinned: true,
    sortOrder: 5,
    count: 5,
    description: 'Watches, jewelry, sunglasses, bags, and fragrances'
  }
];

export const PRESET_CATEGORY_TEMPLATES: Omit<WardrobeCategory, 'sortOrder'>[] = [
  {
    id: 'watches',
    label: 'Watches',
    itemType: 'watch',
    iconType: 'preset',
    iconKey: 'Watch',
    isVisible: true,
    description: 'Luxury horology, chronographs, and everyday wristwatches'
  },
  {
    id: 'jewelry',
    label: 'Jewellery',
    itemType: 'jewelry',
    iconType: 'preset',
    iconKey: 'Diamond',
    isVisible: true,
    description: 'Rings, chains, bracelets, necklaces, and earrings'
  },
  {
    id: 'bags',
    label: 'Bags',
    itemType: 'bag',
    iconType: 'preset',
    iconKey: 'Handbag',
    isVisible: true,
    description: 'Handbags, totes, crossbody pouches, and weekender duffels'
  },
  {
    id: 'backpacks',
    label: 'Backpacks',
    itemType: 'bag',
    iconType: 'preset',
    iconKey: 'Backpack',
    isVisible: true,
    description: 'Tech backpacks, travel bags, and rucksacks'
  },
  {
    id: 'caps',
    label: 'Caps & Hats',
    itemType: 'accessory',
    iconType: 'preset',
    iconKey: 'BaseballCap',
    isVisible: true,
    description: 'Baseball caps, beanies, bucket hats, and fedoras'
  },
  {
    id: 'perfumes',
    label: 'Perfumes',
    itemType: 'fragrance',
    iconType: 'preset',
    iconKey: 'Drop',
    isVisible: true,
    description: 'Signature scents, eau de parfum, and colognes'
  },
  {
    id: 'cosmetics',
    label: 'Cosmetics',
    itemType: 'beauty',
    iconType: 'preset',
    iconKey: 'Sparkle',
    isVisible: true,
    description: 'Skincare, grooming, beauty, and cosmetic essentials'
  },
  {
    id: 'gadgets',
    label: 'Gadgets',
    itemType: 'gadget',
    iconType: 'preset',
    iconKey: 'DeviceMobile',
    isVisible: true,
    description: 'Smart devices, earbuds, smart rings, and wearables'
  },
  {
    id: 'collectibles',
    label: 'Collectibles',
    itemType: 'collectible',
    iconType: 'preset',
    iconKey: 'Crown',
    isVisible: true,
    description: 'Limited edition fashion pieces and design collectibles'
  },
  {
    id: 'dresses',
    label: 'Dresses',
    itemType: 'clothing',
    iconType: 'preset',
    iconKey: 'Dress',
    isVisible: true,
    description: 'Evening gowns, casual sundresses, and one-piece outfits'
  },
  {
    id: 'sunglasses',
    label: 'Sunglasses',
    itemType: 'accessory',
    iconType: 'preset',
    iconKey: 'Sunglasses',
    isVisible: true,
    description: 'Designer eyewear, shades, and optical frames'
  }
];

class WardrobeCategoryService {
  private listeners: Set<() => void> = new Set();

  private getStorageKey(userId?: string): string {
    const uid = userId || 'default_user';
    return `yorvyn_categories_${uid}`;
  }

  public subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private notify(): void {
    this.listeners.forEach(fn => fn());
  }

  /**
   * Retrieves all user categories sorted by user display order.
   */
  public getCategories(userId?: string): WardrobeCategory[] {
    if (typeof localStorage === 'undefined' && typeof window === 'undefined') return [...DEFAULT_WARDROBE_CATEGORIES];

    try {
      const raw = localStorage.getItem(this.getStorageKey(userId));
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed.sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0));
        }
      }
    } catch (err) {
      console.warn('[WardrobeCategoryService] Storage read error:', err);
    }

    return [...DEFAULT_WARDROBE_CATEGORIES];
  }

  /**
   * Retrieves only visible categories for the horizontal capsule bar.
   */
  public getVisibleCategories(userId?: string): WardrobeCategory[] {
    return this.getCategories(userId).filter(c => c.isVisible !== false);
  }

  /**
   * Saves categories list to local storage.
   */
  private save(categories: WardrobeCategory[], userId?: string): void {
    if (typeof localStorage === 'undefined' && typeof window === 'undefined') return;
    try {
      localStorage.setItem(this.getStorageKey(userId), JSON.stringify(categories));
      this.notify();
    } catch (err) {
      console.warn('[WardrobeCategoryService] Storage save error:', err);
    }
  }

  /**
   * Adds a new category to the user's category list.
   */
  public addCategory(
    newCat: Omit<WardrobeCategory, 'sortOrder' | 'id'> & { id?: string },
    userId?: string
  ): WardrobeCategory {
    const list = this.getCategories(userId);
    const maxSort = list.reduce((m, c) => Math.max(m, c.sortOrder ?? 0), -1);

    const baseSlug = (newCat.label || 'category')
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/(^_|_$)/g, '');
    const generatedId = baseSlug ? `${baseSlug}_${Date.now().toString(36)}` : `cat_${Date.now()}`;

    const created: WardrobeCategory = {
      ...newCat,
      id: newCat.id || generatedId,
      isDefault: newCat.isDefault ?? false,
      isVisible: newCat.isVisible ?? true,
      sortOrder: maxSort + 1,
      count: newCat.count ?? 0
    };

    list.push(created);
    this.save(list, userId);
    return created;
  }

  /**
   * Updates an existing category by ID.
   */
  public updateCategory(
    id: string,
    updates: Partial<WardrobeCategory>,
    userId?: string
  ): WardrobeCategory | null {
    const list = this.getCategories(userId);
    const idx = list.findIndex(c => c.id === id);
    if (idx === -1) return null;

    list[idx] = {
      ...list[idx],
      ...updates
    };

    this.save(list, userId);
    return list[idx];
  }

  /**
   * Deletes a category. Default categories can only be hidden, not permanently removed.
   */
  public deleteCategory(id: string, userId?: string): boolean {
    const list = this.getCategories(userId);
    const target = list.find(c => c.id === id);
    if (!target) return false;

    if (target.isDefault) {
      // Protected system default categories cannot be deleted
      return false;
    }

    const filtered = list.filter(c => c.id !== id);
    // Recalculate sort order
    filtered.forEach((c, i) => {
      c.sortOrder = i;
    });
    this.save(filtered, userId);
    return true;
  }

  /**
   * Reorders categories according to an array of IDs.
   */
  public reorderCategories(orderedIds: string[], userId?: string): WardrobeCategory[] {
    const current = this.getCategories(userId);
    const map = new Map(current.map(c => [c.id, c]));

    const reordered: WardrobeCategory[] = [];
    orderedIds.forEach((id, idx) => {
      const item = map.get(id);
      if (item) {
        reordered.push({ ...item, sortOrder: idx });
        map.delete(id);
      }
    });

    // Append any omitted categories
    let idx = reordered.length;
    map.forEach(item => {
      reordered.push({ ...item, sortOrder: idx++ });
    });

    this.save(reordered, userId);
    return reordered;
  }

  /**
   * Toggles visibility of a category in the horizontal capsule bar.
   */
  public toggleVisibility(
    id: string,
    explicitVisibleOrUserId?: boolean | string,
    userId?: string
  ): WardrobeCategory | null {
    const isExplicit = typeof explicitVisibleOrUserId === 'boolean';
    const effectiveUserId = isExplicit ? userId : (explicitVisibleOrUserId as string | undefined);
    const list = this.getCategories(effectiveUserId);
    const cat = list.find(c => c.id === id);
    if (!cat) return null;

    cat.isVisible = isExplicit ? (explicitVisibleOrUserId as boolean) : !cat.isVisible;
    this.save(list, effectiveUserId);
    return cat;
  }

  /**
   * Toggles pinned favorite state.
   */
  public togglePin(
    id: string,
    explicitPinnedOrUserId?: boolean | string,
    userId?: string
  ): WardrobeCategory | null {
    const isExplicit = typeof explicitPinnedOrUserId === 'boolean';
    const effectiveUserId = isExplicit ? userId : (explicitPinnedOrUserId as string | undefined);
    const list = this.getCategories(effectiveUserId);
    const cat = list.find(c => c.id === id);
    if (!cat) return null;

    cat.isPinned = isExplicit ? (explicitPinnedOrUserId as boolean) : !cat.isPinned;
    this.save(list, effectiveUserId);
    return cat;
  }

  /**
   * Resets categories to factory defaults.
   */
  public resetToDefaults(userId?: string): WardrobeCategory[] {
    const defaults = [...DEFAULT_WARDROBE_CATEGORIES];
    this.save(defaults, userId);
    return defaults;
  }
}

export const wardrobeCategoryService = new WardrobeCategoryService();
