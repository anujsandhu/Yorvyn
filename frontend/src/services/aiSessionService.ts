/**
 * Yorvyn Persistent AI Session & Search API Service
 * Manages persistent conversational sessions, message histories, and search operations.
 */

import axios, { AxiosInstance } from 'axios';
import { supabase } from '../utils/supabase';

export interface AISession {
  id: string;
  user_id: string;
  title: string;
  description?: string;
  session_type: string;
  status: 'active' | 'archived' | 'deleted';
  metadata: Record<string, any>;
  context_summary?: string;
  message_count: number;
  search_count: number;
  last_message_at?: string;
  created_at: string;
  updated_at: string;
  archived_at?: string;
}

export interface AIMessage {
  id: string;
  session_id: string;
  user_id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  content_type: string;
  attachments: any[];
  metadata: Record<string, any>;
  request_id?: string;
  parent_message_id?: string;
  sequence_number: number;
  status: 'completed' | 'pending' | 'processing' | 'failed';
  created_at: string;
  updated_at: string;
}

export interface AISearchRecord {
  id: string;
  session_id: string;
  user_id: string;
  message_id?: string;
  search_type: string;
  query: string;
  normalized_query?: string;
  status: string;
  result_summary?: string;
  result_metadata: Record<string, any>;
  provider?: string;
  model_name?: string;
  execution_provenance?: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const aiClient: AxiosInstance = axios.create({
  baseURL: `${API_BASE_URL}/ai`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach verified Supabase JWT Bearer token and correlation ID to each request
aiClient.interceptors.request.use(async (config) => {
  try {
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) {
      config.headers.Authorization = `Bearer ${session.access_token}`;
    }
  } catch {
    // Proceed unauthenticated or with default headers
  }

  if (!config.headers['X-Correlation-ID']) {
    config.headers['X-Correlation-ID'] = `sess_${Math.random().toString(36).substring(2, 12)}`;
  }
  return config;
});

// Automatic token refresh on 401
aiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest?._retry) {
      originalRequest._retry = true;
      try {
        const { data: { session } } = await supabase.auth.refreshSession();
        if (session?.access_token) {
          originalRequest.headers.Authorization = `Bearer ${session.access_token}`;
          return aiClient(originalRequest);
        }
      } catch {
        // Refresh failed
      }
    }
    return Promise.reject(error);
  }
);

export interface GarmentArtifact {
  turn_id: string;
  job_id?: string;
  category?: string;
  recognition?: {
    garment?: { subcategory?: string };
    reconstruction_readiness?: { unknown_geometry?: string[] };
    component_handoff?: { safe_components?: string[]; uncertain_components?: string[]; clarification_prompts?: string[] };
  };
  edits?: string[];
  design_command?: Record<string, any>;
  mesh_report?: {extents: number[]};
  previous_mesh_report?: {extents: number[]};
}

export const aiSessionService = {
  async watchGarmentActivity(session: string, turn: string, signal: AbortSignal, update: (activity: string)=>void) {
    const {data} = await supabase.auth.getSession();
    if (!data.session) return;
    const response = await fetch(`${API_BASE_URL}/ai/sessions/${session}/garment-turns/${turn}/activity`, {
      headers: {Authorization: `Bearer ${data.session.access_token}`}, signal,
    });
    if (!response.ok || !response.body) return;
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (!signal.aborted) {
      const chunk = await reader.read();
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value,{stream:true});
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) if (line) update(JSON.parse(line).activity);
    }
  },
  async garmentTurn(session: string, instruction: string, files: File[], requestId: string, previous?: string): Promise<AIMessage> {
    const body = new FormData();
    body.append('instruction', instruction);
    body.append('request_id', requestId);
    if (previous) body.append('previous', previous);
    files.forEach(file => body.append('images', file));
    const { data } = await aiClient.post(`/sessions/${session}/garment-turns`, body, {
      headers: { 'Content-Type': 'multipart/form-data' }, timeout: 180000,
    });
    return data;
  },
  async candidateBlob(session: string, turn: string): Promise<Blob> {
    const { data } = await aiClient.get(`/sessions/${session}/garment-turns/${turn}/candidate`, { responseType: 'blob' });
    return data;
  },

  /**
   * Creates a brand new persistent AI session with a permanent UUID.
   */
  async createSession(title: string = 'New conversation', sessionType: string = 'general'): Promise<AISession> {
    const res = await aiClient.post('/sessions', {
      title,
      session_type: sessionType,
    });
    return res.data.session;
  },

  /**
   * Lists sessions for the authenticated user with status and title search filters.
   */
  async listSessions(
    status: string = 'active',
    sessionType?: string,
    search?: string,
    limit: number = 30,
    cursor?: string
  ): Promise<{ items: AISession[]; next_cursor?: string }> {
    const params: Record<string, any> = { status, limit };
    if (sessionType) params.session_type = sessionType;
    if (search) params.search = search;
    if (cursor) params.cursor = cursor;

    const res = await aiClient.get('/sessions', { params });
    return res.data;
  },

  /**
   * Retrieves single session details with metadata and counts.
   */
  async getSession(sessionId: string): Promise<AISession> {
    const res = await aiClient.get(`/sessions/${sessionId}`);
    return res.data;
  },

  /**
   * Renames a session or updates metadata.
   */
  async updateSession(sessionId: string, updates: { title?: string; description?: string }): Promise<AISession> {
    const res = await aiClient.patch(`/sessions/${sessionId}`, updates);
    return res.data;
  },

  /**
   * Archives a session.
   */
  async archiveSession(sessionId: string): Promise<AISession> {
    const res = await aiClient.post(`/sessions/${sessionId}/archive`);
    return res.data;
  },

  /**
   * Restores an archived session.
   */
  async restoreSession(sessionId: string): Promise<AISession> {
    const res = await aiClient.post(`/sessions/${sessionId}/restore`);
    return res.data;
  },

  /**
   * Soft-deletes a session.
   */
  async deleteSession(sessionId: string): Promise<boolean> {
    const res = await aiClient.delete(`/sessions/${sessionId}`);
    return res.data.success;
  },

  /**
   * Retrieves chronological messages for a session.
   */
  async getSessionMessages(
    sessionId: string,
    limit: number = 50,
    cursor?: string
  ): Promise<{ items: AIMessage[]; next_cursor?: string }> {
    const params: Record<string, any> = { limit };
    if (cursor) params.cursor = cursor;

    const res = await aiClient.get(`/sessions/${sessionId}/messages`, { params });
    return res.data;
  },

  /**
   * Sends user message to session with client idempotency key.
   */
  async sendMessage(
    sessionId: string,
    content: string,
    requestId?: string,
    attachments: any[] = []
  ): Promise<{
    success: boolean;
    session_id: string;
    user_message_id: string;
    assistant_message_id: string;
    search_id?: string;
    response: {
      content: string;
      outfits?: any[];
      tool_calls?: any[];
      animation_intent?: string;
      provider_used?: string;
      idempotent_replay?: boolean;
    };
  }> {
    const res = await aiClient.post(`/sessions/${sessionId}/messages`, {
      content,
      content_type: 'text',
      attachments,
      request_id: requestId || `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    });
    return res.data;
  },

  /**
   * Retrieves search provenance records for a session.
   */
  async getSessionSearches(sessionId: string, searchType?: string): Promise<{ items: AISearchRecord[] }> {
    const params: Record<string, any> = {};
    if (searchType) params.search_type = searchType;
    const res = await aiClient.get(`/sessions/${sessionId}/searches`, { params });
    return res.data;
  },

  /**
   * Retrieves global search history across all user sessions.
   */
  async listGlobalSearches(q?: string, searchType?: string, status?: string): Promise<{ items: AISearchRecord[] }> {
    const params: Record<string, any> = {};
    if (q) params.q = q;
    if (searchType) params.search_type = searchType;
    if (status) params.status = status;
    const res = await aiClient.get('/searches', { params });
    return res.data;
  },
};

