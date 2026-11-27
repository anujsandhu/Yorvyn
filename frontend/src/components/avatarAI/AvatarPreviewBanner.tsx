import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sparkle,
  Check,
  X,
  Eye,
  EyeSlash
} from '../icons';
import { 
  avatarPreviewOrchestrator, 
  AvatarPreviewState 
} from '../../engine/avatarAI/avatarPreviewOrchestrator';
import './AvatarPreviewBanner.css';

interface AvatarPreviewBannerProps {
  onAccepted?: () => void;
  onRejected?: () => void;
}

export const AvatarPreviewBanner: React.FC<AvatarPreviewBannerProps> = ({
  onAccepted,
  onRejected
}) => {
  const [state, setState] = useState<AvatarPreviewState>(avatarPreviewOrchestrator.getState());

  useEffect(() => {
    return avatarPreviewOrchestrator.subscribe((next) => {
      setState(next);
    });
  }, []);

  if (!state.isPreviewActive || !state.activeProposal) {
    return null;
  }

  const proposal = state.activeProposal;
  const currentDisplayedProposal = avatarPreviewOrchestrator.getActiveProposalOrAlternative() || proposal;
  const confidencePercent = Math.round(proposal.confidence * 100);
  const hasAlternatives = proposal.alternatives && proposal.alternatives.length > 0;

  const handleToggleCompare = () => {
    avatarPreviewOrchestrator.toggleBeforeAfter();
  };

  const handleAccept = () => {
    avatarPreviewOrchestrator.acceptPreview();
    if (onAccepted) onAccepted();
  };

  const handleReject = () => {
    avatarPreviewOrchestrator.rejectPreview();
    if (onRejected) onRejected();
  };

  const handleSelectAlternative = (index: number) => {
    avatarPreviewOrchestrator.selectAlternative(index);
  };

  return (
    <AnimatePresence>
      <motion.div 
        className="avatar-preview-banner-container"
        initial={{ opacity: 0, y: -20, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -20, scale: 0.95 }}
        transition={{ duration: 0.2 }}
      >
        <div className={`avatar-preview-banner ${state.isShowingOriginal ? 'showing-original' : ''}`}>
          <div className="preview-banner-top">
            <div className="preview-banner-identity">
              <div className="preview-sparkle-badge">
                <Sparkle size={18} weight="fill" />
              </div>
              <div className="preview-banner-titles">
                <div className="preview-title-row">
                  <span className="preview-title">
                    {state.isShowingOriginal 
                      ? 'Original Appearance (Before)' 
                      : currentDisplayedProposal.title}
                  </span>
                  {!state.isShowingOriginal && (
                    <span className="preview-confidence-tag">
                      {confidencePercent}% AI Match
                    </span>
                  )}
                  {state.isShowingOriginal && (
                    <span className="preview-mode-tag">
                      Baseline
                    </span>
                  )}
                </div>
                <div className="preview-summary">
                  {state.isShowingOriginal 
                    ? 'Comparing against your saved avatar profile.' 
                    : currentDisplayedProposal.summary}
                </div>
              </div>
            </div>

            <div className="preview-banner-actions">
              <button
                type="button"
                className={`btn-preview-compare ${state.isShowingOriginal ? 'active' : ''}`}
                onClick={handleToggleCompare}
                title="Toggle Before / After preview"
              >
                {state.isShowingOriginal ? (
                  <>
                    <EyeSlash size={14} weight="bold" />
                    <span>Show Proposed</span>
                  </>
                ) : (
                  <>
                    <Eye size={14} weight="bold" />
                    <span>Compare</span>
                  </>
                )}
              </button>

              <button
                type="button"
                className="btn-preview-accept"
                onClick={handleAccept}
                title="Accept changes into Avatar DNA"
              >
                <Check size={14} weight="bold" />
                <span>Apply</span>
              </button>

              <button
                type="button"
                className="btn-preview-reject"
                onClick={handleReject}
                title="Discard suggested changes"
              >
                <X size={14} weight="bold" />
              </button>
            </div>
          </div>

          {hasAlternatives && !state.isShowingOriginal && (
            <div className="preview-alternatives-strip">
              <span className="preview-alt-label">Options:</span>
              <button
                type="button"
                className={`preview-alt-pill ${state.activeAlternativeIndex === -1 ? 'active' : ''}`}
                onClick={() => handleSelectAlternative(-1)}
              >
                1. {proposal.title}
              </button>
              {proposal.alternatives!.map((alt, idx) => (
                <button
                  key={alt.id || idx}
                  type="button"
                  className={`preview-alt-pill ${state.activeAlternativeIndex === idx ? 'active' : ''}`}
                  onClick={() => handleSelectAlternative(idx)}
                >
                  {idx + 2}. {alt.title}
                </button>
              ))}
            </div>
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  );
};

