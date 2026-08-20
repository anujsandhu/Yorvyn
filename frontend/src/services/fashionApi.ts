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

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/fashion';

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
  }
};
