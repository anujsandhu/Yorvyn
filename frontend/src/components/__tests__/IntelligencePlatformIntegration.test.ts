import { describe, expect, it, vi, beforeEach } from 'vitest';
import { intelligenceApi, intelligenceHttp } from '../../services/intelligenceApi';

describe('YIP intelligenceApi client (Phase 17.0)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('ranks smart wardrobe search via /intelligence/multimodal/similarity', async () => {
    const spy = vi.spyOn(intelligenceHttp, 'post').mockResolvedValueOnce({
      data: {
        matches: [{ item_id: 'w1', similarity_score: 0.91, matched_attributes: ['denim', 'jacket'] }],
      },
    } as any);

    const out = await intelligenceApi.rankWardrobeSearch('denim jacket', [{ id: 'w1', name: 'Denim Jacket' }]);
    expect(spy).toHaveBeenCalledWith('/multimodal/similarity', expect.objectContaining({ query_text: 'denim jacket' }));
    expect(out[0].item_id).toBe('w1');
  });

  it('fetches owner-scoped wardrobe recommendations', async () => {
    const spy = vi.spyOn(intelligenceHttp, 'get').mockResolvedValueOnce({
      data: {
        suggestions: [{ item_id: 'w2', name: 'Navy Coat', category: 'outerwear', color: 'navy', affinity_score: 88, rationale: ['Color match'] }],
      },
    } as any);

    const recs = await intelligenceApi.getWardrobeRecommendations('formal');
    expect(spy).toHaveBeenCalledWith('/personalization/recommendations', expect.any(Object));
    expect(recs[0].name).toBe('Navy Coat');
  });

  it('parses quality critic summary cleanly without exposing internal model IDs', async () => {
    vi.spyOn(intelligenceHttp, 'post').mockResolvedValueOnce({
      data: {
        publication_allowed: true,
        overall_status: 'PASSED_WITH_WARNINGS',
        critical_defect_count: 0,
        major_defect_count: 0,
        minor_defect_count: 1,
        domains: { fit: { score: 86, metrics: { fit_classification: 'Regular' } } },
        defects: [{ suggested_action: 'Check hem clearance.' }],
      },
    } as any);

    const fb = await intelligenceApi.inspectJobQuality('job_123', 'jacket');
    expect(fb.publication_allowed).toBe(true);
    expect(fb.fit_classification).toBe('Regular');
    expect(fb.suggestions).toEqual(['Check hem clearance.']);
  });

  it('calls hybrid recommendation, outfit recommendation, and feedback routes cleanly', async () => {
    const postSpy = vi.spyOn(intelligenceHttp, 'post')
      .mockResolvedValueOnce({
        data: {
          owner_id: 'u1',
          surface: 'wardrobe',
          algorithm_mode: 'hybrid',
          ranking_version: '17.0-rec-v1',
          preset_used: 'hybrid_balanced',
          consent_granted: true,
          cold_start_mode: false,
          recommendations: [{
            item_id: 'w9',
            name: 'Merino Knit',
            category: 'tops',
            subcategory: 'sweater',
            color: 'navy',
            style: ['quiet_luxury'],
            fit: 'regular',
            material: 'wool',
            final_score: 0.92,
            normalized_signals: { user_preference_relevance: 0.9 },
            reasons: [{ code: 'preferred_category', message: 'Matches preferred categories: tops', supporting_signal: 'category_affinity', signal_value: 0.9 }],
            is_exploration: false,
          }],
          category_recommendations: { tops: 0.92 },
          knowledge_notes: [],
        },
      } as any)
      .mockResolvedValueOnce({
        data: {
          owner_id: 'u1',
          occasion: 'smart_casual',
          compatibility_is_prediction_not_rule: true,
          outfits: [{ outfit_id: 'o1', title: 'Smart Casual Look', items: [], compatibility_prediction: 0.87, color_harmony_score: 0.9, style_compatibility_score: 0.85, occasion: 'smart_casual', rationale: [] }],
          complementary_items: [],
          wardrobe_gaps: [],
        },
      } as any)
      .mockResolvedValueOnce({
        data: { recorded: true, interaction_type: 'liked', treated_as_positive_preference: true },
      } as any);

    const h = await intelligenceApi.getHybridRecommendations({ surface: 'wardrobe', topK: 4 });
    expect(postSpy).toHaveBeenNthCalledWith(1, '/recommendations/hybrid', expect.objectContaining({ surface: 'wardrobe', top_k: 4 }));
    expect(h.recommendations[0].item_id).toBe('w9');

    const o = await intelligenceApi.getOutfitRecommendations({ occasion: 'smart_casual' });
    expect(postSpy).toHaveBeenNthCalledWith(2, '/recommendations/outfit', expect.objectContaining({ occasion: 'smart_casual' }));
    expect(o.compatibility_is_prediction_not_rule).toBe(true);

    const r = await intelligenceApi.recordRecommendationFeedback({ interactionType: 'liked', itemData: { id: 'w9' } });
    expect(postSpy).toHaveBeenNthCalledWith(3, '/recommendations/feedback', expect.objectContaining({ interaction_type: 'liked' }));
    expect(r.recorded).toBe(true);

    postSpy.mockResolvedValueOnce({ data: { recommendations: [{ item_id: 'w10', name: 'Camel Coat' }] } } as any);
    const sim = await intelligenceApi.getSimilarGarments({ id: 'w9', category: 'outerwear' }, 3);
    expect(postSpy).toHaveBeenNthCalledWith(4, '/recommendations/hybrid', expect.objectContaining({ mode: 'neural_hybrid', surface: 'similar_items' }));
    expect(sim[0].item_id).toBe('w10');

    postSpy
      .mockResolvedValueOnce({
        data: { query: 'merino twill', internal_hits: [], external_evidence: [], external_status: 'BLOCKED_NO_CREDENTIALS', warnings: [] },
      } as any)
      .mockResolvedValueOnce({
        data: { thread_id: 'lg_1', workflow_name: 'garment.research', status: 'COMPLETED', awaiting_confirmation: false, state: {} },
      } as any);

    const web = await intelligenceApi.searchExternalWeb('merino twill');
    expect(postSpy).toHaveBeenNthCalledWith(5, '/web/search', expect.objectContaining({ query: 'merino twill', include_internal_rag: true }));
    expect(web.external_status).toBe('BLOCKED_NO_CREDENTIALS');

    const wf = await intelligenceApi.executeWorkflow('garment.research', { query: 'wool drape' });
    expect(postSpy).toHaveBeenNthCalledWith(6, '/workflows/execute', expect.objectContaining({ workflow_name: 'garment.research' }));
    expect(wf.status).toBe('COMPLETED');
  });
});
