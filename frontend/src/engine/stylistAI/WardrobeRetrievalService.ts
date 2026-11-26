/**
 * YORVYN — Wardrobe Retrieval Service (Phase 11)
 * Queries and filters the user's personal digital wardrobe,
 * including owned staples and custom 3D reconstructed garments.
 */

import { Garment, GarmentCategory } from '../../types/fashion';
import { DEFAULT_FALLBACK_WARDROBE } from '../../data/fashionCatalogData';

export class WardrobeRetrievalService {
  private wardrobe: Garment[] = [];

  constructor(customWardrobe?: Garment[]) {
    this.wardrobe = customWardrobe && customWardrobe.length > 0
      ? [...customWardrobe]
      : [...DEFAULT_FALLBACK_WARDROBE];
  }

  public setWardrobe(items: Garment[]): void {
    this.wardrobe = [...items];
  }

  public getAll(): Garment[] {
    return [...this.wardrobe];
  }

  public getByCategory(category: GarmentCategory | 'top' | 'bottom' | 'outerwear' | 'footwear' | 'accessory'): Garment[] {
    return this.wardrobe.filter(item => item.category.toLowerCase() === category.toLowerCase());
  }

  public searchWardrobe(query: string): Garment[] {
    const q = query.toLowerCase().trim();
    if (!q) return this.getAll();

    return this.wardrobe.filter(item =>
      item.name.toLowerCase().includes(q) ||
      item.subcategory.toLowerCase().includes(q) ||
      item.brand.toLowerCase().includes(q) ||
      item.material.toLowerCase().includes(q) ||
      item.color.toLowerCase().includes(q) ||
      (item.aesthetic && item.aesthetic.some(a => a.toLowerCase().includes(q)))
    );
  }

  public getCustom3DPieces(): Garment[] {
    return this.wardrobe.filter(item => item.is_custom_3d || !!item.glb_url);
  }

  public getById(id: string): Garment | undefined {
    return this.wardrobe.find(item => item.id === id);
  }
}

