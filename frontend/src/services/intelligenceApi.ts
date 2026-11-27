/**
 * YORVYN Intelligence Platform (YIP) Frontend Service Client (Phase 17.0).
 * Exposes human-friendly garment quality checks, smart wardrobe search & recommendations,
 * fit analysis, and construction knowledge grounding via authenticated `/api/intelligence` routes.
 * Never exposes internal model IDs, raw embeddings, or low-level solver internals to normal users.
 */
import axios, { AxiosInstance } from 'axios';
import { supabase } from '../utils/supabase';

const INTELLIGENCE_BASE_URL =
  import.meta.env.VITE_INTELLIGENCE_API_URL || `${import.meta.env.VITE_API_URL || '/api'}/intelligence`;

export const intelligenceHttp: AxiosInstance = axios.create({
  baseURL: INTELLIGENCE_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

intelligenceHttp.interceptors.request.use(async (config) => {
  try {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (session?.access_token) {
      config.headers.Authorization = `Bearer ${session.access_token}`;
    }
  } catch {
    // Allow graceful fallback if no active auth session exists yet
  }
  return config;
});

export interface SmartSearchMatch {
  item_id: string;
  similarity_score: number;
  matched_attributes: string[];
}

export interface WardrobeRecommendationItem {
  item_id: string;
  name: string;
  category: string;
  color: string;
  affinity_score: number;
  rationale: string[];
}

export interface GarmentQualityFeedback {
  publication_allowed: boolean;
  overall_status: string;
  critical_defect_count: number;
  major_defect_count: number;
  minor_defect_count: number;
  fit_classification?: string;
  fit_score?: number;
  suggestions: string[];
}

export interface KnowledgeHint {
  title: string;
  snippet: string;
  source: string;
  domain: string;
}

export interface RecommendationReason {
  code: string;
  message: string;
  supporting_signal: string;
  signal_value: number;
}

export interface HybridRecommendationItem {
  item_id: string;
  name: string;
  category: string;
  subcategory: string;
  color: string;
  style: string[];
  fit: string;
  material: string;
  image_url?: string;
  final_score: number;
  normalized_signals: Record<string, number>;
  reasons: RecommendationReason[];
  is_exploration: boolean;
}

export interface HybridRecommendationResponse {
  owner_id: string;
  surface: string;
  algorithm_mode: string;
  ranking_version: string;
  preset_used: string;
  consent_granted: boolean;
  cold_start_mode: boolean;
  recommendations: HybridRecommendationItem[];
  category_recommendations: Record<string, number>;
  knowledge_notes: string[];
}

export interface OutfitRecommendationResponse {
  owner_id: string;
  occasion: string;
  anchor_item_id?: string;
  compatibility_is_prediction_not_rule: boolean;
  outfits: Array<{
    outfit_id: string;
    title: string;
    items: HybridRecommendationItem[];
    compatibility_prediction: number;
    color_harmony_score: number;
    style_compatibility_score: number;
    occasion: string;
    rationale: string[];
  }>;
  complementary_items: Array<{
    slot: string;
    item: HybridRecommendationItem;
    compatibility_prediction: number;
    reason: string;
  }>;
  wardrobe_gaps: Array<{
    missing_category: string;
    severity: string;
    suggestion: string;
  }>;
}

export interface ExternalWebReference {
  source_url: string;
  source_title: string;
  retrieved_content: string;
  domain: string;
  trust_classification: string;
  verification_status: string;
}

export interface UnifiedResearchResult {
  query: string;
  internal_hits: Array<{ title: string; snippet: string; source: string; verification_status: string }>;
  external_evidence: ExternalWebReference[];
  external_answer_summary?: string;
  external_status: string;
  warnings: string[];
}

export interface WorkflowExecutionSummary {
  thread_id: string;
  workflow_name: string;
  status: string;
  awaiting_confirmation: boolean;
  state: Record<string, any>;
}

export const intelligenceApi = {
  async rankWardrobeSearch(queryText: string, items: Array<Record<string, any>>, topK = 12): Promise<SmartSearchMatch[]> {
    const res = await intelligenceHttp.post('/multimodal/similarity', {
      query_text: queryText,
      candidates: items,
      top_k: topK,
    });
    return res.data?.matches || [];
  },

  async getWardrobeRecommendations(occasion?: string): Promise<WardrobeRecommendationItem[]> {
    const res = await intelligenceHttp.get('/personalization/recommendations', {
      params: { occasion, consent_granted: true, top_k: 4 },
    });
    return res.data?.suggestions || [];
  },

  async inspectJobQuality(jobId: string, category = 'tops', avatarProfileId = 'standard_175'): Promise<GarmentQualityFeedback> {
    const res = await intelligenceHttp.post('/evaluation/critic', {
      job_id: jobId,
      category,
      avatar_profile_id: avatarProfileId,
    });
    const defects = Array.isArray(res.data?.defects) ? res.data.defects : [];
    const fitMetrics = res.data?.domains?.fit?.metrics || {};
    return {
      publication_allowed: Boolean(res.data?.publication_allowed),
      overall_status: String(res.data?.overall_status || 'PASSED'),
      critical_defect_count: Number(res.data?.critical_defect_count || 0),
      major_defect_count: Number(res.data?.major_defect_count || 0),
      minor_defect_count: Number(res.data?.minor_defect_count || 0),
      fit_classification: fitMetrics.fit_classification,
      fit_score: res.data?.domains?.fit?.score ?? undefined,
      suggestions: defects.slice(0, 3).map((d: any) => String(d.suggested_action || '')).filter(Boolean),
    };
  },

  async analyzeFit(jobId?: string, category = 'tops', avatarProfileId = 'standard_175') {
    const res = await intelligenceHttp.post('/fit/analyze', {
      job_id: jobId,
      category,
      avatar_profile_id: avatarProfileId,
    });
    return res.data;
  },

  async queryFashionKnowledge(query: string, topK = 2): Promise<KnowledgeHint[]> {
    const res = await intelligenceHttp.post('/knowledge/search', {
      query,
      verified_only: true,
      top_k: topK,
    });
    const hits = Array.isArray(res.data?.hits) ? res.data.hits : [];
    return hits.map((h: any) => ({
      title: String(h.title || ''),
      snippet: String(h.snippet || ''),
      source: String(h.source || ''),
      domain: String(h.domain || ''),
    }));
  },

  async getHybridRecommendations(params: {
    mode?: 'hybrid' | 'neural_hybrid' | 'content' | 'category';
    surface?: string;
    sessionId?: string;
    occasion?: string;
    searchQuery?: string;
    anchorItem?: Record<string, any>;
    candidates?: Array<Record<string, any>>;
    topK?: number;
  } = {}): Promise<HybridRecommendationResponse> {
    const res = await intelligenceHttp.post('/recommendations/hybrid', {
      mode: params.mode || 'neural_hybrid',
      surface: params.surface || 'wardrobe',
      session_id: params.sessionId,
      occasion: params.occasion,
      search_query: params.searchQuery,
      anchor_item: params.anchorItem,
      candidates: params.candidates,
      top_k: params.topK || 6,
      include_knowledge: true,
    });
    return res.data;
  },

  async getSimilarGarments(anchorItem: Record<string, any>, topK = 4): Promise<HybridRecommendationItem[]> {
    const res = await intelligenceHttp.post('/recommendations/hybrid', {
      mode: 'neural_hybrid',
      surface: 'similar_items',
      anchor_item: anchorItem,
      top_k: topK,
      include_knowledge: false,
    });
    return res.data?.recommendations || [];
  },

  async getOutfitRecommendations(params: {
    occasion?: string;
    anchorItem?: Record<string, any>;
    candidates?: Array<Record<string, any>>;
    maxOutfits?: number;
  } = {}): Promise<OutfitRecommendationResponse> {
    const res = await intelligenceHttp.post('/recommendations/outfit', {
      occasion: params.occasion || 'casual',
      anchor_item: params.anchorItem,
      candidates: params.candidates,
      max_outfits: params.maxOutfits || 3,
    });
    return res.data;
  },

  async recordRecommendationFeedback(params: {
    interactionType: string;
    itemData?: Record<string, any>;
    searchQuery?: string;
    sessionId?: string;
  }) {
    const res = await intelligenceHttp.post('/recommendations/feedback', {
      interaction_type: params.interactionType,
      item_data: params.itemData,
      search_query: params.searchQuery,
      session_id: params.sessionId,
    });
    return res.data;
  },

  async getRecommendationProfile() {
    const res = await intelligenceHttp.get('/recommendations/profile');
    return res.data;
  },

  async resetRecommendationProfile(scope: 'all' | 'explicit' | 'inferred' | 'session' = 'all') {
    const res = await intelligenceHttp.post('/recommendations/profile/reset', { scope });
    return res.data;
  },

  async searchExternalWeb(query: string, includeInternalRag = true, maxResults = 4): Promise<UnifiedResearchResult> {
    const res = await intelligenceHttp.post('/web/search', {
      query,
      include_internal_rag: includeInternalRag,
      max_results: maxResults,
    });
    return res.data;
  },

  async executeWorkflow(
    workflowName: 'garment.research' | 'fashion.discovery' | 'design.assistance',
    payload: Record<string, any>,
    threadId?: string,
  ): Promise<WorkflowExecutionSummary> {
    const res = await intelligenceHttp.post('/workflows/execute', {
      workflow_name: workflowName,
      payload,
      thread_id: threadId,
    });
    return res.data;
  },

  async resumeWorkflow(threadId: string, humanConfirmed = true): Promise<WorkflowExecutionSummary> {
    const res = await intelligenceHttp.post('/workflows/resume', {
      thread_id: threadId,
      human_confirmed: humanConfirmed,
    });
    return res.data;
  },

  // Phase 17.5 — Guided Live Garment Capture & Reconstruction Readiness
  async createCaptureSession(params: {
    garment_category: string;
    garment_subcategory?: string;
    capture_mode: 'hanger' | 'mannequin' | 'flat_lay' | 'worn';
    consent_granted?: boolean;
  }) {
    const res = await intelligenceHttp.post('/capture/sessions', params);
    return res.data;
  },

  async getCaptureSession(sessionId: string) {
    const res = await intelligenceHttp.get(`/capture/sessions/${sessionId}`);
    return res.data;
  },

  async uploadCapturedView(sessionId: string, file: File | Blob, viewLabel: string) {
    const form = new FormData();
    form.append('image', file, file instanceof File ? file.name : `${viewLabel}.webp`);
    form.append('view_label', viewLabel);
    const res = await intelligenceHttp.post(`/capture/sessions/${sessionId}/images`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },

  async deleteCapturedView(sessionId: string, imageId: string) {
    const res = await intelligenceHttp.delete(`/capture/sessions/${sessionId}/images/${imageId}`);
    return res.data;
  },

  async evaluateCaptureReadiness(sessionId: string) {
    const res = await intelligenceHttp.post(`/capture/sessions/${sessionId}/evaluate`);
    return res.data;
  },

  async finalizeCaptureSession(sessionId: string, idempotencyKey?: string) {
    const res = await intelligenceHttp.post(`/capture/sessions/${sessionId}/finalize`, {
      idempotency_key: idempotencyKey,
    });
    return res.data;
  },

  async cancelCaptureSession(sessionId: string) {
    const res = await intelligenceHttp.delete(`/capture/sessions/${sessionId}`);
    return res.data;
  },
};
