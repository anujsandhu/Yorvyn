/**
 * YORVYN — Garment Layer Manager & Outfit State Machine
 * Enforces layering rules, replaces conflicting garments, and coordinates selective skin visibility.
 */

export type GarmentLayerType = 'underwear' | 'bottom' | 'top' | 'outfit' | 'outerwear' | 'shoes' | 'accessory';

export interface GarmentLayerSpec {
  id: string;
  name: string;
  layerType: GarmentLayerType;
  layerIndex: number; // 0: Underwear, 1: Bottom, 2: Top, 3: Outfit, 4: Outerwear, 5: Shoes
  hidesSkin: boolean;
  occludesLowerLayers?: GarmentLayerType[];
}

export interface LayerManagerOutfitState {
  underwear?: GarmentLayerSpec;
  bottom?: GarmentLayerSpec;
  top?: GarmentLayerSpec;
  outfit?: GarmentLayerSpec;
  outerwear?: GarmentLayerSpec;
  shoes?: GarmentLayerSpec;
  accessories: GarmentLayerSpec[];
}

export class GarmentLayerManager {
  /**
   * Applies a new garment and enforces intelligent replacement rules:
   * - Equipping an 'outfit' (suit/dress) replaces separate 'top' and 'bottom'.
   * - Equipping a separate 'top' or 'bottom' clears the full 'outfit'.
   * - 'underwear' NEVER hides body skin.
   * - Removing all clothing retains 'underwear' (or bare mannequin).
   */
  public static applyGarment(
    current: LayerManagerOutfitState,
    garment: GarmentLayerSpec
  ): LayerManagerOutfitState {
    const next: LayerManagerOutfitState = {
      ...current,
      accessories: current.accessories ? [...current.accessories] : []
    };

    switch (garment.layerType) {
      case 'outfit':
        // Full outfit replaces separate top and bottom
        next.outfit = garment;
        delete next.top;
        delete next.bottom;
        break;

      case 'top':
        // Equipping separate top removes conflicting full outfit
        next.top = garment;
        delete next.outfit;
        break;

      case 'bottom':
        // Equipping separate bottom removes conflicting full outfit
        next.bottom = garment;
        delete next.outfit;
        break;

      case 'outerwear':
        next.outerwear = garment;
        break;

      case 'shoes':
        next.shoes = garment;
        break;

      case 'underwear':
        // Form-fitting underwear: NEVER hides skin
        next.underwear = { ...garment, hidesSkin: false };
        break;

      case 'accessory':
        next.accessories = next.accessories.filter(a => a.id !== garment.id);
        next.accessories.push(garment);
        break;
    }

    return next;
  }

  /**
   * Removes all outer clothing, returning the avatar to bare mannequin or underwear.
   */
  public static undressToMannequin(withUnderwear: boolean = true): LayerManagerOutfitState {
    return {
      underwear: withUnderwear
        ? {
            id: 'briefs',
            name: 'Briefs',
            layerType: 'underwear',
            layerIndex: 0,
            hidesSkin: false
          }
        : undefined,
      accessories: []
    };
  }

  /**
   * Determines whether body skin faces should be hidden for a given layer.
   * Underwear and bare mannequins NEVER hide skin.
   */
  public static shouldHideSkin(garment: GarmentLayerSpec): boolean {
    if (garment.layerType === 'underwear') return false;
    return garment.hidesSkin;
  }
}
