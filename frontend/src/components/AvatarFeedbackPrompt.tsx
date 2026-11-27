/**
 * Yorvyn — 3D Avatar Customization Feedback Prompt
 * 
 * Elegant, compact luxury brand feedback prompt displayed after appearance adjustments:
 * "How does your avatar look now?"
 * - Interactive Thumbs-Up and Thumbs-Down buttons
 * - Directly triggers real 3D avatar approval or disapproval animations
 * - Optional inline comment / tag feedback
 * - Undo / Revert support
 * - Persists ratings to Supabase avatar_feedback table
 */

import React, { useState } from 'react';
import { ThumbsUp, ThumbsDown, Check, ArrowCounterClockwise, X, ChatCircleText } from './icons';
import { avatarFeedbackService } from '../services/feedback/avatarFeedbackService';
import toast from 'react-hot-toast';
import './AvatarFeedbackPrompt.css';

export interface AvatarFeedbackPromptProps {
  customizationEvent: string;
  avatarConfig: Record<string, any>;
  userId?: string;
  onRate?: (rating: 'positive' | 'negative') => void;
  onUndo?: () => void;
  onDismiss?: () => void;
}

export const AvatarFeedbackPrompt: React.FC<AvatarFeedbackPromptProps> = ({
  customizationEvent,
  avatarConfig,
  userId,
  onRate,
  onUndo,
  onDismiss
}) => {
  const [selectedRating, setSelectedRating] = useState<'positive' | 'negative' | null>(null);
  const [comment, setComment] = useState('');
  const [showCommentField, setShowCommentField] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleRating = async (rating: 'positive' | 'negative') => {
    setSelectedRating(rating);
    onRate?.(rating);

    // If positive, submit immediately unless comment is wanted
    if (rating === 'positive') {
      setIsSubmitting(true);
      await avatarFeedbackService.submitFeedback({
        userId,
        configurationSnapshot: avatarConfig,
        customizationEvent,
        rating: 'positive',
        comment: comment.trim() || undefined
      });
      setIsSubmitting(false);
      setSubmitted(true);
      toast.success('Pleased you like the fit! Saved to your profile.', { duration: 2500 });
      setTimeout(() => onDismiss?.(), 2800);
    } else {
      // For negative rating, offer comment field and undo
      setShowCommentField(true);
    }
  };

  const handleCommentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRating) return;

    setIsSubmitting(true);
    await avatarFeedbackService.submitFeedback({
      userId,
      configurationSnapshot: avatarConfig,
      customizationEvent,
      rating: selectedRating,
      comment: comment.trim() || undefined
    });
    setIsSubmitting(false);
    setSubmitted(true);
    toast.success('Feedback recorded. You can undo or adjust anytime in Settings.', { duration: 3000 });
    setTimeout(() => onDismiss?.(), 3000);
  };

  if (submitted) {
    return (
      <div className="avatar-feedback-pill submitted" role="status">
        <div className="af-check-badge">
          <Check size={14} strokeWidth={2.5} />
        </div>
        <span className="af-text">Feedback recorded</span>
      </div>
    );
  }

  return (
    <div className="avatar-feedback-pill" role="region" aria-label="Avatar Customization Feedback">
      <div className="af-main-row">
        <span className="af-label">How does your avatar look now?</span>

        <div className="af-actions">
          <button
            type="button"
            className={`af-btn thumbs-up ${selectedRating === 'positive' ? 'active' : ''}`}
            onClick={() => handleRating('positive')}
            disabled={isSubmitting}
            title="Approve appearance (Thumbs Up)"
            aria-label="Thumbs Up"
          >
            <ThumbsUp size={14} strokeWidth={2.2} />
          </button>

          <button
            type="button"
            className={`af-btn thumbs-down ${selectedRating === 'negative' ? 'active' : ''}`}
            onClick={() => handleRating('negative')}
            disabled={isSubmitting}
            title="Disapprove appearance (Thumbs Down)"
            aria-label="Thumbs Down"
          >
            <ThumbsDown size={14} strokeWidth={2.2} />
          </button>

          {onUndo && (
            <button
              type="button"
              className="af-undo-btn"
              onClick={onUndo}
              title="Undo last adjustment"
              aria-label="Undo last adjustment"
            >
              <ArrowCounterClockwise size={13} /> Revert
            </button>
          )}

          {onDismiss && (
            <button
              type="button"
              className="af-close-btn"
              onClick={onDismiss}
              title="Dismiss"
              aria-label="Dismiss feedback prompt"
            >
              <X size={13} />
            </button>
          )}
        </div>
      </div>

      {showCommentField && !submitted && (
        <form className="af-comment-form" onSubmit={handleCommentSubmit}>
          <div className="af-input-row">
            <ChatCircleText size={13} className="af-comment-icon" />
            <input
              type="text"
              className="af-comment-input"
              placeholder="What would you refine? (e.g. hair tone, drape)"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              autoFocus
              maxLength={120}
            />
            <button
              type="submit"
              className="af-submit-btn"
              disabled={isSubmitting}
            >
              Submit
            </button>
          </div>
        </form>
      )}
    </div>
  );
};
