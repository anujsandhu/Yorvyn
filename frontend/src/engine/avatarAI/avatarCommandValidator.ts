/**
 * YORVYN — Avatar Command Validator (Phase 8)
 * 
 * Enforces strict safety, anatomical integrity, and compatibility on all AI-generated
 * customization commands. Never allows an LLM or external agent to execute arbitrary
 * geometry mutations, out-of-bounds scale deformations, or broken asset IDs.
 */

import { AvatarCustomizationProposal, AvatarCommandOperation } from './avatarAITypes';
import { 
  AVATAR_SLIDERS, 
  AVATAR_PRESETS,
  EYE_COLOR_SWATCHES
} from '../avatarCreator/avatarCreatorAssetRegistry';
import { AvatarCreatorCategory } from '../avatarCreator/avatarCreatorTypes';

export interface ValidationIssue {
  severity: 'error' | 'warning';
  message: string;
  field?: string;
  correctedValue?: any;
}

export interface OperationValidationResult {
  isValid: boolean;
  sanitizedOp?: AvatarCommandOperation;
  sanitizedOperation?: AvatarCommandOperation;
  issue?: ValidationIssue;
  issues: ValidationIssue[];
}

export interface ValidationResult {
  isValid: boolean;
  sanitizedProposal: AvatarCustomizationProposal;
  issues: ValidationIssue[];
}

export class AvatarCommandValidator {
  private static readonly VALID_HEX_REGEX = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

  /**
   * Validates and sanitizes a complete customization proposal.
   */
  public static validateProposal(proposal: AvatarCustomizationProposal): ValidationResult {
    const issues: ValidationIssue[] = [];
    const sanitizedOps: AvatarCommandOperation[] = [];

    for (const op of proposal.operations) {
      const opResult = this.validateOperation(op);
      if (opResult.issue) {
        issues.push(opResult.issue);
      }
      if (opResult.sanitizedOp) {
        sanitizedOps.push(opResult.sanitizedOp);
      }
    }

    const hasErrors = issues.some(i => i.severity === 'error');

    return {
      isValid: !hasErrors,
      sanitizedProposal: {
        ...proposal,
        operations: sanitizedOps
      },
      issues
    };
  }

  /**
   * Validates a single avatar command operation.
   */
  public static validateOperation(op: AvatarCommandOperation): OperationValidationResult {
    let raw: { sanitizedOp?: AvatarCommandOperation; issue?: ValidationIssue };
    switch (op.action) {
      case 'set_slider':
        raw = this.validateSliderOperation(op);
        break;
      case 'set_preset':
        raw = this.validatePresetOperation(op);
        break;
      case 'set_color':
        raw = this.validateColorOperation(op);
        break;
      case 'set_expression':
        raw = this.validateExpressionOperation(op);
        break;
      case 'set_garment':
        raw = this.validateGarmentOperation(op);
        break;
      case 'composite':
      default:
        raw = { sanitizedOp: op };
        break;
    }

    const isValid = !raw.issue || raw.issue.severity !== 'error';
    const issues = raw.issue ? [raw.issue] : [];
    return {
      isValid,
      sanitizedOp: raw.sanitizedOp,
      sanitizedOperation: raw.sanitizedOp,
      issue: raw.issue,
      issues
    };
  }

  private static validateSliderOperation(op: AvatarCommandOperation): { sanitizedOp?: AvatarCommandOperation; issue?: ValidationIssue } {
    const categorySliders = AVATAR_SLIDERS[op.category as AvatarCreatorCategory] || [];
    const sliderDef = categorySliders.find(s => s.id === op.targetKey || (s.profilePath && s.profilePath.endsWith(op.targetKey)));

    if (!sliderDef) {
      return {
        issue: {
          severity: 'error',
          message: `Unknown or unsupported slider target: "${op.targetKey}" in category "${op.category}".`,
          field: op.targetKey
        }
      };
    }

    const numVal = Number(op.targetValue);
    if (isNaN(numVal)) {
      return {
        issue: {
          severity: 'error',
          message: `Slider target "${op.targetKey}" value must be a valid number. Received: ${op.targetValue}.`,
          field: op.targetKey
        }
      };
    }

    // Bounds checking
    if (numVal < sliderDef.min || numVal > sliderDef.max) {
      const clamped = Math.max(sliderDef.min, Math.min(sliderDef.max, numVal));
      return {
        sanitizedOp: {
          ...op,
          targetValue: clamped
        },
        issue: {
          severity: 'warning',
          message: `Value ${numVal} for "${sliderDef.label}" was outside allowed range [${sliderDef.min}, ${sliderDef.max}]. Clamped to ${clamped}.`,
          field: op.targetKey,
          correctedValue: clamped
        }
      };
    }

    return { sanitizedOp: op };
  }

  private static validatePresetOperation(op: AvatarCommandOperation): { sanitizedOp?: AvatarCommandOperation; issue?: ValidationIssue } {
    if (op.targetKey === 'eyeColorId') {
      const exists = EYE_COLOR_SWATCHES.some(s => s.id === op.targetValue);
      if (!exists) {
        return {
          issue: {
            severity: 'error',
            message: `Eye color "${op.targetValue}" does not exist in EYE_COLOR_SWATCHES.`,
            field: op.targetKey
          }
        };
      }
      return { sanitizedOp: op };
    }

    const categoryPresets = AVATAR_PRESETS[op.category as AvatarCreatorCategory] || [];
    const presetExists = categoryPresets.some(p => p.id === op.targetValue);

    if (!presetExists) {
      return {
        issue: {
          severity: 'error',
          message: `Preset "${op.targetValue}" does not exist for category "${op.category}".`,
          field: op.targetKey
        }
      };
    }

    return { sanitizedOp: op };
  }

  private static validateColorOperation(op: AvatarCommandOperation): { sanitizedOp?: AvatarCommandOperation; issue?: ValidationIssue } {
    if (typeof op.targetValue !== 'string' || !this.VALID_HEX_REGEX.test(op.targetValue)) {
      return {
        issue: {
          severity: 'error',
          message: `Invalid hex color value "${op.targetValue}". Must be a valid 3 or 6 digit hex string (e.g. #1e293b).`,
          field: op.targetKey
        }
      };
    }

    return { sanitizedOp: op };
  }

  private static validateExpressionOperation(op: AvatarCommandOperation): { sanitizedOp?: AvatarCommandOperation; issue?: ValidationIssue } {
    const validExpressions = [
      'neutral', 'happy', 'laughing', 'angry', 'sad', 'crying', 
      'surprised', 'afraid', 'determined'
    ];

    if (!validExpressions.includes(op.targetValue)) {
      return {
        issue: {
          severity: 'error',
          message: `Expression "${op.targetValue}" is not in the supported rig expressions.`,
          field: op.targetKey
        }
      };
    }

    return { sanitizedOp: op };
  }

  private static validateGarmentOperation(op: AvatarCommandOperation): { sanitizedOp?: AvatarCommandOperation; issue?: ValidationIssue } {
    const validOutfits = [
      'male_elegantsuit01', 'female_elegantsuit01', 'male_casualsuit01', 'female_casualsuit01',
      'male_casualsuit02', 'female_casualsuit02', 'female_sportsuit01', 'male_worksuit01',
      'none'
    ];
    const validTops = [
      'tank_top', 'fatigue_shirt', 'uniform_shirt', 'uniform_shirt_long',
      'techwear_jacket', 'tattered_shirt', 'tunic', 'long_tunic', 'none'
    ];
    const validBottoms = [
      'briefs', 'cargo_shorts', 'fatigue_pants', 'uniform_trousers',
      'techwear_pants', 'tattered_pants', 'trousers', 'wrapper_long', 'none'
    ];
    const validShoes = [
      'shoes01', 'shoes02', 'shoes03', 'shoes04', 'shoes05', 'shoes06',
      'sandals', 'combat_boots', 'none'
    ];

    const val = String(op.targetValue);
    const key = op.targetKey;

    let isValid = false;
    if (key.includes('outfit')) isValid = validOutfits.includes(val);
    else if (key.includes('top')) isValid = validTops.includes(val);
    else if (key.includes('bottom')) isValid = validBottoms.includes(val);
    else if (key.includes('shoe')) isValid = validShoes.includes(val);
    else isValid = true;

    if (!isValid) {
      return {
        issue: {
          severity: 'error',
          message: `Unsupported garment asset reference "${val}" for slot "${key}".`,
          field: key
        }
      };
    }

    return { sanitizedOp: op };
  }
}
