import React from 'react';
import { Garment, GarmentAssetType } from '../types/fashion';
import { HumanParams } from '../engine/ara/core/params';

export interface FashionCatalogItem {
  id: string;
  name: string;
  brand: string;
  category: 'outfit' | 'top' | 'bottom' | 'shoes' | 'outerwear' | 'accessory';
  subcategory?: string;
  material?: string;
  userNotes?: string;
  priceDisplay: string;
  color: string;
  imageUrl?: string;
  hasBlueDot?: boolean;
  collection: 'halloween' | 'diesel' | 'yorvyn' | 'ralph_lauren' | 'cos' | 'staples' | 'quiet_luxury' | 'capsule';
  assetType: GarmentAssetType;
  araOutfitId?: string;
  araShoesId?: string;
  appliedParams: Partial<HumanParams>;
}

export interface OutfitSuggestionItem {
  id: string;
  title: string;
  modelImage: string;
  pieces: { name: string; imageUrl: string }[];
  appliedParams: Partial<HumanParams>;
}

export const OUTFIT_SUGGESTIONS: OutfitSuggestionItem[] = [
  {
    id: 'sugg-ecru-casual',
    title: 'Relaxed Ecru Look',
    modelImage: '/items/dummy_outfit_1.png',
    pieces: [
      { name: 'Pleated Pants', imageUrl: '/items/garments/isolated_garment_4.png' },
      { name: 'White Sneakers', imageUrl: '/items/garments/isolated_garment_7.png' }
    ],
    appliedParams: {
      outfit: 'male_casualsuit06',
      shoes: 'shoes01'
    }
  },
  {
    id: 'sugg-sage-earth',
    title: 'Sage Earth Tone',
    modelImage: '/items/dummy_outfit_2.png',
    pieces: [
      { name: 'Slate Pants', imageUrl: '/items/garments/isolated_garment_6.png' },
      { name: 'Trainers', imageUrl: '/items/garments/isolated_garment_1.png' }
    ],
    appliedParams: {
      outfit: 'none',
      top: 'uniform_shirt_long',
      bottom: 'uniform_trousers',
      shoes: 'shoes01',
      garmentStyles: {
        uniform_shirt_long: { color: '#3f6212' },
        uniform_trousers: { color: '#475569' }
      }
    }
  },
  {
    id: 'sugg-denim-classic',
    title: 'Denim Classic Layer',
    modelImage: '/items/dummy_outfit_3.png',
    pieces: [
      { name: 'Khaki Chinos', imageUrl: '/items/garments/isolated_garment_11.png' },
      { name: 'Retro Low-Tops', imageUrl: '/items/garments/isolated_garment_13.png' }
    ],
    appliedParams: {
      outfit: 'none',
      top: 'techwear_jacket',
      bottom: 'uniform_trousers',
      shoes: 'shoes01',
      garmentStyles: {
        techwear_jacket: { color: '#0284c7', color2: '#f8fafc' },
        uniform_trousers: { color: '#d97706' }
      }
    }
  },
  {
    id: 'sugg-monochrome-street',
    title: 'Streetwear Monochrome',
    modelImage: '/items/dummy_outfit_4.png',
    pieces: [
      { name: 'Cargos', imageUrl: '/items/garments/isolated_garment_14.png' },
      { name: 'Black Low-Tops', imageUrl: '/items/garments/isolated_garment_5.png' }
    ],
    appliedParams: {
      outfit: 'male_casualsuit01',
      shoes: 'shoes04'
    }
  }
];

// ── Clean Minimal Studio SVGs (Matching Reference Wireframe) ──
export const ManAvatarIcon: React.FC = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
);

export const WomanAvatarIcon: React.FC = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z" />
    <line x1="3" y1="6" x2="21" y2="6" />
    <path d="M16 10a4 4 0 0 1-8 0" />
  </svg>
);

// ── Curated Ensembles ──
export const CURATED_ENSEMBLES: FashionCatalogItem[] = [
  {
    id: 'cld-blouse',
    name: 'Atelier Stealth Bomber Suit',
    brand: 'Yorvyn Haute',
    category: 'outfit',
    assetType: '3d_mesh',
    priceDisplay: '₹ 16,900',
    color: '#0f172a',
    collection: 'yorvyn',
    imageUrl: '/items/garments/isolated_garment_1.png',
    araOutfitId: 'male_elegantsuit01',
    appliedParams: {
      outfit: 'male_elegantsuit01',
      top: 'none',
      bottom: 'none',
      shoes: 'shoes02'
    }
  },
  {
    id: 'cld-knit',
    name: 'Cyberpunk Neon Circuit Tracksuit',
    brand: 'Quiet Luxury',
    category: 'outfit',
    assetType: '3d_mesh',
    priceDisplay: '₹ 24,000',
    color: '#38bdf8',
    collection: 'quiet_luxury',
    imageUrl: '/items/garments/isolated_garment_2.png',
    araOutfitId: 'male_casualsuit03',
    appliedParams: {
      outfit: 'male_casualsuit03',
      top: 'none',
      bottom: 'none',
      shoes: 'shoes04'
    }
  },
  {
    id: 'cld-blazer',
    name: 'Oversized Flannel & Denim Layer',
    brand: 'Quiet Luxury',
    category: 'outfit',
    assetType: '3d_mesh',
    priceDisplay: '₹ 18,500',
    color: '#0284c7',
    collection: 'quiet_luxury',
    imageUrl: '/items/garments/isolated_garment_3.png',
    araOutfitId: 'male_casualsuit06',
    appliedParams: {
      outfit: 'male_casualsuit06',
      top: 'none',
      bottom: 'none',
      shoes: 'shoes01'
    }
  },
  {
    id: 'hal-goddess',
    name: 'Midnight Atelier Tuxedo Suit',
    brand: 'Yorvyn Special',
    category: 'outfit',
    assetType: '3d_mesh',
    priceDisplay: '₹ 18,500',
    color: '#1e1b18',
    collection: 'yorvyn',
    imageUrl: '/items/garments/isolated_garment_8.png',
    araOutfitId: 'male_elegantsuit01',
    appliedParams: {
      outfit: 'male_elegantsuit01',
      top: 'none',
      bottom: 'none',
      shoes: 'shoes02'
    }
  },
  {
    id: 'sig-polo',
    name: 'Modern Atelier Casual Ensemble',
    brand: 'Yorvyn Studio',
    category: 'outfit',
    assetType: '3d_mesh',
    priceDisplay: '₹ 8,990',
    color: '#1e293b',
    collection: 'yorvyn',
    imageUrl: '/items/garments/isolated_garment_11.png',
    araOutfitId: 'male_casualsuit06',
    appliedParams: {
      outfit: 'male_casualsuit06',
      top: 'none',
      bottom: 'none',
      shoes: 'shoes01'
    }
  }
];

// ── Genuine 3D Garments with Layer Mapping ──
export const FASHION_CATALOG: FashionCatalogItem[] = [
  // ── 6 Tops Items (Matches Reference Screenshot) ──
  {
    id: 'relaxed-shirt',
    name: 'Relaxed Shirt',
    brand: 'Yorvyn Studio',
    category: 'top',
    assetType: '3d_mesh',
    priceDisplay: '₹ 8,990',
    color: '#fef3c7',
    collection: 'yorvyn',
    imageUrl: '/items/garments/isolated_garment_1.png',
    hasBlueDot: true,
    appliedParams: {
      outfit: 'none',
      top: 'uniform_shirt',
      bottom: 'uniform_trousers',
      shoes: 'shoes01',
      garmentStyles: {
        uniform_shirt: { color: '#fef3c7', pattern: 'solid' },
        uniform_trousers: { color: '#d6d3d1' }
      }
    }
  },
  {
    id: 'oversized-hoodie',
    name: 'Oversized Hoodie',
    brand: 'Quiet Luxury',
    category: 'top',
    assetType: '3d_mesh',
    priceDisplay: '₹ 12,500',
    color: '#1a1d24',
    collection: 'quiet_luxury',
    imageUrl: '/items/garments/isolated_garment_2.png',
    hasBlueDot: true,
    appliedParams: {
      outfit: 'none',
      top: 'techwear_jacket',
      bottom: 'uniform_trousers',
      shoes: 'shoes01',
      garmentStyles: {
        techwear_jacket: { color: '#16181d', color2: '#00d2ff', pattern: 'techwear' },
        uniform_trousers: { color: '#252932' }
      }
    }
  },
  {
    id: 'denim-jacket',
    name: 'Denim Jacket',
    brand: 'Diesel',
    category: 'top',
    assetType: '3d_mesh',
    priceDisplay: '₹ 18,900',
    color: '#0284c7',
    collection: 'diesel',
    imageUrl: '/items/garments/isolated_garment_3.png',
    appliedParams: {
      outfit: 'none',
      top: 'techwear_jacket',
      bottom: 'uniform_trousers',
      shoes: 'shoes01',
      garmentStyles: {
        techwear_jacket: { color: '#0284c7', color2: '#cbd5e1' },
        uniform_trousers: { color: '#d6d3d1' }
      }
    }
  },
  {
    id: 'knitted-sweater',
    name: 'Knitted Sweater',
    brand: 'COS Atelier',
    category: 'top',
    assetType: '3d_mesh',
    priceDisplay: '₹ 14,500',
    color: '#e2d9cc',
    collection: 'cos',
    imageUrl: '/items/garments/isolated_garment_12.png',
    appliedParams: {
      outfit: 'none',
      top: 'uniform_shirt_long',
      bottom: 'uniform_trousers',
      shoes: 'shoes01',
      garmentStyles: {
        uniform_shirt_long: { color: '#e2d9cc', pattern: 'solid' },
        uniform_trousers: { color: '#475569' }
      }
    }
  },
  {
    id: 'polo-shirt',
    name: 'Polo Shirt',
    brand: 'Ralph Lauren',
    category: 'top',
    subcategory: 'shirts',
    assetType: '3d_mesh',
    priceDisplay: '₹ 9,500',
    color: '#ffffff',
    collection: 'ralph_lauren',
    imageUrl: '/items/garments/isolated_garment_10.png',
    appliedParams: {
      outfit: 'none',
      top: 'uniform_shirt',
      bottom: 'uniform_trousers',
      shoes: 'shoes01',
      garmentStyles: {
        uniform_shirt: { color: '#ffffff', color2: '#166534', pattern: 'striped' },
        uniform_trousers: { color: '#f8fafc' }
      }
    }
  },
  {
    id: 'casual-shirt',
    name: 'Casual Shirt',
    brand: 'Yorvyn Studio',
    category: 'top',
    assetType: '3d_mesh',
    priceDisplay: '₹ 8,200',
    color: '#93c5fd',
    collection: 'yorvyn',
    imageUrl: '/items/garments/isolated_garment_13.png',
    appliedParams: {
      outfit: 'none',
      top: 'uniform_shirt',
      bottom: 'uniform_trousers',
      shoes: 'shoes01',
      garmentStyles: {
        uniform_shirt: { color: '#93c5fd', pattern: 'solid' },
        uniform_trousers: { color: '#334155' }
      }
    }
  },
  {
    id: 'undress-mannequin',
    name: 'Bare Mannequin (Undress All)',
    brand: 'Yorvyn Atelier',
    category: 'outfit',
    assetType: '3d_mesh',
    priceDisplay: 'Mannequin Base',
    color: '#64748b',
    collection: 'yorvyn',
    imageUrl: '/items/garments/isolated_garment_1.png',
    araOutfitId: 'none',
    appliedParams: {
      outfit: 'none',
      top: 'none',
      bottom: 'none',
      shoes: 'none',
      underwear: true
    }
  },
  {
    id: 'cld-blouse',
    name: 'Atelier Stealth Bomber Suit',
    brand: 'Yorvyn Haute',
    category: 'outfit',
    assetType: '3d_mesh',
    priceDisplay: '₹ 16,900',
    color: '#0f172a',
    collection: 'yorvyn',
    imageUrl: '/items/garments/isolated_garment_1.png',
    hasBlueDot: true,
    appliedParams: {
      outfit: 'male_elegantsuit01',
      top: 'none',
      bottom: 'none',
      shoes: 'shoes02'
    }
  },
  {
    id: 'cld-knit',
    name: 'Cyberpunk Neon Circuit Tracksuit',
    brand: 'Quiet Luxury',
    category: 'outfit',
    assetType: '3d_mesh',
    priceDisplay: '₹ 24,000',
    color: '#38bdf8',
    collection: 'quiet_luxury',
    imageUrl: '/items/garments/isolated_garment_2.png',
    hasBlueDot: true,
    appliedParams: {
      outfit: 'male_casualsuit03',
      top: 'none',
      bottom: 'none',
      shoes: 'shoes04'
    }
  },
  {
    id: 'cld-blazer',
    name: 'Oversized Flannel & Denim Layer',
    brand: 'Quiet Luxury',
    category: 'outfit',
    assetType: '3d_mesh',
    priceDisplay: '₹ 18,500',
    color: '#0284c7',
    collection: 'quiet_luxury',
    imageUrl: '/items/garments/isolated_garment_3.png',
    appliedParams: {
      outfit: 'male_casualsuit06',
      top: 'none',
      bottom: 'none',
      shoes: 'shoes01'
    }
  },
  {
    id: 'cld-trousers',
    name: 'Midnight Silk Tuxedo Suit',
    brand: 'Capsule Archive',
    category: 'outfit',
    assetType: '3d_mesh',
    priceDisplay: '₹ 21,900',
    color: '#e2e8f0',
    collection: 'capsule',
    imageUrl: '/items/garments/isolated_garment_4.png',
    appliedParams: {
      outfit: 'male_elegantsuit01',
      top: 'none',
      bottom: 'none',
      shoes: 'shoes02'
    }
  },
  {
    id: 'cld-sneakers',
    name: 'Monogram Varsity Letterman Jacket',
    brand: 'Yorvyn Haute',
    category: 'outerwear',
    assetType: '3d_mesh',
    priceDisplay: '₹ 28,500',
    color: '#ffffff',
    collection: 'yorvyn',
    imageUrl: '/items/garments/isolated_garment_5.png',
    araShoesId: 'shoes01',
    appliedParams: {
      outfit: 'none',
      top: 'techwear_jacket',
      bottom: 'uniform_trousers',
      shoes: 'shoes01',
      garmentStyles: {
        techwear_jacket: { color: '#ffffff', color2: '#0f172a' }
      }
    }
  },
  {
    id: 'hal-pumpkin',
    name: 'Vintage Striped Rugby Polo',
    brand: 'Bitmoji Fashion',
    category: 'top',
    assetType: '3d_mesh',
    priceDisplay: '₹ 6,499',
    color: '#831843',
    collection: 'halloween',
    imageUrl: '/items/garments/isolated_garment_6.png',
    hasBlueDot: true,
    appliedParams: {
      outfit: 'none',
      top: 'uniform_shirt',
      bottom: 'uniform_trousers',
      shoes: 'shoes01',
      garmentStyles: {
        uniform_shirt: { color: '#831843', pattern: 'striped' }
      }
    }
  },
  {
    id: 'hal-medusa',
    name: 'Quilted Scarlet Puffer Jacket',
    brand: 'Bitmoji Fashion',
    category: 'outerwear',
    assetType: '3d_mesh',
    priceDisplay: '₹ 14,999',
    color: '#dc2626',
    collection: 'halloween',
    imageUrl: '/items/garments/isolated_garment_7.png',
    hasBlueDot: true,
    appliedParams: {
      outfit: 'none',
      top: 'techwear_jacket',
      bottom: 'uniform_trousers',
      shoes: 'shoes01',
      garmentStyles: {
        techwear_jacket: { color: '#dc2626', color2: '#111111' }
      }
    }
  },
  {
    id: 'hal-goddess',
    name: 'Royal Formal Atelier Cape Suit',
    brand: 'Bitmoji Fashion',
    category: 'outfit',
    assetType: '3d_mesh',
    priceDisplay: '₹ 22,999',
    color: '#b91c1c',
    collection: 'halloween',
    imageUrl: '/items/garments/isolated_garment_8.png',
    araOutfitId: 'male_elegantsuit01',
    appliedParams: {
      outfit: 'male_elegantsuit01',
      top: 'none',
      bottom: 'none',
      shoes: 'shoes02'
    }
  },
  {
    id: 'dsl-biker',
    name: 'Cream Shearling Fleece Aviator',
    brand: 'Diesel',
    category: 'outerwear',
    assetType: '3d_mesh',
    priceDisplay: '₹ 32,900',
    color: '#fef08a',
    collection: 'diesel',
    imageUrl: '/items/garments/isolated_garment_9.png',
    araOutfitId: 'male_casualsuit01',
    appliedParams: {
      outfit: 'none',
      top: 'techwear_jacket',
      bottom: 'uniform_trousers',
      shoes: 'shoes01',
      garmentStyles: {
        techwear_jacket: { color: '#fef08a', color2: '#334155' }
      }
    }
  },
  {
    id: 'wiz-cloak',
    name: 'Emerald Heritage Long-Sleeve Shirt',
    brand: 'Yorvyn Special',
    category: 'top',
    assetType: '3d_mesh',
    priceDisplay: '₹ 7,500',
    color: '#16a34a',
    collection: 'yorvyn',
    imageUrl: '/items/garments/isolated_garment_10.png',
    appliedParams: {
      outfit: 'none',
      top: 'uniform_shirt_long',
      bottom: 'uniform_trousers',
      shoes: 'shoes01',
      garmentStyles: {
        uniform_shirt_long: { color: '#16a34a', pattern: 'solid' }
      }
    }
  },
  {
    id: 'sig-polo',
    name: 'Minimalist Midnight Relaxed Suit',
    brand: 'Ralph Lauren',
    category: 'outfit',
    assetType: '3d_mesh',
    priceDisplay: '₹ 19,990',
    color: '#111111',
    collection: 'ralph_lauren',
    imageUrl: '/items/garments/isolated_garment_11.png',
    araOutfitId: 'male_casualsuit06',
    appliedParams: {
      outfit: 'male_casualsuit06',
      top: 'none',
      bottom: 'none',
      shoes: 'shoes01'
    }
  },
  {
    id: 'sig-jeans',
    name: 'Burgundy Structured Sweatshirt',
    brand: 'Diesel',
    category: 'top',
    assetType: '3d_mesh',
    priceDisplay: '₹ 15,500',
    color: '#701a75',
    collection: 'diesel',
    imageUrl: '/items/garments/isolated_garment_12.png',
    appliedParams: {
      outfit: 'none',
      top: 'uniform_shirt_long',
      bottom: 'uniform_trousers',
      shoes: 'shoes01',
      garmentStyles: {
        uniform_shirt_long: { color: '#701a75', pattern: 'solid' }
      }
    }
  },
  {
    id: 'sig-sneakers',
    name: 'Classic White Piqué Crest Polo',
    brand: 'COS',
    category: 'top',
    assetType: '3d_mesh',
    priceDisplay: '₹ 8,500',
    color: '#ffffff',
    collection: 'cos',
    imageUrl: '/items/garments/isolated_garment_13.png',
    appliedParams: {
      outfit: 'none',
      top: 'uniform_shirt',
      bottom: 'uniform_trousers',
      shoes: 'shoes01',
      garmentStyles: {
        uniform_shirt: { color: '#ffffff', pattern: 'solid' }
      }
    }
  },
  {
    id: 'bespoke-tux',
    name: 'Azure Block-Stripe Casual Polo',
    brand: 'Yorvyn Atelier',
    category: 'top',
    assetType: '3d_mesh',
    priceDisplay: '₹ 9,000',
    color: '#38bdf8',
    collection: 'yorvyn',
    imageUrl: '/items/garments/isolated_garment_14.png',
    appliedParams: {
      outfit: 'none',
      top: 'uniform_shirt',
      bottom: 'uniform_trousers',
      shoes: 'shoes01',
      garmentStyles: {
        uniform_shirt: { color: '#38bdf8', pattern: 'striped' }
      }
    }
  },
  {
    id: 'moto-leather',
    name: 'Iconic Black Leather Biker Jacket',
    brand: 'Diesel Atelier',
    category: 'outerwear',
    assetType: '3d_mesh',
    priceDisplay: '₹ 38,000',
    color: '#0f172a',
    collection: 'diesel',
    imageUrl: '/items/garments/isolated_garment_15.png',
    appliedParams: {
      outfit: 'none',
      top: 'techwear_jacket',
      bottom: 'uniform_trousers',
      shoes: 'shoes04',
      garmentStyles: {
        techwear_jacket: { color: '#111111', color2: '#000000' }
      }
    }
  },
  // ── Bottoms & Trousers ──
  {
    id: 'atelier-pleated-trousers',
    name: 'Relaxed Tailored Pleated Trousers',
    brand: 'Yorvyn Atelier',
    category: 'bottom',
    assetType: '3d_mesh',
    priceDisplay: '₹ 12,500',
    color: '#334155',
    collection: 'quiet_luxury',
    imageUrl: '/items/garments/isolated_garment_4.png',
    appliedParams: {
      bottom: 'uniform_trousers',
      garmentStyles: {
        uniform_trousers: { color: '#334155' }
      }
    }
  },
  {
    id: 'selvedge-raw-denim',
    name: 'Japanese Selvedge Raw Denim Jeans',
    brand: 'Diesel',
    category: 'bottom',
    assetType: '3d_mesh',
    priceDisplay: '₹ 15,900',
    color: '#0f172a',
    collection: 'diesel',
    imageUrl: '/items/garments/isolated_garment_6.png',
    appliedParams: {
      bottom: 'techwear_pants',
      garmentStyles: {
        techwear_pants: { color: '#1e293b' }
      }
    }
  },
  // ── Footwear & Shoes ──
  {
    id: 'minimalist-leather-sneakers',
    name: 'Minimalist White Leather Low-Tops',
    brand: 'Common Projects',
    category: 'shoes',
    assetType: '3d_mesh',
    priceDisplay: '₹ 22,000',
    color: '#ffffff',
    collection: 'quiet_luxury',
    imageUrl: '/items/garments/isolated_garment_7.png',
    araShoesId: 'shoes01',
    appliedParams: {
      shoes: 'shoes01'
    }
  },
  {
    id: 'formal-oxford-derbies',
    name: 'Classic Black Oxford Dress Shoes',
    brand: 'Yorvyn Atelier',
    category: 'shoes',
    assetType: '3d_mesh',
    priceDisplay: '₹ 18,900',
    color: '#0f172a',
    collection: 'yorvyn',
    imageUrl: '/items/garments/isolated_garment_1.png',
    araShoesId: 'shoes02',
    appliedParams: {
      shoes: 'shoes02'
    }
  },
  {
    id: 'chelsea-leather-boots',
    name: 'Chunky Lug-Sole Chelsea Boots',
    brand: 'Bottega Veneta',
    category: 'shoes',
    subcategory: 'shoes',
    assetType: '3d_mesh',
    priceDisplay: '₹ 28,500',
    color: '#1e1e1e',
    collection: 'capsule',
    imageUrl: '/items/garments/isolated_garment_10.png',
    araShoesId: 'shoes04',
    appliedParams: {
      shoes: 'shoes04'
    }
  },
  // ── Hoodies & Sweatshirts ──
  {
    id: 'heavyweight-hoodie-cream',
    name: 'Heavyweight Cream Boxy Hoodie',
    brand: 'Yorvyn Studio',
    category: 'top',
    subcategory: 'hoodies',
    assetType: '3d_mesh',
    material: '500 GSM French Terry',
    userNotes: 'Boxy drop-shoulder silhouette with double-layered hood',
    priceDisplay: '₹ 14,900',
    color: '#f5f5f4',
    collection: 'yorvyn',
    imageUrl: '/items/garments/isolated_garment_3.png',
    appliedParams: {
      outfit: 'none',
      top: 'uniform_shirt_long',
      bottom: 'uniform_trousers',
      shoes: 'shoes01',
      garmentStyles: {
        uniform_shirt_long: { color: '#f5f5f4', pattern: 'solid' },
        uniform_trousers: { color: '#334155' }
      }
    }
  },
  {
    id: 'streetwear-zip-hoodie',
    name: 'Washed Vintage Zip Hoodie',
    brand: 'Diesel',
    category: 'top',
    subcategory: 'hoodies',
    assetType: '3d_mesh',
    material: 'Washed Organic Cotton',
    userNotes: 'Sun-faded enzyme wash with distressed seam details',
    priceDisplay: '₹ 19,200',
    color: '#334155',
    collection: 'diesel',
    imageUrl: '/items/garments/isolated_garment_5.png',
    appliedParams: {
      outfit: 'none',
      top: 'uniform_shirt_long',
      bottom: 'uniform_trousers',
      shoes: 'shoes01',
      garmentStyles: {
        uniform_shirt_long: { color: '#334155', pattern: 'solid' },
        uniform_trousers: { color: '#1e293b' }
      }
    }
  },
  // ── Shorts ──
  {
    id: 'pleated-bermuda-shorts',
    name: 'Pleated Relaxed Bermuda Shorts',
    brand: 'COS',
    category: 'bottom',
    subcategory: 'shorts',
    assetType: '3d_mesh',
    material: 'Linen & Lyocell Blend',
    userNotes: 'High-waisted double front pleats with knee drop',
    priceDisplay: '₹ 9,500',
    color: '#94a3b8',
    collection: 'cos',
    imageUrl: '/items/garments/isolated_garment_8.png',
    appliedParams: {
      outfit: 'none',
      top: 'uniform_shirt',
      bottom: 'cargo_shorts',
      shoes: 'shoes01',
      garmentStyles: {
        cargo_shorts: { color: '#94a3b8', pattern: 'solid' },
        uniform_shirt: { color: '#ffffff' }
      }
    }
  },
  {
    id: 'tailored-linen-shorts',
    name: 'Tailored Off-White Linen Shorts',
    brand: 'Yorvyn Atelier',
    category: 'bottom',
    subcategory: 'shorts',
    assetType: '3d_mesh',
    material: 'Pure Belgian Linen',
    userNotes: 'Pressed crease tailored shorts with side adjusters',
    priceDisplay: '₹ 11,800',
    color: '#f1f5f9',
    collection: 'yorvyn',
    imageUrl: '/items/garments/isolated_garment_4.png',
    appliedParams: {
      outfit: 'none',
      top: 'uniform_shirt',
      bottom: 'cargo_shorts',
      shoes: 'shoes01',
      garmentStyles: {
        cargo_shorts: { color: '#f1f5f9', pattern: 'solid' },
        uniform_shirt: { color: '#334155' }
      }
    }
  },
  // ── Skirts ──
  {
    id: 'silk-midi-skirt',
    name: 'Bias-Cut Silk Midi Skirt',
    brand: 'The Row',
    category: 'bottom',
    subcategory: 'skirts',
    assetType: '2d_image',
    material: '100% Mulberry Silk Charmeuse',
    userNotes: 'Fluid bias drape falling just below the knee',
    priceDisplay: '₹ 32,000',
    color: '#0f172a',
    collection: 'quiet_luxury',
    imageUrl: '/items/garments/isolated_garment_9.png',
    appliedParams: {
      outfit: 'female_casualsuit01'
    }
  },
  {
    id: 'pleated-tennis-skirt',
    name: 'Minimalist Pleated Tennis Skirt',
    brand: 'COS',
    category: 'bottom',
    subcategory: 'skirts',
    assetType: '2d_image',
    material: 'Structured Wool Blend',
    userNotes: 'Clean knife pleats with invisible side zip',
    priceDisplay: '₹ 8,900',
    color: '#ffffff',
    collection: 'cos',
    imageUrl: '/items/garments/isolated_garment_7.png',
    appliedParams: {
      outfit: 'female_casualsuit02'
    }
  },
  // ── Accessories (Requirement 4) ──
  {
    id: 'watch-oyster-chrono',
    name: 'Oyster Perpetual Chronograph Watch',
    brand: 'Rolex',
    category: 'accessory',
    subcategory: 'watches',
    assetType: '2d_image',
    material: 'Oystersteel & Sapphire Crystal',
    userNotes: 'Swiss precision chronometer with tachymetric bezel and brushed bracelet',
    priceDisplay: '₹ 945,000',
    color: '#94a3b8',
    collection: 'quiet_luxury',
    imageUrl: '/items/garments/isolated_garment_1.png',
    appliedParams: {}
  },
  {
    id: 'ring-titanium-signet',
    name: 'Titanium Minimalist Signet Ring',
    brand: 'Tom Wood',
    category: 'accessory',
    subcategory: 'rings',
    assetType: '2d_image',
    material: 'Solid Grade 5 Titanium',
    userNotes: 'Architectural brushed matte top with ergonomic inner contour',
    priceDisplay: '₹ 24,000',
    color: '#64748b',
    collection: 'staples',
    imageUrl: '/items/garments/isolated_garment_2.png',
    appliedParams: {}
  },
  {
    id: 'necklace-platinum-chain',
    name: 'Fine Platinum Venetian Box Chain',
    brand: 'Cartier',
    category: 'accessory',
    subcategory: 'necklaces',
    assetType: '2d_image',
    material: '950 Platinum',
    userNotes: 'Discreet 1.8mm Venetian link chain with lobster clasp',
    priceDisplay: '₹ 88,000',
    color: '#e2e8f0',
    collection: 'quiet_luxury',
    imageUrl: '/items/garments/isolated_garment_3.png',
    appliedParams: {}
  },
  {
    id: 'bracelet-calfskin-braided',
    name: 'Braided Intrecciato Leather Bracelet',
    brand: 'Bottega Veneta',
    category: 'accessory',
    subcategory: 'bracelets',
    assetType: '2d_image',
    material: 'Supple Nappa Calfskin',
    userNotes: 'Double-wrap braided cuff with brushed brass hook closure',
    priceDisplay: '₹ 36,000',
    color: '#1e293b',
    collection: 'quiet_luxury',
    imageUrl: '/items/garments/isolated_garment_4.png',
    appliedParams: {}
  },
  {
    id: 'earrings-silver-studs',
    name: 'Minimalist Sterling Sphere Studs',
    brand: 'Acne Studios',
    category: 'accessory',
    subcategory: 'earrings',
    assetType: '2d_image',
    material: '925 Sterling Silver',
    userNotes: 'Mirror-polished solid spheres with secure push-back clasps',
    priceDisplay: '₹ 16,500',
    color: '#cbd5e1',
    collection: 'staples',
    imageUrl: '/items/garments/isolated_garment_5.png',
    appliedParams: {}
  },
  {
    id: 'sunglasses-hexagonal-acetate',
    name: 'Hexagonal Black Acetate Sunglasses',
    brand: 'Saint Laurent',
    category: 'accessory',
    subcategory: 'sunglasses',
    assetType: '3d_mesh',
    material: 'Cured Italian Acetate',
    userNotes: 'Beveled geometric frames with category 3 UV400 grey tinted lenses',
    priceDisplay: '₹ 34,000',
    color: '#0f172a',
    collection: 'quiet_luxury',
    imageUrl: '/items/garments/isolated_garment_6.png',
    appliedParams: {}
  },
  {
    id: 'bag-structured-leather-tote',
    name: 'Structured Grain Calfskin Tote',
    brand: 'Lemaire',
    category: 'accessory',
    subcategory: 'bags',
    assetType: '2d_image',
    material: 'Vegetable-Tanned Grain Leather',
    userNotes: 'Seamless molded tote bag with tubular handles and cotton lining',
    priceDisplay: '₹ 72,000',
    color: '#334155',
    collection: 'quiet_luxury',
    imageUrl: '/items/garments/isolated_garment_7.png',
    appliedParams: {}
  },
  {
    id: 'belt-brushed-saddle',
    name: 'Brushed Nickel Saddle Leather Belt',
    brand: 'Hermès',
    category: 'accessory',
    subcategory: 'belts',
    assetType: '2d_image',
    material: 'Bridle Saddle Leather',
    userNotes: '32mm hand-burnished edge leather strap with palladium buckle',
    priceDisplay: '₹ 56,000',
    color: '#1e1e1e',
    collection: 'quiet_luxury',
    imageUrl: '/items/garments/isolated_garment_8.png',
    appliedParams: {}
  },
  {
    id: 'cap-heritage-cotton',
    name: 'Heritage Washed Twill Dad Cap',
    brand: 'Ralph Lauren',
    category: 'accessory',
    subcategory: 'caps',
    assetType: '2d_image',
    material: '100% Chino Cotton Twill',
    userNotes: 'Low-profile unconstructed crown with antique brass slider',
    priceDisplay: '₹ 6,200',
    color: '#475569',
    collection: 'ralph_lauren',
    imageUrl: '/items/garments/isolated_garment_9.png',
    appliedParams: {}
  },
  {
    id: 'scarf-cashmere-fringe',
    name: 'Ribbed Fringe Pure Cashmere Scarf',
    brand: 'Loro Piana',
    category: 'accessory',
    subcategory: 'scarves',
    assetType: '2d_image',
    material: '100% Baby Cashmere',
    userNotes: 'Hand-knotted fringe hem with water-drop rippled finish',
    priceDisplay: '₹ 68,000',
    color: '#e2e8f0',
    collection: 'quiet_luxury',
    imageUrl: '/items/garments/isolated_garment_10.png',
    appliedParams: {}
  }
];

// ── Realistic Digital Wardrobe Fallback Items ──
export const DEFAULT_FALLBACK_WARDROBE: Garment[] = [
  {
    id: 'wardrobe_1',
    name: 'Oversized Merino Wool Crewneck',
    category: 'top',
    subcategory: 'knitwear',
    color: '#e2e8f0',
    material: 'merino wool',
    pattern: 'solid',
    formality: 4,
    warmth: 6,
    seasons: ['autumn', 'winter', 'spring'],
    weather_tags: ['mild', 'chilly'],
    aesthetic: ['quiet_luxury', 'minimalist_scandi'],
    brand: 'COS',
    image_url: 'https://images.unsplash.com/photo-1576566588028-4147f3842f27?auto=format&fit=crop&w=600&q=80',
    thumbnail_url: 'https://images.unsplash.com/photo-1576566588028-4147f3842f27?auto=format&fit=crop&w=600&q=80',
    wear_count: 8,
    favorite: true,
    asset_type: '2d_image',
    fitting_status: 'unsupported'
  },
  {
    id: 'wardrobe_2',
    name: 'Relaxed Tailored Pleated Trousers',
    category: 'bottom',
    subcategory: 'trousers',
    color: '#334155',
    material: 'wool blend',
    pattern: 'solid',
    formality: 6,
    warmth: 5,
    seasons: ['all_season'],
    weather_tags: ['mild', 'indoor'],
    aesthetic: ['quiet_luxury', 'smart_casual'],
    brand: 'Yorvyn Atelier',
    image_url: 'https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=600&q=80',
    thumbnail_url: 'https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=600&q=80',
    wear_count: 5,
    favorite: false,
    asset_type: '2d_image',
    fitting_status: 'unsupported'
  },
  {
    id: 'wardrobe_3',
    name: 'Double-Breasted Wool Overcoat',
    category: 'outerwear',
    subcategory: 'overcoat',
    color: '#1e293b',
    material: 'cashmere blend',
    pattern: 'solid',
    formality: 7,
    warmth: 8,
    seasons: ['winter', 'autumn'],
    weather_tags: ['cold', 'windy'],
    aesthetic: ['quiet_luxury', 'timeless'],
    brand: 'Quiet Luxury',
    image_url: 'https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?auto=format&fit=crop&w=600&q=80',
    thumbnail_url: 'https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?auto=format&fit=crop&w=600&q=80',
    wear_count: 12,
    favorite: true,
    asset_type: '2d_image',
    fitting_status: 'unsupported'
  },
  {
    id: 'wardrobe_4',
    name: 'Minimalist White Leather Low-Tops',
    category: 'footwear',
    subcategory: 'sneakers',
    color: '#ffffff',
    material: 'italian leather',
    pattern: 'solid',
    formality: 4,
    warmth: 4,
    seasons: ['spring', 'summer', 'autumn'],
    weather_tags: ['mild', 'sunny'],
    aesthetic: ['minimalist_scandi', 'smart_casual'],
    brand: 'Common Projects',
    image_url: 'https://images.unsplash.com/photo-1560769629-975ec94e6a86?auto=format&fit=crop&w=600&q=80',
    thumbnail_url: 'https://images.unsplash.com/photo-1560769629-975ec94e6a86?auto=format&fit=crop&w=600&q=80',
    wear_count: 15,
    favorite: false,
    asset_type: '3d_mesh',
    fitting_status: 'ready'
  },
  {
    id: 'wardrobe_5',
    name: 'Classic Crisp Oxford Cotton Shirt',
    category: 'top',
    subcategory: 'shirt',
    color: '#f8fafc',
    material: 'oxford cotton',
    pattern: 'solid',
    formality: 6,
    warmth: 4,
    seasons: ['all_season'],
    weather_tags: ['mild', 'office'],
    aesthetic: ['smart_casual', 'preppy'],
    brand: 'Ralph Lauren',
    image_url: 'https://images.unsplash.com/photo-1596755094514-f87e34085b2c?auto=format&fit=crop&w=600&q=80',
    thumbnail_url: 'https://images.unsplash.com/photo-1596755094514-f87e34085b2c?auto=format&fit=crop&w=600&q=80',
    wear_count: 9,
    favorite: true,
    asset_type: '2d_image',
    fitting_status: 'unsupported'
  },
  {
    id: 'wardrobe_6',
    name: 'Japanese Selvedge Raw Denim Jeans',
    category: 'bottom',
    subcategory: 'denim',
    color: '#0f172a',
    material: 'selvedge denim',
    pattern: 'raw',
    formality: 4,
    warmth: 5,
    seasons: ['all_season'],
    weather_tags: ['mild', 'cool'],
    aesthetic: ['streetwear', 'heritage'],
    brand: 'Diesel',
    image_url: 'https://images.unsplash.com/photo-1542272604-780c96856484?auto=format&fit=crop&w=600&q=80',
    thumbnail_url: 'https://images.unsplash.com/photo-1542272604-780c96856484?auto=format&fit=crop&w=600&q=80',
    wear_count: 22,
    favorite: false,
    asset_type: '2d_image',
    fitting_status: 'unsupported'
  },
  {
    id: 'wardrobe_7',
    name: 'Chunky Leather Chelsea Boots',
    category: 'footwear',
    subcategory: 'boots',
    color: '#0f172a',
    material: 'calfskin leather',
    pattern: 'solid',
    formality: 6,
    warmth: 6,
    seasons: ['autumn', 'winter'],
    weather_tags: ['rainy', 'cold'],
    aesthetic: ['modern_luxury', 'edgy'],
    brand: 'Bottega Veneta',
    image_url: 'https://images.unsplash.com/photo-1638247025967-b4e38f787b76?auto=format&fit=crop&w=600&q=80',
    thumbnail_url: 'https://images.unsplash.com/photo-1638247025967-b4e38f787b76?auto=format&fit=crop&w=600&q=80',
    wear_count: 7,
    favorite: false,
    asset_type: '2d_image',
    fitting_status: 'unsupported'
  },
  {
    id: 'wardrobe_8',
    name: 'Hexagonal Black Acetate Sunglasses',
    category: 'accessory',
    subcategory: 'sunglasses',
    color: '#0f172a',
    material: 'cured acetate',
    pattern: 'solid',
    formality: 5,
    warmth: 1,
    seasons: ['all_season'],
    weather_tags: ['sunny', 'outdoor'],
    aesthetic: ['quiet_luxury', 'modern'],
    brand: 'Saint Laurent',
    image_url: 'https://images.unsplash.com/photo-1511499767150-a48a237f0083?auto=format&fit=crop&w=600&q=80',
    thumbnail_url: 'https://images.unsplash.com/photo-1511499767150-a48a237f0083?auto=format&fit=crop&w=600&q=80',
    wear_count: 18,
    favorite: true,
    asset_type: '3d_mesh',
    fitting_status: 'ready'
  },
  {
    id: 'wardrobe_9',
    name: 'Oystersteel Chronograph Watch',
    category: 'accessory',
    subcategory: 'watches',
    color: '#94a3b8',
    material: 'oystersteel',
    pattern: 'solid',
    formality: 7,
    warmth: 1,
    seasons: ['all_season'],
    weather_tags: ['all_weather'],
    aesthetic: ['quiet_luxury', 'heritage'],
    brand: 'Rolex',
    image_url: 'https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9?auto=format&fit=crop&w=600&q=80',
    thumbnail_url: 'https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9?auto=format&fit=crop&w=600&q=80',
    wear_count: 31,
    favorite: true,
    asset_type: '2d_image',
    fitting_status: 'unsupported'
  },
  {
    id: 'wardrobe_10',
    name: 'Heavyweight Boxy Hoodie',
    category: 'top',
    subcategory: 'hoodies',
    color: '#f5f5f4',
    material: 'french terry cotton',
    pattern: 'solid',
    formality: 3,
    warmth: 7,
    seasons: ['autumn', 'winter', 'spring'],
    weather_tags: ['chilly', 'mild'],
    aesthetic: ['streetwear', 'minimalist'],
    brand: 'Yorvyn Studio',
    image_url: 'https://images.unsplash.com/photo-1556905055-8f358a7a47b2?auto=format&fit=crop&w=600&q=80',
    thumbnail_url: 'https://images.unsplash.com/photo-1556905055-8f358a7a47b2?auto=format&fit=crop&w=600&q=80',
    wear_count: 14,
    favorite: false,
    asset_type: '3d_mesh',
    fitting_status: 'ready'
  },
  {
    id: 'wardrobe_11',
    name: 'Tailored Linen Bermuda Shorts',
    category: 'bottom',
    subcategory: 'shorts',
    color: '#cbd5e1',
    material: 'pure linen',
    pattern: 'solid',
    formality: 4,
    warmth: 2,
    seasons: ['spring', 'summer'],
    weather_tags: ['warm', 'sunny'],
    aesthetic: ['smart_casual', 'scandi'],
    brand: 'COS',
    image_url: 'https://images.unsplash.com/photo-1591195853828-11db59a44f6b?auto=format&fit=crop&w=600&q=80',
    thumbnail_url: 'https://images.unsplash.com/photo-1591195853828-11db59a44f6b?auto=format&fit=crop&w=600&q=80',
    wear_count: 6,
    favorite: false,
    asset_type: '3d_mesh',
    fitting_status: 'ready'
  },
  {
    id: 'wardrobe_12',
    name: 'Structured Grain Leather Tote Bag',
    category: 'accessory',
    subcategory: 'bags',
    color: '#334155',
    material: 'grain calfskin',
    pattern: 'solid',
    formality: 6,
    warmth: 1,
    seasons: ['all_season'],
    weather_tags: ['all_weather'],
    aesthetic: ['quiet_luxury', 'timeless'],
    brand: 'Lemaire',
    image_url: 'https://images.unsplash.com/photo-1548036328-c9fa89d128fa?auto=format&fit=crop&w=600&q=80',
    thumbnail_url: 'https://images.unsplash.com/photo-1548036328-c9fa89d128fa?auto=format&fit=crop&w=600&q=80',
    wear_count: 11,
    favorite: true,
    asset_type: '2d_image',
    fitting_status: 'unsupported'
  }
];

export const TRY_NEW_LOOK_ITEMS = CURATED_ENSEMBLES;

