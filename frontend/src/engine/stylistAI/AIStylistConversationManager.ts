/**
 * YORVYN — Conversational AI Stylist Manager (Phase 11)
 * Natural language intent parsing, structured proposal generation,
 * and conversational styling orchestration.
 */

import {
  StylistIntent,
  StylistProposal,
  OutfitRecommendation,
  OccasionType,
  ClothingStyle,
  WeatherContext,
  PersonalFashionProfile
} from './types';
import { OutfitRecommendationEngine } from './OutfitRecommendationEngine';
import { OutfitPreviewOrchestrator } from './OutfitPreviewOrchestrator';
import { HumanParams } from '../ara/core/params';
import { AvatarProfile } from '../../types/avatarProfile';

export class AIStylistConversationManager {
  private recommendationEngine: OutfitRecommendationEngine;
  private previewOrchestrator: OutfitPreviewOrchestrator;

  constructor(
    recommendationEngine?: OutfitRecommendationEngine,
    previewOrchestrator?: OutfitPreviewOrchestrator
  ) {
    this.recommendationEngine = recommendationEngine || new OutfitRecommendationEngine();
    this.previewOrchestrator = previewOrchestrator || new OutfitPreviewOrchestrator();
  }

  /**
   * Parses natural language user prompts into a strongly typed StylistIntent.
   */
  public parseIntent(prompt: string): StylistIntent {
    const p = prompt.toLowerCase();

    // 1. Detect Occasion
    let occasion: OccasionType | undefined;
    if (p.includes('college') || p.includes('campus') || p.includes('university')) occasion = 'college';
    else if (p.includes('interview')) occasion = 'interview';
    else if (p.includes('formal') || p.includes('business formal') || p.includes('boardroom')) occasion = 'business_formal';
    else if (p.includes('work') || p.includes('office')) occasion = 'work_office';
    else if (p.includes('wedding') || p.includes('festive') || p.includes('diwali') || p.includes('sangeet')) occasion = 'wedding_festive';
    else if (p.includes('gala') || p.includes('evening')) occasion = 'gala_evening';
    else if (p.includes('party') || p.includes('club') || p.includes('night out')) occasion = 'party_night';
    else if (p.includes('travel') || p.includes('airport') || p.includes('flight')) occasion = 'travel_airport';
    else if (p.includes('date') || p.includes('dinner')) occasion = 'date_night';
    else if (p.includes('gym') || p.includes('workout') || p.includes('sport')) occasion = 'gym_sport';
    else if (p.includes('brunch') || p.includes('weekend')) occasion = 'weekend_brunch';
    else if (p.includes('casual')) occasion = 'casual_day';

    // 2. Detect Style
    let style: ClothingStyle | undefined;
    if (p.includes('streetwear') || p.includes('urban') || p.includes('hype')) style = 'streetwear';
    else if (p.includes('minimal') || p.includes('scandi') || p.includes('clean')) style = 'minimalist';
    else if (p.includes('quiet luxury') || p.includes('luxury') || p.includes('old money')) style = 'quiet_luxury';
    else if (p.includes('formal') || p.includes('tuxedo') || p.includes('suit')) style = 'formal';
    else if (p.includes('business')) style = 'business';
    else if (p.includes('festive') || p.includes('ethnic') || p.includes('traditional')) style = 'festive';
    else if (p.includes('sportswear') || p.includes('athletic')) style = 'sportswear';
    else if (p.includes('vintage') || p.includes('retro')) style = 'vintage';
    else if (p.includes('casual')) style = 'casual';

    // 3. Detect Budget Limits
    let budgetLimit: number | undefined;
    const budgetMatch = p.match(/(?:under|below|budget of|within)\s*(?:₹|rs\.?|inr)?\s*([0-9,]+)/i);
    if (budgetMatch) {
      budgetLimit = parseInt(budgetMatch[1].replace(/,/g, ''), 10);
    }

    // 4. Detect Intent Type
    if (p.includes('sneaker') || p.includes('shoe') || p.includes('footwear')) {
      return {
        type: 'find_alternatives',
        targetSlot: 'footwear',
        occasion,
        style,
        query: prompt
      };
    }

    if (p.includes('trouser') || p.includes('pant') || p.includes('jean')) {
      return {
        type: 'find_alternatives',
        targetSlot: 'bottom',
        occasion,
        style,
        query: prompt
      };
    }

    if (p.includes('colour') || p.includes('color') || p.includes('palette')) {
      return {
        type: 'color_advice',
        occasion,
        style,
        query: prompt
      };
    }

    if (p.includes('minimal')) {
      return {
        type: 'minimal_styling',
        style: 'minimalist',
        occasion,
        query: prompt
      };
    }

    if (budgetLimit) {
      return {
        type: 'budget_filter',
        budgetLimit,
        occasion,
        style,
        query: prompt
      };
    }

    return {
      type: 'recommend_outfit',
      occasion,
      style,
      budgetLimit,
      query: prompt
    };
  }

  /**
   * Processes a user chat message, generates structured recommendations, and stages preview.
   */
  public async handleMessage(
    userMessage: string,
    profile: PersonalFashionProfile,
    currentParams: HumanParams,
    weather?: WeatherContext,
    avatarProfile?: Partial<AvatarProfile>
  ): Promise<StylistProposal> {
    const intent = this.parseIntent(userMessage);

    const recs = this.recommendationEngine.generateOutfits(profile, {
      occasion: intent.occasion,
      style: intent.style,
      budgetLimit: intent.budgetLimit,
      weather,
      avatarProfile,
      maxResults: 3
    });

    if (recs.length === 0) {
      // Fallback to casual day ensemble
      const fallbackRecs = this.recommendationEngine.generateOutfits(profile, {
        occasion: 'casual_day',
        style: 'casual',
        weather,
        avatarProfile,
        maxResults: 1
      });
      recs.push(...fallbackRecs);
    }

    const selectedOutfit = recs[0];
    const staged = this.previewOrchestrator.stageOutfit(selectedOutfit, currentParams);

    const explanation = this.formulateConversationalReply(intent, selectedOutfit, recs.length);

    return {
      id: `prop_${Date.now()}`,
      intent,
      recommendations: recs,
      selectedOutfitIndex: 0,
      explanation,
      appliedParams: staged.stagedParams,
      stagedAt: new Date().toISOString()
    };
  }

  private formulateConversationalReply(intent: StylistIntent, outfit: OutfitRecommendation, totalOptions: number): string {
    const title = outfit.title;
    const match = outfit.matchScore;

    if (intent.type === 'budget_filter') {
      return `I've assembled the "${title}" (${match}% match), keeping the total combination within your budget at ${outfit.priceDisplay}. It pairs cleanly on your 3D avatar.`;
    }

    if (intent.type === 'find_alternatives') {
      return `Here are ${totalOptions} alternative combinations featuring ${outfit.top.name} and ${outfit.bottom.name}. I've draped option 1 on your 3D twin.`;
    }

    if (intent.type === 'minimal_styling') {
      return `Streamlined your look with the "${title}" (${match}% match). Understated monochrome lines and minimal layering create a crisp, modern aesthetic.`;
    }

    return `I recommend the "${title}" (${match}% match). ${outfit.stylingExplanation} I've staged this look directly onto your 3D avatar for inspection.`;
  }
}
