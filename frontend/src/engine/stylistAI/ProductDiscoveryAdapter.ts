/**
 * YORVYN — Product Discovery Adapter & Personal Shopping Engine (Phase 11)
 * Connects AI Stylist to real catalog products, brand filters,
 * transparent price comparisons, and outfit shopping bundles.
 *
 * GUARANTEE: Never invents products, stock levels, or arbitrary prices.
 */

import {
  FashionCatalogItem,
  FASHION_CATALOG,
  CURATED_ENSEMBLES
} from '../../data/fashionCatalogData';

export interface ProductSearchFilters {
  category?: string;
  brand?: string;
  maxPrice?: number;
  minPrice?: number;
  collection?: string;
  sortBy?: 'price_asc' | 'price_desc' | 'recommended';
  assetTypeOnly?: '3d_mesh' | '2d_image';
}

export class ProductDiscoveryAdapter {
  private catalog: FashionCatalogItem[] = [];

  constructor(customCatalog?: FashionCatalogItem[]) {
    this.catalog = customCatalog && customCatalog.length > 0
      ? [...customCatalog]
      : [...FASHION_CATALOG];
  }

  /**
   * Extracts clean numeric price from formatted string (e.g. "₹ 16,900" -> 16900).
   */
  public static parseNumericPrice(priceDisplay?: string): number {
    if (!priceDisplay) return 0;
    const digits = priceDisplay.replace(/[^0-9]/g, '');
    return digits ? parseInt(digits, 10) : 0;
  }

  public searchProducts(query: string = '', filters: ProductSearchFilters = {}): FashionCatalogItem[] {
    const q = query.toLowerCase().trim();

    let results = this.catalog.filter(item => {
      // Exclude undress/mannequin base from shopping recommendations
      if (item.id === 'undress-mannequin') return false;

      // Text query match
      if (q) {
        const matchesName = item.name.toLowerCase().includes(q);
        const matchesBrand = item.brand.toLowerCase().includes(q);
        const matchesCat = item.category.toLowerCase().includes(q);
        const matchesCollection = item.collection.toLowerCase().includes(q);
        if (!matchesName && !matchesBrand && !matchesCat && !matchesCollection) {
          return false;
        }
      }

      // Category filter
      if (filters.category && filters.category !== 'all') {
        if (item.category.toLowerCase() !== filters.category.toLowerCase()) {
          return false;
        }
      }

      // Brand filter
      if (filters.brand && item.brand.toLowerCase() !== filters.brand.toLowerCase()) {
        return false;
      }

      // Price filter
      const price = ProductDiscoveryAdapter.parseNumericPrice(item.priceDisplay);
      if (filters.maxPrice !== undefined && price > filters.maxPrice) {
        return false;
      }
      if (filters.minPrice !== undefined && price < filters.minPrice) {
        return false;
      }

      // Asset type filter
      if (filters.assetTypeOnly && item.assetType !== filters.assetTypeOnly) {
        return false;
      }

      return true;
    });

    // Sorting
    if (filters.sortBy === 'price_asc') {
      results.sort((a, b) => ProductDiscoveryAdapter.parseNumericPrice(a.priceDisplay) - ProductDiscoveryAdapter.parseNumericPrice(b.priceDisplay));
    } else if (filters.sortBy === 'price_desc') {
      results.sort((a, b) => ProductDiscoveryAdapter.parseNumericPrice(b.priceDisplay) - ProductDiscoveryAdapter.parseNumericPrice(a.priceDisplay));
    }

    return results;
  }

  public getCuratedEnsembles(): FashionCatalogItem[] {
    return [...CURATED_ENSEMBLES];
  }

  public getById(id: string): FashionCatalogItem | undefined {
    return this.catalog.find(item => item.id === id) || CURATED_ENSEMBLES.find(item => item.id === id);
  }

  public listBrands(): string[] {
    const brands = new Set<string>();
    this.catalog.forEach(item => {
      if (item.brand && item.id !== 'undress-mannequin') {
        brands.add(item.brand);
      }
    });
    return Array.from(brands);
  }
}

