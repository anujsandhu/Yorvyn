/**
 * YORVYN — Versioned Garment & Accessory Taxonomy & Capability Matrix (Phase 17.5)
 *
 * Explicit registry declaring supported categories, subcategories, fitting strategies,
 * attachment bones, conflict rules, and honest capability verification states.
 * Categories never inherit VERIFIED status simply because a generic mesh loader accepts them.
 */

export const TAXONOMY_VERSION = '17.5.0';

export type MajorCategoryDomain =
  | 'upper_body'
  | 'lower_body'
  | 'full_body'
  | 'footwear'
  | 'headwear'
  | 'accessory';

export type FittingStrategyType =
  | 'upper_body'
  | 'lower_body'
  | 'full_body'
  | 'footwear'
  | 'headwear'
  | 'rigid_accessory'
  | 'soft_accessory';

export type CategoryCapabilityState =
  | 'DECLARED'
  | 'AVAILABLE'
  | 'EXECUTABLE'
  | 'VERIFIED'
  | 'DEGRADED'
  | 'UNAVAILABLE';

export type LayerSlotType =
  | 'underwear'
  | 'top'
  | 'bottom'
  | 'outerwear'
  | 'dress'
  | 'footwear'
  | 'headwear'
  | 'belt'
  | 'bag'
  | 'jewelry'
  | 'eyewear'
  | 'neckwear'
  | 'gloves';

export interface CategoryTaxonomyEntry {
  id: string;
  label: string;
  domain: MajorCategoryDomain;
  subcategories: string[];
  fittingStrategy: FittingStrategyType;
  layerSlot: LayerSlotType;
  layerPriority: number;
  conflictsWith: LayerSlotType[];
  targetBone: string;
  capabilityState: CategoryCapabilityState;
  prerequisites: string[];
  fallbackStrategy: FittingStrategyType | 'reject_with_diagnostic';
  limitations: string;
}

export const GARMENT_CATEGORY_MATRIX: Record<string, CategoryTaxonomyEntry> = {
  tshirt: {
    id: 'tshirt',
    label: 'T-Shirts & Tops',
    domain: 'upper_body',
    subcategories: ['tshirt', 'polo', 'shirt', 'formal_shirt', 'blouse', 'crop_top', 'tank_top', 'vest'],
    fittingStrategy: 'upper_body',
    layerSlot: 'top',
    layerPriority: 20,
    conflictsWith: ['dress'],
    targetBone: 'Spine2',
    capabilityState: 'VERIFIED',
    prerequisites: ['valid_mesh', 'torso_or_upper_landmarks'],
    fallbackStrategy: 'upper_body',
    limitations: 'Assumes canonical Y-up neutral A-pose/T-pose rest alignment.',
  },
  hoodie: {
    id: 'hoodie',
    label: 'Hoodies & Sweaters',
    domain: 'upper_body',
    subcategories: ['hoodie', 'sweatshirt', 'sweater', 'cardigan', 'pullover'],
    fittingStrategy: 'upper_body',
    layerSlot: 'top',
    layerPriority: 22,
    conflictsWith: ['dress'],
    targetBone: 'Spine2',
    capabilityState: 'VERIFIED',
    prerequisites: ['valid_mesh', 'torso_or_upper_landmarks'],
    fallbackStrategy: 'upper_body',
    limitations: 'Hood placement preserves collar continuity; folded rear hoods without explicit hood tags stay attached to collar.',
  },
  jacket: {
    id: 'jacket',
    label: 'Jackets & Outerwear',
    domain: 'upper_body',
    subcategories: ['jacket', 'denim_jacket', 'leather_jacket', 'blazer', 'coat', 'trench_coat', 'parka', 'raincoat', 'waistcoat'],
    fittingStrategy: 'upper_body',
    layerSlot: 'outerwear',
    layerPriority: 30,
    conflictsWith: [],
    targetBone: 'Spine2',
    capabilityState: 'VERIFIED',
    prerequisites: ['valid_mesh', 'torso_or_upper_landmarks'],
    fallbackStrategy: 'upper_body',
    limitations: 'Structured lapels/buttons are preserved proportionally; dynamic inner-outerwear collision is bounded.',
  },
  traditional_upper: {
    id: 'traditional_upper',
    label: 'Kurtas, Tunics & Sherwanis',
    domain: 'upper_body',
    subcategories: ['tunic', 'kurta', 'sherwani'],
    fittingStrategy: 'upper_body',
    layerSlot: 'top',
    layerPriority: 24,
    conflictsWith: ['dress'],
    targetBone: 'Spine2',
    capabilityState: 'EXECUTABLE',
    prerequisites: ['valid_mesh', 'torso_and_hip_landmarks'],
    fallbackStrategy: 'upper_body',
    limitations: 'Extended hem drape below mid-thigh relies on hip-to-knee correspondence without bespoke slit physics.',
  },
  trousers: {
    id: 'trousers',
    label: 'Trousers, Jeans & Shorts',
    domain: 'lower_body',
    subcategories: ['jeans', 'straight_trousers', 'slim_trousers', 'wide_leg_trousers', 'formal_pants', 'joggers', 'sweatpants', 'shorts', 'cargo_pants', 'leggings'],
    fittingStrategy: 'lower_body',
    layerSlot: 'bottom',
    layerPriority: 18,
    conflictsWith: ['dress'],
    targetBone: 'Hips',
    capabilityState: 'VERIFIED',
    prerequisites: ['valid_mesh', 'hips_and_leg_landmarks'],
    fallbackStrategy: 'lower_body',
    limitations: 'Wide-leg and flared cuffs use binned centerline mapping relative to avatar leg bones.',
  },
  skirt: {
    id: 'skirt',
    label: 'Skirts',
    domain: 'lower_body',
    subcategories: ['skirt', 'mini_skirt', 'midi_skirt', 'maxi_skirt'],
    fittingStrategy: 'lower_body',
    layerSlot: 'bottom',
    layerPriority: 19,
    conflictsWith: ['dress'],
    targetBone: 'Hips',
    capabilityState: 'EXECUTABLE',
    prerequisites: ['valid_mesh', 'hips_landmarks'],
    fallbackStrategy: 'lower_body',
    limitations: 'Dynamic pleat self-collision during fast running poses uses bounded XPBD substeps.',
  },
  traditional_lower: {
    id: 'traditional_lower',
    label: 'Dhoti, Salwar & Patiala',
    domain: 'lower_body',
    subcategories: ['dhoti', 'salwar', 'patiala'],
    fittingStrategy: 'lower_body',
    layerSlot: 'bottom',
    layerPriority: 19,
    conflictsWith: ['dress'],
    targetBone: 'Hips',
    capabilityState: 'DECLARED',
    prerequisites: ['valid_mesh', 'hips_and_leg_landmarks'],
    fallbackStrategy: 'lower_body',
    limitations: 'Pleat-rich traditional lower wear lacks dedicated multi-fold pleat templates.',
  },
  dress: {
    id: 'dress',
    label: 'Dresses, Gowns & Jumpsuits',
    domain: 'full_body',
    subcategories: ['dress', 'gown', 'jumpsuit', 'romper', 'overalls', 'bodysuit', 'anarkali', 'layered_outfit'],
    fittingStrategy: 'full_body',
    layerSlot: 'dress',
    layerPriority: 21,
    conflictsWith: ['top', 'bottom'],
    targetBone: 'Spine2',
    capabilityState: 'EXECUTABLE',
    prerequisites: ['valid_mesh', 'torso_hips_and_leg_landmarks'],
    fallbackStrategy: 'full_body',
    limitations: 'Long flowing gowns may experience knee poke-through on extreme sitting poses without high-step cloth substeps.',
  },
  traditional_drape: {
    id: 'traditional_drape',
    label: 'Sarees & Lehengas',
    domain: 'full_body',
    subcategories: ['saree', 'lehenga'],
    fittingStrategy: 'full_body',
    layerSlot: 'dress',
    layerPriority: 21,
    conflictsWith: ['top', 'bottom'],
    targetBone: 'Spine2',
    capabilityState: 'DECLARED',
    prerequisites: ['multi_component_drape_mesh'],
    fallbackStrategy: 'full_body',
    limitations: 'Unpinned saree pallu wrap physics requires dedicated shoulder-anchor simulation.',
  },
  footwear: {
    id: 'footwear',
    label: 'Footwear',
    domain: 'footwear',
    subcategories: ['sneakers', 'formal_shoes', 'boots', 'sandals', 'slippers', 'heels', 'flats', 'loafers', 'sports_footwear', 'shoes'],
    fittingStrategy: 'footwear',
    layerSlot: 'footwear',
    layerPriority: 15,
    conflictsWith: [],
    targetBone: 'LeftFoot',
    capabilityState: 'EXECUTABLE',
    prerequisites: ['valid_mesh', 'foot_landmarks'],
    fallbackStrategy: 'reject_with_diagnostic',
    limitations: 'Single-mesh paired shoes are aligned around ankle center and grounded cleanly; heel arch tilt is rigid.',
  },
  headwear: {
    id: 'headwear',
    label: 'Headwear',
    domain: 'headwear',
    subcategories: ['cap', 'hat', 'beanie', 'helmet', 'turban', 'headscarf', 'hood'],
    fittingStrategy: 'headwear',
    layerSlot: 'headwear',
    layerPriority: 40,
    conflictsWith: [],
    targetBone: 'Head',
    capabilityState: 'EXECUTABLE',
    prerequisites: ['valid_mesh', 'head_landmarks'],
    fallbackStrategy: 'rigid_accessory',
    limitations: 'Hair volume deformation under tight headwear is approximated via crown clearance.',
  },
  bag: {
    id: 'bag',
    label: 'Bags & Backpacks',
    domain: 'accessory',
    subcategories: ['backpack', 'handbag', 'shoulder_bag', 'crossbody_bag'],
    fittingStrategy: 'rigid_accessory',
    layerSlot: 'bag',
    layerPriority: 45,
    conflictsWith: [],
    targetBone: 'Spine2',
    capabilityState: 'EXECUTABLE',
    prerequisites: ['valid_mesh', 'shoulder_or_hand_landmarks'],
    fallbackStrategy: 'rigid_accessory',
    limitations: 'Backpacks attach to Spine2/UpperBack; handheld bags attach to RightHand without finger grip IK.',
  },
  belt: {
    id: 'belt',
    label: 'Belts',
    domain: 'accessory',
    subcategories: ['belt'],
    fittingStrategy: 'rigid_accessory',
    layerSlot: 'belt',
    layerPriority: 35,
    conflictsWith: [],
    targetBone: 'Hips',
    capabilityState: 'EXECUTABLE',
    prerequisites: ['valid_mesh', 'waist_landmarks'],
    fallbackStrategy: 'rigid_accessory',
    limitations: 'Circular belt meshes scale uniformly to waist X/Z envelope + clearance.',
  },
  eyewear: {
    id: 'eyewear',
    label: 'Glasses & Sunglasses',
    domain: 'accessory',
    subcategories: ['glasses', 'sunglasses'],
    fittingStrategy: 'rigid_accessory',
    layerSlot: 'eyewear',
    layerPriority: 42,
    conflictsWith: [],
    targetBone: 'Head',
    capabilityState: 'EXECUTABLE',
    prerequisites: ['valid_mesh', 'head_landmarks'],
    fallbackStrategy: 'rigid_accessory',
    limitations: 'Nose-bridge alignment is estimated from Head bone + anatomical face forward offset.',
  },
  jewelry: {
    id: 'jewelry',
    label: 'Watches, Bracelets & Necklaces',
    domain: 'accessory',
    subcategories: ['watch', 'bracelet', 'necklace', 'ring', 'earrings'],
    fittingStrategy: 'rigid_accessory',
    layerSlot: 'jewelry',
    layerPriority: 44,
    conflictsWith: [],
    targetBone: 'LeftHand',
    capabilityState: 'EXECUTABLE',
    prerequisites: ['valid_mesh', 'wrist_or_neck_landmarks'],
    fallbackStrategy: 'rigid_accessory',
    limitations: 'Watch/bracelet anchors at wrist; necklace anchors at neck base; rings/earrings remain AVAILABLE/coarse.',
  },
  soft_accessory: {
    id: 'soft_accessory',
    label: 'Scarves, Ties & Gloves',
    domain: 'accessory',
    subcategories: ['scarf', 'gloves', 'tie', 'bow_tie', 'hair_accessory'],
    fittingStrategy: 'soft_accessory',
    layerSlot: 'neckwear',
    layerPriority: 38,
    conflictsWith: [],
    targetBone: 'Neck',
    capabilityState: 'EXECUTABLE',
    prerequisites: ['valid_mesh', 'neck_or_hand_landmarks'],
    fallbackStrategy: 'rigid_accessory',
    limitations: 'Individual finger articulation for gloves is approximated when avatar lacks finger bones.',
  },
};

const ALIAS_MAP: Record<string, string> = {
  top: 'tshirt',
  tops: 'tshirt',
  shirt: 'tshirt',
  shirts: 'tshirt',
  blouse: 'tshirt',
  polo: 'tshirt',
  tee: 'tshirt',
  sweater: 'hoodie',
  sweatshirt: 'hoodie',
  cardigan: 'hoodie',
  pullover: 'hoodie',
  outerwear: 'jacket',
  coat: 'jacket',
  blazer: 'jacket',
  trench_coat: 'jacket',
  parka: 'jacket',
  denim_jacket: 'jacket',
  leather_jacket: 'jacket',
  kurta: 'traditional_upper',
  sherwani: 'traditional_upper',
  tunic: 'traditional_upper',
  bottom: 'trousers',
  bottoms: 'trousers',
  pants: 'trousers',
  jeans: 'trousers',
  shorts: 'trousers',
  joggers: 'trousers',
  leggings: 'trousers',
  skirts: 'skirt',
  mini_skirt: 'skirt',
  midi_skirt: 'skirt',
  maxi_skirt: 'skirt',
  dhoti: 'traditional_lower',
  salwar: 'traditional_lower',
  patiala: 'traditional_lower',
  dresses: 'dress',
  dresses_and_skirts: 'dress',
  gown: 'dress',
  jumpsuit: 'dress',
  romper: 'dress',
  outfit: 'dress',
  saree: 'traditional_drape',
  lehenga: 'traditional_drape',
  shoes: 'footwear',
  sneakers: 'footwear',
  boots: 'footwear',
  heels: 'footwear',
  sandals: 'footwear',
  hat: 'headwear',
  cap: 'headwear',
  beanie: 'headwear',
  helmet: 'headwear',
  turban: 'headwear',
  bags: 'bag',
  backpack: 'bag',
  handbag: 'bag',
  shoulder_bag: 'bag',
  crossbody_bag: 'bag',
  glasses: 'eyewear',
  sunglasses: 'eyewear',
  watch: 'jewelry',
  bracelet: 'jewelry',
  necklace: 'jewelry',
  ring: 'jewelry',
  earrings: 'jewelry',
  scarf: 'soft_accessory',
  tie: 'soft_accessory',
  bow_tie: 'soft_accessory',
  gloves: 'soft_accessory',
  accessory: 'jewelry',
};

export class GarmentCategoryRegistry {
  public static resolve(category?: string | null, subcategory?: string | null): CategoryTaxonomyEntry {
    const rawSub = (subcategory || '').trim().toLowerCase();
    const rawCat = (category || 'tshirt').trim().toLowerCase();

    if (rawSub && GARMENT_CATEGORY_MATRIX[rawSub]) {
      return GARMENT_CATEGORY_MATRIX[rawSub];
    }
    if (rawSub && ALIAS_MAP[rawSub]) {
      return GARMENT_CATEGORY_MATRIX[ALIAS_MAP[rawSub]];
    }
    if (GARMENT_CATEGORY_MATRIX[rawCat]) {
      return GARMENT_CATEGORY_MATRIX[rawCat];
    }
    if (ALIAS_MAP[rawCat]) {
      return GARMENT_CATEGORY_MATRIX[ALIAS_MAP[rawCat]];
    }
    for (const entry of Object.values(GARMENT_CATEGORY_MATRIX)) {
      if (entry.subcategories.includes(rawSub) || entry.subcategories.includes(rawCat)) {
        return entry;
      }
    }
    return GARMENT_CATEGORY_MATRIX.tshirt;
  }

  public static listCapabilities(): CategoryTaxonomyEntry[] {
    return Object.values(GARMENT_CATEGORY_MATRIX);
  }
}
