/**
 * YORVYN — Fabric Material Physical Profiles (Phase 10)
 * Calibrated parameter profiles for realistic cloth simulation.
 *
 * NOTE: All profiles are configurable computational estimates based on
 * asset metadata, not claims of exact laboratory physical measurements.
 */

import { FabricPhysicsProfile, FabricProfileId } from './types';

export const FABRIC_PHYSICS_PROFILES: Record<FabricProfileId, FabricPhysicsProfile> = {
  cotton: {
    id: 'cotton',
    name: 'Cotton Jersey',
    description: 'Soft, natural draping with moderate bending resistance and subtle folds.',
    mass: 0.22, // 220 g/m² standard t-shirt / shirt cotton
    stretchStiffness: 0.88,
    bendingStiffness: 0.42,
    shearStiffness: 0.60,
    damping: 0.93,
    friction: 0.45,
    thickness: 0.0025, // 2.5 mm
    gravityMultiplier: 1.0,
    isEstimate: true
  },

  denim: {
    id: 'denim',
    name: 'Heavy Twill Denim',
    description: 'Stiffer, structured appearance with high bending resistance and defined creases.',
    mass: 0.45, // 450 g/m² heavy 14oz denim
    stretchStiffness: 0.96,
    bendingStiffness: 0.85,
    shearStiffness: 0.82,
    damping: 0.95,
    friction: 0.65,
    thickness: 0.0040, // 4.0 mm
    gravityMultiplier: 1.05,
    isEstimate: true
  },

  silk: {
    id: 'silk',
    name: 'Silk Satin',
    description: 'Lightweight, fluid appearance with low bending resistance and graceful ripples.',
    mass: 0.09, // 90 g/m² lightweight silk
    stretchStiffness: 0.82,
    bendingStiffness: 0.16,
    shearStiffness: 0.35,
    damping: 0.86,
    friction: 0.20,
    thickness: 0.0015, // 1.5 mm
    gravityMultiplier: 0.92,
    isEstimate: true
  },

  wool: {
    id: 'wool',
    name: 'Worsted Wool',
    description: 'Heavier appearance with soft, damped folds and muted swaying.',
    mass: 0.38, // 380 g/m² suiting wool
    stretchStiffness: 0.90,
    bendingStiffness: 0.58,
    shearStiffness: 0.70,
    damping: 0.97, // high damping dampens oscillation
    friction: 0.55,
    thickness: 0.0035, // 3.5 mm
    gravityMultiplier: 1.02,
    isEstimate: true
  },

  leather: {
    id: 'leather',
    name: 'Structured Leather',
    description: 'Substantial, rigid appearance with minimal stretch and strong surface definition.',
    mass: 0.52, // 520 g/m² jacket leather
    stretchStiffness: 0.98,
    bendingStiffness: 0.90,
    shearStiffness: 0.92,
    damping: 0.96,
    friction: 0.75,
    thickness: 0.0050, // 5.0 mm
    gravityMultiplier: 1.08,
    isEstimate: true
  },

  knitted: {
    id: 'knitted',
    name: 'Flexible Rib Knit',
    description: 'Elastic, flexible deformation that conforms dynamically to movement.',
    mass: 0.28, // 280 g/m² knit sweater / jersey
    stretchStiffness: 0.62, // significantly more stretch compliance
    bendingStiffness: 0.28,
    shearStiffness: 0.48,
    damping: 0.91,
    friction: 0.50,
    thickness: 0.0032, // 3.2 mm
    gravityMultiplier: 0.98,
    isEstimate: true
  },

  knitwear: {
    id: 'knitwear',
    name: 'Flexible Rib Knit',
    description: 'Elastic, flexible deformation that conforms dynamically to movement.',
    mass: 0.28,
    stretchStiffness: 0.62,
    bendingStiffness: 0.28,
    shearStiffness: 0.48,
    damping: 0.91,
    friction: 0.50,
    thickness: 0.0032,
    gravityMultiplier: 0.98,
    isEstimate: true
  },

  synthetic: {
    id: 'synthetic',
    name: 'Technical Synthetic',
    description: 'Lightweight performance fabric with crisp drape and quick deformation recovery.',
    mass: 0.18, // 180 g/m²
    stretchStiffness: 0.85,
    bendingStiffness: 0.48,
    shearStiffness: 0.55,
    damping: 0.92,
    friction: 0.35,
    thickness: 0.0020, // 2.0 mm
    gravityMultiplier: 0.98,
    isEstimate: true
  },

  linen: {
    id: 'linen',
    name: 'Crisp Natural Linen',
    description: 'Airy natural weave with firm creases, distinct folding lines, and breathable body.',
    mass: 0.24, // 240 g/m²
    stretchStiffness: 0.90,
    bendingStiffness: 0.62,
    shearStiffness: 0.68,
    damping: 0.94,
    friction: 0.55,
    thickness: 0.0028, // 2.8 mm
    gravityMultiplier: 1.02,
    isEstimate: true
  }
};

export class FabricMaterialProfile {
  /**
   * Retrieves the physics profile for the given fabric type.
   * Defaults to 'cotton' if unknown or unspecified.
   */
  public static getProfile(fabricId?: string): FabricPhysicsProfile {
    if (!fabricId) return FABRIC_PHYSICS_PROFILES.cotton;
    const normalized = fabricId.toLowerCase().trim() as FabricProfileId;
    return FABRIC_PHYSICS_PROFILES[normalized] || FABRIC_PHYSICS_PROFILES.cotton;
  }

  /**
   * Returns all available fabric profiles for selection UI.
   */
  public static listProfiles(): FabricPhysicsProfile[] {
    return Object.values(FABRIC_PHYSICS_PROFILES);
  }

  /**
   * Checks if an ID corresponds to a recognized fabric profile.
   */
  public static isValidProfile(fabricId: string): fabricId is FabricProfileId {
    return fabricId in FABRIC_PHYSICS_PROFILES;
  }
}

