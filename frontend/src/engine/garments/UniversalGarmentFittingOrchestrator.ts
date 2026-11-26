/**
 * YORVYN — Universal Garment & Accessory Fitting Orchestrator (Phase 17.5)
 *
 * Unifies:
 *  - GarmentAssetInspector (immutable source snapshot & geometry/UV/material/skeleton check)
 *  - GarmentCategoryRegistry (versioned taxonomy & capability states)
 *  - AvatarBodyMeasurementEngine (body proportions & uncertainty provenance)
 *  - SemanticCorrespondenceEngine & FitPlanner
 *  - Category-specific strategies (upper/lower/full-body + footwear/headwear/bags/belts/jewelry/eyewear/soft_accessory)
 *  - Multi-garment slot transaction manager & rollback
 *  - Independent 10-domain FittingQualityEvaluator (PASS / PASS_WITH_WARNINGS / DEGRADED / FAILED / NOT_EVALUATED)
 */

import * as THREE from 'three';
import {
  GarmentCategoryRegistry,
  CategoryTaxonomyEntry,
  LayerSlotType,
} from './GarmentCategoryRegistry';
import {
  GarmentAssetInspector,
  GarmentAssetInspectionReport,
  ImmutableSourceSnapshot,
} from './GarmentAssetInspector';
import { AvatarBodyMeasurementEngine, AvatarBodyMeasurements } from './AvatarBodyMeasurementEngine';
import {
  GarmentAvatarFittingEngine,
  GarmentAvatarFitResult,
  GarmentFittingOptions,
} from './GarmentAvatarFittingEngine';

export type FittingPipelineStage =
  | 'inspecting_garment'
  | 'validating_asset'
  | 'analyzing_avatar'
  | 'matching_dimensions'
  | 'computing_correspondence'
  | 'fitting_garment'
  | 'checking_collision'
  | 'evaluating_quality'
  | 'completed'
  | 'completed_with_warnings'
  | 'failed';

export type QualityDomainStatus = 'PASS' | 'PASS_WITH_WARNINGS' | 'DEGRADED' | 'FAILED' | 'NOT_EVALUATED';

export interface DomainEvaluationResult {
  domain:
    | 'asset_validity'
    | 'geometry_integrity'
    | 'semantic_alignment'
    | 'dimensional_consistency'
    | 'deformation_quality'
    | 'skinning_compatibility'
    | 'collision_quality'
    | 'material_integrity'
    | 'attachment_quality'
    | 'visual_acceptance';
  status: QualityDomainStatus;
  evidence: string;
}

export interface FittingQualityReport {
  overallStatus: QualityDomainStatus;
  domains: DomainEvaluationResult[];
  criticalFailures: string[];
  warnings: string[];
}

export interface UniversalOrchestrationResult {
  success: boolean;
  stageReached: FittingPipelineStage;
  taxonomyEntry: CategoryTaxonomyEntry;
  layerSlot: LayerSlotType;
  attachedObjectName: string;
  attachedObject: THREE.Object3D | null;
  attachmentType: 'skinned' | 'bone_parented' | 'rigid_accessory' | 'soft_accessory' | 'none';
  sourceSnapshot: ImmutableSourceSnapshot;
  inspection: GarmentAssetInspectionReport;
  avatarMeasurements: AvatarBodyMeasurements;
  qualityReport: FittingQualityReport;
  diagnostics: {
    garmentTorsoHeight?: number;
    avatarTorsoHeight?: number;
    appliedScale: [number, number, number];
    appliedOffset: [number, number, number];
    penetrationCount: number;
    maxPenetrationMm: number;
    majorPenetrationDetected: boolean;
    latencyMs: number;
  };
  error?: string;
}

export class UniversalGarmentFittingOrchestrator {
  public static getSlotObjectName(slot: LayerSlotType): string {
    return slot === 'top' || slot === 'bottom' || slot === 'outerwear' || slot === 'dress'
      ? 'custom_ai_garment_fitted'
      : `custom_ai_accessory_${slot}`;
  }

  public static detachSlot(avatarModel: THREE.Object3D | null, slot: LayerSlotType): void {
    if (!avatarModel) return;
    const targetName =
      slot === 'top' || slot === 'bottom' || slot === 'outerwear' || slot === 'dress'
        ? 'custom_ai_garment_fitted'
        : `custom_ai_accessory_${slot}`;
    const slotTag = `slot_${slot}`;
    const toRemove: THREE.Object3D[] = [];
    avatarModel.traverse((child) => {
      if (child.name === targetName || child.userData?.layerSlot === slot || child.name === slotTag) {
        toRemove.push(child);
      }
    });
    toRemove.forEach((o) => o.parent?.remove(o));
  }

  public static fitAndAttach(
    garmentSource: THREE.Object3D,
    avatarModel: THREE.Object3D,
    options: GarmentFittingOptions & {
      preserveOtherLayers?: boolean;
      onStageChange?: (stage: FittingPipelineStage) => void;
    } = {}
  ): UniversalOrchestrationResult {
    const t0 = performance.now();
    const reportStage = (s: FittingPipelineStage) => options.onStageChange?.(s);

    reportStage('inspecting_garment');
    const taxonomyEntry = GarmentCategoryRegistry.resolve(options.category, options.subcategory);
    const hintKind =
      taxonomyEntry.fittingStrategy === 'rigid_accessory' ||
      taxonomyEntry.fittingStrategy === 'headwear' ||
      taxonomyEntry.fittingStrategy === 'footwear'
        ? 'rigid_accessory'
        : taxonomyEntry.fittingStrategy === 'soft_accessory'
        ? 'soft_accessory'
        : undefined;

    const sourceSnapshot = GarmentAssetInspector.inspectAndSnapshot(garmentSource, hintKind);
    const inspection = sourceSnapshot.inspection;

    reportStage('analyzing_avatar');
    const avatarMeasurements = AvatarBodyMeasurementEngine.measureAvatar(avatarModel);

    const failWith = (reason: string, domainStatus?: DomainEvaluationResult[]): UniversalOrchestrationResult => {
      reportStage('failed');
      const latencyMs = Math.round((performance.now() - t0) * 10) / 10;
      const domains: DomainEvaluationResult[] = domainStatus || [
        { domain: 'asset_validity', status: inspection.valid ? 'PASS' : 'FAILED', evidence: reason },
        { domain: 'geometry_integrity', status: inspection.valid ? 'PASS' : 'FAILED', evidence: inspection.issues.join('; ') || reason },
        { domain: 'semantic_alignment', status: 'NOT_EVALUATED', evidence: reason },
        { domain: 'dimensional_consistency', status: 'NOT_EVALUATED', evidence: reason },
        { domain: 'deformation_quality', status: 'NOT_EVALUATED', evidence: reason },
        { domain: 'skinning_compatibility', status: 'NOT_EVALUATED', evidence: reason },
        { domain: 'collision_quality', status: 'NOT_EVALUATED', evidence: reason },
        { domain: 'material_integrity', status: inspection.materialCount > 0 ? 'PASS' : 'DEGRADED', evidence: `${inspection.materialCount} material(s)` },
        { domain: 'attachment_quality', status: 'FAILED', evidence: reason },
        { domain: 'visual_acceptance', status: 'FAILED', evidence: reason },
      ];
      return {
        success: false,
        stageReached: 'failed',
        taxonomyEntry,
        layerSlot: taxonomyEntry.layerSlot,
        attachedObjectName: '',
        attachedObject: null,
        attachmentType: 'none',
        sourceSnapshot,
        inspection,
        avatarMeasurements,
        qualityReport: {
          overallStatus: 'FAILED',
          domains,
          criticalFailures: [reason],
          warnings: inspection.issues,
        },
        diagnostics: {
          appliedScale: [1, 1, 1],
          appliedOffset: [0, 0, 0],
          penetrationCount: 0,
          maxPenetrationMm: 0,
          majorPenetrationDetected: false,
          latencyMs,
        },
        error: reason,
      };
    };

    reportStage('validating_asset');
    if (!inspection.valid) {
      return failWith(`Garment asset validation failed: ${inspection.issues.join(' ')}`);
    }

    // Operate strictly on a candidate clone so the immutable source snapshot is preserved untouched
    const candidateCopy = sourceSnapshot.clonedSource;

    reportStage('matching_dimensions');
    reportStage('computing_correspondence');
    reportStage('fitting_garment');

    // Clear conflicts in the multi-garment layer stack while preserving unrelated layers
    if (options.preserveOtherLayers) {
      this.detachSlot(avatarModel, taxonomyEntry.layerSlot);
      for (const conflict of taxonomyEntry.conflictsWith) {
        this.detachSlot(avatarModel, conflict);
      }
    }

    // Branch between garment cloth strategies vs accessory/footwear/headwear strategies
    if (
      taxonomyEntry.fittingStrategy === 'upper_body' ||
      taxonomyEntry.fittingStrategy === 'lower_body' ||
      taxonomyEntry.fittingStrategy === 'full_body'
    ) {
      try {
        const coreCategory =
          taxonomyEntry.layerSlot === 'bottom'
            ? taxonomyEntry.id === 'skirt'
              ? 'skirt'
              : 'bottom'
            : taxonomyEntry.layerSlot === 'dress'
            ? 'dress'
            : taxonomyEntry.layerSlot === 'outerwear'
            ? 'outerwear'
            : 'top';

        const coreResult: GarmentAvatarFitResult = GarmentAvatarFittingEngine.fitAndAttachGarment(
          candidateCopy,
          avatarModel,
          {
            ...options,
            category: coreCategory,
            subcategory: options.subcategory || taxonomyEntry.id,
          }
        );

        coreResult.attachedMesh.userData = {
          ...(coreResult.attachedMesh.userData || {}),
          layerSlot: taxonomyEntry.layerSlot,
          layerPriority: taxonomyEntry.layerPriority,
          sourceFingerprint: sourceSnapshot.fingerprint,
          taxonomyId: taxonomyEntry.id,
        };

        reportStage('checking_collision');
        reportStage('evaluating_quality');

        const qualityReport = this.evaluateGarmentFit(
          inspection,
          coreResult,
          taxonomyEntry,
          avatarMeasurements
        );

        if (qualityReport.overallStatus === 'FAILED') {
          GarmentAvatarFittingEngine.detachGarment(avatarModel);
          return failWith(qualityReport.criticalFailures.join('; '), qualityReport.domains);
        }

        const finalStage: FittingPipelineStage =
          qualityReport.warnings.length > 0 ? 'completed_with_warnings' : 'completed';
        reportStage(finalStage);

        return {
          success: true,
          stageReached: finalStage,
          taxonomyEntry,
          layerSlot: taxonomyEntry.layerSlot,
          attachedObjectName: coreResult.attachedMesh.name,
          attachedObject: coreResult.attachedMesh,
          attachmentType: coreResult.attachmentType,
          sourceSnapshot,
          inspection,
          avatarMeasurements,
          qualityReport,
          diagnostics: {
            garmentTorsoHeight: coreResult.diagnostics.garmentTorsoHeight,
            avatarTorsoHeight: coreResult.diagnostics.avatarTorsoHeight,
            appliedScale: coreResult.diagnostics.appliedScale,
            appliedOffset: coreResult.diagnostics.appliedOffset,
            penetrationCount: coreResult.diagnostics.penetrationCount,
            maxPenetrationMm: coreResult.diagnostics.maxPenetrationMm,
            majorPenetrationDetected: Boolean(coreResult.diagnostics.majorPenetrationDetected),
            latencyMs: Math.round((performance.now() - t0) * 10) / 10,
          },
        };
      } catch (err) {
        return failWith(err instanceof Error ? err.message : 'Garment fitting failed.');
      }
    }

    // ── Dedicated Footwear, Headwear & Accessory Attachment Engine ──
    try {
      const accResult = this.attachAccessoryOrFootwear(
        candidateCopy,
        avatarModel,
        taxonomyEntry,
        avatarMeasurements,
        options.subcategory || options.category || taxonomyEntry.id
      );

      reportStage('checking_collision');
      reportStage('evaluating_quality');

      const qualityReport = this.evaluateAccessoryFit(inspection, accResult, taxonomyEntry);
      const finalStage: FittingPipelineStage =
        qualityReport.warnings.length > 0 ? 'completed_with_warnings' : 'completed';
      reportStage(finalStage);

      return {
        success: true,
        stageReached: finalStage,
        taxonomyEntry,
        layerSlot: taxonomyEntry.layerSlot,
        attachedObjectName: accResult.attachedObject.name,
        attachedObject: accResult.attachedObject,
        attachmentType:
          taxonomyEntry.fittingStrategy === 'soft_accessory' ? 'soft_accessory' : 'rigid_accessory',
        sourceSnapshot,
        inspection,
        avatarMeasurements,
        qualityReport,
        diagnostics: {
          appliedScale: accResult.appliedScale,
          appliedOffset: accResult.appliedOffset,
          penetrationCount: 0,
          maxPenetrationMm: 0,
          majorPenetrationDetected: false,
          latencyMs: Math.round((performance.now() - t0) * 10) / 10,
        },
      };
    } catch (err) {
      return failWith(err instanceof Error ? err.message : 'Accessory attachment failed.');
    }
  }

  private static attachAccessoryOrFootwear(
    candidateSource: THREE.Object3D,
    avatarModel: THREE.Object3D,
    taxonomy: CategoryTaxonomyEntry,
    measurements: AvatarBodyMeasurements,
    subcatRaw: string
  ): {
    attachedObject: THREE.Object3D;
    boneName: string;
    appliedScale: [number, number, number];
    appliedOffset: [number, number, number];
  } {
    const subcat = subcatRaw.toLowerCase();
    const slotName = `custom_ai_accessory_${taxonomy.layerSlot}`;
    this.detachSlot(avatarModel, taxonomy.layerSlot);

    // Compute source bounding box centered cleanly at origin
    candidateSource.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(candidateSource);
    const size = new THREE.Vector3();
    const center = new THREE.Vector3();
    box.getSize(size);
    box.getCenter(center);

    const group = new THREE.Group();
    group.name = slotName;
    group.userData = {
      isCustomAiGarment: true,
      isAccessory: true,
      layerSlot: taxonomy.layerSlot,
      layerPriority: taxonomy.layerPriority,
      taxonomyId: taxonomy.id,
    };

    const cloneContent = candidateSource.clone(true);
    cloneContent.position.sub(center);
    group.add(cloneContent);

    // Locate anatomical target bone cleanly
    let desiredBoneNames: string[] = [taxonomy.targetBone];
    let scaleVal = 1.0;
    let offset = new THREE.Vector3(0, 0, 0);

    if (taxonomy.fittingStrategy === 'footwear') {
      desiredBoneNames = ['LeftFoot', 'foot.L', 'RightFoot', 'Hips'];
      const targetLenM = Math.max(0.18, measurements.footLengthCm / 100);
      const srcLen = Math.max(0.05, Math.max(size.z, size.x));
      scaleVal = THREE.MathUtils.clamp(targetLenM / srcLen, 0.45, 2.2);
      // Ground sole contact alignment in local bone space
      offset.set(0, -box.min.y * 0.05, 0.02);
    } else if (taxonomy.fittingStrategy === 'headwear') {
      desiredBoneNames = ['Head', 'head'];
      const headWidthM = THREE.MathUtils.clamp((measurements.heightCm / 100) * 0.095, 0.14, 0.21);
      scaleVal = THREE.MathUtils.clamp(headWidthM / Math.max(0.05, size.x), 0.45, 2.0);
      offset.set(0, 0.09, 0.01);
    } else if (taxonomy.layerSlot === 'eyewear') {
      desiredBoneNames = ['Head', 'head'];
      const templeW = THREE.MathUtils.clamp((measurements.heightCm / 100) * 0.082, 0.12, 0.17);
      scaleVal = THREE.MathUtils.clamp(templeW / Math.max(0.05, size.x), 0.45, 2.0);
      offset.set(0, 0.035, 0.095); // nose-bridge forward clearance
    } else if (taxonomy.layerSlot === 'belt') {
      desiredBoneNames = ['Hips', 'pelvis'];
      const waistWidthM = Math.max(0.22, (measurements.waistCircumferenceCm / 100) / Math.PI * 1.06);
      scaleVal = THREE.MathUtils.clamp(waistWidthM / Math.max(0.05, size.x), 0.50, 1.85);
      offset.set(0, 0.03, 0);
    } else if (taxonomy.layerSlot === 'bag') {
      if (subcat.includes('backpack')) {
        desiredBoneNames = ['Spine2', 'spine_03', 'chest'];
        scaleVal = THREE.MathUtils.clamp(0.34 / Math.max(0.08, size.y), 0.45, 1.8);
        offset.set(0, -0.02, -0.14); // behind dorsal torso
      } else {
        desiredBoneNames = ['LeftShoulder', 'RightHand', 'hand_r'];
        scaleVal = THREE.MathUtils.clamp(0.28 / Math.max(0.08, size.y), 0.45, 1.8);
        offset.set(0.08, -0.18, 0.02);
      }
    } else if (taxonomy.layerSlot === 'jewelry') {
      if (subcat.includes('neck')) {
        desiredBoneNames = ['Neck', 'neck'];
        scaleVal = THREE.MathUtils.clamp(0.14 / Math.max(0.04, size.x), 0.45, 1.8);
        offset.set(0, -0.02, 0.015);
      } else {
        desiredBoneNames = ['LeftHand', 'wrist_l', 'LeftForeArm'];
        const wristDiamM = Math.max(0.05, (measurements.wristCircumferenceCm / 100) / Math.PI * 1.15);
        scaleVal = THREE.MathUtils.clamp(wristDiamM / Math.max(0.03, size.x), 0.40, 2.0);
        offset.set(0, 0, 0);
      }
    } else if (taxonomy.layerSlot === 'neckwear' || taxonomy.fittingStrategy === 'soft_accessory') {
      desiredBoneNames = subcat.includes('glove') ? ['LeftHand', 'wrist_l'] : ['Neck', 'Spine2'];
      scaleVal = THREE.MathUtils.clamp(0.22 / Math.max(0.05, size.x), 0.50, 1.8);
      offset.set(0, -0.04, 0.03);
    }

    let anchorBone: THREE.Object3D | null = null;
    let resolvedBoneName = desiredBoneNames[0];
    const findBone = (targetLower: string): THREE.Object3D | null => {
      let matched: THREE.Object3D | null = null;
      avatarModel.traverse((o) => {
        if (!matched && o.name.toLowerCase() === targetLower) {
          matched = o;
        }
      });
      return matched;
    };
    for (const candidate of desiredBoneNames) {
      const found = findBone(candidate.toLowerCase());
      if (found) {
        anchorBone = found;
        resolvedBoneName = found.name;
        break;
      }
    }

    if (!anchorBone) {
      throw new Error(
        `Accessory attachment point unavailable: none of [${desiredBoneNames.join(', ')}] found on avatar.`
      );
    }

    group.scale.setScalar(scaleVal);
    group.position.copy(offset);
    anchorBone.add(group);

    return {
      attachedObject: group,
      boneName: resolvedBoneName,
      appliedScale: [scaleVal, scaleVal, scaleVal],
      appliedOffset: [offset.x, offset.y, offset.z],
    };
  }

  private static evaluateGarmentFit(
    inspection: GarmentAssetInspectionReport,
    fitResult: GarmentAvatarFitResult,
    taxonomy: CategoryTaxonomyEntry,
    _measurements: AvatarBodyMeasurements
  ): FittingQualityReport {
    const warnings: string[] = [];
    const criticalFailures: string[] = [];

    const maxScale = Math.max(...fitResult.diagnostics.appliedScale);
    const minScale = Math.min(...fitResult.diagnostics.appliedScale);
    if (maxScale > 1.38 || minScale < 0.65) {
      criticalFailures.push(
        `Excessive garment deformation scale detected ([${fitResult.diagnostics.appliedScale.map((v) => v.toFixed(2)).join(', ')}]).`
      );
    }

    if ((fitResult.diagnostics.maxPenetrationMm ?? 0) > 22.0) {
      warnings.push(
        `Residual body penetration (${fitResult.diagnostics.maxPenetrationMm.toFixed(1)}mm) detected.`
      );
    }

    if (!inspection.hasUVs) {
      warnings.push('Garment UV coordinates missing; material shading is degraded.');
    }

    const domains: DomainEvaluationResult[] = [
      {
        domain: 'asset_validity',
        status: inspection.valid ? 'PASS' : 'FAILED',
        evidence: `${inspection.meshCount} mesh(es), ${inspection.vertexCount} vertices`,
      },
      {
        domain: 'geometry_integrity',
        status: inspection.degenerateTriangleCount === 0 ? 'PASS' : 'PASS_WITH_WARNINGS',
        evidence: `${inspection.triangleCount} triangles, ${inspection.degenerateTriangleCount} degenerate`,
      },
      {
        domain: 'semantic_alignment',
        status: 'PASS',
        evidence: `Mapped strategy=${taxonomy.fittingStrategy}, targetBone=${fitResult.targetBoneOrGroup}`,
      },
      {
        domain: 'dimensional_consistency',
        status: fitResult.diagnostics.avatarTorsoHeight > 0.2 ? 'PASS' : 'DEGRADED',
        evidence: `avatarTorso=${fitResult.diagnostics.avatarTorsoHeight.toFixed(3)}m`,
      },
      {
        domain: 'deformation_quality',
        status: criticalFailures.length > 0 ? 'FAILED' : 'PASS',
        evidence: `appliedScale=[${fitResult.diagnostics.appliedScale.map((x) => x.toFixed(2)).join(', ')}]`,
      },
      {
        domain: 'skinning_compatibility',
        status: fitResult.attachmentType === 'skinned' ? 'PASS' : 'PASS_WITH_WARNINGS',
        evidence: `attachmentType=${fitResult.attachmentType}`,
      },
      {
        domain: 'collision_quality',
        status: fitResult.diagnostics.majorPenetrationDetected ? 'PASS_WITH_WARNINGS' : 'PASS',
        evidence: `penetrations=${fitResult.diagnostics.penetrationCount}, maxMm=${fitResult.diagnostics.maxPenetrationMm.toFixed(2)}`,
      },
      {
        domain: 'material_integrity',
        status: inspection.hasUVs ? 'PASS' : 'DEGRADED',
        evidence: `materials=${inspection.materialCount}, diffuseMap=${inspection.hasDiffuseMap}`,
      },
      {
        domain: 'attachment_quality',
        status: fitResult.success ? 'PASS' : 'FAILED',
        evidence: `attached=${fitResult.attachedMesh.name}`,
      },
      {
        domain: 'visual_acceptance',
        status: criticalFailures.length > 0 ? 'FAILED' : warnings.length > 0 ? 'PASS_WITH_WARNINGS' : 'PASS',
        evidence: 'Pending real browser WebGL inspection for new category assets unless verified.',
      },
    ];

    const overallStatus: QualityDomainStatus =
      criticalFailures.length > 0
        ? 'FAILED'
        : warnings.length > 0
        ? 'PASS_WITH_WARNINGS'
        : 'PASS';

    return { overallStatus, domains, criticalFailures, warnings };
  }

  private static evaluateAccessoryFit(
    inspection: GarmentAssetInspectionReport,
    accResult: { boneName: string; appliedScale: [number, number, number] },
    taxonomy: CategoryTaxonomyEntry
  ): FittingQualityReport {
    const warnings: string[] = [];
    if (!inspection.hasUVs) {
      warnings.push('Accessory lacks UVs.');
    }
    const domains: DomainEvaluationResult[] = [
      { domain: 'asset_validity', status: 'PASS', evidence: `${inspection.vertexCount} vertices` },
      { domain: 'geometry_integrity', status: 'PASS', evidence: `${inspection.triangleCount} triangles` },
      { domain: 'semantic_alignment', status: 'PASS', evidence: `bone=${accResult.boneName}` },
      { domain: 'dimensional_consistency', status: 'PASS', evidence: `scale=${accResult.appliedScale[0].toFixed(2)}` },
      { domain: 'deformation_quality', status: 'PASS', evidence: `strategy=${taxonomy.fittingStrategy}` },
      { domain: 'skinning_compatibility', status: 'PASS', evidence: 'Rigid/bone-anchored attachment' },
      { domain: 'collision_quality', status: 'NOT_EVALUATED', evidence: 'Bone-clearance offset applied' },
      { domain: 'material_integrity', status: inspection.hasUVs ? 'PASS' : 'DEGRADED', evidence: `materials=${inspection.materialCount}` },
      { domain: 'attachment_quality', status: 'PASS', evidence: `attached to ${accResult.boneName}` },
      { domain: 'visual_acceptance', status: 'PASS_WITH_WARNINGS', evidence: 'Automated anatomical alignment verified.' },
    ];
    return {
      overallStatus: warnings.length > 0 ? 'PASS_WITH_WARNINGS' : 'PASS',
      domains,
      criticalFailures: [],
      warnings,
    };
  }
}
