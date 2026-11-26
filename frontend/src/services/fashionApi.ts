/**
 * Yorvyn Fashion Intelligence API Client
 */

import axios, { AxiosInstance } from 'axios';
import { supabase } from '../utils/supabase';
import {
  Garment,
  UserProfile,
  OutfitGenerationResponse,
  StylistChatResponse,
  ClosetAnalytics
} from '../types/fashion';

const API_BASE_URL = import.meta.env.VITE_FASHION_API_URL || `${import.meta.env.VITE_API_URL || '/api'}/fashion`;
const BILLING_BASE_URL = import.meta.env.VITE_BILLING_API_URL || `${import.meta.env.VITE_API_URL || '/api'}/billing`;
const GARMENTS_BASE_URL = import.meta.env.VITE_GARMENTS_API_URL || `${import.meta.env.VITE_API_URL || '/api'}/garments`;

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const garmentsApi = axios.create({
  baseURL: GARMENTS_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

const billingApi = axios.create({
  baseURL: BILLING_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

function setupAuthInterceptors(client: AxiosInstance) {
  client.interceptors.request.use(async (config) => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) {
        config.headers.Authorization = `Bearer ${session.access_token}`;
      }
    } catch {
      // Proceed unauthenticated
    }
    if (!config.headers['X-Correlation-ID']) {
      config.headers['X-Correlation-ID'] = `cl_${Math.random().toString(36).substring(2, 12)}`;
    }
    return config;
  });

  client.interceptors.response.use(
    (response) => response,
    async (error) => {
      const originalRequest = error.config;
      if (error.response?.status === 401 && !originalRequest?._retry) {
        originalRequest._retry = true;
        try {
          const { data: { session } } = await supabase.auth.refreshSession();
          if (session?.access_token) {
            originalRequest.headers.Authorization = `Bearer ${session.access_token}`;
            return client(originalRequest);
          }
        } catch {
          // Refresh failed
        }
      }
      return Promise.reject(error);
    }
  );
}

setupAuthInterceptors(api);
setupAuthInterceptors(garmentsApi);
setupAuthInterceptors(billingApi);

export interface StructuredApiError extends Error {
  status: number;
  code?: string;
  retryable: boolean;
  response?: any;
}

const RETRYABLE_HTTP_STATUSES = new Set([408, 429, 502, 503, 504]);
const PERMANENT_HTTP_STATUSES = new Set([400, 401, 403, 404, 409, 422]);

function buildStructuredApiError(err: any, fallbackMessage: string): StructuredApiError {
  const status: number = err?.response?.status || 500;
  const rawDetail = err?.response?.data?.detail;
  let message = fallbackMessage;
  let code: string | undefined;
  let retryable: boolean = RETRYABLE_HTTP_STATUSES.has(status) || !err?.response;

  if (typeof rawDetail === 'string' && rawDetail.trim()) {
    message = rawDetail;
  } else if (rawDetail && typeof rawDetail === 'object') {
    message = rawDetail.message || rawDetail.detail || JSON.stringify(rawDetail);
    code = rawDetail.code;
    if (typeof rawDetail.retryable === 'boolean') {
      retryable = rawDetail.retryable;
    }
  } else if (typeof err?.message === 'string' && err.message.trim()) {
    message = err.message;
  }

  if (PERMANENT_HTTP_STATUSES.has(status) && typeof rawDetail?.retryable !== 'boolean') {
    retryable = false;
  }

  const normalized = new Error(message) as StructuredApiError;
  normalized.status = status;
  normalized.code = code;
  normalized.retryable = retryable;
  normalized.response = err?.response;
  return normalized;
}

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  ttlMs: number;
}

const MAX_RESPONSE_CACHE_ENTRIES = 200;
const responseCache = new Map<string, CacheEntry<any>>();
const inFlightRequests = new Map<string, Promise<any>>();
let apiCacheHits = 0;
let apiCacheMisses = 0;

export function getApiCacheStats(): { entries: number; hits: number; misses: number; hitRatio: number } {
  const total = apiCacheHits + apiCacheMisses;
  return {
    entries: responseCache.size,
    hits: apiCacheHits,
    misses: apiCacheMisses,
    hitRatio: total > 0 ? Math.round((apiCacheHits / total) * 10000) / 10000 : 0,
  };
}

export function invalidateApiCache(prefix?: string): void {
  if (!prefix) {
    responseCache.clear();
    return;
  }
  for (const key of responseCache.keys()) {
    if (key.startsWith(prefix)) {
      responseCache.delete(key);
    }
  }
}

async function deduplicatedFetch<T>(
  key: string,
  fetcher: () => Promise<T>,
  ttlMs: number = 45000
): Promise<T> {
  const cached = responseCache.get(key);
  if (cached && Date.now() - cached.timestamp <= cached.ttlMs) {
    apiCacheHits++;
    // Touch LRU order
    responseCache.delete(key);
    responseCache.set(key, cached);
    return cached.data;
  }

  const existingInFlight = inFlightRequests.get(key);
  if (existingInFlight) {
    apiCacheHits++;
    return existingInFlight as Promise<T>;
  }

  apiCacheMisses++;
  const promise = (async () => {
    try {
      const data = await fetcher();
      if (ttlMs > 0) {
        if (responseCache.size >= MAX_RESPONSE_CACHE_ENTRIES) {
          const oldestKey = responseCache.keys().next().value;
          if (oldestKey) responseCache.delete(oldestKey);
        }
        responseCache.set(key, { data, timestamp: Date.now(), ttlMs });
      }
      return data;
    } finally {
      inFlightRequests.delete(key);
    }
  })();

  inFlightRequests.set(key, promise);
  return promise;
}

export const fashionApi = {
  invalidateCache: invalidateApiCache,

  // Health & Knowledge
  async getHealth() {
    return deduplicatedFetch('health', async () => {
      const res = await api.get('/health');
      return res.data;
    }, 15000);
  },

  async getKnowledge() {
    return deduplicatedFetch('knowledge', async () => {
      const res = await api.get('/knowledge');
      return res.data;
    }, 60000);
  },

  // User Profile
  async getProfile(userId: string = 'default_user', signal?: AbortSignal): Promise<UserProfile> {
    return deduplicatedFetch(`profile:${userId}`, async () => {
      const res = await api.get(`/profile?user_id=${userId}`, { signal });
      return res.data;
    }, 60000);
  },

  async updateProfile(profile: Partial<UserProfile>, userId: string = 'default_user'): Promise<UserProfile> {
    invalidateApiCache(`profile:${userId}`);
    const res = await api.post(`/profile?user_id=${userId}`, profile);
    return res.data;
  },

  // Digital Wardrobe
  async getWardrobe(category?: string, userId: string = 'default_user', signal?: AbortSignal): Promise<{ items: Garment[]; total: number }> {
    const key = `wardrobe:${userId}:${category || 'all'}`;
    return deduplicatedFetch(key, async () => {
      const url = category ? `/wardrobe?user_id=${userId}&category=${category}` : `/wardrobe?user_id=${userId}`;
      const res = await api.get(url, { signal });
      return res.data;
    }, 45000);
  },

  async addGarment(garment: Partial<Garment>, userId: string = 'default_user'): Promise<Garment> {
    invalidateApiCache(`wardrobe:${userId}`);
    invalidateApiCache(`analytics:${userId}`);
    const res = await api.post(`/wardrobe?user_id=${userId}`, garment);
    return res.data.item;
  },

  async deleteGarment(itemId: string, userId: string = 'default_user') {
    invalidateApiCache(`wardrobe:${userId}`);
    invalidateApiCache(`analytics:${userId}`);
    const res = await api.delete(`/wardrobe/${itemId}?user_id=${userId}`);
    return res.data;
  },

  async toggleFavorite(itemId: string, userId: string = 'default_user'): Promise<Garment> {
    invalidateApiCache(`wardrobe:${userId}`);
    const res = await api.post(`/wardrobe/${itemId}/favorite?user_id=${userId}`);
    return res.data.item;
  },

  async recordWear(itemId: string, userId: string = 'default_user'): Promise<Garment> {
    invalidateApiCache(`wardrobe:${userId}`);
    invalidateApiCache(`analytics:${userId}`);
    const res = await api.post(`/wardrobe/${itemId}/wear?user_id=${userId}`);
    return res.data.item;
  },

  // Closet Analytics
  async getAnalytics(userId: string = 'default_user', signal?: AbortSignal): Promise<ClosetAnalytics> {
    return deduplicatedFetch(`analytics:${userId}`, async () => {
      const res = await api.get(`/analytics?user_id=${userId}`, { signal });
      return res.data;
    }, 60000);
  },

  // Contextual Outfit Generation
  async generateOutfits(params: {
    occasion?: string;
    temperature_celsius?: number;
    condition?: string;
    target_aesthetic?: string;
    max_outfits?: number;
    user_id?: string;
  }, signal?: AbortSignal): Promise<OutfitGenerationResponse> {
    const key = `outfits:${JSON.stringify(params)}`;
    return deduplicatedFetch(key, async () => {
      const res = await api.post('/outfits/generate', params, { signal });
      return res.data;
    }, 30000);
  },

  // Conversational Stylist Chat
  async chatWithStylist(message: string, temperature?: number, userId: string = 'default_user'): Promise<StylistChatResponse> {
    const res = await api.post('/chat', {
      message,
      temperature_celsius: temperature,
      user_id: userId
    });
    return res.data;
  },

  // Feedback Learning Loop
  async sendFeedback(outfitId: string, action: 'wear_today' | 'like' | 'dislike' | 'save' | 'skip', note?: string, userId: string = 'default_user') {
    const res = await api.post('/feedback', {
      outfit_id: outfitId,
      action,
      note,
      user_id: userId
    });
    return res.data;
  },

  // 3D Avatar Configuration & Persistence
  async getAvatarConfig(userId: string = 'default_user', signal?: AbortSignal): Promise<any> {
    return deduplicatedFetch(`avatar:${userId}`, async () => {
      const res = await api.get(`/avatar?user_id=${userId}`, { signal });
      return res.data;
    }, 60000);
  },

  async saveAvatarConfig(config: any, userId: string = 'default_user'): Promise<any> {
    invalidateApiCache(`avatar:${userId}`);
    const res = await api.post(`/avatar?user_id=${userId}`, config);
    return res.data;
  },

  async resetAvatarConfig(userId: string = 'default_user'): Promise<any> {
    invalidateApiCache(`avatar:${userId}`);
    const res = await api.post(`/avatar/reset?user_id=${userId}`);
    return res.data;
  },

  // ── AI Garment Photo Automatic Analysis ──
  async analyzeGarmentPhoto(
    frontImage: File | Blob,
    options?: {
      backImage?: File | Blob;
      sideImage?: File | Blob;
      detailImage?: File | Blob;
      userCorrections?: any;
      userId?: string;
    }
  ): Promise<any> {
    const formData = new FormData();
    formData.append('front_image', frontImage);
    if (options?.backImage) formData.append('back_image', options.backImage);
    if (options?.sideImage) formData.append('side_image', options.sideImage);
    if (options?.detailImage) formData.append('detail_image', options.detailImage);
    if (options?.userCorrections) formData.append('user_corrections', JSON.stringify(options.userCorrections));
    formData.append('user_id', options?.userId || 'default_user');

    try {
      const res = await api.post('/garment-gen/analyze', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data;
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Automatic garment analysis failed';
      const error: any = new Error(detail);
      error.status = err?.response?.status || 500;
      error.response = err?.response;
      throw error;
    }
  },

  // ── Phase 14.27 Multi-View Garment Identification ──
  async multiviewIdentify(
    images: (File | Blob)[],
    options?: {
      garmentId?: string;
      viewHints?: Record<string, string>;
      mockMode?: boolean;
      userId?: string;
    }
  ): Promise<any> {
    const formData = new FormData();
    images.forEach((img) => formData.append('images', img));
    if (options?.garmentId) formData.append('garment_id', options.garmentId);
    if (options?.viewHints) formData.append('view_hints', JSON.stringify(options.viewHints));
    if (options?.mockMode !== undefined) formData.append('mock_mode', String(options.mockMode));
    if (options?.userId) formData.append('user_id', options.userId);

    try {
      const res = await garmentsApi.post('/multiview-identify', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data;
    } catch (err: any) {
      throw buildStructuredApiError(err, 'Multi-view identification failed');
    }
  },

  async getGarmentEvidence(garmentId: string): Promise<any> {
    try {
      const res = await garmentsApi.get(`/${garmentId}/evidence`);
      return res.data;
    } catch (err: any) {
      throw buildStructuredApiError(err, 'Failed to load garment evidence');
    }
  },

  async validateGarmentSpecification(garmentId: string): Promise<any> {
    try {
      const res = await garmentsApi.post(`/${garmentId}/validate`);
      return res.data;
    } catch (err: any) {
      throw buildStructuredApiError(err, 'Garment specification validation failed');
    }
  },

  async multiviewReconstruct(
    images: (File | Blob)[],
    specification: Record<string, any>,
    options?: { userId?: string; category?: string; subcategory?: string; idempotencyKey?: string }
  ): Promise<any> {
    const formData = new FormData();
    images.forEach((img) => formData.append('images', img));
    formData.append('specification_json', JSON.stringify(specification));
    if (options?.userId) formData.append('user_id', options.userId);
    if (options?.category) formData.append('final_category', options.category);
    if (options?.subcategory) formData.append('final_subcategory', options.subcategory);
    if (options?.idempotencyKey) formData.append('idempotency_key', options.idempotencyKey);

    try {
      const res = await garmentsApi.post('/multiview-reconstruct', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data;
    } catch (err: any) {
      throw buildStructuredApiError(err, 'Evidence handoff to reconstruction failed');
    }
  },

  async detectGarmentInstances(
    image: File | Blob,
    categoryHint?: string
  ): Promise<any> {
    const formData = new FormData();
    formData.append('image', image);
    if (categoryHint) formData.append('category_hint', categoryHint);

    try {
      const res = await api.post('/garment-gen/detect-instances', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data;
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Instance detection failed';
      const error: any = new Error(detail);
      error.status = err?.response?.status || 500;
      error.response = err?.response;
      throw error;
    }
  },

  async submitGarmentFeedback(payload: {
    inferenceId: string;
    analysisId?: string;
    jobId?: string;
    sessionId?: string;
    searchId?: string;
    eventType: string;
    originalValue?: any;
    correctedValue?: any;
    feedbackText?: string;
    rating?: number;
    isVisualCorrection?: boolean;
    metadata?: any;
  }): Promise<any> {
    const res = await api.post('/garment-gen/feedback', {
      inference_id: payload.inferenceId,
      analysis_id: payload.analysisId,
      job_id: payload.jobId,
      session_id: payload.sessionId,
      search_id: payload.searchId,
      event_type: payload.eventType,
      original_value: payload.originalValue,
      corrected_value: payload.correctedValue,
      feedback_text: payload.feedbackText,
      rating: payload.rating,
      is_visual_correction: payload.isVisualCorrection ?? true,
      metadata: payload.metadata || {},
    });
    return res.data;
  },

  // ── AI Photo-to-3D Garment Generation ──
  async createGarment3DJob(
    frontImage: File | Blob,
    category?: string,
    backImage?: File | Blob,
    userId: string = 'default_user',
    options?: {
      sideImage?: File | Blob;
      detailImage?: File | Blob;
      subcategory?: string;
      detectionMetadata?: any;
    }
  ): Promise<{ job_id: string; status: string; progress: number; current_stage: string }> {
    const formData = new FormData();
    formData.append('front_image', frontImage);
    if (backImage) formData.append('back_image', backImage);
    if (options?.sideImage) formData.append('side_image', options.sideImage);
    if (options?.detailImage) formData.append('detail_image', options.detailImage);
    if (category) formData.append('category', category);
    if (options?.subcategory) formData.append('subcategory', options.subcategory);
    if (options?.detectionMetadata) formData.append('detection_metadata', JSON.stringify(options.detectionMetadata));
    formData.append('user_id', userId);

    try {
      const res = await api.post('/garment-gen/jobs', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return res.data;
    } catch (err: any) {
      throw buildStructuredApiError(err, 'Job submission failed');
    }
  },

  async getGarment3DJobStatus(jobId: string): Promise<any> {
    try {
      const res = await api.get(`/garment-gen/jobs/${jobId}`);
      return res.data;
    } catch (err: any) {
      throw buildStructuredApiError(err, 'Failed to retrieve job status');
    }
  },

  async cancelGarment3DJob(jobId: string): Promise<any> {
    const res = await api.post(`/garment-gen/jobs/${jobId}/cancel`);
    return res.data;
  },

  async saveGarment3DToWardrobe(jobId: string, userId: string = 'default_user'): Promise<any> {
    invalidateApiCache(`wardrobe:${userId}`);
    invalidateApiCache('wardrobe');
    invalidateApiCache(`analytics:${userId}`);
    const res = await api.post(`/garment-gen/jobs/${jobId}/save?user_id=${userId}`);
    return res.data;
  },

  async getGarment3DDiagnostics(jobId: string): Promise<any> {
    try {
      const res = await api.get(`/garment-gen/jobs/${jobId}/diagnostics`);
      return res.data;
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Failed to retrieve diagnostics';
      const status = err?.response?.status || 500;
      const error: any = new Error(detail);
      error.status = status;
      error.response = err?.response;
      throw error;
    }
  },

  // Speech & Voice AI
  async getSpeechConfig(): Promise<any> {
    const res = await api.get('/speech/config');
    return res.data;
  },

  async transcribeAudio(audioBlob: Blob, language: string = 'en'): Promise<{ text: string; provider: string; status: string }> {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'mic_recording.webm');
    formData.append('language', language);
    const res = await api.post('/speech/transcribe', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return res.data;
  },

  async synthesizeSpeech(text: string, voice?: string): Promise<any> {
    const res = await api.post('/speech/synthesize', { text, voice });
    return res.data;
  },

  // Real ML Metrics
  async getMLMetrics(): Promise<any> {
    const res = await api.get('/ml/metrics');
    return res.data;
  },

  // ── ML Phase 1: Fashion DNA & Intelligence Foundation ──
  async getFashionDNA(userId: string = 'default_user'): Promise<any> {
    const res = await api.get(`/dna?user_id=${userId}`);
    return res.data;
  },

  async updateFashionDNA(updates: any, userId: string = 'default_user'): Promise<any> {
    const res = await api.put(`/dna?user_id=${userId}`, updates);
    return res.data;
  },

  async syncFashionDNAFromAvatar(avatarProfile: any, userId: string = 'default_user'): Promise<any> {
    const res = await api.post(`/dna/sync-avatar?user_id=${userId}`, avatarProfile);
    return res.data;
  },

  async syncAvatarDna(avatarProfile: any, userId: string = 'default_user'): Promise<any> {
    return this.syncFashionDNAFromAvatar(avatarProfile, userId);
  },

  async resetFashionDNA(userId: string = 'default_user'): Promise<any> {
    const res = await api.post(`/dna/reset?user_id=${userId}`);
    return res.data;
  },

  async intelligentChat(
    message: string,
    conversationId?: string,
    temporaryConstraints?: any,
    userId: string = 'default_user'
  ): Promise<any> {
    const res = await api.post('/chat/intelligent', {
      message,
      conversation_id: conversationId,
      temporary_constraints: temporaryConstraints,
      user_id: userId
    });
    return res.data;
  },

  async getIntelligenceMetrics(userId?: string): Promise<any> {
    const url = userId ? `/intelligence/metrics?user_id=${userId}` : '/intelligence/metrics';
    const res = await api.get(url);
    return res.data;
  },

  async getWardrobeGaps(userId: string = 'default_user'): Promise<any> {
    const res = await api.get(`/wardrobe/gaps?user_id=${userId}`);
    return res.data;
  },

  async evaluateCandidateOutfit(
    itemIds: string[],
    occasion: string = 'casual',
    weatherTempC: number = 20.0,
    userId: string = 'default_user'
  ): Promise<any> {
    const res = await api.post(`/recommendations/evaluate?user_id=${userId}`, {
      item_ids: itemIds,
      occasion,
      weather_temp_c: weatherTempC
    });
    return res.data;
  },

  async recordOutfitFeedback(
    outfitId: string,
    feedback: 'liked' | 'saved' | 'rejected' | 'worn',
    notes?: string,
    userId: string = 'default_user'
  ): Promise<any> {
    const res = await api.post(`/recommendations/feedback?user_id=${userId}`, {
      outfit_id: outfitId,
      feedback,
      notes
    });
    return res.data;
  },

  async unifiedVoiceChat(
    audioBlob: Blob,
    conversationId?: string,
    language: string = 'en'
  ): Promise<any> {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'voice_recording.webm');
    formData.append('language', language);
    if (conversationId) {
      formData.append('conversation_id', conversationId);
    }
    const res = await api.post('/speech/voice-chat', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return res.data;
  },

  // ── ML Phase 2: Body & Colour Intelligence ─────────────────────────────────
  async getBodyProfile(userId: string = 'default_user'): Promise<any> {
    const res = await api.get(`/body/profile?user_id=${userId}`);
    return res.data;
  },

  async updateBodyMeasurements(
    measurements: Record<string, number | null>,
    unit: 'cm' | 'in' = 'cm',
    userId: string = 'default_user'
  ): Promise<any> {
    const res = await api.put(`/body/measurements?user_id=${userId}`, {
      measurements,
      unit
    });
    return res.data;
  },

  async analyzeBodyProportions(
    proportionsData: {
      height_cm?: number;
      shoulder_cm?: number;
      waist_cm?: number;
      hip_cm?: number;
    },
    userId: string = 'default_user'
  ): Promise<any> {
    const res = await api.post(`/body/analyze-proportions?user_id=${userId}`, proportionsData);
    return res.data;
  },

  async analyzeSkinColour(
    payload: {
      skin_hex?: string;
      r?: number;
      g?: number;
      b?: number;
      ambient_lighting?: string;
    },
    userId: string = 'default_user'
  ): Promise<any> {
    const res = await api.post(`/colour/analyze?user_id=${userId}`, payload);
    return res.data;
  },

  async getPersonalColourPalette(
    undertone?: string,
    paletteId?: string,
    userId: string = 'default_user'
  ): Promise<any> {
    const params = new URLSearchParams();
    if (undertone) params.append('undertone', undertone);
    if (paletteId) params.append('palette_id', paletteId);
    params.append('user_id', userId);
    const res = await api.get(`/colour/palette?${params.toString()}`);
    return res.data;
  },

  async evaluateClothingFit(
    garmentSpec: Record<string, any>,
    garmentName?: string,
    userId: string = 'default_user'
  ): Promise<any> {
    const res = await api.post(`/compatibility/fit?user_id=${userId}`, {
      garment_spec: garmentSpec,
      garment_name: garmentName
    });
    return res.data;
  },

  async evaluateColourCompatibility(
    garmentColors: string[],
    occasion: string = 'casual',
    userId: string = 'default_user'
  ): Promise<any> {
    const res = await api.post(`/compatibility/colour?user_id=${userId}`, {
      garment_colors: garmentColors,
      occasion
    });
    return res.data;
  },

  async compareAvatarWithBodyProfile(userId: string = 'default_user'): Promise<any> {
    const res = await api.get(`/avatar/compare?user_id=${userId}`);
    return res.data;
  },

  // ── Phase 9: Production Saved Looks & Curation ──

  async getLooks(tag?: string, userId: string = 'default_user'): Promise<any[]> {
    const params = new URLSearchParams();
    if (tag) params.append('tag', tag);
    params.append('user_id', userId);
    const res = await api.get(`/looks?${params.toString()}`);
    return res.data;
  },

  async createLook(
    lookData: {
      name: string;
      garment_ids: string[];
      description?: string;
      avatar_snapshot?: Record<string, any>;
      tags?: string[];
      is_favorite?: boolean;
    },
    userId: string = 'default_user'
  ): Promise<any> {
    const res = await api.post('/looks', {
      user_id: userId,
      ...lookData
    });
    return res.data;
  },

  async getLook(lookId: string, userId: string = 'default_user'): Promise<any> {
    const res = await api.get(`/looks/${lookId}?user_id=${userId}`);
    return res.data;
  },

  async updateLook(
    lookId: string,
    updates: {
      name?: string;
      description?: string;
      garment_ids?: string[];
      avatar_snapshot?: Record<string, any>;
      tags?: string[];
      is_favorite?: boolean;
    },
    userId: string = 'default_user'
  ): Promise<any> {
    const res = await api.put(`/looks/${lookId}`, {
      user_id: userId,
      ...updates
    });
    return res.data;
  },

  async deleteLook(lookId: string, userId: string = 'default_user'): Promise<any> {
    const res = await api.delete(`/looks/${lookId}?user_id=${userId}`);
    return res.data;
  },

  async duplicateLook(lookId: string, newName?: string, userId: string = 'default_user'): Promise<any> {
    const res = await api.post(`/looks/${lookId}/duplicate`, {
      user_id: userId,
      new_name: newName
    });
    return res.data;
  },

  async recordLookWear(lookId: string, userId: string = 'default_user'): Promise<any> {
    const res = await api.post(`/looks/${lookId}/wear?user_id=${userId}`);
    return res.data;
  },

  async validateLookCompatibility(garmentIds: string[], userId: string = 'default_user'): Promise<any> {
    const res = await api.post('/looks/validate', {
      user_id: userId,
      garment_ids: garmentIds
    });
    return res.data;
  },

  async previewLook3D(lookId: string, userId: string = 'default_user'): Promise<any> {
    const res = await api.get(`/looks/${lookId}/preview?user_id=${userId}`);
    return res.data;
  },

  // ── Phase 9: Consent & Privacy (GDPR Compliance) ──

  async getUserConsent(userId: string = 'default_user'): Promise<any> {
    const res = await api.get(`/consent?user_id=${userId}`);
    return res.data;
  },

  async updateUserConsent(
    consent: {
      ephemeral_processing_accepted: boolean;
      ai_training_opt_in: boolean;
      terms_version?: string;
    },
    userId: string = 'default_user'
  ): Promise<any> {
    const res = await api.post('/consent', {
      user_id: userId,
      ...consent
    });
    return res.data;
  },

  async exportUserData(userId: string = 'default_user'): Promise<any> {
    const res = await api.get(`/user/export?user_id=${userId}`);
    return res.data;
  },

  async purgeUserData(userId: string = 'default_user'): Promise<any> {
    const res = await api.post('/user/purge', {
      user_id: userId
    });
    return res.data;
  },

  // ── Phase 9: AI Job Queue & Infrastructure Health ──

  async getGarmentGenHealth(): Promise<any> {
    const res = await api.get('/garment-gen/health');
    return res.data;
  },

  async retryGarmentGenJob(jobId: string): Promise<any> {
    try {
      const res = await api.post(`/garment-gen/jobs/${jobId}/retry`);
      return res.data;
    } catch (err: any) {
      throw buildStructuredApiError(err, 'Job retry failed');
    }
  },

  // ── Phase 10: Production Billing & Subscriptions ──

  async getBillingPlans(): Promise<any> {
    const res = await billingApi.get('/plans');
    return res.data;
  },

  async getUserSubscription(userId?: string): Promise<any> {
    const res = await billingApi.get('/subscription', {
      params: userId ? { user_id: userId } : {}
    });
    return res.data;
  },

  async getUserUsage(userId?: string): Promise<any> {
    const res = await billingApi.get('/usage', {
      params: userId ? { user_id: userId } : {}
    });
    return res.data;
  },

  async createCheckoutSession(params: {
    planId: string;
    userId?: string;
    successUrl?: string;
    cancelUrl?: string;
  }): Promise<any> {
    const res = await billingApi.post('/create-checkout-session', {
      plan_id: params.planId,
      user_id: params.userId,
      success_url: params.successUrl,
      cancel_url: params.cancelUrl
    });
    return res.data;
  },

  async createPortalSession(params?: {
    userId?: string;
    returnUrl?: string;
  }): Promise<any> {
    const res = await billingApi.post('/create-portal-session', {
      user_id: params?.userId,
      return_url: params?.returnUrl
    });
    return res.data;
  },

  // ── Phase 11: Controlled Private Beta Onboarding & Operations ──

  async validateBetaInvite(token: string): Promise<any> {
    const res = await api.post('/beta/validate-invite', { token });
    return res.data;
  },

  async activateBetaInvite(token: string): Promise<any> {
    const res = await api.post('/beta/activate-invite', { token });
    return res.data;
  },

  async getBetaCohort(cohort?: string): Promise<any> {
    const res = await api.get('/beta/cohort', {
      params: cohort ? { cohort } : {}
    });
    return res.data;
  },

  async submitBetaFeedback(feedbackData: {
    job_id?: string;
    correlation_id?: string;
    reconstruction_rating?: number;
    fitting_rating?: number;
    texture_rating?: number;
    category_correct?: boolean;
    usability_rating?: number;
    feedback_text?: string;
    failure_category?: string;
    reproduction_steps?: string;
    include_raw_image?: boolean;
    severity?: 'low' | 'normal' | 'high' | 'critical';
  }): Promise<any> {
    const res = await api.post('/beta/feedback', feedbackData);
    return res.data;
  },

  async getBetaFeedback(): Promise<any> {
    const res = await api.get('/beta/feedback');
    return res.data;
  },

  async getBetaDefects(severity?: string): Promise<any> {
    const res = await api.get('/beta/defects', {
      params: severity ? { severity } : {}
    });
    return res.data;
  },

  async getOpsMetrics(): Promise<any> {
    const res = await api.get('/ops/metrics');
    return res.data;
  },

  async getOpsAlerts(): Promise<any> {
    const res = await api.get('/ops/alerts');
    return res.data;
  },

  async getOpsCostBreakdown(): Promise<any> {
    const res = await api.get('/ops/cost-breakdown');
    return res.data;
  }
};
