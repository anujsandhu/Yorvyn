/**
 * YORVYN — Master Garment-to-Avatar Fitting & Attachment Engine (Phase 5)
 * 
 * Orchestrates the full 9-step virtual try-on fitting pipeline:
 * 1. Validated asset ingestion
 * 2. Avatar skeletal & anatomical landmark extraction
 * 3. Category & subcategory identification
 * 4. Anatomical wearing position determination
 * 5. Coordinate space alignment (handling ground-relative, local, and armature spaces)
 * 6. Multi-axis anatomical contouring (neckline, shoulders, chest, waist, sleeves)
 * 7. Transform application & proportional ease scaling
 * 8. BVH collision resolution with guaranteed 3.0mm skin clearance
 * 9. Dual-mode attachment:
 *    - Skinned: BVH barycentric skin weight transfer bound to avatar skeleton
 *    - Bone-parented: Exact bone-space transformation parented to target bone (Spine2 / Hips)
 * 
 * Strict avatar preservation: protects head, face, eyes, hair, skin, hands, and feet.
 * Only hides conflicting default attire (Alex_8 suit).
 */

import * as THREE from 'three';
import { GarmentCollisionResolver, CollisionResolutionResult } from './GarmentCollisionResolver';
import { GarmentSkinningAdapter, SkinningAdaptationResult } from './GarmentSkinningAdapter';

export type GarmentCategoryType =
  | 'top'
  | 'hoodie'
  | 'outerwear'
  | 'jacket'
  | 'bottom'
  | 'pants'
  | 'trousers'
  | 'skirt'
  | 'dress'
  | 'shoes'
  | 'outfit';

export interface AvatarLandmarks {
  hipsPos: THREE.Vector3;
  spinePos: THREE.Vector3;
  spine1Pos: THREE.Vector3;
  spine2Pos: THREE.Vector3;
  neckPos: THREE.Vector3;
  headPos: THREE.Vector3;
  leftShoulderPos: THREE.Vector3;
  rightShoulderPos: THREE.Vector3;
  leftArmPos: THREE.Vector3;
  rightArmPos: THREE.Vector3;
  leftForeArmPos: THREE.Vector3;
  rightForeArmPos: THREE.Vector3;
  leftHandPos: THREE.Vector3;
  rightHandPos: THREE.Vector3;
  leftUpLegPos?: THREE.Vector3;
  rightUpLegPos?: THREE.Vector3;
  leftLegPos?: THREE.Vector3;
  rightLegPos?: THREE.Vector3;
  leftFootPos: THREE.Vector3;
  rightFootPos: THREE.Vector3;
  torsoHeight: number;
  shoulderSpan: number;
  chestWidth: number;
  chestDepth: number;
  chestCenterZ: number;
  waistWidth: number;
  hipsWidth: number;
  hipsDepth: number;
  hipsCenterZ: number;
  waistY: number;
  neckY: number;
  bodyMesh: THREE.SkinnedMesh;
  bodyGeometry: THREE.BufferGeometry;
  skeleton: THREE.Skeleton;
  parentGroup: THREE.Object3D;
}

export interface AuthoredSleeveFrame {
  origin: THREE.Vector3;
  dir: THREE.Vector3;
  right: THREE.Vector3;
  up: THREE.Vector3;
  length: number;
  maxRadius: number;
  valid: boolean;
}

export interface AuthoredLegProfile {
  crotchY: number;
  pelvisMinY: number;
  legMaxY: number;
  hipsWidth: number;
  hipsDepth: number;
  hipsCenterZ: number;
  leftCenterX: Float32Array;
  leftCenterZ: Float32Array;
  rightCenterX: Float32Array;
  rightCenterZ: Float32Array;
  numBins: number;
}

export interface GarmentGeometryLandmarks {
  boundingBox: THREE.Box3;
  minY: number;
  maxY: number;
  centerX: number;
  centerZ: number;
  torsoHeight: number;
  shoulderSpan: number;
  torsoWidth: number;
  torsoDepth: number;
  torsoCenterZ: number;
  torsoMinY: number;
  torsoMaxY: number;
  leftSleeveFrame: AuthoredSleeveFrame;
  rightSleeveFrame: AuthoredSleeveFrame;
  legProfile: AuthoredLegProfile;
  bodiceWidth: number;
  bodiceDepth: number;
  isGroundRelative: boolean;
  isHoodie: boolean;
}

export interface GarmentFittingOptions {
  category?: GarmentCategoryType | string;
  subcategory?: string;
  attachmentMode?: 'skinned' | 'bone_parented' | 'auto';
  targetBoneName?: string;
  easeTorso?: number;
  easeShoulder?: number;
  minClearanceMeters?: number;
  wireframe?: boolean;
}

export interface ExtractedComponentMesh {
  mesh: THREE.Mesh;
  name: string;
  userData: Record<string, any>;
  clonedGeometry: THREE.BufferGeometry;
  material: THREE.Material;
  semanticTag?: string;
}

export interface GarmentAvatarFitResult {
  success: boolean;
  attachedMesh: THREE.Object3D;
  attachmentType: 'skinned' | 'bone_parented';
  targetBoneOrGroup: string;
  collisionResult?: CollisionResolutionResult;
  skinningResult?: SkinningAdaptationResult;
  diagnostics: {
    garmentTorsoHeight: number;
    avatarTorsoHeight: number;
    appliedScale: [number, number, number];
    appliedOffset: [number, number, number];
    penetrationCount: number;
    maxPenetrationMm: number;
    majorPenetrationDetected?: boolean;
    resolvedVerticesCount: number;
    componentCount?: number;
    componentNames?: string[];
  };
}

export class GarmentAvatarFittingEngine {
  private static readonly DEFAULT_CLEARANCE = 0.0030; // 3.0mm
  private static readonly ATTACHED_GARMENT_NAME = 'custom_ai_garment_fitted';

  /**
   * Primary entry point: Fits and attaches any custom 3D garment asset (single-mesh or multi-component GLB hierarchy)
   * to the active avatar model.
   */
  public static fitAndAttachGarment(
    garmentSource: THREE.Object3D,
    avatarModel: THREE.Object3D,
    options: GarmentFittingOptions = {}
  ): GarmentAvatarFitResult {
    // 1. Remove any previously fitted custom garment
    this.detachGarment(avatarModel);

    // 2. Extract avatar anatomical landmarks, skeleton, and body geometry
    const avatar = this.extractAvatarLandmarks(avatarModel);
    if (!avatar) {
      throw new Error('[GarmentAvatarFittingEngine] Could not locate avatar body mesh or skeleton in model hierarchy.');
    }

    // 3. Extract all garment component meshes (compacting shared GLB vertex buffers per component)
    const extractedComponents = this.extractGarmentMeshes(garmentSource, options.wireframe);
    const isMultiComponent = extractedComponents.length > 1;
    const rawCat = (options.category || 'top').toLowerCase();
    const rawSubcat = (options.subcategory || '').toLowerCase();

    const componentHasBodice = extractedComponents.some(
      (c) => c.name === 'upper_bodice' || c.userData?.semantic_type === 'bodice'
    );
    const componentHasSkirt = extractedComponents.some(
      (c) => c.name.includes('skirt') || c.userData?.semantic_type === 'skirt'
    );

    let category: GarmentCategoryType = 'top';
    if (
      rawCat === 'skirt' ||
      rawCat === 'skirts' ||
      rawSubcat.includes('skirt') ||
      (isMultiComponent && componentHasSkirt && !componentHasBodice)
    ) {
      category = 'skirt';
    } else if (rawCat === 'bottom' || rawCat === 'bottoms' || rawCat === 'pants' || rawCat === 'trousers' || rawCat === 'jeans' || rawCat === 'shorts') {
      category = 'bottom';
    } else if (rawCat === 'dress' || rawCat === 'dresses' || rawCat === 'dresses_and_skirts') {
      category = 'dress';
    } else if (rawCat === 'outerwear' || rawCat === 'jacket' || rawCat === 'coat') {
      category = 'outerwear';
    } else if (rawCat === 'outfit') {
      category = 'outfit';
    } else {
      category = 'top';
    }

    const subcategory = rawSubcat || (category === 'top' && !isMultiComponent ? 'hoodie' : '');
    const componentHasHood = extractedComponents.some(
      (c) => c.semanticTag === 'hood' || c.name.includes('hood') || c.userData?.semantic_type === 'hood'
    );
    const isHoodie =
      componentHasHood ||
      subcategory.includes('hood') ||
      (!isMultiComponent && subcategory === 'jacket');

    // Analyze composite bounding box across all components so scales/offsets share one coherent coordinate frame
    const garmentLandmarks = this.analyzeGarmentGeometries(
      extractedComponents,
      isHoodie
    );

    const minClearance = options.minClearanceMeters ?? this.DEFAULT_CLEARANCE;
    const mode = options.attachmentMode || 'auto';
    const shouldSkin = (mode === 'skinned' || mode === 'auto') && !!avatar.skeleton;
    const isRealBodyMesh = (avatar.bodyGeometry.attributes.position?.count || 0) > 400;
    const isUpperCategory = category === 'top' || category === 'outerwear';
    const coreBodyGeo = isRealBodyMesh
      ? this.getOrBuildCoreBodyGeometry(avatar.bodyGeometry, avatar.skeleton)
      : avatar.bodyGeometry;
    const lowerOutfitCollider =
      isRealBodyMesh && isUpperCategory
        ? this.getOrBuildLowerOutfitCollider(avatarModel, avatar.bodyGeometry, avatar.waistY + 0.08)
        : null;

    if (!isMultiComponent) {
      // ── Single-Mesh Path (Preserves direct SkinnedMesh / Mesh return for backward compatibility) ──
      const primary = extractedComponents[0];
      const { transformedPositions, componentTags, appliedScale, appliedOffset } = this.applyComponentFittingTransform(
        primary.clonedGeometry,
        garmentLandmarks,
        avatar,
        category,
        isHoodie,
        options,
        primary.semanticTag
      );

      const useClearance = isRealBodyMesh ? Math.max(minClearance, 0.011) : minClearance;
      let collisionResult = GarmentCollisionResolver.resolveBodyCollisionsBVH(
        transformedPositions,
        coreBodyGeo,
        { minClearanceMeters: useClearance, stiffness: 1.0 }
      );
      if (lowerOutfitCollider && isUpperCategory) {
        const outfitPass = GarmentCollisionResolver.resolveBodyCollisionsBVH(
          collisionResult.resolvedPositions,
          lowerOutfitCollider,
          { minClearanceMeters: 0.006, stiffness: 1.0 }
        );
        collisionResult = {
          ...collisionResult,
          penetrationCount: collisionResult.penetrationCount + outfitPass.penetrationCount,
          maxPenetrationMeters: Math.max(collisionResult.maxPenetrationMeters, outfitPass.maxPenetrationMeters),
          resolvedPositions: outfitPass.resolvedPositions
        };
      }

      primary.clonedGeometry.setAttribute(
        'position',
        new THREE.BufferAttribute(collisionResult.resolvedPositions, 3)
      );
      primary.clonedGeometry.computeVertexNormals();

      let attachedMesh: THREE.Object3D;
      let attachmentType: 'skinned' | 'bone_parented';
      let targetTargetName: string;
      let skinningResult: SkinningAdaptationResult | undefined;

      if (shouldSkin) {
        skinningResult = GarmentSkinningAdapter.generateSemanticSkinWeights({
          positions: collisionResult.resolvedPositions,
          componentTags,
          skeleton: avatar.skeleton,
          landmarks: avatar,
          category,
          influencesPerVertex: 4
        });

        // For real human meshes, transfer torso core weights from arm-free coreBodyGeo so clavicles/spine match 1:1 in Idle
        if (isRealBodyMesh && coreBodyGeo.attributes.skinIndex && isUpperCategory) {
          const bvhSkin = GarmentSkinningAdapter.transferBodySkinWeightsBVH(
            collisionResult.resolvedPositions,
            coreBodyGeo,
            4
          );
          for (let v = 0; v < componentTags.length; v++) {
            const tag = componentTags[v];
            if (tag !== 'left_sleeve' && tag !== 'right_sleeve' && tag !== 'left_cuff' && tag !== 'right_cuff' && tag !== 'hood') {
              for (let k = 0; k < 4; k++) {
                skinningResult.skinIndices[v * 4 + k] = bvhSkin.skinIndices[v * 4 + k];
                skinningResult.skinWeights[v * 4 + k] = bvhSkin.skinWeights[v * 4 + k];
              }
            }
          }
        }

        primary.clonedGeometry.setAttribute(
          'skinIndex',
          new THREE.BufferAttribute(skinningResult.skinIndices, 4)
        );
        primary.clonedGeometry.setAttribute(
          'skinWeight',
          new THREE.BufferAttribute(skinningResult.skinWeights, 4)
        );

        const skinnedMesh = new THREE.SkinnedMesh(primary.clonedGeometry, primary.material);
        skinnedMesh.bind(avatar.skeleton, avatar.bodyMesh.bindMatrix);
        skinnedMesh.name = this.ATTACHED_GARMENT_NAME;
        skinnedMesh.userData = {
          ...primary.userData,
          isCustomAiGarment: true,
          componentCount: 1,
          componentNames: [primary.name]
        };
        skinnedMesh.castShadow = true;
        skinnedMesh.receiveShadow = true;
        skinnedMesh.frustumCulled = false;

        avatar.parentGroup.add(skinnedMesh);

        attachedMesh = skinnedMesh;
        attachmentType = 'skinned';
        targetTargetName = avatar.parentGroup.name || 'avatarParent';
      } else {
        const targetBoneName = options.targetBoneName || (category === 'bottom' || category === 'skirt' ? 'Hips' : 'Spine2');
        const targetBone = avatarModel.getObjectByName(targetBoneName);

        const staticMesh = new THREE.Mesh(primary.clonedGeometry, primary.material);
        staticMesh.name = this.ATTACHED_GARMENT_NAME;
        staticMesh.userData = {
          ...primary.userData,
          isCustomAiGarment: true,
          componentCount: 1,
          componentNames: [primary.name]
        };
        staticMesh.castShadow = true;
        staticMesh.receiveShadow = true;
        staticMesh.frustumCulled = false;

        if (targetBone) {
          targetBone.updateWorldMatrix(true, true);
          const invBoneMatrix = targetBone.matrixWorld.clone().invert();
          staticMesh.applyMatrix4(invBoneMatrix);
          targetBone.add(staticMesh);
          targetTargetName = targetBoneName;
        } else {
          avatar.parentGroup.add(staticMesh);
          targetTargetName = avatar.parentGroup.name;
        }

        attachedMesh = staticMesh;
        attachmentType = 'bone_parented';
      }

      this.updateAvatarClothingVisibility(avatarModel, category, true);

      return {
        success: true,
        attachedMesh,
        attachmentType,
        targetBoneOrGroup: targetTargetName,
        collisionResult,
        skinningResult,
        diagnostics: {
          garmentTorsoHeight: garmentLandmarks.torsoHeight,
          avatarTorsoHeight: avatar.torsoHeight,
          appliedScale: [appliedScale[0], appliedScale[1], appliedScale[2]],
          appliedOffset: [appliedOffset[0], appliedOffset[1], appliedOffset[2]],
          penetrationCount: collisionResult.penetrationCount,
          maxPenetrationMm: collisionResult.maxPenetrationMeters * 1000,
          majorPenetrationDetected: collisionResult.maxPenetrationMeters * 1000 > 8.0 || collisionResult.penetrationCount > 25,
          resolvedVerticesCount: primary.clonedGeometry.attributes.position.count,
          componentCount: 1,
          componentNames: [primary.name]
        }
      };
    }

    // ── Multi-Component GLB Hierarchy Path ──
    const garmentGroup = new THREE.Group();
    garmentGroup.name = this.ATTACHED_GARMENT_NAME;

    let totalPenetrationCount = 0;
    let overallMaxPenetrationMeters = 0;
    let totalClearanceWeighted = 0;
    let totalResolvedVertices = 0;
    let appliedScale: [number, number, number] = [1, 1, 1];
    let appliedOffset: [number, number, number] = [0, 0, 0];
    let totalNormalized = 0;
    let totalPruned = 0;
    const allSkinIndices: number[] = [];
    const allSkinWeights: number[] = [];
    const componentNames: string[] = [];

    const targetBoneName = options.targetBoneName || (category === 'bottom' || category === 'skirt' ? 'Hips' : 'Spine2');
    const targetBone = !shouldSkin ? avatarModel.getObjectByName(targetBoneName) : null;

    for (const comp of extractedComponents) {
      const { transformedPositions, componentTags, appliedScale: compScale, appliedOffset: compOffset } =
        this.applyComponentFittingTransform(
          comp.clonedGeometry,
          garmentLandmarks,
          avatar,
          category,
          isHoodie,
          options,
          comp.semanticTag
        );

      appliedScale = compScale;
      appliedOffset = compOffset;

      const isArmComp =
        comp.semanticTag === 'left_sleeve' ||
        comp.semanticTag === 'right_sleeve' ||
        comp.semanticTag === 'left_cuff' ||
        comp.semanticTag === 'right_cuff';
      const targetBodyGeo = isArmComp ? avatar.bodyGeometry : coreBodyGeo;
      const compClearance = isRealBodyMesh
        ? Math.max(minClearance, isArmComp ? 0.006 : 0.011)
        : minClearance;

      let compCollision = GarmentCollisionResolver.resolveBodyCollisionsBVH(
        transformedPositions,
        targetBodyGeo,
        { minClearanceMeters: compClearance, stiffness: 1.0 }
      );

      if (
        lowerOutfitCollider &&
        !isArmComp &&
        comp.semanticTag !== 'hood' &&
        isUpperCategory
      ) {
        const outfitPass = GarmentCollisionResolver.resolveBodyCollisionsBVH(
          compCollision.resolvedPositions,
          lowerOutfitCollider,
          { minClearanceMeters: 0.006, stiffness: 1.0 }
        );
        compCollision = {
          ...compCollision,
          penetrationCount: compCollision.penetrationCount + outfitPass.penetrationCount,
          maxPenetrationMeters: Math.max(compCollision.maxPenetrationMeters, outfitPass.maxPenetrationMeters),
          resolvedPositions: outfitPass.resolvedPositions
        };
      }

      comp.clonedGeometry.setAttribute(
        'position',
        new THREE.BufferAttribute(compCollision.resolvedPositions, 3)
      );
      comp.clonedGeometry.computeVertexNormals();

      const compVertCount = comp.clonedGeometry.attributes.position.count;
      totalPenetrationCount += compCollision.penetrationCount;
      overallMaxPenetrationMeters = Math.max(overallMaxPenetrationMeters, compCollision.maxPenetrationMeters);
      totalClearanceWeighted += compCollision.averageClearanceMeters * compVertCount;
      totalResolvedVertices += compVertCount;
      componentNames.push(comp.name);

      if (shouldSkin) {
        const useBodyWeightTransfer =
          isRealBodyMesh &&
          !!coreBodyGeo.attributes.skinIndex &&
          (comp.semanticTag === 'torso' ||
            comp.semanticTag === 'placket' ||
            comp.semanticTag === 'zipper' ||
            comp.semanticTag === 'collar' ||
            comp.semanticTag === 'lapel' ||
            comp.semanticTag === 'kangaroo_pocket' ||
            comp.semanticTag === 'drawstrings' ||
            (comp.semanticTag === 'waistband' && category !== 'skirt') ||
            comp.name.includes('bodice'));

        const compSkin = useBodyWeightTransfer
          ? GarmentSkinningAdapter.transferBodySkinWeightsBVH(
              compCollision.resolvedPositions,
              coreBodyGeo,
              4
            )
          : GarmentSkinningAdapter.generateSemanticSkinWeights({
              positions: compCollision.resolvedPositions,
              componentTags,
              skeleton: avatar.skeleton,
              landmarks: avatar,
              category,
              influencesPerVertex: 4
            });

        totalNormalized += compSkin.normalizedCount;
        totalPruned += compSkin.prunedCount;
        for (let idx = 0; idx < compSkin.skinIndices.length; idx++) {
          allSkinIndices.push(compSkin.skinIndices[idx]);
          allSkinWeights.push(compSkin.skinWeights[idx]);
        }

        comp.clonedGeometry.setAttribute(
          'skinIndex',
          new THREE.BufferAttribute(compSkin.skinIndices, 4)
        );
        comp.clonedGeometry.setAttribute(
          'skinWeight',
          new THREE.BufferAttribute(compSkin.skinWeights, 4)
        );

        const compSkinned = new THREE.SkinnedMesh(comp.clonedGeometry, comp.material);
        compSkinned.bind(avatar.skeleton, avatar.bodyMesh.bindMatrix);
        compSkinned.name = comp.name;
        compSkinned.userData = {
          ...comp.userData,
          isCustomAiGarment: true,
          semanticTag: comp.semanticTag
        };
        compSkinned.castShadow = true;
        compSkinned.receiveShadow = true;
        compSkinned.frustumCulled = false;

        garmentGroup.add(compSkinned);
      } else {
        const compMesh = new THREE.Mesh(comp.clonedGeometry, comp.material);
        compMesh.name = comp.name;
        compMesh.userData = {
          ...comp.userData,
          isCustomAiGarment: true,
          semanticTag: comp.semanticTag
        };
        compMesh.castShadow = true;
        compMesh.receiveShadow = true;
        compMesh.frustumCulled = false;

        garmentGroup.add(compMesh);
      }
    }

    garmentGroup.userData = {
      ...garmentSource.userData,
      isCustomAiGarment: true,
      isMultiComponent: true,
      componentCount: extractedComponents.length,
      componentNames
    };

    let attachmentType: 'skinned' | 'bone_parented';
    let targetTargetName: string;
    if (shouldSkin) {
      avatar.parentGroup.add(garmentGroup);
      attachmentType = 'skinned';
      targetTargetName = avatar.parentGroup.name || 'avatarParent';
    } else {
      if (targetBone) {
        targetBone.updateWorldMatrix(true, true);
        const invBoneMatrix = targetBone.matrixWorld.clone().invert();
        garmentGroup.applyMatrix4(invBoneMatrix);
        targetBone.add(garmentGroup);
        targetTargetName = targetBoneName;
      } else {
        avatar.parentGroup.add(garmentGroup);
        targetTargetName = avatar.parentGroup.name;
      }
      attachmentType = 'bone_parented';
    }

    const aggregatedCollision: CollisionResolutionResult = {
      penetrationCount: totalPenetrationCount,
      maxPenetrationMeters: overallMaxPenetrationMeters,
      averageClearanceMeters: totalResolvedVertices > 0 ? totalClearanceWeighted / totalResolvedVertices : 0,
      resolvedPositions: new Float32Array(0)
    };

    const aggregatedSkinning: SkinningAdaptationResult | undefined = shouldSkin
      ? {
          valid: true,
          normalizedCount: totalNormalized,
          prunedCount: totalPruned,
          skinIndices: new Uint16Array(allSkinIndices),
          skinWeights: new Float32Array(allSkinWeights)
        }
      : undefined;

    this.updateAvatarClothingVisibility(avatarModel, category, true);

    return {
      success: true,
      attachedMesh: garmentGroup,
      attachmentType,
      targetBoneOrGroup: targetTargetName,
      collisionResult: aggregatedCollision,
      skinningResult: aggregatedSkinning,
      diagnostics: {
        garmentTorsoHeight: garmentLandmarks.torsoHeight,
        avatarTorsoHeight: avatar.torsoHeight,
        appliedScale: [appliedScale[0], appliedScale[1], appliedScale[2]],
        appliedOffset: [appliedOffset[0], appliedOffset[1], appliedOffset[2]],
        penetrationCount: totalPenetrationCount,
        maxPenetrationMm: overallMaxPenetrationMeters * 1000,
        majorPenetrationDetected: overallMaxPenetrationMeters * 1000 > 8.0 || totalPenetrationCount > 25,
        resolvedVerticesCount: totalResolvedVertices,
        componentCount: extractedComponents.length,
        componentNames
      }
    };
  }

  /**
   * Detaches any equipped custom garment without destroying shared GLTF cache buffers,
   * and restores default avatar clothing visibility.
   */
  public static detachGarment(avatarModel: THREE.Object3D | null): void {
    if (!avatarModel) return;

    const toRemove: THREE.Object3D[] = [];
    avatarModel.traverse((child) => {
      if (child.name === this.ATTACHED_GARMENT_NAME || child.name === 'custom_ai_garment') {
        toRemove.push(child);
      }
    });

    toRemove.forEach((obj) => {
      obj.parent?.remove(obj);
      // NOTE: We do not call geometry.dispose() or material.dispose() on detached meshes
      // because gltf scenes in Studio3DAssetManager cache share geometries and materials.
      // Disposing them invalidates WebGL GPU buffers for all subsequent equip actions.
    });

    // Restore full default clothing visibility
    this.updateAvatarClothingVisibility(avatarModel, null, false);
  }

  /**
   * Updates clothing visibility with strict avatar body, head, hair, and face preservation.
   * Accurately supports both single-material meshes and multi-material SkinnedMeshes.
   */
  public static updateAvatarClothingVisibility(
    avatarModel: THREE.Object3D,
    customCategory: GarmentCategoryType | string | null,
    isEquipped: boolean
  ): void {
    const rawCat = (customCategory || '').toLowerCase();
    let cat: 'top' | 'bottom' | 'dress' | 'outerwear' | 'shoes' = 'top';
    if (
      rawCat === 'bottom' ||
      rawCat === 'bottoms' ||
      rawCat === 'pants' ||
      rawCat === 'trousers' ||
      rawCat === 'jeans' ||
      rawCat === 'shorts' ||
      rawCat === 'skirt' ||
      rawCat === 'skirts'
    ) {
      cat = 'bottom';
    } else if (rawCat === 'dress' || rawCat === 'dresses' || rawCat === 'dresses_and_skirts' || rawCat === 'outfit') {
      cat = 'dress';
    } else if (rawCat === 'outerwear' || rawCat === 'jacket' || rawCat === 'coat') {
      cat = 'outerwear';
    } else if (rawCat === 'shoes' || rawCat === 'footwear' || rawCat === 'boots') {
      cat = 'shoes';
    } else {
      cat = 'top';
    }

    const checkPartType = (matName: string) => {
      const isSkin = matName.includes('skin') || matName.includes('body') || matName.includes('head') ||
        matName.includes('face') || matName.includes('arm') || matName.includes('hand') || matName.includes('leg') ||
        matName.includes('caucasian') || matName.includes('african') || matName.includes('asian');
      const isHair = matName.includes('hair') || matName.includes('eyebrow') || matName.includes('lash') || matName.includes('beard') || matName.includes('mhair');
      const isEyes = matName.includes('eye') || matName.includes('teeth') || matName.includes('tongue');

      if (isSkin || isHair || isEyes) return 'anatomical';

      const isOutfit = matName.includes('outfit') || matName.includes('suit');
      const isBottom = matName.includes('bottom') || matName.includes('pant') || matName.includes('trouser') || matName.includes('shorts') || matName.includes('jean') || matName.includes('skirt') || matName.includes('legging');
      const isTop = !isBottom && (matName.includes('top') || matName.includes('shirt') || matName.includes('jacket') || matName.includes('hoodie') || matName.includes('uniform') || matName.includes('tee') || matName.includes('sweater') || matName.includes('knit'));
      const isShoes = matName.includes('shoe') || matName.includes('footwear') || matName.includes('boot');

      if (isOutfit) return 'outfit';
      if (isBottom) return 'bottom';
      if (isTop) return 'top';
      if (isShoes) return 'shoes';
      return 'other';
    };

    avatarModel.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const m = child as THREE.Mesh;
        if (
          m.name === this.ATTACHED_GARMENT_NAME ||
          m.name === 'custom_ai_garment' ||
          m.userData?.isCustomAiGarment ||
          m.parent?.name === this.ATTACHED_GARMENT_NAME ||
          m.parent?.userData?.isCustomAiGarment
        ) {
          return;
        }

        if (!isEquipped || !customCategory) {
          // Restore all clothing
          m.visible = true;
          if (Array.isArray(m.material)) {
            m.material.forEach((matItem) => {
              if (matItem) {
                matItem.visible = true;
                matItem.clippingPlanes = [];
                matItem.needsUpdate = true;
              }
            });
          } else if (m.material) {
            m.material.visible = true;
            m.material.clippingPlanes = [];
            m.material.needsUpdate = true;
          }
          return;
        }

        // Multi-material mesh handling
        if (Array.isArray(m.material)) {
          let hasVisibleSubmesh = false;
          m.material.forEach((matItem) => {
            if (!matItem) return;
            const matName = (matItem.name || m.name || '').toLowerCase();
            const partType = checkPartType(matName);

            if (partType === 'anatomical') {
              matItem.visible = true;
              matItem.clippingPlanes = [];
              hasVisibleSubmesh = true;
            } else if (cat === 'top' || cat === 'outerwear') {
              if (partType === 'top') {
                matItem.visible = false;
              } else if (partType === 'outfit') {
                matItem.visible = true;
                const waistPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 0.710);
                matItem.clippingPlanes = [waistPlane];
                matItem.clipShadows = true;
                hasVisibleSubmesh = true;
              } else {
                matItem.visible = true;
                matItem.clippingPlanes = [];
                hasVisibleSubmesh = true;
              }
            } else if (cat === 'bottom') {
              if (partType === 'bottom') {
                matItem.visible = false;
              } else if (partType === 'outfit') {
                matItem.visible = true;
                const waistPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -0.83);
                matItem.clippingPlanes = [waistPlane];
                matItem.clipShadows = true;
                hasVisibleSubmesh = true;
              } else {
                matItem.visible = true;
                matItem.clippingPlanes = [];
                hasVisibleSubmesh = true;
              }
            } else if (cat === 'dress') {
              if (partType === 'top' || partType === 'bottom' || partType === 'outfit') {
                matItem.visible = false;
              } else {
                matItem.visible = true;
                matItem.clippingPlanes = [];
                hasVisibleSubmesh = true;
              }
            } else if (cat === 'shoes') {
              if (partType === 'shoes') {
                matItem.visible = false;
              } else {
                matItem.visible = true;
                matItem.clippingPlanes = [];
                hasVisibleSubmesh = true;
              }
            }
            matItem.needsUpdate = true;
          });
          m.visible = hasVisibleSubmesh;
        } else if (m.material) {
          // Single material mesh handling
          const matName = (m.material.name || m.name || '').toLowerCase();
          const partType = checkPartType(matName);

          if (partType === 'anatomical') {
            m.visible = true;
            m.material.visible = true;
            m.material.clippingPlanes = [];
            return;
          }

          if (cat === 'top' || cat === 'outerwear') {
            if (partType === 'top') {
              m.visible = false;
              m.material.visible = false;
            } else if (partType === 'outfit') {
              m.visible = true;
              m.material.visible = true;
              const waistPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 0.710);
              m.material.clippingPlanes = [waistPlane];
              m.material.clipShadows = true;
              m.material.needsUpdate = true;
            } else {
              m.visible = true;
              m.material.visible = true;
            }
          } else if (cat === 'bottom') {
            if (partType === 'bottom') {
              m.visible = false;
              m.material.visible = false;
            } else if (partType === 'outfit') {
              m.visible = true;
              m.material.visible = true;
              const waistPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -0.83);
              m.material.clippingPlanes = [waistPlane];
              m.material.clipShadows = true;
              m.material.needsUpdate = true;
            } else {
              m.visible = true;
              m.material.visible = true;
            }
          } else if (cat === 'dress') {
            if (partType === 'top' || partType === 'bottom' || partType === 'outfit') {
              m.visible = false;
              m.material.visible = false;
            } else {
              m.visible = true;
              m.material.visible = true;
            }
          } else if (cat === 'shoes') {
            if (partType === 'shoes') {
              m.visible = false;
              m.material.visible = false;
            } else {
              m.visible = true;
              m.material.visible = true;
            }
          }
        }
      }
    });
  }

  /**
   * Extracts anatomical body mesh, skeleton, and key joint positions from the avatar model hierarchy.
   */
  private static extractAvatarLandmarks(avatarModel: THREE.Object3D): AvatarLandmarks | null {
    let bodyMesh: THREE.SkinnedMesh | null = null;

    // 1. Locate Alex_1 or first SkinnedMesh with body skin
    avatarModel.traverse((child) => {
      if ((child as THREE.SkinnedMesh).isSkinnedMesh) {
        const sm = child as THREE.SkinnedMesh;
        const name = (sm.name || '').toLowerCase();
        const mat = Array.isArray(sm.material) ? sm.material[0] : sm.material;
        const matName = (mat?.name || '').toLowerCase();

        if (name === 'alex_1' || matName.includes('skin') || matName.includes('body')) {
          bodyMesh = sm;
        } else if (!bodyMesh) {
          bodyMesh = sm;
        }
      }
    });

    if (!bodyMesh) return null;

    const bm = bodyMesh as THREE.SkinnedMesh;
    const skeleton = bm.skeleton;
    const bodyGeometry = bm.geometry;
    const parentGroup = bm.parent || avatarModel;

    // 2. Identify bone positions in bind pose
    const getBonePos = (names: string[]): THREE.Vector3 => {
      if (skeleton && skeleton.bones) {
        for (const name of names) {
          const lower = name.toLowerCase();
          const idx = skeleton.bones.findIndex((b) => {
            const bName = b.name.toLowerCase();
            return (
              bName === lower ||
              bName.endsWith(lower) ||
              bName.replace(/^mixamorig/, '') === lower ||
              bName.replace(/^ara_/, '') === lower
            );
          });
          if (idx >= 0) {
            if (skeleton.boneInverses && skeleton.boneInverses[idx]) {
              const inv = skeleton.boneInverses[idx].clone().invert();
              const p = new THREE.Vector3();
              const q = new THREE.Quaternion();
              const s = new THREE.Vector3();
              inv.decompose(p, q, s);
              if (p.lengthSq() > 1e-6) {
                return p;
              }
            }
            const bone = skeleton.bones[idx];
            if (bone) {
              const p = new THREE.Vector3();
              bone.getWorldPosition(p);
              if (parentGroup && (parentGroup as any).worldToLocal) {
                parentGroup.worldToLocal(p);
              }
              return p;
            }
          }
        }
      }
      for (const name of names) {
        const bone = avatarModel.getObjectByName(name);
        if (bone) {
          const p = new THREE.Vector3();
          bone.getWorldPosition(p);
          if (parentGroup && (parentGroup as any).worldToLocal) {
            parentGroup.worldToLocal(p);
          }
          return p;
        }
      }
      return new THREE.Vector3();
    };

    // Calculate anatomical height landmarks from body geometry in bind pose
    const pos = bodyGeometry.attributes.position;
    let feetY = Infinity, headY = -Infinity, hipsY = 0, hipsCount = 0, neckY = 0, neckCount = 0;

    for (let i = 0; i < pos.count; i++) {
      const y = pos.getY(i);
      const x = pos.getX(i);
      const z = pos.getZ(i);

      if (y < feetY) feetY = y;
      if (y > headY) headY = y;

      if (Math.hypot(x, z) < 0.10) {
        if (y > 0.70 && y < 0.90) {
          hipsY += y;
          hipsCount++;
        }
        if (y > 1.20 && y < 1.35) {
          neckY += y;
          neckCount++;
        }
      }
    }

    const hipsPos = getBonePos(['Hips', 'pelvis']);
    const spinePos = getBonePos(['Spine', 'spine_01']);
    const spine1Pos = getBonePos(['Spine1', 'spine_02']);
    const spine2Pos = getBonePos(['Spine2', 'spine_03', 'chest']);
    const neckPos = getBonePos(['Neck']);
    const headPos = getBonePos(['Head']);
    const leftShoulderPos = getBonePos(['LeftShoulder', 'clavicle_l']);
    const rightShoulderPos = getBonePos(['RightShoulder', 'clavicle_r']);
    const leftArmPos = getBonePos(['LeftArm', 'upperarm_l', 'arm_l']);
    const rightArmPos = getBonePos(['RightArm', 'upperarm_r', 'arm_r']);
    const leftForeArmPos = getBonePos(['LeftForeArm', 'lowerarm_l', 'forearm_l']);
    const rightForeArmPos = getBonePos(['RightForeArm', 'lowerarm_r', 'forearm_r']);
    const leftHandPos = getBonePos(['LeftHand', 'hand_l', 'wrist_l']);
    const rightHandPos = getBonePos(['RightHand', 'hand_r', 'wrist_r']);
    const leftUpLegPos = getBonePos(['LeftUpLeg', 'thigh_l']);
    const rightUpLegPos = getBonePos(['RightUpLeg', 'thigh_r']);
    const leftLegPos = getBonePos(['LeftLeg', 'calf_l']);
    const rightLegPos = getBonePos(['RightLeg', 'calf_r']);
    const leftFootPos = getBonePos(['LeftFoot', 'foot_l']);
    const rightFootPos = getBonePos(['RightFoot', 'foot_r']);

    const calculatedWaistY = hipsPos.y !== 0 ? hipsPos.y : (hipsCount > 0 ? hipsY / hipsCount : 0.815);
    const calculatedNeckY = neckPos.y !== 0 ? neckPos.y : (neckCount > 0 ? neckY / neckCount : 1.280);
    const armDistance = leftArmPos.distanceTo(rightArmPos);
    const shoulderSpan = armDistance > 0.1 ? Math.max(armDistance + 0.10, 0.36) : 0.36;

    // Measure actual torso ribcage, sternum/bust Z envelope, and hips slice from bind bodyGeometry
    const torsoSpanY = Math.max(0.25, calculatedNeckY - calculatedWaistY);
    const armHalfSpan = armDistance > 0.08
      ? Math.max(Math.abs(leftArmPos.x - rightArmPos.x) * 0.5, 0.145)
      : 0.18;
    const chestBandY = calculatedWaistY + torsoSpanY * 0.62;
    const solarBandY = calculatedWaistY + torsoSpanY * 0.42;
    const shLowY = calculatedNeckY - torsoSpanY * 0.30;
    const shHighY = calculatedNeckY - 0.025;

    let solarMinX = Infinity, solarMaxX = -Infinity, solarCount = 0;
    let shMinX = Infinity, shMaxX = -Infinity, shCount = 0;
    let chestMinZ = Infinity, chestMaxZ = -Infinity, chestZCount = 0;
    let hipsMinX = Infinity, hipsMaxX = -Infinity, hipsMinZ = Infinity, hipsMaxZ = -Infinity, hipsSliceCount = 0;

    for (let i = 0; i < pos.count; i++) {
      const vx = pos.getX(i);
      const vy = pos.getY(i);
      const vz = pos.getZ(i);

      if (Math.abs(vy - solarBandY) <= 0.075 && Math.abs(vx) <= armHalfSpan * 1.15) {
        if (vx < solarMinX) solarMinX = vx;
        if (vx > solarMaxX) solarMaxX = vx;
        solarCount++;
      }
      if (vy >= shLowY && vy <= shHighY && Math.abs(vx) <= 0.26) {
        if (vx < shMinX) shMinX = vx;
        if (vx > shMaxX) shMaxX = vx;
        shCount++;
      }
      if (Math.abs(vy - chestBandY) <= 0.075 && Math.abs(vx) <= Math.min(0.155, armHalfSpan * 0.90)) {
        if (vz < chestMinZ) chestMinZ = vz;
        if (vz > chestMaxZ) chestMaxZ = vz;
        chestZCount++;
      }
      if (Math.abs(vy - calculatedWaistY) <= 0.075 && Math.abs(vx) <= Math.max(0.225, armHalfSpan * 1.35)) {
        if (vx < hipsMinX) hipsMinX = vx;
        if (vx > hipsMaxX) hipsMaxX = vx;
        if (vz < hipsMinZ) hipsMinZ = vz;
        if (vz > hipsMaxZ) hipsMaxZ = vz;
        hipsSliceCount++;
      }
    }

    const measuredShoulderWidth = shCount >= 8 ? Math.max(0.32, shMaxX - shMinX) : 0;
    const finalShoulderSpan = Math.max(shoulderSpan, measuredShoulderWidth);
    const measuredChestWidth = solarCount >= 8 ? Math.max(0.24, solarMaxX - solarMinX) : 0;
    const chestWidth = Math.max(Math.abs(leftArmPos.x - rightArmPos.x) * 0.92, measuredChestWidth, 0.29);
    const chestDepth = chestZCount >= 6 ? Math.max(0.16, chestMaxZ - chestMinZ) : chestWidth * 0.64;
    const chestCenterZ = chestZCount >= 6 ? (chestMinZ + chestMaxZ) * 0.5 : spine2Pos.z;

    const waistWidth = chestWidth * 0.86;
    const hipsWidth = hipsSliceCount >= 8 ? Math.max(0.26, hipsMaxX - hipsMinX) : chestWidth * 0.96;
    const hipsDepth = hipsSliceCount >= 8 ? Math.max(0.16, hipsMaxZ - hipsMinZ) : chestDepth * 0.96;
    const hipsCenterZ = hipsSliceCount >= 8 ? (hipsMinZ + hipsMaxZ) * 0.5 : hipsPos.z;

    return {
      hipsPos,
      spinePos,
      spine1Pos,
      spine2Pos,
      neckPos,
      headPos,
      leftShoulderPos,
      rightShoulderPos,
      leftArmPos,
      rightArmPos,
      leftForeArmPos,
      rightForeArmPos,
      leftHandPos,
      rightHandPos,
      leftUpLegPos,
      rightUpLegPos,
      leftLegPos,
      rightLegPos,
      leftFootPos,
      rightFootPos,
      torsoHeight: calculatedNeckY - (calculatedWaistY - 0.055),
      shoulderSpan: finalShoulderSpan,
      chestWidth,
      chestDepth,
      chestCenterZ,
      waistWidth,
      hipsWidth,
      hipsDepth,
      hipsCenterZ,
      waistY: calculatedWaistY,
      neckY: calculatedNeckY,
      bodyMesh: bm,
      bodyGeometry,
      skeleton,
      parentGroup
    };
  }

  /**
   * Builds and caches an arm/hand-excluded BufferGeometry for BVH collision and torso skinning transfer,
   * preventing flared dresses/hems/torsos from colliding with hanging forearms and hands.
   */
  private static getOrBuildCoreBodyGeometry(
    bodyGeo: THREE.BufferGeometry,
    skeleton: THREE.Skeleton
  ): THREE.BufferGeometry {
    if (bodyGeo.userData?._coreBodyGeometry) {
      return bodyGeo.userData._coreBodyGeometry;
    }

    const idxAttr = bodyGeo.index;
    const skinIdx = bodyGeo.attributes.skinIndex;
    const skinWgt = bodyGeo.attributes.skinWeight;
    if (!idxAttr || !skinIdx || !skinWgt || !skeleton?.bones?.length) {
      return bodyGeo;
    }

    const armBoneIndices = new Set<number>();
    skeleton.bones.forEach((b, idx) => {
      const bName = (b.name || '').toLowerCase();
      const isArmOrHand =
        /(arm|forearm|hand|wrist|finger|thumb|index|middle|ring|pinky)/.test(bName) &&
        !/(shoulder|clavicle)/.test(bName);
      if (isArmOrHand) {
        armBoneIndices.add(idx);
      }
    });

    if (armBoneIndices.size === 0) {
      return bodyGeo;
    }

    const posAttr = bodyGeo.attributes.position;
    const armVert = new Uint8Array(posAttr.count);
    for (let v = 0; v < posAttr.count; v++) {
      let wArm = 0;
      for (let k = 0; k < 4; k++) {
        if (armBoneIndices.has(skinIdx.getX(v * 4 + k))) {
          wArm += skinWgt.getX(v * 4 + k);
        }
      }
      if (wArm > 0.35) {
        armVert[v] = 1;
      }
    }

    const coreIndices: number[] = [];
    for (let f = 0; f < idxAttr.count; f += 3) {
      const i0 = idxAttr.getX(f);
      const i1 = idxAttr.getX(f + 1);
      const i2 = idxAttr.getX(f + 2);
      if (armVert[i0] === 0 && armVert[i1] === 0 && armVert[i2] === 0) {
        coreIndices.push(i0, i1, i2);
      }
    }

    if (coreIndices.length < 30) {
      return bodyGeo;
    }

    const coreGeo = new THREE.BufferGeometry();
    coreGeo.setAttribute('position', posAttr);
    coreGeo.setAttribute('skinIndex', skinIdx);
    coreGeo.setAttribute('skinWeight', skinWgt);
    if (bodyGeo.attributes.normal) {
      coreGeo.setAttribute('normal', bodyGeo.attributes.normal);
    }
    coreGeo.setIndex(new THREE.Uint32BufferAttribute(coreIndices, 1));
    bodyGeo.userData = bodyGeo.userData || {};
    bodyGeo.userData._coreBodyGeometry = coreGeo;
    return coreGeo;
  }

  /**
   * Builds a lightweight lower-body collider from visible default outfit trousers (e.g. Alex_8)
   * so untucked tops and outerwear clear waistbelt pouches and glutes without poke-through.
   */
  private static getOrBuildLowerOutfitCollider(
    avatarModel: THREE.Object3D,
    bodyGeo: THREE.BufferGeometry,
    cutoffY: number
  ): THREE.BufferGeometry | null {
    if (bodyGeo.userData?._lowerOutfitCollider !== undefined) {
      return bodyGeo.userData._lowerOutfitCollider;
    }

    let outfitMesh: THREE.Mesh | null = null;
    avatarModel.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const m = child as THREE.Mesh;
        const n = (m.name || '').toLowerCase();
        if (n === 'alex_8' || n.includes('outfit')) {
          outfitMesh = m;
        }
      }
    });

    if (!outfitMesh || !(outfitMesh as THREE.Mesh).geometry?.attributes?.position) {
      bodyGeo.userData = bodyGeo.userData || {};
      bodyGeo.userData._lowerOutfitCollider = null;
      return null;
    }

    const om = outfitMesh as THREE.Mesh;
    const oPos = om.geometry.attributes.position;
    const oIdx = om.geometry.index;
    if (!oIdx || oPos.count < 400) {
      bodyGeo.userData = bodyGeo.userData || {};
      bodyGeo.userData._lowerOutfitCollider = null;
      return null;
    }

    const lowerIndices: number[] = [];
    for (let f = 0; f < oIdx.count; f += 3) {
      const i0 = oIdx.getX(f);
      const i1 = oIdx.getX(f + 1);
      const i2 = oIdx.getX(f + 2);
      if (oPos.getY(i0) <= cutoffY && oPos.getY(i1) <= cutoffY && oPos.getY(i2) <= cutoffY) {
        lowerIndices.push(i0, i1, i2);
      }
    }

    if (lowerIndices.length < 30) {
      bodyGeo.userData = bodyGeo.userData || {};
      bodyGeo.userData._lowerOutfitCollider = null;
      return null;
    }

    const colGeo = new THREE.BufferGeometry();
    colGeo.setAttribute('position', oPos);
    colGeo.setIndex(new THREE.Uint32BufferAttribute(lowerIndices, 1));
    bodyGeo.userData = bodyGeo.userData || {};
    bodyGeo.userData._lowerOutfitCollider = colGeo;
    return colGeo;
  }

  /**
   * Derives standardized Fitting / Skinning component tag from GLB node metadata (`name` / `userData`).
   */
  private static deriveSemanticTagFromMetadata(
    name: string,
    userData: Record<string, any> = {}
  ): string | undefined {
    const idStr = String(userData.component_id || name || '').toLowerCase();
    const semType = String(userData.semantic_type || '').toLowerCase();

    if (idStr.includes('left_leg')) return 'left_leg';
    if (idStr.includes('right_leg')) return 'right_leg';
    if (semType === 'leg') return idStr.includes('right') ? 'right_leg' : 'left_leg';
    if (idStr.includes('left_sleeve') || idStr.includes('left_outerwear_sleeve')) return 'left_sleeve';
    if (idStr.includes('right_sleeve') || idStr.includes('right_outerwear_sleeve')) return 'right_sleeve';
    if (semType === 'sleeve') return idStr.includes('right') ? 'right_sleeve' : 'left_sleeve';

    // Handle cuffs carefully: leg cuffs map to leg bones, sleeve cuffs map to sleeve/wrist bones
    if (idStr.includes('left_cuff')) return userData.parent_id?.includes('leg') ? 'left_leg' : 'left_cuff';
    if (idStr.includes('right_cuff')) return userData.parent_id?.includes('leg') ? 'right_leg' : 'right_cuff';
    if (semType === 'cuff') {
      if (String(userData.parent_id || '').includes('leg')) {
        return idStr.includes('right') ? 'right_leg' : 'left_leg';
      }
      return idStr.includes('right') ? 'right_cuff' : 'left_cuff';
    }

    if (idStr.includes('hood') || semType === 'hood') return 'hood';
    if (idStr.includes('pocket') || semType === 'pocket') return 'kangaroo_pocket';
    if (idStr.includes('drawstring') || idStr.includes('eyelet') || semType === 'drawstring' || semType === 'eyelet') {
      return 'drawstrings';
    }
    if (idStr.includes('waistband') || idStr.includes('hem_loop') || semType === 'waistband' || semType === 'hem') {
      return 'waistband';
    }
    if (idStr.includes('placket') || semType === 'placket') return 'placket';
    if (idStr.includes('zipper') || semType === 'zipper') return 'zipper';
    if (idStr.includes('lapel') || semType === 'lapel') return 'lapel';
    if (idStr.includes('collar') || semType === 'collar') return 'collar';
    if (idStr.includes('skirt') || semType === 'skirt') return 'skirt';
    if (idStr.includes('torso') || idStr.includes('bodice') || semType === 'torso' || semType === 'bodice') {
      return 'torso';
    }
    return undefined;
  }

  /**
   * Compacts a component mesh's geometry so each component owns only the vertices referenced by its index sub-slice
   * (essential when GLBExporter shares one vertex buffer across multiple glTF component primitives).
   */
  private static compactComponentGeometry(
    mesh: THREE.Mesh,
    relMatrix: THREE.Matrix4,
    isRelIdentity: boolean,
    compactSharedBuffers: boolean
  ): THREE.BufferGeometry {
    const srcGeo = mesh.geometry;
    const posAttr = srcGeo.attributes.position;
    if (!posAttr) {
      return srcGeo.clone();
    }

    const indexAttr = srcGeo.index;
    const shouldCompact =
      compactSharedBuffers && indexAttr !== null && indexAttr !== undefined && indexAttr.count > 0;

    if (!shouldCompact) {
      const cloned = srcGeo.clone();
      if (!isRelIdentity) {
        cloned.applyMatrix4(relMatrix);
      }
      if ((srcGeo as any).componentTags) {
        (cloned as any).componentTags = (srcGeo as any).componentTags;
      }
      if ((srcGeo as any).componentIndices) {
        cloned.setAttribute(
          'componentType',
          new THREE.BufferAttribute((srcGeo as any).componentIndices, 1)
        );
      }
      return cloned;
    }

    // Collect referenced vertex indices in ascending order for deterministic compact mapping
    const usedSet = new Set<number>();
    for (let i = 0; i < indexAttr!.count; i++) {
      usedSet.add(indexAttr!.getX(i));
    }

    // If the index buffer already references almost every vertex cleanly and relMatrix is identity, fast clone
    if (usedSet.size === posAttr.count && isRelIdentity) {
      const cloned = srcGeo.clone();
      if ((srcGeo as any).componentTags) {
        (cloned as any).componentTags = (srcGeo as any).componentTags;
      }
      return cloned;
    }

    const uniqueVerts = Array.from(usedSet).sort((a, b) => a - b);
    const oldToNew = new Map<number, number>();
    uniqueVerts.forEach((oldIdx, newIdx) => oldToNew.set(oldIdx, newIdx));

    const newCount = uniqueVerts.length;
    const newPos = new Float32Array(newCount * 3);
    const normAttr = srcGeo.attributes.normal;
    const newNorm = normAttr ? new Float32Array(newCount * 3) : null;
    const uvAttr = srcGeo.attributes.uv;
    const newUv = uvAttr ? new Float32Array(newCount * 2) : null;

    const srcTags = (srcGeo as any).componentTags as string[] | undefined;
    const compactedTags: string[] | undefined = srcTags ? new Array(newCount) : undefined;

    const tmpVec = new THREE.Vector3();
    const tmpNorm = new THREE.Vector3();
    const normalMatrix = !isRelIdentity ? new THREE.Matrix3().getNormalMatrix(relMatrix) : null;

    for (let k = 0; k < newCount; k++) {
      const oldIdx = uniqueVerts[k];
      tmpVec.set(posAttr.getX(oldIdx), posAttr.getY(oldIdx), posAttr.getZ(oldIdx));
      if (!isRelIdentity) {
        tmpVec.applyMatrix4(relMatrix);
      }
      newPos[k * 3] = tmpVec.x;
      newPos[k * 3 + 1] = tmpVec.y;
      newPos[k * 3 + 2] = tmpVec.z;

      if (newNorm && normAttr) {
        tmpNorm.set(normAttr.getX(oldIdx), normAttr.getY(oldIdx), normAttr.getZ(oldIdx));
        if (normalMatrix) {
          tmpNorm.applyMatrix3(normalMatrix).normalize();
        }
        newNorm[k * 3] = tmpNorm.x;
        newNorm[k * 3 + 1] = tmpNorm.y;
        newNorm[k * 3 + 2] = tmpNorm.z;
      }

      if (newUv && uvAttr) {
        newUv[k * 2] = uvAttr.getX(oldIdx);
        newUv[k * 2 + 1] = uvAttr.getY(oldIdx);
      }

      if (compactedTags && srcTags) {
        compactedTags[k] = srcTags[oldIdx];
      }
    }

    const newIndices = new Uint32Array(indexAttr!.count);
    for (let i = 0; i < indexAttr!.count; i++) {
      newIndices[i] = oldToNew.get(indexAttr!.getX(i)) ?? 0;
    }

    const compacted = new THREE.BufferGeometry();
    compacted.setAttribute('position', new THREE.BufferAttribute(newPos, 3));
    if (newNorm) {
      compacted.setAttribute('normal', new THREE.BufferAttribute(newNorm, 3));
    }
    if (newUv) {
      compacted.setAttribute('uv', new THREE.BufferAttribute(newUv, 2));
    }
    compacted.setIndex(new THREE.BufferAttribute(newIndices, 1));
    if (compactedTags) {
      (compacted as any).componentTags = compactedTags;
    }
    return compacted;
  }

  /**
   * Extracts all component meshes, compacted geometries, and materials from the reconstructed garment hierarchy.
   */
  private static extractGarmentMeshes(
    source: THREE.Object3D,
    wireframe?: boolean
  ): ExtractedComponentMesh[] {
    source.updateMatrixWorld(true);
    const invSourceWorld = source.matrixWorld.clone().invert();
    const identity = new THREE.Matrix4();

    const meshes: THREE.Mesh[] = [];
    source.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        meshes.push(child as THREE.Mesh);
      }
    });

    if (meshes.length === 0) {
      throw new Error('[GarmentAvatarFittingEngine] No mesh found in garment source hierarchy.');
    }

    const isMultiMesh = meshes.length > 1;
    const results: ExtractedComponentMesh[] = [];

    for (let idx = 0; idx < meshes.length; idx++) {
      const mesh = meshes[idx];
      const relMatrix = new THREE.Matrix4().multiplyMatrices(invSourceWorld, mesh.matrixWorld);
      const isRelIdentity = relMatrix.elements.every((v, k) => Math.abs(v - identity.elements[k]) < 1e-5);

      const clonedGeometry = this.compactComponentGeometry(mesh, relMatrix, isRelIdentity, isMultiMesh);
      if ((clonedGeometry.attributes.position?.count || 0) === 0) {
        continue;
      }

      // Ensure material is double-sided standard PBR material with preserved texture fidelity
      let mat = mesh.material;
      if (Array.isArray(mat)) mat = mat[0];
      const clonedMat = (mat as THREE.Material).clone();
      const stdMat = clonedMat as THREE.MeshStandardMaterial;
      stdMat.side = THREE.DoubleSide;
      if (wireframe !== undefined) {
        stdMat.wireframe = wireframe;
      }

      // When diffuse texture map is present, set neutral white tint so texture colors are not blackened
      if (stdMat.map) {
        stdMat.color = new THREE.Color(0xffffff);
        stdMat.map.flipY = false;
        stdMat.map.needsUpdate = true;
      }

      const compName = mesh.name || mesh.userData?.component_id || `component_${idx}`;
      const semanticTag = this.deriveSemanticTagFromMetadata(compName, mesh.userData || {});

      results.push({
        mesh,
        name: compName,
        userData: { ...(mesh.userData || {}) },
        clonedGeometry,
        material: clonedMat,
        semanticTag
      });
    }

    if (results.length === 0) {
      throw new Error('[GarmentAvatarFittingEngine] No valid non-empty mesh found in garment source hierarchy.');
    }

    return results;
  }

  /**
   * Computes a normalized authored sleeve frame (proximal origin, axis direction, orthogonal cross-section frame,
   * sleeve length, and max cross-sectional radius) from component meshes or lateral sleeve vertices.
   */
  private static extractAuthoredSleeveFrame(
    components: ExtractedComponentMesh[],
    side: 'left' | 'right',
    centerX: number,
    centerZ: number,
    fallbackShoulderY: number,
    shoulderSpan: number
  ): AuthoredSleeveFrame {
    const isLeft = side === 'left';
    const sleeveTag = isLeft ? 'left_sleeve' : 'right_sleeve';
    const cuffTag = isLeft ? 'left_cuff' : 'right_cuff';
    const defaultDir = new THREE.Vector3(isLeft ? 0.52 : -0.52, -0.84, 0.14).normalize();
    const upHint = new THREE.Vector3(0, 0, 1);
    const buildOrtho = (dir: THREE.Vector3) => {
      const right = new THREE.Vector3().crossVectors(dir, upHint);
      if (right.lengthSq() < 1e-6) right.set(isLeft ? 1 : -1, 0, 0);
      right.normalize();
      const up = new THREE.Vector3().crossVectors(right, dir).normalize();
      if (up.z < 0) {
        up.negate();
        right.negate();
      }
      return { right, up };
    };

    const pts: Array<[number, number, number]> = [];
    for (const comp of components) {
      if (comp.semanticTag === sleeveTag || comp.semanticTag === cuffTag) {
        const pos = comp.clonedGeometry.attributes.position;
        for (let i = 0; i < pos.count; i++) {
          pts.push([pos.getX(i), pos.getY(i), pos.getZ(i)]);
        }
      }
    }

    if (pts.length >= 12) {
      let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
      for (const p of pts) {
        if (p[0] < minX) minX = p[0];
        if (p[0] > maxX) maxX = p[0];
        if (p[1] < minY) minY = p[1];
        if (p[1] > maxY) maxY = p[1];
      }
      // Verify the slice is strictly lateral (guards against arbitrary triangle slicing in synthetic tests)
      const isLateral = isLeft ? minX > centerX - 0.08 : maxX < centerX + 0.08;
      if (isLateral && (maxY - minY > 0.06 || maxX - minX > 0.06)) {
        // Approximate proximal (top/inner) vs distal (bottom/outer) along rough diagonal toward cuff
        const ySpan = Math.max(0.05, maxY - minY);
        const proxTopCut = maxY - ySpan * 0.16;
        const distBotCut = minY + ySpan * 0.16;

        let px = 0, py = 0, pz = 0, pc = 0;
        let dx = 0, dy = 0, dz = 0, dc = 0;
        for (const p of pts) {
          if (p[1] >= proxTopCut) {
            px += p[0]; py += p[1]; pz += p[2]; pc++;
          }
          if (p[1] <= distBotCut) {
            dx += p[0]; dy += p[1]; dz += p[2]; dc++;
          }
        }
        if (pc >= 3 && dc >= 3) {
          const origin = new THREE.Vector3(px / pc, py / pc, pz / pc);
          const distal = new THREE.Vector3(dx / dc, dy / dc, dz / dc);
          const diff = new THREE.Vector3().subVectors(distal, origin);
          const length = diff.length();
          if (length >= 0.08 && Math.abs(maxX - minX) < shoulderSpan * 0.55) {
            const dir = diff.normalize();
            const { right, up } = buildOrtho(dir);
            let maxR = 0;
            for (const p of pts) {
              const rx = p[0] - origin.x;
              const ry = p[1] - origin.y;
              const rz = p[2] - origin.z;
              const xr = rx * right.x + ry * right.y + rz * right.z;
              const yu = rx * up.x + ry * up.y + rz * up.z;
              const r = Math.hypot(xr, yu);
              if (r > maxR) maxR = r;
            }
            return {
              origin,
              dir,
              right,
              up,
              length,
              maxRadius: Math.max(0.04, maxR),
              valid: true
            };
          }
        }
      }
    }

    const fallbackOrtho = buildOrtho(defaultDir);
    return {
      origin: new THREE.Vector3(centerX + (isLeft ? 0.175 : -0.175), fallbackShoulderY, centerZ + 0.01),
      dir: defaultDir,
      right: fallbackOrtho.right,
      up: fallbackOrtho.up,
      length: 0.52,
      maxRadius: 0.075,
      valid: false
    };
  }

  /**
   * Analyzes composite reconstructed garment bounds and anatomical landmarks across one or more component geometries.
   */
  private static analyzeGarmentGeometries(
    components: ExtractedComponentMesh[],
    isHoodie: boolean
  ): GarmentGeometryLandmarks {
    const compositeBox = new THREE.Box3();
    const torsoCoreBox = new THREE.Box3();
    let hasDedicatedTorsoMesh = false;

    for (const comp of components) {
      const geometry = comp.clonedGeometry;
      geometry.computeBoundingBox();
      if (geometry.boundingBox && !geometry.boundingBox.isEmpty()) {
        compositeBox.union(geometry.boundingBox);
        if (
          comp.semanticTag === 'torso' ||
          comp.semanticTag === 'waistband' ||
          comp.semanticTag === 'placket' ||
          comp.semanticTag === 'zipper'
        ) {
          torsoCoreBox.union(geometry.boundingBox);
          hasDedicatedTorsoMesh = true;
        }
      }
    }

    const minY = compositeBox.min.y;
    const maxY = compositeBox.max.y;
    const centerX = (compositeBox.min.x + compositeBox.max.x) / 2;
    const centerZ = (compositeBox.min.z + compositeBox.max.z) / 2;

    const isGroundRelative = minY >= 0.50;
    const torsoHeight = isHoodie
      ? (maxY - minY) * 0.72
      : (maxY - minY);
    const shoulderSpan = compositeBox.max.x - compositeBox.min.x;

    // Derive core torso width/depth/Z center excluding hood overhang and splayed sleeves
    let torsoWidth = 0.40;
    let torsoDepth = 0.24;
    let torsoCenterZ = centerZ;
    let torsoMinY = minY;
    let torsoMaxY = minY + torsoHeight;

    if (hasDedicatedTorsoMesh && !torsoCoreBox.isEmpty()) {
      const tw = torsoCoreBox.max.x - torsoCoreBox.min.x;
      const td = torsoCoreBox.max.z - torsoCoreBox.min.z;
      if (tw >= 0.22 && tw <= 0.65) torsoWidth = tw;
      if (td >= 0.14 && td <= 0.45) torsoDepth = td;
      torsoCenterZ = (torsoCoreBox.min.z + torsoCoreBox.max.z) / 2;
      torsoMinY = torsoCoreBox.min.y;
      torsoMaxY = torsoCoreBox.max.y;
    } else if (components.length > 0) {
      // Single-mesh fallback: sample inner-X column below collar/hood level
      const midLowY = minY + torsoHeight * 0.18;
      const midHighY = minY + torsoHeight * 0.68;
      let sMinX = Infinity, sMaxX = -Infinity, sMinZ = Infinity, sMaxZ = -Infinity, sCount = 0;
      for (const comp of components) {
        const pos = comp.clonedGeometry.attributes.position;
        for (let i = 0; i < pos.count; i++) {
          const x = pos.getX(i);
          const y = pos.getY(i);
          const z = pos.getZ(i);
          if (y >= midLowY && y <= midHighY && Math.abs(x - centerX) <= 0.23) {
            if (x < sMinX) sMinX = x;
            if (x > sMaxX) sMaxX = x;
            if (z < sMinZ) sMinZ = z;
            if (z > sMaxZ) sMaxZ = z;
            sCount++;
          }
        }
      }
      if (sCount >= 8) {
        const sw = sMaxX - sMinX;
        const sd = sMaxZ - sMinZ;
        if (sw >= 0.22 && sw <= 0.55) torsoWidth = sw;
        if (sd >= 0.14 && sd <= 0.40) torsoDepth = sd;
        torsoCenterZ = (sMinZ + sMaxZ) * 0.5;
      }
    }

    const fallbackShoulderY = minY + torsoHeight - 0.07;
    const leftSleeveFrame = this.extractAuthoredSleeveFrame(
      components, 'left', centerX, torsoCenterZ, fallbackShoulderY, shoulderSpan
    );
    const rightSleeveFrame = this.extractAuthoredSleeveFrame(
      components, 'right', centerX, torsoCenterZ, fallbackShoulderY, shoulderSpan
    );

    // Derive crotch, hip/pelvis dimensions, and binned leg tube centerlines for bottoms & skirts
    const totalH = Math.max(0.1, maxY - minY);
    const hasShortLegTag = components.some(
      (c) => (c.name || '').toLowerCase().includes('short') || (c.semanticTag === 'left_leg' || c.semanticTag === 'right_leg')
    );
    let authCrotchY = totalH < 0.62
      ? minY + totalH * 0.42
      : maxY - totalH * 0.23;

    // Prefer explicit waistband/fly minY or middle vertex depression if present
    let wbMinY = Infinity;
    let hasWb = false;
    let legTopY = -Infinity;
    for (const comp of components) {
      if (comp.semanticTag === 'waistband' || comp.semanticTag === 'placket') {
        comp.clonedGeometry.computeBoundingBox();
        if (comp.clonedGeometry.boundingBox) {
          wbMinY = Math.min(wbMinY, comp.clonedGeometry.boundingBox.min.y);
          hasWb = true;
        }
      }
      if (comp.semanticTag === 'left_leg' || comp.semanticTag === 'right_leg') {
        comp.clonedGeometry.computeBoundingBox();
        if (comp.clonedGeometry.boundingBox) {
          legTopY = Math.max(legTopY, comp.clonedGeometry.boundingBox.max.y);
        }
      }
    }
    if (hasWb && hasShortLegTag && wbMinY > minY + totalH * 0.15 && wbMinY < maxY - 0.03) {
      if (legTopY > minY + 0.05 && legTopY < maxY - 0.02) {
        authCrotchY = Math.min(wbMinY, legTopY);
      }
    }
    const pelvisMinY = hasWb && wbMinY < maxY - 0.02 ? wbMinY : authCrotchY;
    const legMaxY = legTopY > minY + 0.05 && legTopY < maxY - 0.02 ? legTopY : authCrotchY;

    let hipMinX = Infinity, hipMaxX = -Infinity, hipMinZ = Infinity, hipMaxZ = -Infinity, hipCount = 0;
    let bodiceMinX = Infinity, bodiceMaxX = -Infinity, bodiceMinZ = Infinity, bodiceMaxZ = -Infinity, bodiceCount = 0;
    const numBins = 10;
    const lSumX = new Float64Array(numBins);
    const lSumZ = new Float64Array(numBins);
    const lCnt = new Int32Array(numBins);
    const rSumX = new Float64Array(numBins);
    const rSumZ = new Float64Array(numBins);
    const rCnt = new Int32Array(numBins);

    for (const comp of components) {
      const pos = comp.clonedGeometry.attributes.position;
      const sem = comp.semanticTag || '';
      for (let i = 0; i < pos.count; i++) {
        const vx = pos.getX(i);
        const vy = pos.getY(i);
        const vz = pos.getZ(i);

        // Hips / pelvis envelope (above crotch, or top 35% of skirt/bottoms)
        if (vy >= Math.max(authCrotchY, maxY - totalH * 0.42)) {
          if (vx < hipMinX) hipMinX = vx;
          if (vx > hipMaxX) hipMaxX = vx;
          if (vz < hipMinZ) hipMinZ = vz;
          if (vz > hipMaxZ) hipMaxZ = vz;
          hipCount++;
        }

        // Dress upper bodice envelope (62%..86% of total height, inner X)
        const yFrac = (vy - minY) / totalH;
        if (yFrac >= 0.62 && yFrac <= 0.86 && Math.abs(vx - centerX) <= 0.24) {
          if (vx < bodiceMinX) bodiceMinX = vx;
          if (vx > bodiceMaxX) bodiceMaxX = vx;
          if (vz < bodiceMinZ) bodiceMinZ = vz;
          if (vz > bodiceMaxZ) bodiceMaxZ = vz;
          bodiceCount++;
        }

        if (vy <= authCrotchY + 0.02) {
          const bFrac = THREE.MathUtils.clamp((authCrotchY - vy) / Math.max(0.05, authCrotchY - minY), 0, 0.999);
          const b = Math.min(numBins - 1, Math.floor(bFrac * numBins));
          const isL = sem === 'left_leg' || (sem !== 'right_leg' && vx >= centerX);
          const isR = sem === 'right_leg' || (sem !== 'left_leg' && vx < centerX);
          if (isL) {
            lSumX[b] += vx; lSumZ[b] += vz; lCnt[b]++;
          } else if (isR) {
            rSumX[b] += vx; rSumZ[b] += vz; rCnt[b]++;
          }
        }
      }
    }

    const leftCenterX = new Float32Array(numBins);
    const leftCenterZ = new Float32Array(numBins);
    const rightCenterX = new Float32Array(numBins);
    const rightCenterZ = new Float32Array(numBins);
    let lastLX = centerX + 0.10, lastLZ = centerZ;
    let lastRX = centerX - 0.10, lastRZ = centerZ;
    for (let b = 0; b < numBins; b++) {
      if (lCnt[b] > 0) {
        lastLX = lSumX[b] / lCnt[b];
        lastLZ = lSumZ[b] / lCnt[b];
      }
      leftCenterX[b] = lastLX;
      leftCenterZ[b] = lastLZ;
      if (rCnt[b] > 0) {
        lastRX = rSumX[b] / rCnt[b];
        lastRZ = rSumZ[b] / rCnt[b];
      }
      rightCenterX[b] = lastRX;
      rightCenterZ[b] = lastRZ;
    }

    const hipsWidth = hipCount >= 8 ? Math.max(0.22, hipMaxX - hipMinX) : torsoWidth;
    const hipsDepth = hipCount >= 8 ? Math.max(0.16, hipMaxZ - hipMinZ) : torsoDepth;
    const hipsCenterZ = hipCount >= 8 ? (hipMinZ + hipMaxZ) * 0.5 : torsoCenterZ;
    const bodiceWidth = bodiceCount >= 8 ? Math.max(0.22, bodiceMaxX - bodiceMinX) : torsoWidth;
    const bodiceDepth = bodiceCount >= 8 ? Math.max(0.15, bodiceMaxZ - bodiceMinZ) : torsoDepth;

    return {
      boundingBox: compositeBox,
      minY,
      maxY,
      centerX,
      centerZ,
      torsoHeight,
      shoulderSpan,
      torsoWidth,
      torsoDepth,
      torsoCenterZ,
      torsoMinY,
      torsoMaxY,
      leftSleeveFrame,
      rightSleeveFrame,
      legProfile: {
        crotchY: authCrotchY,
        pelvisMinY,
        legMaxY,
        hipsWidth,
        hipsDepth,
        hipsCenterZ,
        leftCenterX,
        leftCenterZ,
        rightCenterX,
        rightCenterZ,
        numBins
      },
      bodiceWidth,
      bodiceDepth,
      isGroundRelative,
      isHoodie
    };
  }

  /**
   * Identifies garment components semantically for each vertex.
   */
  public static identifyComponents(
    geometry: THREE.BufferGeometry,
    garmentLandmarks: GarmentGeometryLandmarks,
    category: GarmentCategoryType,
    isHoodie: boolean,
    semanticOverride?: string
  ): string[] {
    const pos = geometry.attributes.position;
    const vCount = pos.count;
    const tags: string[] = new Array(vCount);

    if ((geometry as any).componentTags && Array.isArray((geometry as any).componentTags)) {
      return (geometry as any).componentTags;
    }

    const compAttr = geometry.attributes.componentType;
    if (compAttr) {
      const typeMap: { [key: number]: string } = {
        1: 'front_torso',
        2: 'back_torso',
        3: 'left_sleeve',
        4: 'right_sleeve',
        5: 'hood',
        6: 'kangaroo_pocket',
        7: 'drawstrings',
        8: 'waistband',
        9: 'left_cuff',
        10: 'right_cuff',
        11: 'left_leg',
        12: 'right_leg'
      };
      for (let i = 0; i < vCount; i++) {
        tags[i] = typeMap[compAttr.getX(i)] || 'front_torso';
      }
      return tags;
    }

    // Multi-component GLB nodes provide exact semantic identity without brittle spatial heuristics
    if (semanticOverride) {
      if (semanticOverride === 'torso') {
        for (let i = 0; i < vCount; i++) {
          const z = pos.getZ(i) - garmentLandmarks.centerZ;
          tags[i] = z >= 0 ? 'front_torso' : 'back_torso';
        }
        return tags;
      }
      tags.fill(semanticOverride);
      return tags;
    }

    const catStr = category as string;
    const isBottom = catStr === 'bottom' || catStr === 'pants' || catStr === 'trousers' || catStr === 'jeans' || catStr === 'shorts';

    if (isBottom) {
      const minY = garmentLandmarks.minY;
      const maxY = garmentLandmarks.maxY;
      const waistThreshold = maxY - (maxY - minY) * 0.15;
      for (let i = 0; i < vCount; i++) {
        const x = pos.getX(i) - garmentLandmarks.centerX;
        const y = pos.getY(i);
        if (y >= waistThreshold) {
          tags[i] = 'waistband';
        } else if (x >= 0) {
          tags[i] = 'left_leg';
        } else {
          tags[i] = 'right_leg';
        }
      }
      return tags;
    }

    const minY = garmentLandmarks.minY;
    const maxY = garmentLandmarks.maxY;
    const torsoHeight = garmentLandmarks.torsoHeight;
    const collarY = isHoodie ? minY + torsoHeight : maxY - 0.05;
    const armThresholdX = Math.max(0.12, garmentLandmarks.shoulderSpan * 0.28);

    for (let i = 0; i < vCount; i++) {
      const x = pos.getX(i) - garmentLandmarks.centerX;
      const y = pos.getY(i);
      const z = pos.getZ(i) - garmentLandmarks.centerZ;

      if (Math.abs(x) < 0.05 && y > collarY - 0.25 && y < collarY + 0.02 && z > 0.09) {
        tags[i] = 'drawstrings';
        continue;
      }

      if (Math.abs(x) < 0.14 && y > minY + 0.08 && y < minY + 0.32 && z > 0.12) {
        tags[i] = 'kangaroo_pocket';
        continue;
      }

      if (isHoodie && y >= collarY - 0.02) {
        tags[i] = 'hood';
        continue;
      }

      if (x > armThresholdX && y < collarY + 0.05) {
        tags[i] = 'left_sleeve';
        continue;
      }
      if (x < -armThresholdX && y < collarY + 0.05) {
        tags[i] = 'right_sleeve';
        continue;
      }

      if (y <= minY + (collarY - minY) * 0.12) {
        tags[i] = 'waistband';
      } else if (z >= 0) {
        tags[i] = 'front_torso';
      } else {
        tags[i] = 'back_torso';
      }
    }

    return tags;
  }

  /**
   * Applies component-specific anatomical fitting into avatar bind space.
   */
  public static applyComponentFittingTransform(
    geometry: THREE.BufferGeometry,
    garmentLandmarks: GarmentGeometryLandmarks,
    avatar: AvatarLandmarks,
    category: GarmentCategoryType,
    isHoodie: boolean,
    options: GarmentFittingOptions,
    semanticOverride?: string
  ): {
    transformedPositions: Float32Array;
    componentTags: string[];
    appliedScale: [number, number, number];
    appliedOffset: [number, number, number];
  } {
    const posAttr = geometry.attributes.position;
    const gCount = posAttr.count;
    const transformedPositions = new Float32Array(gCount * 3);
    const componentTags = this.identifyComponents(
      geometry,
      garmentLandmarks,
      category,
      isHoodie,
      semanticOverride
    );

    const catStr = category as string;
    const isBottom = catStr === 'bottom' || catStr === 'pants' || catStr === 'trousers' || catStr === 'jeans' || catStr === 'shorts';
    const isSkirt = catStr === 'skirt' || catStr === 'skirts';
    const isDressOrOutfit = category === 'dress' || category === 'outfit';

    if (isSkirt) {
      const targetTopY = avatar.waistY + 0.025;
      const skirtHeight = Math.max(
        0.32,
        Math.min(avatar.waistY - 0.16, (garmentLandmarks.maxY - garmentLandmarks.minY) * 0.90)
      );
      const scaleY = skirtHeight / Math.max(0.1, garmentLandmarks.maxY - garmentLandmarks.minY);
      const scaleX = (avatar.hipsWidth * 1.15) / Math.max(0.20, garmentLandmarks.legProfile.hipsWidth);
      const scaleZ = (avatar.hipsDepth * 1.20) / Math.max(0.15, garmentLandmarks.legProfile.hipsDepth);
      const targetHemY = targetTopY - skirtHeight;
      const authHipZ = garmentLandmarks.legProfile.hipsCenterZ;

      for (let i = 0; i < gCount; i++) {
        const x = (posAttr.getX(i) - garmentLandmarks.centerX) * scaleX;
        const y = (posAttr.getY(i) - garmentLandmarks.minY) * scaleY + targetHemY;
        const z = (posAttr.getZ(i) - authHipZ) * scaleZ + avatar.hipsCenterZ;
        transformedPositions[i * 3] = x;
        transformedPositions[i * 3 + 1] = y;
        transformedPositions[i * 3 + 2] = z;
      }
      return {
        transformedPositions,
        componentTags,
        appliedScale: [scaleX, scaleY, scaleZ],
        appliedOffset: [0, targetHemY, avatar.hipsCenterZ]
      };
    }

    if (isBottom) {
      const authMinY = garmentLandmarks.minY;
      const authMaxY = garmentLandmarks.maxY;
      const authH = Math.max(0.1, authMaxY - authMinY);
      const isShorts = Boolean(options.subcategory?.toLowerCase().includes('short')) || authH < 0.62;
      const lp = garmentLandmarks.legProfile;
      const authCrotchY = lp.crotchY;
      const isMultiBottomNode = Boolean(semanticOverride);

      const lUp = (avatar.leftUpLegPos && avatar.leftUpLegPos.lengthSq() > 1e-4)
        ? avatar.leftUpLegPos
        : new THREE.Vector3(0.08, avatar.waistY - 0.075, avatar.hipsCenterZ);
      const rUp = (avatar.rightUpLegPos && avatar.rightUpLegPos.lengthSq() > 1e-4)
        ? avatar.rightUpLegPos
        : new THREE.Vector3(-0.08, avatar.waistY - 0.075, avatar.hipsCenterZ);
      const lKnee = (avatar.leftLegPos && avatar.leftLegPos.lengthSq() > 1e-4)
        ? avatar.leftLegPos
        : new THREE.Vector3(lUp.x + 0.03, (lUp.y + 0.06) * 0.5, avatar.hipsCenterZ + 0.015);
      const rKnee = (avatar.rightLegPos && avatar.rightLegPos.lengthSq() > 1e-4)
        ? avatar.rightLegPos
        : new THREE.Vector3(rUp.x - 0.03, (rUp.y + 0.06) * 0.5, avatar.hipsCenterZ + 0.015);
      const lAnkle = (avatar.leftFootPos && avatar.leftFootPos.lengthSq() > 1e-4)
        ? avatar.leftFootPos
        : new THREE.Vector3(lKnee.x + 0.02, 0.06, avatar.hipsCenterZ);
      const rAnkle = (avatar.rightFootPos && avatar.rightFootPos.lengthSq() > 1e-4)
        ? avatar.rightFootPos
        : new THREE.Vector3(rKnee.x - 0.02, 0.06, avatar.hipsCenterZ);

      const targetWaistY = avatar.waistY + 0.04;
      const targetCrotchY = lUp.y - 0.030;
      const footMinY = Math.max(0.04, Math.min(0.11, Math.min(lAnkle.y, rAnkle.y)));
      const targetBottomY = isShorts
        ? targetCrotchY - (targetCrotchY - footMinY) * 0.38
        : footMinY;

      // For multi-component GLBs, bridge any backend seam gap cleanly by overlapping pelvis & leg tops by +-2.5cm
      const pelvisTargetFloorY = isMultiBottomNode ? targetCrotchY - 0.025 : targetCrotchY;
      const legTargetTopY = isMultiBottomNode ? targetCrotchY + 0.025 : targetCrotchY;
      const pelvisSrcMinY = isMultiBottomNode ? lp.pelvisMinY : authCrotchY;
      const legSrcMaxY = isMultiBottomNode ? lp.legMaxY : authCrotchY;

      const scaleHipX = (avatar.hipsWidth * 1.15) / Math.max(0.20, lp.hipsWidth);
      const scaleHipZ = (avatar.hipsDepth * 1.18) / Math.max(0.15, lp.hipsDepth);
      const legRadialScale = Math.max(scaleHipX, scaleHipZ) * 1.06;
      const scaleY = (targetWaistY - targetBottomY) / authH;

      const sampleAuthLegCenter = (isLeft: boolean, gy: number): { cx: number; cz: number } => {
        const bFloat = THREE.MathUtils.clamp(
          (legSrcMaxY - gy) / Math.max(0.05, legSrcMaxY - authMinY),
          0,
          1
        ) * (lp.numBins - 1);
        const b0 = Math.floor(bFloat);
        const b1 = Math.min(lp.numBins - 1, b0 + 1);
        const f = bFloat - b0;
        const arrX = isLeft ? lp.leftCenterX : lp.rightCenterX;
        const arrZ = isLeft ? lp.leftCenterZ : lp.rightCenterZ;
        return {
          cx: arrX[b0] + (arrX[b1] - arrX[b0]) * f,
          cz: arrZ[b0] + (arrZ[b1] - arrZ[b0]) * f
        };
      };

      const sampleAvatarLegBoneXZ = (isLeft: boolean, fullFrac: number): { x: number; z: number } => {
        const up = isLeft ? lUp : rUp;
        const knee = isLeft ? lKnee : rKnee;
        const ankle = isLeft ? lAnkle : rAnkle;
        if (fullFrac <= 0.5) {
          const u = fullFrac / 0.5;
          return {
            x: THREE.MathUtils.lerp(up.x, knee.x, u),
            z: THREE.MathUtils.lerp(up.z, knee.z, u)
          };
        }
        const u = (fullFrac - 0.5) / 0.5;
        return {
          x: THREE.MathUtils.lerp(knee.x, ankle.x, u),
          z: THREE.MathUtils.lerp(knee.z, ankle.z, u)
        };
      };

      const isPelvisNode = semanticOverride === 'waistband' || semanticOverride === 'placket';

      for (let i = 0; i < gCount; i++) {
        const gx = posAttr.getX(i);
        const gy = posAttr.getY(i);
        const gz = posAttr.getZ(i);
        const tag = componentTags[i];

        if (isPelvisNode || (!isMultiBottomNode && gy >= authCrotchY)) {
          const tPelvis = THREE.MathUtils.clamp((gy - pelvisSrcMinY) / Math.max(0.04, authMaxY - pelvisSrcMinY), 0, 1);
          const fy = pelvisTargetFloorY + tPelvis * (targetWaistY - pelvisTargetFloorY);
          const fx = (gx - garmentLandmarks.centerX) * scaleHipX;
          const fz = (gz - lp.hipsCenterZ) * scaleHipZ + avatar.hipsCenterZ;
          transformedPositions[i * 3] = fx;
          transformedPositions[i * 3 + 1] = fy;
          transformedPositions[i * 3 + 2] = fz;
        } else {
          const tLeg = THREE.MathUtils.clamp((legSrcMaxY - gy) / Math.max(0.05, legSrcMaxY - authMinY), 0, 1);
          const fy = legTargetTopY - tLeg * (legTargetTopY - targetBottomY);
          const isLeft = tag === 'left_leg' || (tag !== 'right_leg' && gx >= garmentLandmarks.centerX);
          const authC = sampleAuthLegCenter(isLeft, gy);
          const avBoneC = sampleAvatarLegBoneXZ(isLeft, isShorts ? tLeg * 0.38 : tLeg);
          const blendT = THREE.MathUtils.smoothstep(tLeg, 0.0, 0.18);

          const hipMappedX = (gx - garmentLandmarks.centerX) * scaleHipX;
          const hipMappedZ = (gz - lp.hipsCenterZ) * scaleHipZ + avatar.hipsCenterZ;
          const legMappedX = avBoneC.x + (gx - authC.cx) * legRadialScale;
          const legMappedZ = avBoneC.z + (gz - authC.cz) * legRadialScale;

          transformedPositions[i * 3] = THREE.MathUtils.lerp(hipMappedX, legMappedX, blendT);
          transformedPositions[i * 3 + 1] = fy;
          transformedPositions[i * 3 + 2] = THREE.MathUtils.lerp(hipMappedZ, legMappedZ, blendT);
        }
      }
      return {
        transformedPositions,
        componentTags,
        appliedScale: [scaleHipX, scaleY, scaleHipZ],
        appliedOffset: [0, targetBottomY, avatar.hipsCenterZ]
      };
    }

    if (isDressOrOutfit) {
      const targetTopY = avatar.neckY + 0.015;
      const isMaxi = (options.subcategory || '').toLowerCase().includes('maxi') ||
        (options.subcategory || '').toLowerCase().includes('gown');
      const targetBotY = isMaxi ? 0.16 : 0.28;
      const totalCoverHeight = Math.max(0.60, targetTopY - targetBotY);
      const authH = Math.max(0.1, garmentLandmarks.maxY - garmentLandmarks.minY);
      const scaleY = totalCoverHeight / authH;

      const scaleChestX = (avatar.chestWidth * 1.15) / Math.max(0.22, garmentLandmarks.bodiceWidth);
      const scaleShoulderX = Math.max(
        scaleChestX,
        (avatar.shoulderSpan * 1.06) / Math.max(0.22, garmentLandmarks.bodiceWidth)
      );
      const scaleChestZ = (avatar.chestDepth * 1.18) / Math.max(0.15, garmentLandmarks.bodiceDepth);
      const scaleHipX = Math.max(
        scaleChestX * 0.94,
        (avatar.hipsWidth * 1.16) / Math.max(0.22, garmentLandmarks.legProfile.hipsWidth)
      );
      const scaleHipZ = Math.max(
        scaleChestZ * 0.94,
        (avatar.hipsDepth * 1.20) / Math.max(0.15, garmentLandmarks.legProfile.hipsDepth)
      );

      for (let i = 0; i < gCount; i++) {
        const yFrac = THREE.MathUtils.clamp((posAttr.getY(i) - garmentLandmarks.minY) / authH, 0, 1);
        const zBlend = THREE.MathUtils.smoothstep(yFrac, 0.42, 0.72);
        const shBlend = THREE.MathUtils.smoothstep(yFrac, 0.76, 0.96);
        const curScaleX = THREE.MathUtils.lerp(
          THREE.MathUtils.lerp(scaleHipX, scaleChestX, zBlend),
          scaleShoulderX,
          shBlend
        );
        const curScaleZ = THREE.MathUtils.lerp(scaleHipZ, scaleChestZ, zBlend);
        const curCenterZ = THREE.MathUtils.lerp(avatar.hipsCenterZ, avatar.chestCenterZ, zBlend);

        const x = (posAttr.getX(i) - garmentLandmarks.centerX) * curScaleX;
        const y = (posAttr.getY(i) - garmentLandmarks.minY) * scaleY + targetBotY;
        const z = (posAttr.getZ(i) - garmentLandmarks.torsoCenterZ) * curScaleZ + curCenterZ;
        transformedPositions[i * 3] = x;
        transformedPositions[i * 3 + 1] = y;
        transformedPositions[i * 3 + 2] = z;
      }
      return {
        transformedPositions,
        componentTags,
        appliedScale: [scaleChestX, scaleY, scaleChestZ],
        appliedOffset: [0, targetBotY, avatar.chestCenterZ]
      };
    }

    // Upper Garment (Top / Hoodie / Jacket / Shirt)
    const targetWaistY = avatar.waistY - 0.105;
    const targetNeckY = avatar.neckY + 0.012;
    const targetTorsoHeight = Math.max(0.25, targetNeckY - targetWaistY);

    const garmentTorsoHeight = Math.max(0.1, garmentLandmarks.torsoHeight);
    const garmentTorsoMinY = garmentLandmarks.minY;
    const collarY = isHoodie ? garmentTorsoMinY + garmentTorsoHeight : garmentLandmarks.maxY - 0.05;

    const chestEase = Math.max(options.easeTorso ?? 1.12, 1.12);
    const scaleChestX = (Math.max(avatar.chestWidth, 0.28) * chestEase) / Math.max(0.24, garmentLandmarks.torsoWidth);
    const scaleHipX = Math.max(scaleChestX, (Math.max(avatar.hipsWidth, 0.28) * 1.18) / Math.max(0.24, garmentLandmarks.torsoWidth));
    const scaleShoulderX = Math.max(scaleChestX, (avatar.shoulderSpan * 1.07) / Math.max(0.24, garmentLandmarks.torsoWidth));

    const scaleChestZ = (Math.max(avatar.chestDepth, 0.18) * 1.18) / Math.max(0.16, garmentLandmarks.torsoDepth);
    const scaleHipZ = Math.max(scaleChestZ, (Math.max(avatar.hipsDepth, 0.18) * 1.24) / Math.max(0.16, garmentLandmarks.torsoDepth));

    const scaleTorsoX = scaleChestX;
    const scaleTorsoZ = scaleChestZ;
    const scaleTorsoY = targetTorsoHeight / garmentTorsoHeight;

    const lArm = avatar.leftArmPos;
    const lArmStart = (avatar.leftShoulderPos && avatar.leftShoulderPos.lengthSq() > 1e-4)
      ? new THREE.Vector3().lerpVectors(avatar.leftShoulderPos, lArm, 0.72)
      : lArm;
    const lFore = (avatar.leftForeArmPos && avatar.leftForeArmPos.lengthSq() > 1e-4)
      ? avatar.leftForeArmPos
      : new THREE.Vector3(lArm.x + 0.12, lArm.y - 0.16, lArm.z);
    const lHand = (avatar.leftHandPos && avatar.leftHandPos.lengthSq() > 1e-4)
      ? avatar.leftHandPos
      : new THREE.Vector3(lFore.x + 0.09, lFore.y - 0.14, lFore.z + 0.05);

    const rArm = avatar.rightArmPos;
    const rArmStart = (avatar.rightShoulderPos && avatar.rightShoulderPos.lengthSq() > 1e-4)
      ? new THREE.Vector3().lerpVectors(avatar.rightShoulderPos, rArm, 0.72)
      : rArm;
    const rFore = (avatar.rightForeArmPos && avatar.rightForeArmPos.lengthSq() > 1e-4)
      ? avatar.rightForeArmPos
      : new THREE.Vector3(rArm.x - 0.12, rArm.y - 0.16, rArm.z);
    const rHand = (avatar.rightHandPos && avatar.rightHandPos.lengthSq() > 1e-4)
      ? avatar.rightHandPos
      : new THREE.Vector3(rFore.x - 0.09, rFore.y - 0.14, rFore.z + 0.05);

    const lLen1 = lArmStart.distanceTo(lFore) || 0.21;
    const lLen2 = lFore.distanceTo(lHand) || 0.20;
    const lTotalLen = lLen1 + lLen2;
    const lDir1 = new THREE.Vector3().subVectors(lFore, lArmStart).normalize();
    const lDir2 = new THREE.Vector3().subVectors(lHand, lFore).normalize();

    const rLen1 = rArmStart.distanceTo(rFore) || 0.21;
    const rLen2 = rFore.distanceTo(rHand) || 0.20;
    const rTotalLen = rLen1 + rLen2;
    const rDir1 = new THREE.Vector3().subVectors(rFore, rArmStart).normalize();
    const rDir2 = new THREE.Vector3().subVectors(rHand, rFore).normalize();

    const upHint = new THREE.Vector3(0, 0, 1);
    const lsf = garmentLandmarks.leftSleeveFrame;
    const rsf = garmentLandmarks.rightSleeveFrame;
    const lSpanRatio = lsf.valid
      ? THREE.MathUtils.clamp(lsf.length / Math.max(0.32, garmentTorsoHeight * 0.90), 0.25, 0.96)
      : 1.0;
    const rSpanRatio = rsf.valid
      ? THREE.MathUtils.clamp(rsf.length / Math.max(0.32, garmentTorsoHeight * 0.90), 0.25, 0.96)
      : 1.0;
    const lSleeveRadialScale = lsf.valid
      ? THREE.MathUtils.clamp((0.068 * Math.max(scaleShoulderX, 0.78)) / Math.max(0.045, lsf.maxRadius), 0.56, 1.05)
      : Math.min(scaleShoulderX, scaleChestZ);
    const rSleeveRadialScale = rsf.valid
      ? THREE.MathUtils.clamp((0.068 * Math.max(scaleShoulderX, 0.78)) / Math.max(0.045, rsf.maxRadius), 0.56, 1.05)
      : Math.min(scaleShoulderX, scaleChestZ);

    for (let i = 0; i < gCount; i++) {
      const gx = posAttr.getX(i);
      const gy = posAttr.getY(i);
      const gz = posAttr.getZ(i);

      const tag = componentTags[i];

      if (tag === 'left_sleeve' || tag === 'left_cuff') {
        const delta = new THREE.Vector3(gx - lsf.origin.x, gy - lsf.origin.y, gz - lsf.origin.z);
        const zLong = delta.dot(lsf.dir);
        const uRaw = THREE.MathUtils.clamp(zLong / Math.max(0.12, lsf.length), 0, 1.02);
        const u = THREE.MathUtils.clamp(uRaw * lSpanRatio, 0, 1);

        const xLocal = delta.dot(lsf.right) * lSleeveRadialScale;
        const yLocal = delta.dot(lsf.up) * lSleeveRadialScale;

        let cPos: THREE.Vector3;
        let cDir: THREE.Vector3;
        const split = lLen1 / lTotalLen;

        if (u <= split) {
          const t = u / split;
          cPos = new THREE.Vector3().lerpVectors(lArmStart, lFore, t);
          cDir = lDir1;
        } else {
          const t = (u - split) / (1 - split);
          cPos = new THREE.Vector3().lerpVectors(lFore, lHand, t);
          cDir = lDir2;
        }

        let avR = new THREE.Vector3().crossVectors(cDir, upHint).normalize();
        if (avR.lengthSq() < 1e-4) avR.set(1, 0, 0);
        let avU = new THREE.Vector3().crossVectors(avR, cDir).normalize();
        if (avU.z < 0) {
          avU.negate();
          avR.negate();
        }

        const fx = cPos.x + xLocal * avR.x + yLocal * avU.x;
        const fy = cPos.y + xLocal * avR.y + yLocal * avU.y;
        const fz = cPos.z + xLocal * avR.z + yLocal * avU.z;

        transformedPositions[i * 3] = fx;
        transformedPositions[i * 3 + 1] = fy;
        transformedPositions[i * 3 + 2] = fz;
        continue;
      }

      if (tag === 'right_sleeve' || tag === 'right_cuff') {
        const delta = new THREE.Vector3(gx - rsf.origin.x, gy - rsf.origin.y, gz - rsf.origin.z);
        const zLong = delta.dot(rsf.dir);
        const uRaw = THREE.MathUtils.clamp(zLong / Math.max(0.12, rsf.length), 0, 1.02);
        const u = THREE.MathUtils.clamp(uRaw * rSpanRatio, 0, 1);

        const xLocal = delta.dot(rsf.right) * rSleeveRadialScale;
        const yLocal = delta.dot(rsf.up) * rSleeveRadialScale;

        let cPos: THREE.Vector3;
        let cDir: THREE.Vector3;
        const split = rLen1 / rTotalLen;

        if (u <= split) {
          const t = u / split;
          cPos = new THREE.Vector3().lerpVectors(rArmStart, rFore, t);
          cDir = rDir1;
        } else {
          const t = (u - split) / (1 - split);
          cPos = new THREE.Vector3().lerpVectors(rFore, rHand, t);
          cDir = rDir2;
        }

        let avR = new THREE.Vector3().crossVectors(cDir, upHint).normalize();
        if (avR.lengthSq() < 1e-4) avR.set(-1, 0, 0);
        let avU = new THREE.Vector3().crossVectors(avR, cDir).normalize();
        if (avU.z < 0) {
          avU.negate();
          avR.negate();
        }

        const fx = cPos.x + xLocal * avR.x + yLocal * avU.x;
        const fy = cPos.y + xLocal * avR.y + yLocal * avU.y;
        const fz = cPos.z + xLocal * avR.z + yLocal * avU.z;

        transformedPositions[i * 3] = fx;
        transformedPositions[i * 3 + 1] = fy;
        transformedPositions[i * 3 + 2] = fz;
        continue;
      }

      if (tag === 'hood') {
        const t = THREE.MathUtils.clamp((gy - collarY) / Math.max(0.1, garmentLandmarks.maxY - collarY), 0, 1);
        const fy = targetNeckY - 0.015 + t * 0.19;
        const fx = (gx - garmentLandmarks.centerX) * scaleTorsoX;
        const hoodBaseZ = THREE.MathUtils.lerp(avatar.chestCenterZ, avatar.neckPos.z, 0.65);
        let fz = hoodBaseZ - 0.03 * Math.sin(t * Math.PI * 0.8) + (gz - garmentLandmarks.torsoCenterZ) * scaleTorsoZ * 0.82;
        if (fz > avatar.neckPos.z + 0.055) {
          fz = avatar.neckPos.z + 0.055;
        }

        transformedPositions[i * 3] = fx;
        transformedPositions[i * 3 + 1] = fy;
        transformedPositions[i * 3 + 2] = fz;
        continue;
      }

      // Torso / Kangaroo Pocket / Waistband / Drawstrings / Placket / Zipper / Collar / Lapel
      const t = THREE.MathUtils.clamp((gy - garmentTorsoMinY) / garmentTorsoHeight, 0, 1.08);
      const fy = targetWaistY + t * targetTorsoHeight;
      const hipMix = THREE.MathUtils.smoothstep(t, 0.10, 0.45);
      const shMix = THREE.MathUtils.smoothstep(t, 0.65, 0.92);
      const curScaleX = THREE.MathUtils.lerp(
        THREE.MathUtils.lerp(scaleHipX, scaleChestX, hipMix),
        scaleShoulderX,
        shMix
      );
      const curScaleZ = THREE.MathUtils.lerp(scaleHipZ, scaleChestZ, THREE.MathUtils.smoothstep(t, 0.10, 0.55));
      const fx = (gx - garmentLandmarks.centerX) * curScaleX;

      const bodyCenterZ = THREE.MathUtils.lerp(avatar.hipsCenterZ, avatar.chestCenterZ, THREE.MathUtils.clamp(t, 0, 1));
      let fz = (gz - garmentLandmarks.torsoCenterZ) * curScaleZ + bodyCenterZ;
      if (tag === 'kangaroo_pocket' || tag === 'drawstrings' || tag === 'placket' || tag === 'zipper') {
        fz += 0.008;
      } else if (tag === 'collar' || tag === 'lapel') {
        fz += 0.005;
      }

      transformedPositions[i * 3] = fx;
      transformedPositions[i * 3 + 1] = fy;
      transformedPositions[i * 3 + 2] = fz;
    }

    return {
      transformedPositions,
      componentTags,
      appliedScale: [scaleTorsoX, scaleTorsoY, scaleTorsoZ],
      appliedOffset: [0, targetWaistY, avatar.chestCenterZ]
    };
  }

  /**
   * Calculates proportional scale factors and anatomical offsets.
   */
  public static calculateFittingTransform(
    garment: GarmentGeometryLandmarks,
    avatar: AvatarLandmarks,
    category: GarmentCategoryType,
    isHoodie: boolean,
    options: GarmentFittingOptions
  ): { scale: THREE.Vector3; offset: THREE.Vector3 } {
    const easeTorso = options.easeTorso ?? 1.02;
    const easeShoulder = options.easeShoulder ?? (isHoodie ? 1.06 : 1.04);

    let scaleX = 1.0;
    let scaleY = 1.0;
    let scaleZ = 1.0;
    let offsetY = avatar.waistY;
    let offsetZ = 0.0;

    if (category === 'top' || category === 'outerwear' || category === 'hoodie' || category === 'jacket') {
      // 1. Proportional scaling to match avatar torso height and shoulder span
      const requiredTorsoHeight = avatar.neckY - (avatar.waistY - 0.08);
      if (garment.torsoHeight > 0.1) {
        scaleY = (requiredTorsoHeight / garment.torsoHeight) * easeTorso;
      }
      if (garment.shoulderSpan > 0.1) {
        scaleX = (avatar.shoulderSpan / (garment.shoulderSpan * 0.70)) * easeShoulder;
      }
      scaleZ = scaleX * 1.03; // chest volume ease

      // Clamp scales within reasonable bounds to avoid extreme distortions
      scaleX = THREE.MathUtils.clamp(scaleX, 0.85, 1.25);
      scaleY = THREE.MathUtils.clamp(scaleY, 0.85, 1.20);
      scaleZ = THREE.MathUtils.clamp(scaleZ, 0.85, 1.25);

      // 2. Anchor waistband to avatar waistband (y ~ 0.735m) for continuous torso coverage over trousers
      offsetY = avatar.waistY - 0.08;
      offsetZ = -0.012; // align with spine posture
    } else if (category === 'bottom' || category === 'pants' || category === 'trousers' || category === 'skirt') {
      const legHeight = avatar.waistY - 0.05;
      scaleY = (legHeight / (garment.maxY - garment.minY)) * 1.01;
      scaleX = (avatar.shoulderSpan / garment.shoulderSpan) * 1.02;
      scaleZ = scaleX * 1.02;
      offsetY = 0.05; // cuff starts near ankles
    } else if (category === 'dress' || category === 'outfit') {
      const totalCoverHeight = avatar.neckY - 0.20;
      scaleY = (totalCoverHeight / (garment.maxY - garment.minY)) * 1.01;
      scaleX = (avatar.shoulderSpan / garment.shoulderSpan) * 1.04;
      scaleZ = scaleX * 1.03;
      offsetY = 0.20;
    }

    return {
      scale: new THREE.Vector3(scaleX, scaleY, scaleZ),
      offset: new THREE.Vector3(0, offsetY, offsetZ)
    };
  }
}
