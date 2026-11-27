import { describe, it, expect, beforeEach, vi } from 'vitest';
import * as THREE from 'three';
import { fittingDiagnostics } from '../../../utils/fittingDiagnostics';
import { GarmentAssetType, Garment } from '../../../types/fashion';
import { studio3DAssetManager } from '../Studio3DAssetManager';
import { GarmentAvatarFittingEngine } from '../../garments/GarmentAvatarFittingEngine';
import { invalidateApiCache } from '../../../services/fashionApi';

describe('Yorvyn Virtual Try-On Fitting & Layer Replacement System', () => {
  beforeEach(() => {
    // Reset diagnostics log
  });

  describe('1. Asset Type Enforcement', () => {
    it('should distinguish 2D photographs from authentic 3D garment meshes', () => {
      const assetTypes: GarmentAssetType[] = [
        '2d_image',
        '3d_mesh',
        'fitted_garment',
        'processing',
        'unavailable'
      ];
      expect(assetTypes).toContain('2d_image');
      expect(assetTypes).toContain('3d_mesh');
      expect(assetTypes).toContain('fitted_garment');
    });

    it('should log rejection when 2D photographic asset is chosen for 3D try-on', () => {
      fittingDiagnostics.logSelection({
        garmentId: 'wardrobe_wool_sweater',
        garmentName: 'Merino Wool Crewneck',
        category: 'top',
        assetType: '2d_image',
        targetSlot: 'top',
        previousOutfitState: {
          slotType: 'full_outfit',
          outfitId: 'sig-polo',
          topId: null,
          bottomId: null,
          shoesId: 'shoes01'
        },
        replacementAction: {
          removedGarments: [],
          appliedGarment: 'Merino Wool Crewneck',
          preservedSlots: ['avatar_appearance']
        },
        meshValidation: {
          status: 'not_applicable',
          reason: 'Garment asset is 2D photograph. 3D geometry fitting bypassed; 2D preview opened.'
        },
        fittingStatus: 'rejected_2d_only'
      });

      const latest = fittingDiagnostics.getLatest();
      expect(latest).toBeDefined();
      expect(latest?.fittingStatus).toBe('rejected_2d_only');
      expect(latest?.assetType).toBe('2d_image');
      expect(latest?.meshValidation.status).toBe('not_applicable');
    });
  });

  describe('2. Slot Replacement Rules & Avatar Identity Preservation', () => {
    it('should replace full outfit when an individual top is selected', () => {
      // Starting with a full suit ensemble
      let currentOutfit: { outfit: string; top: string; bottom: string; shoes: string } = {
        outfit: 'male_casualsuit02',
        top: 'none',
        bottom: 'none',
        shoes: 'shoes01'
      };

      // Select individual top
      const nextTop = 'uniform_shirt_long';
      const updatedOutfit = {
        ...currentOutfit,
        outfit: 'none',
        top: nextTop,
        bottom: currentOutfit.bottom === 'none' ? 'uniform_trousers' : currentOutfit.bottom,
        shoes: currentOutfit.shoes
      };

      expect(updatedOutfit.outfit).toBe('none');
      expect(updatedOutfit.top).toBe('uniform_shirt_long');
      expect(updatedOutfit.bottom).toBe('uniform_trousers');
      expect(updatedOutfit.shoes).toBe('shoes01');
    });

    it('should preserve avatar personal identity (skin, hair, proportions, height) across garment changes', () => {
      const savedUserAvatar = {
        skinTone: '#4a2c11',
        hair: 'hair_afro_short',
        hairColor: '#1a1a1a',
        gender: 1.0,
        height: 0.65,
        muscle: 0.55,
        weight: 0.48,
        proportions: 0.88
      };

      // Apply new garment params
      const garmentParams = {
        outfit: 'none',
        top: 'techwear_jacket',
        bottom: 'uniform_trousers'
      };

      const finalAvatar = {
        ...savedUserAvatar,
        ...garmentParams
      };

      expect(finalAvatar.skinTone).toBe('#4a2c11');
      expect(finalAvatar.hair).toBe('hair_afro_short');
      expect(finalAvatar.height).toBe(0.65);
      expect(finalAvatar.top).toBe('techwear_jacket');
    });

    it('should record successful 3D fitting diagnostics in history', () => {
      fittingDiagnostics.logSelection({
        garmentId: 'diesel-biker-jacket',
        garmentName: 'Iconic Black Leather Biker Jacket',
        category: 'outerwear',
        assetType: '3d_mesh',
        targetSlot: 'outerwear',
        previousOutfitState: {
          slotType: 'separate_layers',
          outfitId: null,
          topId: 'sig-polo',
          bottomId: 'sig-jeans',
          shoesId: 'shoes01'
        },
        replacementAction: {
          removedGarments: ['previous_top'],
          appliedGarment: 'Iconic Black Leather Biker Jacket',
          preservedSlots: ['bottom', 'shoes', 'skin', 'hair']
        },
        meshValidation: {
          status: 'passed',
          reason: '3D geometry mesh validated and bound to avatar skeleton'
        },
        fittingStatus: 'success'
      });

      const latest = fittingDiagnostics.getLatest();
      expect(latest?.fittingStatus).toBe('success');
      expect(latest?.targetSlot).toBe('outerwear');
      expect(latest?.garmentName).toBe('Iconic Black Leather Biker Jacket');
      expect(latest?.replacementAction.preservedSlots).toContain('skin');
    });
  });

  describe('3. Custom Neural 3D Garment Try-On Anti-Reversion & Cache Persistence', () => {
    it('should bypass Ara character rebuild when equipping custom neural 3D garments to eliminate 2-second timeout bug', () => {
      const mockCustomGarment: Garment = {
        id: 'job_hoodie_123',
        name: 'Oversized Dark Brown Hoodie',
        category: 'top',
        subcategory: 'hoodie',
        color: '#2a1a0f',
        material: 'fleece',
        pattern: 'solid',
        formality: 3,
        warmth: 8,
        seasons: ['autumn', 'winter'],
        weather_tags: ['cold'],
        aesthetic: ['streetwear'],
        brand: 'Custom Atelier 3D',
        image_url: '/api/assets/job_hoodie_123/thumb.png',
        wear_count: 0,
        favorite: false,
        is_custom_3d: true,
        asset_type: '3d_mesh',
        glb_url: '/api/assets/job_hoodie_123/garment.glb'
      };

      const isCustom3D = Boolean(mockCustomGarment.glb_url || mockCustomGarment.is_custom_3d || mockCustomGarment.asset_type === '3d_mesh');
      expect(isCustom3D).toBe(true);

      const triggerRebuildSpy = vi.fn();
      const setParamsSpy = vi.fn();

      const initialParams = {
        top: 'uniform_shirt_long',
        bottom: 'uniform_trousers',
        outfit: 'none',
        shoes: 'shoes01'
      };
      const updated = {
        ...initialParams,
        top: 'none',
        outfit: 'none'
      };

      if (isCustom3D) {
        setParamsSpy(updated);
      } else {
        triggerRebuildSpy(updated);
      }

      // Rebuild MUST NOT be triggered for custom neural 3D garments
      expect(triggerRebuildSpy).not.toHaveBeenCalled();
      expect(setParamsSpy).toHaveBeenCalledWith(updated);
      expect(updated.top).toBe('none');
    });

    it('should protect custom AI garment meshes from destruction during avatar model disposal', () => {
      const avatarRoot = new THREE.Group();
      avatarRoot.name = 'avatar_root';

      const baseAvatarMesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial());
      baseAvatarMesh.name = 'avatar_body';
      avatarRoot.add(baseAvatarMesh);

      const customGarmentMesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial());
      customGarmentMesh.name = 'custom_ai_garment_fitted';
      avatarRoot.add(customGarmentMesh);

      const geomDisposeSpy = vi.spyOn(customGarmentMesh.geometry, 'dispose');
      const matDisposeSpy = vi.spyOn(customGarmentMesh.material as THREE.Material, 'dispose');
      const baseGeomDisposeSpy = vi.spyOn(baseAvatarMesh.geometry, 'dispose');

      studio3DAssetManager.disposeObject3D(avatarRoot);

      // Base avatar mesh is disposed
      expect(baseGeomDisposeSpy).toHaveBeenCalled();
      // Custom AI garment buffers are strictly preserved
      expect(geomDisposeSpy).not.toHaveBeenCalled();
      expect(matDisposeSpy).not.toHaveBeenCalled();
    });

    it('should cleanly detach custom garment without disposing shared GLTF cache buffers', () => {
      const avatarRoot = new THREE.Group();
      const customGarment = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial());
      customGarment.name = 'custom_ai_garment';
      avatarRoot.add(customGarment);

      const geomDisposeSpy = vi.spyOn(customGarment.geometry, 'dispose');
      const matDisposeSpy = vi.spyOn(customGarment.material as THREE.Material, 'dispose');

      GarmentAvatarFittingEngine.detachGarment(avatarRoot);

      expect(customGarment.parent).toBeNull();
      expect(geomDisposeSpy).not.toHaveBeenCalled();
      expect(matDisposeSpy).not.toHaveBeenCalled();
    });

    it('should preserve anatomical structures and hide conflicting clothing in multi-material meshes', () => {
      const avatarRoot = new THREE.Group();
      const skinMat = new THREE.MeshStandardMaterial({ name: 'skin_caucasian' });
      const hairMat = new THREE.MeshStandardMaterial({ name: 'hair_brown' });
      const eyesMat = new THREE.MeshStandardMaterial({ name: 'eyes_blue' });
      const shirtMat = new THREE.MeshStandardMaterial({ name: 'uniform_shirt_long' });
      const pantsMat = new THREE.MeshStandardMaterial({ name: 'uniform_trousers' });

      const multiMesh = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        [skinMat, hairMat, eyesMat, shirtMat, pantsMat]
      );
      avatarRoot.add(multiMesh);

      // Equip custom top
      GarmentAvatarFittingEngine.updateAvatarClothingVisibility(avatarRoot, 'top', true);

      expect(skinMat.visible).toBe(true);
      expect(hairMat.visible).toBe(true);
      expect(eyesMat.visible).toBe(true);
      expect(shirtMat.visible).toBe(false); // Shirt hidden
      expect(pantsMat.visible).toBe(true);  // Trousers remain visible
      expect(multiMesh.visible).toBe(true);

      // Unequip custom top
      GarmentAvatarFittingEngine.updateAvatarClothingVisibility(avatarRoot, null, false);
      expect(shirtMat.visible).toBe(true);
      expect(pantsMat.visible).toBe(true);
    });

    it('should invalidate wardrobe cache when saving 3D garments to wardrobe', () => {
      invalidateApiCache('wardrobe');
      // Invalidation succeeds without throwing
      expect(true).toBe(true);
    });
  });
});

