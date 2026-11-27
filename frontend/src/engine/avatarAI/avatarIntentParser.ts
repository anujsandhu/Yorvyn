/**
 * YORVYN — Avatar Intent Parser (Phase 8)
 * 
 * Natural language intent parser for conversational avatar customization.
 * Translates human stylistic requests into validated, structured Avatar DNA proposals.
 */

import { AvatarProfile } from '../../types/avatarProfile';
import { AvatarCustomizationProposal, AvatarCommandOperation } from './avatarAITypes';
import { AvatarCommandValidator } from './avatarCommandValidator';

export class AvatarIntentParser {
  /**
   * Parses natural language instructions into a structured customization proposal.
   */
  public static parse(prompt: string, current: AvatarProfile): AvatarCustomizationProposal {
    const p = prompt.trim().toLowerCase();
    const isMasc = current.genderPresentation !== 'feminine';

    // 1. Multi-Option Request Detection (e.g. "show me three different hairstyle combinations")
    if (p.includes('three') || p.includes('3') || p.includes('combinations') || p.includes('alternatives') || p.includes('options')) {
      if (p.includes('hair') || p.includes('style')) {
        return this.generateHairstyleComboAlternatives(current);
      }
      if (p.includes('outfit') || p.includes('look') || p.includes('dress')) {
        return this.generateOutfitComboAlternatives(current);
      }
    }

    // 2. Face Shape & Morphology
    if (p.includes('narrow') && (p.includes('face') || p.includes('jaw') || p.includes('head'))) {
      const newWidth = Math.max(-1, (current.face.faceWidth ?? 0) - 0.25);
      const newJaw = Math.max(-1, (current.face.jawWidth ?? 0) - 0.20);
      return this.buildProposal({
        title: 'Refined Narrower Facial Structure',
        summary: 'Tapered face width and sculpted jaw angles for a narrower contour',
        category: 'face',
        confidence: 0.94,
        operations: [
          { action: 'set_slider', category: 'face', targetKey: 'faceWidth', targetValue: newWidth, displayLabel: 'Face Width (-25%)' },
          { action: 'set_slider', category: 'face', targetKey: 'jawWidth', targetValue: newJaw, displayLabel: 'Jaw Width (-20%)' }
        ],
        profilePatch: {
          face: {
            ...current.face,
            faceWidth: newWidth,
            jawWidth: newJaw
          }
        },
        explanation: 'Subtly reduced lateral cheek fullness and jaw breadth while maintaining anatomical balance.'
      });
    }

    if (p.includes('chisel') || (p.includes('wide') && p.includes('jaw')) || p.includes('defined jaw')) {
      const newJaw = Math.min(1, (current.face.jawWidth ?? 0) + 0.30);
      const newChin = Math.min(1, (current.face.chinProjection ?? 0) + 0.20);
      return this.buildProposal({
        title: 'Chiseled Jawline Definition',
        summary: 'Prominent jaw breadth with forward chin projection',
        category: 'face',
        confidence: 0.92,
        operations: [
          { action: 'set_slider', category: 'face', targetKey: 'jawWidth', targetValue: newJaw, displayLabel: 'Jaw Width (+30%)' },
          { action: 'set_slider', category: 'face', targetKey: 'chinProjection', targetValue: newChin, displayLabel: 'Chin Projection (+20%)' }
        ],
        profilePatch: {
          face: {
            ...current.face,
            jawWidth: newJaw,
            chinProjection: newChin
          }
        },
        explanation: 'Enhanced mandibular structure for a confident, chiseled editorial silhouette.'
      });
    }

    // 3. Body Proportions & Stature
    if (p.includes('shoulder') && (p.includes('broad') || p.includes('wider') || p.includes('athletic'))) {
      const newShoulders = Math.min(1, (current.proportions.shoulderWidth ?? 0) + 0.35);
      return this.buildProposal({
        title: 'Broader Athletic Shoulder Frame',
        summary: 'Expanded clavicular width to enhance v-taper athletic frame',
        category: 'body',
        confidence: 0.95,
        operations: [
          { action: 'set_slider', category: 'body', targetKey: 'shoulderWidth', targetValue: newShoulders, displayLabel: 'Shoulder Breadth (+35%)' }
        ],
        profilePatch: {
          proportions: {
            ...current.proportions,
            shoulderWidth: newShoulders,
            silhouette: 'athletic'
          }
        },
        explanation: 'Broadened shoulder frame while preserving natural thoracic posture.'
      });
    }

    if (p.includes('athletic') || p.includes('muscle') || p.includes('toned')) {
      return this.buildProposal({
        title: 'Athletic Tapered Silhouette',
        summary: 'Muscular athletic body definition with tapered waist and broader shoulders',
        category: 'body',
        confidence: 0.96,
        operations: [
          { action: 'set_preset', category: 'body', targetKey: 'silhouette', targetValue: 'athletic', displayLabel: 'Athletic Preset' },
          { action: 'set_slider', category: 'body', targetKey: 'muscleDefinition', targetValue: 0.75, displayLabel: 'Muscle Tone (75%)' },
          { action: 'set_slider', category: 'body', targetKey: 'waistWidth', targetValue: -0.15, displayLabel: 'Waist Taper (-15%)' }
        ],
        profilePatch: {
          proportions: {
            ...current.proportions,
            silhouette: 'athletic',
            muscleDefinition: 0.75,
            waistWidth: -0.15
          }
        },
        explanation: 'Configured athletic physique with prominent muscle definition and athletic waist taper.'
      });
    }

    if (p.includes('slender') || p.includes('slim') || p.includes('lean')) {
      return this.buildProposal({
        title: 'Slender Editorial Silhouette',
        summary: 'Elongated limbs with slender waist and subtle muscle tone',
        category: 'body',
        confidence: 0.93,
        operations: [
          { action: 'set_preset', category: 'body', targetKey: 'silhouette', targetValue: 'slender', displayLabel: 'Slender Preset' },
          { action: 'set_slider', category: 'body', targetKey: 'muscleDefinition', targetValue: 0.35, displayLabel: 'Muscle Tone (35%)' }
        ],
        profilePatch: {
          proportions: {
            ...current.proportions,
            silhouette: 'slender',
            muscleDefinition: 0.35
          }
        },
        explanation: 'Transitioned avatar proportions to a high-fashion slender profile.'
      });
    }

    // 4. Hairstyles & Texture
    if (p.includes('modern') && (p.includes('hair') || p.includes('texture') || p.includes('textured'))) {
      const targetHair = isMasc ? 'short01' : 'bob02';
      return this.buildProposal({
        title: isMasc ? 'Modern Textured Crop' : 'Wavy Textured Lob',
        summary: 'Dynamic textured hairstyle with natural movement and crown volume',
        category: 'hair',
        confidence: 0.95,
        operations: [
          { action: 'set_preset', category: 'hair', targetKey: 'hairStyleId', targetValue: targetHair, displayLabel: isMasc ? 'Textured Crop' : 'Wavy Lob' }
        ],
        profilePatch: {
          appearance: {
            ...current.appearance,
            hairStyleId: targetHair
          }
        },
        explanation: 'Selected modern textured hair asset matching head topology and natural crown flow.'
      });
    }

    if (p.includes('fade') || p.includes('taper') || p.includes('short hair') || p.includes('crop')) {
      return this.buildProposal({
        title: 'Clean Low Fade Crop',
        summary: 'Neat short taper cut with clean side profiles',
        category: 'hair',
        confidence: 0.94,
        operations: [
          { action: 'set_preset', category: 'hair', targetKey: 'hairStyleId', targetValue: 'short04', displayLabel: 'Clean Fade' }
        ],
        profilePatch: {
          appearance: {
            ...current.appearance,
            hairStyleId: 'short04'
          }
        },
        explanation: 'Applied sharp fade hairstyle with calibrated skull alignment.'
      });
    }

    if (p.includes('afro') || p.includes('curls') || p.includes('curly') || p.includes('natural hair')) {
      return this.buildProposal({
        title: 'Volumetric Natural Afro',
        summary: 'Sculpted natural textured afro silhouette',
        category: 'hair',
        confidence: 0.96,
        operations: [
          { action: 'set_preset', category: 'hair', targetKey: 'hairStyleId', targetValue: 'afro01', displayLabel: 'Natural Afro' }
        ],
        profilePatch: {
          appearance: {
            ...current.appearance,
            hairStyleId: 'afro01'
          }
        },
        explanation: 'Selected high-definition afro geometry with balanced crown curvature.'
      });
    }

    if (p.includes('braid') || p.includes('cornrow') || p.includes('plaits')) {
      return this.buildProposal({
        title: 'Artisanal Braided Hairstyle',
        summary: 'Intricate braided hairstyle woven close to the scalp',
        category: 'hair',
        confidence: 0.93,
        operations: [
          { action: 'set_preset', category: 'hair', targetKey: 'hairStyleId', targetValue: 'braid01', displayLabel: 'Braided Style' }
        ],
        profilePatch: {
          appearance: {
            ...current.appearance,
            hairStyleId: 'braid01'
          }
        },
        explanation: 'Applied precision braided hair mesh.'
      });
    }

    // 5. Facial Hair
    if (p.includes('boxed beard') || p.includes('short beard') || (p.includes('beard') && p.includes('short'))) {
      return this.buildProposal({
        title: 'Defined Short Boxed Beard',
        summary: 'Clean geometric jaw contour with dense short boxed beard',
        category: 'facial_hair',
        confidence: 0.95,
        operations: [
          { action: 'set_preset', category: 'facial_hair', targetKey: 'facialHairId', targetValue: 'short_beard', displayLabel: 'Short Boxed Beard' }
        ],
        profilePatch: {
          appearance: {
            ...current.appearance,
            facialHairId: 'short_beard'
          }
        },
        explanation: 'Grounded short beard asset mapped directly to the jaw joint coordinates.'
      });
    }

    if (p.includes('stubble') || p.includes('5 o clock shadow')) {
      return this.buildProposal({
        title: 'Refined 5 O’Clock Stubble',
        summary: 'Understated facial stubble shadowing along cheek and jaw',
        category: 'facial_hair',
        confidence: 0.94,
        operations: [
          { action: 'set_preset', category: 'facial_hair', targetKey: 'facialHairId', targetValue: 'stubble', displayLabel: 'Designer Stubble' }
        ],
        profilePatch: {
          appearance: {
            ...current.appearance,
            facialHairId: 'stubble'
          }
        },
        explanation: 'Applied natural micro-density stubble to accentuate jaw bone structure.'
      });
    }

    if (p.includes('clean shaven') || p.includes('no beard') || p.includes('shave')) {
      return this.buildProposal({
        title: 'Clean Shaven Appearance',
        summary: 'Smooth facial complexion without facial hair',
        category: 'facial_hair',
        confidence: 0.98,
        operations: [
          { action: 'set_preset', category: 'facial_hair', targetKey: 'facialHairId', targetValue: 'none', displayLabel: 'Clean Shaven' }
        ],
        profilePatch: {
          appearance: {
            ...current.appearance,
            facialHairId: 'none'
          }
        },
        explanation: 'Removed facial hair layers to reveal natural skin contour.'
      });
    }

    // 6. Eyes & Gaze
    if (p.includes('eye') && (p.includes('color') || p.includes('colour') || p.includes('blue') || p.includes('green') || p.includes('hazel'))) {
      let targetEye = 'blue';
      let eyeName = 'Sapphire Blue';
      if (p.includes('green')) { targetEye = 'green'; eyeName = 'Emerald Green'; }
      else if (p.includes('hazel') || p.includes('light')) { targetEye = 'brownlight'; eyeName = 'Warm Hazel'; }
      else if (p.includes('grey') || p.includes('slate')) { targetEye = 'grey'; eyeName = 'Nordic Slate'; }

      return this.buildProposal({
        title: `${eyeName} Iris Appearance`,
        summary: `Vibrant ${eyeName.toLowerCase()} iris pigmentation with realistic catchlight highlights`,
        category: 'eyes',
        confidence: 0.95,
        operations: [
          { action: 'set_preset', category: 'eyes', targetKey: 'eyeColorId', targetValue: targetEye, displayLabel: eyeName }
        ],
        profilePatch: {
          appearance: {
            ...current.appearance,
            eyeColorId: targetEye
          }
        },
        explanation: 'Applied high-fidelity iris diffuse map with physical clearcoat catchlight.'
      });
    }

    // 7. Skin & Complexion Undertone
    if (p.includes('skin') && (p.includes('undertone') || p.includes('tone') || p.includes('warm') || p.includes('cool') || p.includes('golden'))) {
      const isWarm = p.includes('warm') || p.includes('golden') || p.includes('amber');
      const targetTone = isWarm ? '#e8b58a' : '#eed2bd';
      const targetModel = isWarm 
        ? (isMasc ? 'young_asian_male' : 'young_asian_female')
        : (isMasc ? 'young_caucasian_male' : 'young_caucasian_female');

      return this.buildProposal({
        title: isWarm ? 'Warm Radiant Golden Complexion' : 'Cool Porcelain Balanced Complexion',
        summary: `Refined skin tone pigmentation with ${isWarm ? 'golden warm' : 'rosy cool'} undertones`,
        category: 'skin',
        confidence: 0.93,
        operations: [
          { action: 'set_color', category: 'skin', targetKey: 'skinToneHex', targetValue: targetTone, displayLabel: isWarm ? 'Warm Gold (#e8b58a)' : 'Cool Rose (#eed2bd)' },
          { action: 'set_preset', category: 'skin', targetKey: 'skinModel', targetValue: targetModel, displayLabel: isWarm ? 'Warm Model' : 'Cool Model' }
        ],
        profilePatch: {
          appearance: {
            ...current.appearance,
            skinToneHex: targetTone,
            skinModel: targetModel,
            skinUndertone: isWarm ? 'warm' : 'cool'
          }
        },
        explanation: 'Calibrated subsurface skin scattering parameters to match requested undertone.'
      });
    }

    // 8. Professional / Wardrobe Style Direction
    if (p.includes('professional') || p.includes('formal') || p.includes('suit') || p.includes('business')) {
      const outfitId = isMasc ? 'male_elegantsuit01' : 'female_casualsuit01';
      const shoesId = isMasc ? 'shoes01' : 'shoes05';
      return this.buildProposal({
        title: 'Executive Atelier Professional Ensemble',
        summary: 'Tailored sharp evening suit with structured lapels and polished footwear',
        category: 'clothing',
        confidence: 0.97,
        operations: [
          { action: 'set_garment', category: 'clothing', targetKey: 'outfitId', targetValue: outfitId, displayLabel: 'Tailored Suit' },
          { action: 'set_garment', category: 'clothing', targetKey: 'shoesId', targetValue: shoesId, displayLabel: 'Dress Shoes' },
          { action: 'set_expression', category: 'expressions', targetKey: 'restingExpression', targetValue: 'determined', displayLabel: 'Determined Poise' }
        ],
        profilePatch: {
          face: {
            ...current.face,
            restingExpression: 'determined'
          },
          wardrobe: {
            ...current.wardrobe,
            isBareMannequin: false,
            outfitId,
            topId: 'none',
            bottomId: 'none',
            shoesId
          }
        },
        explanation: 'Dressed character in structured atelier tailoring with polished footwear and confident expression.'
      });
    }

    if (p.includes('streetwear') || p.includes('cyberpunk') || p.includes('techwear')) {
      return this.buildProposal({
        title: 'Cyberpunk Techwear Ensemble',
        summary: 'High-performance hooded windbreaker with tactical modular pants and runners',
        category: 'clothing',
        confidence: 0.96,
        operations: [
          { action: 'set_garment', category: 'clothing', targetKey: 'topId', targetValue: 'techwear_jacket', displayLabel: 'Techwear Jacket' },
          { action: 'set_garment', category: 'clothing', targetKey: 'bottomId', targetValue: 'techwear_pants', displayLabel: 'Tactical Pants' },
          { action: 'set_garment', category: 'clothing', targetKey: 'shoesId', targetValue: 'shoes04', displayLabel: 'Sneakers' }
        ],
        profilePatch: {
          wardrobe: {
            ...current.wardrobe,
            isBareMannequin: false,
            outfitId: 'none',
            topId: 'techwear_jacket',
            bottomId: 'techwear_pants',
            shoesId: 'shoes04'
          }
        },
        explanation: 'Fitted layered techwear separates with responsive footwear.'
      });
    }

    // Default Fallback: General Guidance
    return this.buildProposal({
      title: 'Styling Recommendation: Balanced Refinement',
      summary: 'Harmonious adjustments tailored to your current 3D avatar',
      category: 'face',
      confidence: 0.85,
      operations: [
        { action: 'set_expression', category: 'expressions', targetKey: 'restingExpression', targetValue: 'neutral', displayLabel: 'Neutral Poise' }
      ],
      profilePatch: {
        face: {
          ...current.face,
          restingExpression: 'neutral'
        }
      },
      explanation: `Analyzed your instruction: "${prompt}". Applied subtle natural poise refinement to complement current character traits.`
    });
  }

  /**
   * Generates a 3-option hairstyle comparison set.
   */
  private static generateHairstyleComboAlternatives(current: AvatarProfile): AvatarCustomizationProposal {
    const isMasc = current.genderPresentation !== 'feminine';
    const opt1 = isMasc ? 'short02' : 'bob01';
    const opt2 = isMasc ? 'short01' : 'bob02';
    const opt3 = isMasc ? 'short04' : 'long01';

    const p1 = this.buildProposal({
      title: isMasc ? 'Option 1: Classic Side Part' : 'Option 1: Sleek French Bob',
      summary: 'Timeless architectural silhouette with clean symmetry',
      category: 'hair',
      confidence: 0.95,
      operations: [{ action: 'set_preset', category: 'hair', targetKey: 'hairStyleId', targetValue: opt1, displayLabel: opt1 }],
      profilePatch: { appearance: { ...current.appearance, hairStyleId: opt1 } },
      explanation: 'Flattering classic cut that accentuates balanced facial geometry.'
    });

    const p2 = this.buildProposal({
      title: isMasc ? 'Option 2: Textured Crop' : 'Option 2: Wavy Shoulder Lob',
      summary: 'Modern relaxed texture with natural volume',
      category: 'hair',
      confidence: 0.93,
      operations: [{ action: 'set_preset', category: 'hair', targetKey: 'hairStyleId', targetValue: opt2, displayLabel: opt2 }],
      profilePatch: { appearance: { ...current.appearance, hairStyleId: opt2 } },
      explanation: 'Softens cheekbones with textured movement.'
    });

    const p3 = this.buildProposal({
      title: isMasc ? 'Option 3: Clean Taper Fade' : 'Option 3: Cascading Waves',
      summary: 'Bold contemporary definition',
      category: 'hair',
      confidence: 0.91,
      operations: [{ action: 'set_preset', category: 'hair', targetKey: 'hairStyleId', targetValue: opt3, displayLabel: opt3 }],
      profilePatch: { appearance: { ...current.appearance, hairStyleId: opt3 } },
      explanation: 'Lengthens vertical stature and creates an editorial presence.'
    });

    p1.alternatives = [p1, p2, p3];
    return p1;
  }

  /**
   * Generates a 3-option outfit comparison set.
   */
  private static generateOutfitComboAlternatives(current: AvatarProfile): AvatarCustomizationProposal {
    const isMasc = current.genderPresentation !== 'feminine';
    const p1 = this.buildProposal({
      title: 'Option 1: Executive Tuxedo Suit',
      summary: 'Formal evening tailoring with satin peak lapels',
      category: 'clothing',
      confidence: 0.95,
      operations: [
        { action: 'set_garment', category: 'clothing', targetKey: 'outfitId', targetValue: isMasc ? 'male_elegantsuit01' : 'female_casualsuit01', displayLabel: 'Tailored Suit' }
      ],
      profilePatch: {
        wardrobe: {
          ...current.wardrobe,
          isBareMannequin: false,
          outfitId: isMasc ? 'male_elegantsuit01' : 'female_casualsuit01',
          topId: 'none',
          bottomId: 'none',
          shoesId: 'shoes01'
        }
      },
      explanation: 'Refined sartorial formalwear for high-profile events.'
    });

    const p2 = this.buildProposal({
      title: 'Option 2: Cyberpunk Techwear',
      summary: 'Tactical hooded jacket with utility pants and sneakers',
      category: 'clothing',
      confidence: 0.94,
      operations: [
        { action: 'set_garment', category: 'clothing', targetKey: 'topId', targetValue: 'techwear_jacket', displayLabel: 'Tech Jacket' },
        { action: 'set_garment', category: 'clothing', targetKey: 'bottomId', targetValue: 'techwear_pants', displayLabel: 'Tech Pants' }
      ],
      profilePatch: {
        wardrobe: {
          ...current.wardrobe,
          isBareMannequin: false,
          outfitId: 'none',
          topId: 'techwear_jacket',
          bottomId: 'techwear_pants',
          shoesId: 'shoes04'
        }
      },
      explanation: 'Modern utilitarian street aesthetic with modular technical layers.'
    });

    const p3 = this.buildProposal({
      title: 'Option 3: Heritage Woven Tunic',
      summary: 'Artisanal woven buba tunic with relaxed trousers',
      category: 'clothing',
      confidence: 0.92,
      operations: [
        { action: 'set_garment', category: 'clothing', targetKey: 'topId', targetValue: 'long_tunic', displayLabel: 'Woven Tunic' },
        { action: 'set_garment', category: 'clothing', targetKey: 'bottomId', targetValue: 'trousers', displayLabel: 'Linen Trousers' }
      ],
      profilePatch: {
        wardrobe: {
          ...current.wardrobe,
          isBareMannequin: false,
          outfitId: 'none',
          topId: 'long_tunic',
          bottomId: 'trousers',
          shoesId: 'shoes05'
        }
      },
      explanation: 'Traditional handcrafted textile heritage ensemble.'
    });

    p1.alternatives = [p1, p2, p3];
    return p1;
  }

  private static buildProposal(params: {
    title: string;
    summary: string;
    category: any;
    confidence: number;
    operations: AvatarCommandOperation[];
    profilePatch: Partial<AvatarProfile>;
    explanation: string;
  }): AvatarCustomizationProposal {
    const rawProposal: AvatarCustomizationProposal = {
      id: `prop_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      title: params.title,
      summary: params.summary,
      category: params.category,
      confidence: params.confidence,
      operations: params.operations,
      profilePatch: params.profilePatch,
      explanation: params.explanation,
      createdAt: new Date().toISOString(),
      source: 'conversational',
      status: 'pending'
    };

    const validation = AvatarCommandValidator.validateProposal(rawProposal);
    return validation.sanitizedProposal;
  }
}
