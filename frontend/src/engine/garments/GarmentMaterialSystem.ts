/**
 * YORVYN — Garment Material System & Fabric Shading Profiles
 * Generates physically based material configurations for fashion textiles.
 */

export type FabricType = 'cotton' | 'denim' | 'leather' | 'silk' | 'wool' | 'techwear' | 'linen';

export interface FabricMaterialConfig {
  name: string;
  color: string;
  roughness: number;
  metalness: number;
  clearcoat?: number;
  clearcoatRoughness?: number;
  sheen?: number;
  doubleSided: boolean;
  alphaMode: 'opaque' | 'mask' | 'blend';
  alphaCutoff?: number;
}

export class GarmentMaterialSystem {
  public static getFabricProfile(type: FabricType, baseColor: string = '#ffffff'): FabricMaterialConfig {
    switch (type) {
      case 'cotton':
        return {
          name: 'Cotton Jersey',
          color: baseColor,
          roughness: 0.75,
          metalness: 0.0,
          doubleSided: true,
          alphaMode: 'opaque'
        };

      case 'denim':
        return {
          name: 'Twill Denim',
          color: baseColor,
          roughness: 0.65,
          metalness: 0.02,
          doubleSided: true,
          alphaMode: 'opaque'
        };

      case 'leather':
        return {
          name: 'Nappa Leather',
          color: baseColor,
          roughness: 0.32,
          metalness: 0.08,
          clearcoat: 0.45,
          clearcoatRoughness: 0.15,
          doubleSided: true,
          alphaMode: 'opaque'
        };

      case 'silk':
        return {
          name: 'Silk Satin',
          color: baseColor,
          roughness: 0.28,
          metalness: 0.05,
          sheen: 0.85,
          doubleSided: true,
          alphaMode: 'opaque'
        };

      case 'wool':
        return {
          name: 'Worsted Wool',
          color: baseColor,
          roughness: 0.85,
          metalness: 0.0,
          doubleSided: true,
          alphaMode: 'opaque'
        };

      case 'techwear':
        return {
          name: 'Ripstop Technical Nylon',
          color: baseColor,
          roughness: 0.42,
          metalness: 0.12,
          clearcoat: 0.25,
          doubleSided: true,
          alphaMode: 'opaque'
        };

      case 'linen':
      default:
        return {
          name: 'Natural Linen',
          color: baseColor,
          roughness: 0.70,
          metalness: 0.0,
          doubleSided: true,
          alphaMode: 'opaque'
        };
    }
  }
}

