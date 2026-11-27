/**
 * YORVYN PHASE 12.3.2 - FRONTEND CORRECTION-TO-RECONSTRUCTION HANDOFF AUDIT SUITE
 * Tests for DEF-01: Authoritative handoff of category, subcategory and user corrections to 3D generation.
 */

import { describe, it, expect, vi } from 'vitest';
import {
  NORMALIZE_CATEGORY_MAP,
  VALID_CATEGORY_SUBCATEGORIES,
  resolveAuthoritativeReconstructionInput
} from '../PhotoTo3DGarmentModal';
import { fashionApi, api } from '../../services/fashionApi';

describe('Phase 12.3.2 DEF-01: Frontend Correction-to-Reconstruction Handoff', () => {
  it('should map categories correctly to frontend reconstruction categories', () => {
    expect(NORMALIZE_CATEGORY_MAP['top']).toBe('top');
    expect(NORMALIZE_CATEGORY_MAP['tops']).toBe('top');
    expect(NORMALIZE_CATEGORY_MAP['bottom']).toBe('bottom');
    expect(NORMALIZE_CATEGORY_MAP['bottoms']).toBe('bottom');
    expect(NORMALIZE_CATEGORY_MAP['outerwear']).toBe('outerwear');
    expect(NORMALIZE_CATEGORY_MAP['jacket']).toBe('outerwear');
    expect(NORMALIZE_CATEGORY_MAP['dress']).toBe('dress');
    expect(NORMALIZE_CATEGORY_MAP['dresses_and_skirts']).toBe('dress');
    expect(NORMALIZE_CATEGORY_MAP['skirt']).toBe('skirt');
    expect(NORMALIZE_CATEGORY_MAP['footwear']).toBe('footwear');
  });

  it('should validate subcategories across all primary categories', () => {
    expect(VALID_CATEGORY_SUBCATEGORIES['outerwear']).toContain('blazer');
    expect(VALID_CATEGORY_SUBCATEGORIES['outerwear']).toContain('denim_jacket');
    expect(VALID_CATEGORY_SUBCATEGORIES['outerwear']).toContain('formal_coat');
    expect(VALID_CATEGORY_SUBCATEGORIES['outerwear']).toContain('trench_coat');
    expect(VALID_CATEGORY_SUBCATEGORIES['outerwear']).toContain('leather_jacket');
    expect(VALID_CATEGORY_SUBCATEGORIES['outerwear']).toContain('bomber_jacket');

    expect(VALID_CATEGORY_SUBCATEGORIES['dress']).toContain('jumpsuit');
    expect(VALID_CATEGORY_SUBCATEGORIES['dress']).toContain('romper');
    expect(VALID_CATEGORY_SUBCATEGORIES['dress']).toContain('casual_dress');
    expect(VALID_CATEGORY_SUBCATEGORIES['skirt']).toContain('skirt');

    expect(VALID_CATEGORY_SUBCATEGORIES['footwear']).toContain('sneakers');
    expect(VALID_CATEGORY_SUBCATEGORIES['footwear']).toContain('boots');
    expect(VALID_CATEGORY_SUBCATEGORIES['footwear']).toContain('sandals');

    expect(VALID_CATEGORY_SUBCATEGORIES['top']).toContain('formal_shirt');
    expect(VALID_CATEGORY_SUBCATEGORIES['top']).toContain('hoodie');
    expect(VALID_CATEGORY_SUBCATEGORIES['top']).toContain('tshirt');

    expect(VALID_CATEGORY_SUBCATEGORIES['bottom']).toContain('jeans');
    expect(VALID_CATEGORY_SUBCATEGORIES['bottom']).toContain('trousers');
    expect(VALID_CATEGORY_SUBCATEGORIES['bottom']).toContain('shorts');
  });

  it('should give authoritative precedence to manual user corrections (DEF-01)', () => {
    const analysisResult = {
      garment_identity: {
        main_category: 'tops',
        subcategory: 'tshirt',
        confidence: 0.95
      },
      user_correction_state: {
        original_prediction: {
          category: 'tops',
          subcategory: 'tshirt',
          confidence: 0.95
        },
        has_user_correction: true,
        final_reconstruction_input: {
          category: 'outerwear',
          subcategory: 'blazer'
        }
      }
    };

    const userCorrections = {
      category: 'outerwear',
      subcategory: 'blazer',
      fabric: 'wool',
      silhouette: 'regular',
      correction_source: 'candidate_selection'
    };

    const { input, error } = resolveAuthoritativeReconstructionInput(
      analysisResult,
      'outerwear',
      'blazer',
      'cotton',
      'regular',
      userCorrections
    );

    expect(error).toBeNull();
    expect(input).not.toBeNull();
    expect(input?.category).toBe('outerwear');
    expect(input?.subcategory).toBe('blazer');
    expect(input?.isUserCorrected).toBe(true);

    // Verify immutability of original AI prediction
    expect(analysisResult.garment_identity.main_category).toBe('tops');
    expect(analysisResult.user_correction_state.original_prediction.category).toBe('tops');
    expect(input?.provenance.originalPrediction.category).toBe('tops');
    expect(input?.provenance.finalReconstructionInput.subcategory).toBe('blazer');
  });

  it('should fallback to candidate selection in user_correction_state if userCorrections is not present', () => {
    const analysisResult = {
      garment_identity: {
        main_category: 'tops',
        subcategory: 'tshirt',
        confidence: 0.88
      },
      user_correction_state: {
        original_prediction: {
          category: 'tops',
          subcategory: 'tshirt',
          confidence: 0.88
        },
        is_user_corrected: true,
        final_reconstruction_input: {
          category: 'bottom',
          subcategory: 'jeans'
        }
      }
    };

    const { input, error } = resolveAuthoritativeReconstructionInput(
      analysisResult,
      'top',
      'tshirt',
      'cotton',
      'regular',
      undefined
    );

    expect(error).toBeNull();
    expect(input).not.toBeNull();
    expect(input?.category).toBe('bottom');
    expect(input?.subcategory).toBe('jeans');
    expect(input?.isUserCorrected).toBe(true);
  });

  it('should default to original AI prediction when no user correction has been applied', () => {
    const analysisResult = {
      garment_identity: {
        main_category: 'tops',
        subcategory: 'hoodie',
        confidence: 0.96
      },
      user_correction_state: {
        original_prediction: {
          category: 'tops',
          subcategory: 'hoodie',
          confidence: 0.96
        },
        is_user_corrected: false
      }
    };

    const { input, error } = resolveAuthoritativeReconstructionInput(
      analysisResult,
      'top',
      'hoodie',
      'cotton',
      'regular',
      undefined
    );

    expect(error).toBeNull();
    expect(input).not.toBeNull();
    expect(input?.category).toBe('top');
    expect(input?.subcategory).toBe('hoodie');
    expect(input?.isUserCorrected).toBe(false);
  });

  it('fashionApi.createGarment3DJob should include subcategory and detectionMetadata in FormData', async () => {
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({
      data: { job_id: 'job_test_123', status: 'queued', progress: 0, current_stage: 'queued' }
    });

    const file = new File(['mock_image'], 'test.png', { type: 'image/png' });

    const metadata = {
      user_correction_state: {
        is_user_corrected: true,
        final_reconstruction_input: {
          category: 'outerwear',
          subcategory: 'denim_jacket'
        }
      }
    };

    const result = await fashionApi.createGarment3DJob(
      file,
      'outerwear',
      undefined,
      'usr_phase_12_3_2',
      {
        subcategory: 'denim_jacket',
        detectionMetadata: metadata
      }
    );

    expect(result.job_id).toBe('job_test_123');
    expect(postSpy).toHaveBeenCalled();

    const [url, formData] = postSpy.mock.calls[0];
    expect(url).toBe('/garment-gen/jobs');
    expect(formData instanceof FormData).toBe(true);

    const fd = formData as FormData;
    expect(fd.get('category')).toBe('outerwear');
    expect(fd.get('subcategory')).toBe('denim_jacket');
    expect(fd.get('user_id')).toBe('usr_phase_12_3_2');
    expect(JSON.parse(fd.get('detection_metadata') as string)).toEqual(metadata);

    postSpy.mockRestore();
  });
});
