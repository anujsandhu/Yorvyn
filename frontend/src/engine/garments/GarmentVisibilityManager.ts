/**
 * YORVYN — Garment Visibility Manager (Phase 5)
 * Manages reversible category-aware body region visibility.
 * Ensures the base body mesh is never deleted, and dynamically restores body skin
 * whenever a garment is taken off.
 */

import * as THREE from 'three';
import { PersistentOutfitState } from './OutfitStateManager';

export class GarmentVisibilityManager {
  /**
   * Synchronizes 3D mesh visibility on the avatar model based on the active outfit state.
   * - Underwear and bare body are ALWAYS visible when undressed.
   * - Equipped outfits, tops, bottoms, and shoes are properly displayed.
   * - Skin, eyes, and hair are strictly protected and never hidden.
   */
  public static syncMeshVisibility(
    modelRoot: THREE.Object3D,
    outfit: PersistentOutfitState
  ): void {
    if (!modelRoot) return;

    modelRoot.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        const mat = Array.isArray(mesh.material) ? mesh.material[0] : mesh.material;
        const matName = (mat?.name || mesh.name || '').toLowerCase();

        const isSkin = matName.includes('skin') || matName.includes('body') || matName.includes('head') ||
          matName.includes('face') || matName.includes('arm') || matName.includes('hand') || matName.includes('leg');
        const isHair = matName.includes('hair') || matName.includes('eyebrow') || matName.includes('lash') || matName.includes('beard');
        const isEyes = matName.includes('eye');
        const isShoes = matName.includes('shoe') || matName.includes('footwear') || matName.includes('sandal') || matName.includes('boot');
        const isBottom = matName.includes('bottom') || matName.includes('pant') || matName.includes('jean') ||
          matName.includes('trouser') || matName.includes('shorts') || matName.includes('sokoto') || matName.includes('briefs') ||
          matName.includes('skirt') || matName.includes('apron') || matName.includes('loincloth') || matName.includes('wrapper');
        const isOutfit = matName.includes('outfit') || matName.includes('suit');
        const isTop = matName.includes('top') || matName.includes('shirt') || matName.includes('jacket') ||
          matName.includes('tunic') || matName.includes('sweater') || matName.includes('hoodie') || matName.includes('vest') || matName.includes('coat');

        // Absolute rule: Avatar skin, eyes, and hair are ALWAYS visible
        if (isSkin || isHair || isEyes) {
          mesh.visible = true;
          return;
        }

        // If no outfit state is provided, default to visible
        if (!outfit) {
          mesh.visible = true;
          return;
        }

        // Outfit proxy mesh visibility (e.g. elegant suit, casual suit)
        if (isOutfit) {
          mesh.visible = !!outfit.outfit;
          return;
        }

        // Top garment visibility (e.g. shirt, jacket, tank top)
        if (isTop) {
          mesh.visible = !!outfit.top && !outfit.outfit;
          return;
        }

        // Bottom garment visibility
        if (isBottom) {
          if (matName.includes('briefs')) {
            // Modesty underwear briefs: visible when wearing underwear and no pants/outfit
            mesh.visible = !!outfit.underwear && !outfit.bottom && !outfit.outfit;
          } else {
            // Trousers / shorts / skirts: visible when bottom is equipped and no full outfit
            mesh.visible = !!outfit.bottom && !outfit.outfit;
          }
          return;
        }

        // Shoes / footwear visibility
        if (isShoes) {
          mesh.visible = !!outfit.shoes;
          return;
        }

        // Accessories & default components (e.g. belts, buckles, straps): visible
        mesh.visible = true;
      }
    });
  }
}

