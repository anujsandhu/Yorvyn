/**
 * Yorvyn Continuous AI Learning & Personalization Engine API Client
 * Manages user personalization memory, feedback ingestion, privacy consent toggles,
 * and administrator model governance.
 */

import axios, { AxiosInstance } from 'axios';
import { supabase } from '../utils/supabase';

export interface UserPreference {
  id: string;
  user_id: string;
  preference_category: string;
  preference_key: string;
  preference_value: any;
  source: string;
  confidence: number;
  evidence_count: number;
  status: 'active' | 'inactive' | 'archived' | 'deleted';
  last_confirmed_at?: string;
  created_at: string;
  updated_at: string;
}

export interface AIFeedbackPayload {
  feedback_type:
    | 'positive'
    | 'negative'
    | 'correction'
    | 'preference'
    | 'accepted_recommendation'
    | 'rejected_recommendation'
    | 'edited_result'
    | 'confirmed_result'
    | 'reported_error';
  session_id?: string;
  message_id?: string;
  search_id?: string;
  rating?: number;
  original_output?: Record<string, any>;
  corrected_output?: Record<string, any>;
  feedback_text?: string;
  metadata?: Record<string, any>;
}

export interface LearningConsent {
  id: string;
  user_id: string;
  personalization_enabled: boolean;
  global_model_training_enabled: boolean;
  image_training_enabled: boolean;
  conversation_training_enabled: boolean;
  consent_version: string;
  consent_updated_at: string;
}

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const learningClient: AxiosInstance = axios.create({
  baseURL: `${API_BASE_URL}/learning`,
  headers: {
    'Content-Type': 'application/json',
  },
});

learningClient.interceptors.request.use(async (config) => {
  try {
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) {
      config.headers.Authorization = `Bearer ${session.access_token}`;
    }
  } catch {
    // Proceed
  }

  if (!config.headers['X-Correlation-ID']) {
    config.headers['X-Correlation-ID'] = `learn_${Math.random().toString(36).substring(2, 12)}`;
  }
  return config;
});

learningClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest?._retry) {
      originalRequest._retry = true;
      try {
        const { data: { session } } = await supabase.auth.refreshSession();
        if (session?.access_token) {
          originalRequest.headers.Authorization = `Bearer ${session.access_token}`;
          return learningClient(originalRequest);
        }
      } catch {
        // Refresh failed
      }
    }
    return Promise.reject(error);
  }
);

export const learningService = {
  // ── Feedback Collection ───────────────────────────────────────────────────
  async submitFeedback(payload: AIFeedbackPayload): Promise<any> {
    const res = await learningClient.post('/feedback', payload);
    return res.data;
  },

  // ── User Personalization Memory (Layer A) ─────────────────────────────────
  async getPreferences(category?: string): Promise<UserPreference[]> {
    const params = category ? { category } : {};
    const res = await learningClient.get('/preferences', { params });
    return res.data;
  },

  async createPreference(
    category: string,
    key: string,
    value: any,
    source: string = 'explicit',
    confidence: number = 0.85
  ): Promise<UserPreference> {
    const res = await learningClient.post('/preferences', {
      category,
      key,
      value,
      source,
      confidence,
    });
    return res.data;
  },

  async updatePreference(prefId: string, updates: Partial<UserPreference>): Promise<UserPreference> {
    const res = await learningClient.patch(`/preferences/${prefId}`, updates);
    return res.data;
  },

  async deletePreference(prefId: string): Promise<boolean> {
    const res = await learningClient.delete(`/preferences/${prefId}`);
    return res.data?.success ?? true;
  },

  async resetPreferences(category?: string): Promise<{ success: boolean; reset_count: number }> {
    const params = category ? { category } : {};
    const res = await learningClient.post('/preferences/reset', null, { params });
    return res.data;
  },

  async exportLearningData(): Promise<any> {
    const res = await learningClient.get('/preferences/export');
    return res.data;
  },

  // ── Granular Consent Management ───────────────────────────────────────────
  async getConsent(): Promise<LearningConsent> {
    const res = await learningClient.get('/consent');
    return res.data;
  },

  async updateConsent(updates: Partial<LearningConsent>): Promise<LearningConsent> {
    const res = await learningClient.put('/consent', updates);
    return res.data;
  },

  async purgeUserData(): Promise<{ success: boolean; preferences_purged: number; training_examples_purged: number }> {
    const res = await learningClient.delete('/user-data');
    return res.data;
  },

  // ── Admin Governance & Operations ─────────────────────────────────────────
  async getAdminDashboard(): Promise<any> {
    const res = await learningClient.get('/admin/dashboard');
    return res.data;
  },

  async getModels(taskType?: string, status?: string): Promise<any[]> {
    const res = await learningClient.get('/admin/models', { params: { task_type: taskType, status } });
    return res.data;
  },

  async triggerTrainingJob(modelName: string, taskType: string, datasetVersion: string): Promise<any> {
    const res = await learningClient.post('/admin/training-jobs', {
      model_name: modelName,
      task_type: taskType,
      dataset_version: datasetVersion,
    });
    return res.data;
  },

  async executeTrainingJob(jobId: string): Promise<any> {
    const res = await learningClient.post(`/admin/training-jobs/${jobId}/execute`);
    return res.data;
  },

  async evaluateModel(modelName: string, modelVersion: string): Promise<any> {
    const res = await learningClient.post('/admin/evaluate-model', null, {
      params: { model_name: modelName, model_version: modelVersion },
    });
    return res.data;
  },

  async deployModel(modelName: string, modelVersion: string): Promise<any> {
    const res = await learningClient.post('/admin/deploy-model', {
      model_name: modelName,
      model_version: modelVersion,
    });
    return res.data;
  },

  async rollbackModel(taskType: string, targetVersion?: string): Promise<any> {
    const res = await learningClient.post('/admin/rollback-model', {
      task_type: taskType,
      target_version: targetVersion,
    });
    return res.data;
  },
};

