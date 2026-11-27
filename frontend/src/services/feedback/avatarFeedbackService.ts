/**
 * Yorvyn — 3D Avatar Quality & Customization Feedback Service
 *
 * Persists user ratings (thumbs-up / thumbs-down), customization events,
 * and avatar configuration snapshots to Supabase `avatar_feedback` table.
 */

import { supabase, isSupabaseConfigured } from '../../utils/supabase';

export interface AvatarFeedbackSubmission {
  userId?: string;
  configurationSnapshot: Record<string, any>;
  customizationEvent: string;
  rating: 'positive' | 'negative' | 'thumbs_up' | 'thumbs_down';
  comment?: string;
}

export interface AvatarFeedbackRecord extends AvatarFeedbackSubmission {
  id: string;
  createdAt: string;
}

const LOCAL_STORAGE_KEY = 'yorvyn_avatar_feedback_cache';

export const avatarFeedbackService = {
  /**
   * Submits user feedback (thumbs-up / thumbs-down) after an avatar appearance change.
   */
  async submitFeedback(data: AvatarFeedbackSubmission): Promise<{ success: boolean; id?: string }> {
    try {
      const payload = {
        user_id: data.userId || null,
        configuration_snapshot: data.configurationSnapshot || {},
        customization_event: data.customizationEvent,
        rating: data.rating,
        comment: data.comment || null,
      };

      if (isSupabaseConfigured) {
        // Fast timeout guard to prevent network hangs in test or offline conditions
        const insertPromise = supabase
          .from('avatar_feedback')
          .insert([payload])
          .select('id')
          .single();

        const timeoutPromise = new Promise<{ data: null; error: { message: string } }>((resolve) =>
          setTimeout(() => resolve({ data: null, error: { message: 'Network timeout' } }), 1200)
        );

        const { data: inserted, error } = await Promise.race([insertPromise, timeoutPromise]);

        if (error) {
          console.warn('[AvatarFeedbackService] Supabase insert warning:', error.message);
          this.cacheLocally(data);
          return { success: true, id: 'cached_' + Date.now() };
        }

        return { success: true, id: inserted?.id };
      } else {
        this.cacheLocally(data);
        return { success: true, id: 'local_' + Date.now() };
      }
    } catch (err) {
      console.warn('[AvatarFeedbackService] Error submitting feedback:', err);
      this.cacheLocally(data);
      return { success: true, id: 'local_fallback_' + Date.now() };
    }
  },

  /**
   * Caches feedback locally when running in offline or demo modes.
   */
  cacheLocally(data: AvatarFeedbackSubmission) {
    try {
      const existing = this.getLocalCache();
      const newRecord: AvatarFeedbackRecord = {
        ...data,
        id: 'local_' + Date.now() + '_' + Math.random().toString(36).substring(2, 6),
        createdAt: new Date().toISOString(),
      };
      existing.unshift(newRecord);
      // Keep up to 50 recent records
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(existing.slice(0, 50)));
    } catch (e) {
      // ignore storage errors
    }
  },

  /**
   * Retrieves cached feedback from local storage.
   */
  getLocalCache(): AvatarFeedbackRecord[] {
    try {
      const raw = localStorage.getItem(LOCAL_STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  },

  /**
   * Fetches the user's feedback history for analytics and review.
   */
  async getUserFeedback(userId?: string): Promise<AvatarFeedbackRecord[]> {
    if (isSupabaseConfigured && userId) {
      try {
        const { data, error } = await supabase
          .from('avatar_feedback')
          .select('*')
          .eq('user_id', userId)
          .order('created_at', { ascending: false })
          .limit(20);

        if (!error && data) {
          return data.map((item) => ({
            id: item.id,
            userId: item.user_id,
            configurationSnapshot: item.configuration_snapshot,
            customizationEvent: item.customization_event,
            rating: item.rating,
            comment: item.comment,
            createdAt: item.created_at,
          }));
        }
      } catch (err) {
        console.warn('[AvatarFeedbackService] Error fetching from Supabase:', err);
      }
    }

    return this.getLocalCache();
  },
};
