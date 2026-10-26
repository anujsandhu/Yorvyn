/**
 * Yorvyn Fashion Intelligence API Client
 */

import axios from 'axios';
import {
  Garment,
  UserProfile,
  OutfitGenerationResponse,
  StylistChatResponse,
  ClosetAnalytics
} from '../types/fashion';

const API_BASE_URL = import.meta.env.VITE_FASHION_API_URL || `${import.meta.env.VITE_API_URL || '/api'}/fashion`;

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const fashionApi = {
  // Health & Knowledge
  async getHealth() {
    const res = await api.get('/health');
    return res.data;
  },

  async getKnowledge() {
    const res = await api.get('/knowledge');
    return res.data;
  },

  // User Profile
  async getProfile(userId: string = 'default_user'): Promise<UserProfile> {
    const res = await api.get(`/profile?user_id=${userId}`);
    return res.data;
  },

  async updateProfile(profile: Partial<UserProfile>, userId: string = 'default_user'): Promise<UserProfile> {
    const res = await api.post(`/profile?user_id=${userId}`, profile);
    return res.data;
  },

  // Digital Wardrobe
  async getWardrobe(category?: string, userId: string = 'default_user'): Promise<{ items: Garment[]; total: number }> {
    const url = category ? `/wardrobe?user_id=${userId}&category=${category}` : `/wardrobe?user_id=${userId}`;
    const res = await api.get(url);
    return res.data;
  },

  async addGarment(garment: Partial<Garment>, userId: string = 'default_user'): Promise<Garment> {
    const res = await api.post(`/wardrobe?user_id=${userId}`, garment);
    return res.data.item;
  },

  async deleteGarment(itemId: string, userId: string = 'default_user') {
    const res = await api.delete(`/wardrobe/${itemId}?user_id=${userId}`);
    return res.data;
  },

  async toggleFavorite(itemId: string, userId: string = 'default_user'): Promise<Garment> {
    const res = await api.post(`/wardrobe/${itemId}/favorite?user_id=${userId}`);
    return res.data.item;
  },

  async recordWear(itemId: string, userId: string = 'default_user'): Promise<Garment> {
    const res = await api.post(`/wardrobe/${itemId}/wear?user_id=${userId}`);
    return res.data.item;
  },

  // Closet Analytics
  async getAnalytics(userId: string = 'default_user'): Promise<ClosetAnalytics> {
    const res = await api.get(`/analytics?user_id=${userId}`);
    return res.data;
  },

  // Contextual Outfit Generation
  async generateOutfits(params: {
    occasion?: string;
    temperature_celsius?: number;
    condition?: string;
    target_aesthetic?: string;
    max_outfits?: number;
    user_id?: string;
  }): Promise<OutfitGenerationResponse> {
    const res = await api.post('/outfits/generate', params);
    return res.data;
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
  async getAvatarConfig(userId: string = 'default_user'): Promise<any> {
    const res = await api.get(`/avatar?user_id=${userId}`);
    return res.data;
  },

  async saveAvatarConfig(config: any, userId: string = 'default_user'): Promise<any> {
    const res = await api.post(`/avatar?user_id=${userId}`, config);
    return res.data;
  },

  async resetAvatarConfig(userId: string = 'default_user'): Promise<any> {
    const res = await api.post(`/avatar/reset?user_id=${userId}`);
    return res.data;
  },

  // ── AI Photo-to-3D Garment Generation ──
  async createGarment3DJob(
    frontImage: File,
    category: string = 'top',
    backImage?: File,
    userId: string = 'default_user'
  ): Promise<{ job_id: string; status: string; progress: number; current_stage: string }> {
    const formData = new FormData();
    formData.append('front_image', frontImage);
    if (backImage) {
      formData.append('back_image', backImage);
    }
    formData.append('category', category);
    formData.append('user_id', userId);

    const res = await api.post('/garment-gen/jobs', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },

  async getGarment3DJobStatus(jobId: string): Promise<any> {
    const res = await api.get(`/garment-gen/jobs/${jobId}`);
    return res.data;
  },

  async cancelGarment3DJob(jobId: string): Promise<any> {
    const res = await api.post(`/garment-gen/jobs/${jobId}/cancel`);
    return res.data;
  },

  async saveGarment3DToWardrobe(jobId: string, userId: string = 'default_user'): Promise<any> {
    const res = await api.post(`/garment-gen/jobs/${jobId}/save?user_id=${userId}`);
    return res.data;
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
  }
};
