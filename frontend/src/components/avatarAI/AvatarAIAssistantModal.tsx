/**
 * YORVYN — PHASE 8: AI Avatar Intelligence & Personalization Modal
 * 
 * Houses 4 dedicated intelligence workspaces:
 * 1. Conversational Stylist: Natural language styling & multi-turn dialogue
 * 2. Photo Personalization: Privacy-first reference photo analysis with explicit consent
 * 3. Hairstyle Intelligence: Face-shape matching matrix, 3-option comparison sets, favorites
 * 4. Occasion & Wardrobe: Contextual styling, color palettes, and 3D outfit staging
 */

import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';
import {
  Sparkle,
  X,
  PaperPlaneTilt,
  UploadSimple,
  ShieldCheck,
  Heart,
  Eye,
  Check,
  ThermometerSimple,
  SunHorizon,
  CaretLeft,
  Scissors
} from '../icons';
import { AvatarCreatorEngine } from '../../engine/avatarCreator/avatarCreatorEngine';
import { 
  avatarPreviewOrchestrator 
} from '../../engine/avatarAI/avatarPreviewOrchestrator';
import { 
  avatarAIConversationManager 
} from '../../engine/avatarAI/avatarAIConversationManager';
import { 
  AvatarAIPrivacyManager 
} from '../../engine/avatarAI/avatarAIPrivacyManager';
import { 
  PhotoAnalysisService 
} from '../../engine/avatarAI/photoAnalysisService';
import { 
  HairstyleRecommendationService 
} from '../../engine/avatarAI/hairstyleRecommendationService';
import { 
  AvatarRecommendationEngine 
} from '../../engine/avatarAI/avatarRecommendationEngine';
import { 
  AIMessage, 
  AvatarCustomizationProposal,
  HairstyleRecommendationItem,
  PhotoAnalysisResult 
} from '../../engine/avatarAI/avatarAITypes';
import './AvatarAIAssistantModal.css';

interface AvatarAIAssistantModalProps {
  isOpen: boolean;
  onClose: () => void;
  creatorEngine: AvatarCreatorEngine;
  embedded?: boolean;
}

type AITab = 'chat' | 'photo' | 'hairstyles' | 'occasions';

export const AvatarAIAssistantModal: React.FC<AvatarAIAssistantModalProps> = ({
  isOpen,
  onClose,
  creatorEngine,
  embedded = true
}) => {
  const [activeTab, setActiveTab] = useState<AITab>('chat');
  const [messages, setMessages] = useState<AIMessage[]>(avatarAIConversationManager.getMessages());
  const [inputText, setInputText] = useState('');
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Photo Analysis State
  const [photoConsent, setPhotoConsent] = useState(false);
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreviewUrl, setPhotoPreviewUrl] = useState<string | null>(null);
  const [isAnalyzingPhoto, setIsAnalyzingPhoto] = useState(false);
  const [photoResult, setPhotoResult] = useState<PhotoAnalysisResult | null>(null);
  const [traitOptions, setTraitOptions] = useState({
    includeFaceShape: true,
    includeSkinTone: true,
    includeHair: true,
    includeFacialHair: true,
    includeBodyProportions: true
  });

  // Hairstyle Intelligence State
  const [hairCategoryFilter, setHairCategoryFilter] = useState<'all' | 'short' | 'medium' | 'long' | 'textured'>('all');
  const [hairRecommendations, setHairRecommendations] = useState<HairstyleRecommendationItem[]>([]);
  const [hairFavorites, setHairFavorites] = useState<string[]>([]);

  // Occasion State
  const [selectedOccasionIndex, setSelectedOccasionIndex] = useState(0);
  const [temperatureCelsius, setTemperatureCelsius] = useState(21);

  // Connect conversation manager to preview orchestrator
  useEffect(() => {
    avatarAIConversationManager.setPreviewOrchestrator(avatarPreviewOrchestrator);
    avatarPreviewOrchestrator.setCreatorEngine(creatorEngine);
  }, [creatorEngine]);

  // Subscribe to conversation messages
  useEffect(() => {
    return avatarAIConversationManager.subscribe((msgs) => {
      setMessages(msgs);
    });
  }, []);

  // Scroll chat to bottom on new message
  useEffect(() => {
    if (activeTab === 'chat') {
      chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, activeTab]);

  // Load hairstyle recommendations based on current avatar face
  useEffect(() => {
    const profile = creatorEngine.getProfile();
    const faceShape = profile.face.faceShapePreset || 'oval';
    const items = HairstyleRecommendationService.getRecommendations(faceShape, profile.genderPresentation);
    setHairRecommendations(items);
    setHairFavorites(HairstyleRecommendationService.getFavorites());
  }, [isOpen, creatorEngine]);

  if (!isOpen) return null;

  const currentProfile = creatorEngine.getProfile();

  // --- Handlers for Chat ---
  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || inputText;
    if (!text.trim()) return;

    if (!textToSend) {
      setInputText('');
    }

    try {
      await avatarAIConversationManager.handleUserMessage(text, currentProfile);
    } catch (err: any) {
      toast.error(err.message || 'Error processing request');
    }
  };

  const handleApplyProposal = () => {
    avatarAIConversationManager.acceptProposal();
    toast.success('Customization applied to Avatar DNA');
  };

  const handleRejectProposal = () => {
    avatarAIConversationManager.rejectProposal();
    toast('Preview reverted');
  };

  // --- Handlers for Photo Personalization ---
  const handlePhotoSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!photoConsent) {
      toast.error('Please agree to privacy consent before uploading');
      return;
    }

    setPhotoFile(file);
    const url = URL.createObjectURL(file);
    setPhotoPreviewUrl(url);
  };

  const handleAnalyzePhoto = async () => {
    if (!photoFile) {
      toast.error('Please select an image file first');
      return;
    }
    if (!photoConsent) {
      toast.error('Privacy consent is required');
      return;
    }

    setIsAnalyzingPhoto(true);
    try {
      AvatarAIPrivacyManager.grantConsent([
        'ephemeral_feature_extraction',
        'zero_retention_guarantee',
        'non_anthropometric_approximation'
      ]);

      const targetFeatures: ('face' | 'skin' | 'hair' | 'facial_hair' | 'proportions')[] = [];
      if (traitOptions.includeFaceShape) targetFeatures.push('face');
      if (traitOptions.includeSkinTone) targetFeatures.push('skin');
      if (traitOptions.includeHair) targetFeatures.push('hair');
      if (traitOptions.includeFacialHair) targetFeatures.push('facial_hair');
      if (traitOptions.includeBodyProportions) targetFeatures.push('proportions');

      const result = await PhotoAnalysisService.analyzePhoto(
        photoFile,
        currentProfile,
        {
          genderHint: currentProfile.genderPresentation,
          targetFeatures
        }
      );

      setPhotoResult(result);
      avatarPreviewOrchestrator.startPreview(result.generatedProposal, currentProfile);
      toast.success('Features extracted and previewing on 3D avatar!');
    } catch (err: any) {
      toast.error(err.message || 'Photo analysis failed');
    } finally {
      setIsAnalyzingPhoto(false);
    }
  };

  // --- Handlers for Hairstyle Intelligence ---
  const handlePreviewHair = (styleId: string) => {
    const proposal: AvatarCustomizationProposal = {
      id: `hair_select_${Date.now()}`,
      title: `Hairstyle: ${styleId}`,
      summary: `Applied 3D hairstyle asset "${styleId}".`,
      category: 'hair',
      confidence: 0.95,
      operations: [
        {
          action: 'set_preset',
          category: 'hair',
          targetKey: 'hairStyleId',
          targetValue: styleId,
          displayLabel: `Hairstyle: ${styleId}`
        }
      ],
      profilePatch: {
        appearance: {
          ...currentProfile.appearance,
          hairStyleId: styleId
        }
      },
      explanation: `Fitted 3D hair asset to head geometry.`,
      createdAt: new Date().toISOString(),
      source: 'recommendation',
      status: 'pending'
    };
    avatarPreviewOrchestrator.startPreview(proposal, currentProfile);
    toast.success('Previewing hairstyle in 3D');
  };

  const handleToggleFavorite = (styleId: string) => {
    const isFav = HairstyleRecommendationService.toggleFavorite(styleId);
    setHairFavorites(HairstyleRecommendationService.getFavorites());
    toast(isFav ? 'Added to hair favorites' : 'Removed from favorites');
  };

  const handleGenerateHairComparisonSet = () => {
    const proposals = HairstyleRecommendationService.getThreeWayHairstyleComparison(currentProfile);
    if (proposals.length > 0) {
      const comboProposal: AvatarCustomizationProposal = {
        ...proposals[0],
        alternatives: proposals.slice(1)
      };
      avatarPreviewOrchestrator.startPreview(comboProposal, currentProfile);
      toast.success('3-Option Hairstyle comparison set loaded in viewport!');
    }
  };

  // --- Handlers for Occasion Styling ---
  const occasionsData = [
    {
      id: 'gala',
      title: 'Luxury Evening Gala',
      aesthetic: 'Formal Atelier Luxury',
      palette: ['#0f172a', '#1e293b', '#d97706', '#f8fafc'],
      description: 'Structured midnight tuxedo with polished dress shoes and confident poise.'
    },
    {
      id: 'keynote',
      title: 'Tech Keynote Presentation',
      aesthetic: 'Executive Minimalism',
      palette: ['#1e1b4b', '#3b82f6', '#475569', '#f1f5f9'],
      description: 'Tailored sharp minimalist blazer with clean lines and visionary presence.'
    },
    {
      id: 'resort',
      title: 'Summer Riviera Resort',
      aesthetic: 'Mediterranean Linen',
      palette: ['#0284c7', '#38bdf8', '#fef08a', '#ffffff'],
      description: 'Relaxed airy linen tailoring suited for sun-drenched coastal occasions.'
    },
    {
      id: 'streetwear',
      title: 'Urban High-Fashion Streetwear',
      aesthetic: 'Contemporary Street Tailoring',
      palette: ['#18181b', '#71717a', '#dc2626', '#fafafa'],
      description: 'Bold oversized silhouettes with high-top kicks and modern texture.'
    }
  ];

  const handlePreviewOccasion = (index: number) => {
    setSelectedOccasionIndex(index);
    const occ = occasionsData[index];
    const styling = AvatarRecommendationEngine.recommendForOccasion(
      {
        occasion: occ.id,
        temperatureCelsius
      },
      currentProfile
    );
    const proposal = AvatarRecommendationEngine.proposalToAvatarDNA(styling, currentProfile);

    avatarPreviewOrchestrator.startPreview(proposal, currentProfile);
    toast.success(`Staging "${occ.title}" look on 3D avatar`);
  };

  if (!isOpen) return null;

  const modalBody = (
    <motion.div 
      className={embedded ? "avatar-ai-tray-view" : "avatar-ai-modal"}
      onClick={(e) => e.stopPropagation()}
      initial={embedded ? { opacity: 0, x: 20 } : { opacity: 0, scale: 0.94, y: 16 }}
      animate={embedded ? { opacity: 1, x: 0 } : { opacity: 1, scale: 1, y: 0 }}
      exit={embedded ? { opacity: 0, x: 20 } : { opacity: 0, scale: 0.94, y: 16 }}
      transition={{ duration: 0.2 }}
    >
      {/* Header */}
      <div className="avatar-ai-header">
        <div className="avatar-ai-header-left">
          {embedded && (
            <button
              type="button"
              className="avatar-ai-back-btn"
              onClick={onClose}
              title="Back to Avatar Studio"
              aria-label="Back"
            >
              <CaretLeft size={18} weight="bold" />
            </button>
          )}
          <div className="avatar-ai-logo-icon">
            <Sparkle size={18} weight="fill" />
          </div>
          <div className="avatar-ai-header-titles">
            <h2>Avatar AI Intelligence</h2>
            <p>Natural language styling, reference photo personalization & 3D wardrobe intelligence</p>
          </div>
        </div>
        <button 
          type="button" 
          className="avatar-ai-close-btn" 
          onClick={onClose}
          title="Close Assistant"
        >
          <X size={16} weight="bold" />
        </button>
      </div>

      {/* Tab Navigation */}
      <div className="avatar-ai-nav-tabs">
        <button
          type="button"
          className={`avatar-ai-tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => setActiveTab('chat')}
        >
          <Sparkle size={16} />
          <span>AI Stylist Chat</span>
        </button>
        <button
          type="button"
          className={`avatar-ai-tab-btn ${activeTab === 'photo' ? 'active' : ''}`}
          onClick={() => setActiveTab('photo')}
        >
          <UploadSimple size={16} />
          <span>Photo Personalization</span>
        </button>
        <button
          type="button"
          className={`avatar-ai-tab-btn ${activeTab === 'hairstyles' ? 'active' : ''}`}
          onClick={() => setActiveTab('hairstyles')}
        >
          <Scissors size={16} />
          <span>Hairstyle Intelligence</span>
        </button>
        <button
          type="button"
          className={`avatar-ai-tab-btn ${activeTab === 'occasions' ? 'active' : ''}`}
          onClick={() => setActiveTab('occasions')}
        >
          <SunHorizon size={16} />
          <span>Occasions & Outfits</span>
        </button>
      </div>

        {/* Modal Body */}
        <div className="avatar-ai-body">
          {/* TAB 1: Conversational Stylist */}
          {activeTab === 'chat' && (
            <div className="ai-chat-container">
              <div className="ai-chat-messages">
                {messages.map((msg) => (
                  <div key={msg.id} className={`ai-message-bubble ${msg.sender}`}>
                    <div>{msg.text}</div>

                    {msg.proposal && (
                      <div className="ai-proposal-card">
                        <div className="ai-proposal-card-header">
                          <span className="ai-proposal-card-title">{msg.proposal.title}</span>
                          <span className="ai-proposal-card-confidence">
                            {Math.round(msg.proposal.confidence * 100)}% match
                          </span>
                        </div>
                        <div className="ai-proposal-actions">
                          <button
                            type="button"
                            className="btn-ai-card-action btn-ai-card-preview"
                            onClick={() => avatarPreviewOrchestrator.startPreview(msg.proposal!, currentProfile)}
                          >
                            <Eye size={13} style={{ marginRight: 4 }} />
                            Preview in 3D
                          </button>
                          <button
                            type="button"
                            className="btn-ai-card-action btn-ai-card-accept"
                            onClick={handleApplyProposal}
                          >
                            <Check size={13} style={{ marginRight: 4 }} />
                            Apply Changes
                          </button>
                          <button
                            type="button"
                            className="btn-ai-card-action"
                            style={{ background: 'rgba(255,255,255,0.08)', color: '#9ca3af' }}
                            onClick={handleRejectProposal}
                          >
                            Revert
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
                <div ref={chatBottomRef} />
              </div>

              {/* Quick Prompt Suggestions */}
              <div className="ai-quick-actions-row">
                <button
                  type="button"
                  className="ai-quick-chip"
                  onClick={() => handleSendMessage('Give me a modern textured hairstyle')}
                >
                  ✂️ Modern textured hairstyle
                </button>
                <button
                  type="button"
                  className="ai-quick-chip"
                  onClick={() => handleSendMessage('Make my jaw wider & more defined')}
                >
                  📐 Chiseled jawline
                </button>
                <button
                  type="button"
                  className="ai-quick-chip"
                  onClick={() => handleSendMessage('Make my shoulders broader (+35%)')}
                >
                  🏋️ Broader shoulders (+35%)
                </button>
                <button
                  type="button"
                  className="ai-quick-chip"
                  onClick={() => handleSendMessage('Give me an athletic body shape')}
                >
                  ⚡ Athletic build
                </button>
                <button
                  type="button"
                  className="ai-quick-chip"
                  onClick={() => handleSendMessage('Change my eye color to emerald green')}
                >
                  👁️ Emerald green eyes
                </button>
              </div>

              {/* Input Bar */}
              <div className="ai-chat-input-row">
                <input
                  type="text"
                  className="ai-chat-input"
                  placeholder="Describe how to adjust your avatar (e.g. 'Narrower chin', 'Short boxed beard')..."
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleSendMessage();
                  }}
                />
                <button
                  type="button"
                  className="btn-ai-send"
                  onClick={() => handleSendMessage()}
                  title="Send instruction"
                >
                  <PaperPlaneTilt size={18} weight="bold" />
                </button>
              </div>
            </div>
          )}

          {/* TAB 2: Photo Personalization */}
          {activeTab === 'photo' && (
            <div className="photo-tab-container">
              {/* Privacy Consent Card */}
              <div className="photo-privacy-banner">
                <div className="photo-privacy-banner-header">
                  <ShieldCheck size={18} weight="fill" color="#818cf8" />
                  <span>Privacy-First Reference Photo Analysis</span>
                </div>
                <div className="photo-privacy-text">
                  Yorvyn processes your photograph <strong>purely in client-side ephemeral memory</strong> to estimate facial proportions, skin undertone, and hairstyle geometry. No photos are permanently stored on disk or servers per our Zero-Retention Policy.
                </div>
                <label className="photo-consent-checkbox-row">
                  <input
                    type="checkbox"
                    checked={photoConsent}
                    onChange={(e) => setPhotoConsent(e.target.checked)}
                  />
                  <span className="photo-consent-label">
                    I consent to ephemeral reference photo processing for Avatar DNA personalization
                  </span>
                </label>
              </div>

              {/* Upload Dropzone */}
              <label className={`photo-dropzone ${!photoConsent ? 'disabled' : ''}`}>
                <input
                  type="file"
                  accept="image/*"
                  style={{ display: 'none' }}
                  disabled={!photoConsent}
                  onChange={handlePhotoSelect}
                />
                {photoPreviewUrl ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    <img 
                      src={photoPreviewUrl} 
                      alt="Reference" 
                      style={{ width: 80, height: 80, borderRadius: 12, objectFit: 'cover' }} 
                    />
                    <div style={{ textAlign: 'left' }}>
                      <div style={{ fontWeight: 600, color: 'var(--ai-text-main, #ffffff)' }}>{photoFile?.name}</div>
                      <div style={{ fontSize: 12, color: 'var(--ai-text-sub, #9ca3af)' }}>Ready for privacy-first feature extraction</div>
                    </div>
                  </div>
                ) : (
                  <>
                    <UploadSimple size={32} color="#818cf8" />
                    <div>
                      <span style={{ fontWeight: 600, color: 'var(--ai-text-main, #ffffff)' }}>Click or drop a reference photo here</span>
                      <div style={{ fontSize: 12, color: 'var(--ai-text-sub, #9ca3af)', marginTop: 4 }}>
                        Front-facing portraits with clear lighting work best
                      </div>
                    </div>
                  </>
                )}
              </label>

              {/* Trait Inclusion Toggles */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14 }}>
                <label style={{ fontSize: 12, color: '#d1d5db', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={traitOptions.includeFaceShape}
                    onChange={(e) => setTraitOptions({ ...traitOptions, includeFaceShape: e.target.checked })}
                  />
                  Face Shape
                </label>
                <label style={{ fontSize: 12, color: '#d1d5db', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={traitOptions.includeSkinTone}
                    onChange={(e) => setTraitOptions({ ...traitOptions, includeSkinTone: e.target.checked })}
                  />
                  Skin Tone & Undertone
                </label>
                <label style={{ fontSize: 12, color: '#d1d5db', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={traitOptions.includeHair}
                    onChange={(e) => setTraitOptions({ ...traitOptions, includeHair: e.target.checked })}
                  />
                  Hairstyle
                </label>
                <label style={{ fontSize: 12, color: '#d1d5db', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={traitOptions.includeFacialHair}
                    onChange={(e) => setTraitOptions({ ...traitOptions, includeFacialHair: e.target.checked })}
                  />
                  Facial Hair
                </label>
                <label style={{ fontSize: 12, color: '#d1d5db', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={traitOptions.includeBodyProportions}
                    onChange={(e) => setTraitOptions({ ...traitOptions, includeBodyProportions: e.target.checked })}
                  />
                  Body Silhouette
                </label>
              </div>

              {/* Analyze Button */}
              <button
                type="button"
                className="btn-ai-card-action btn-ai-card-accept"
                style={{ padding: '12px 20px', fontSize: 14, justifySelf: 'flex-start' }}
                disabled={!photoConsent || !photoFile || isAnalyzingPhoto}
                onClick={handleAnalyzePhoto}
              >
                <Sparkle size={16} weight="fill" style={{ marginRight: 6 }} />
                {isAnalyzingPhoto ? 'Analyzing traits...' : 'Analyze Reference & Preview in 3D'}
              </button>

              {/* Detected Traits Grid */}
              {photoResult && (
                <div className="photo-traits-grid">
                  <div className="trait-card">
                    <span className="trait-title">Face Shape</span>
                    <span className="trait-value">{photoResult.detectedTraits.faceShape.description}</span>
                    <span className="trait-confidence">{Math.round(photoResult.detectedTraits.faceShape.confidence * 100)}% confidence</span>
                  </div>
                  <div className="trait-card">
                    <span className="trait-title">Skin Tone</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span 
                        style={{ 
                          width: 14, 
                          height: 14, 
                          borderRadius: '50%', 
                          background: photoResult.detectedTraits.skinTone.hex, 
                          border: '1px solid rgba(255,255,255,0.2)' 
                        }} 
                      />
                      <span className="trait-value">{photoResult.detectedTraits.skinTone.description}</span>
                    </div>
                    <span className="trait-confidence">{Math.round(photoResult.detectedTraits.skinTone.confidence * 100)}% confidence</span>
                  </div>
                  <div className="trait-card">
                    <span className="trait-title">Detected Hair</span>
                    <span className="trait-value">{photoResult.detectedTraits.hair.styleName}</span>
                    <span className="trait-confidence">{Math.round(photoResult.detectedTraits.hair.confidence * 100)}% confidence</span>
                  </div>
                  <div className="trait-card">
                    <span className="trait-title">Body Silhouette</span>
                    <span className="trait-value">{photoResult.detectedTraits.proportions.estimatedSilhouette}</span>
                    <span className="trait-confidence" style={{ color: '#9ca3af' }}>{photoResult.detectedTraits.proportions.disclaimer}</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: Hairstyle Intelligence */}
          {activeTab === 'hairstyles' && (
            <div className="hairstyles-tab-container">
              {/* Header info */}
              <div className="hairstyles-face-badge">
                <div className="hairstyles-face-info">
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--ai-text-main, #ffffff)' }}>
                    Face Shape Compatibility: {currentProfile.face.faceShapePreset?.toUpperCase() || 'OVAL'}
                  </span>
                  <span style={{ fontSize: 12, color: 'var(--ai-text-sub, #9ca3af)' }}>
                    Hairstyles weighted by facial proportion harmony and 3D mesh compatibility
                  </span>
                </div>
                <button
                  type="button"
                  className="btn-preview-hair"
                  style={{ width: 'auto', padding: '8px 14px' }}
                  onClick={handleGenerateHairComparisonSet}
                >
                  <Sparkle size={14} weight="fill" style={{ marginRight: 6 }} />
                  Compare 3-Option Set
                </button>
              </div>

              {/* Filter Tabs */}
              <div style={{ display: 'flex', gap: 6 }}>
                {(['all', 'short', 'medium', 'long', 'textured'] as const).map((filter) => (
                  <button
                    key={filter}
                    type="button"
                    className={`preview-alt-pill ${hairCategoryFilter === filter ? 'active' : ''}`}
                    onClick={() => setHairCategoryFilter(filter)}
                  >
                    {filter.charAt(0).toUpperCase() + filter.slice(1)}
                  </button>
                ))}
              </div>

              {/* Hairstyle Cards Grid */}
              <div className="hairstyles-grid">
                {hairRecommendations
                  .filter(h => hairCategoryFilter === 'all' || h.category === hairCategoryFilter)
                  .map((item) => {
                    const isFav = hairFavorites.includes(item.styleId);
                    return (
                      <div key={item.styleId} className="hairstyle-card">
                        <div className="hairstyle-card-header">
                          <span className="hairstyle-card-name">{item.name}</span>
                          <button
                            type="button"
                            className={`btn-favorite-heart ${isFav ? 'is-favorite' : ''}`}
                            onClick={() => handleToggleFavorite(item.styleId)}
                            title={isFav ? 'Favorited' : 'Add to favorites'}
                          >
                            <Heart size={16} weight={isFav ? 'fill' : 'regular'} />
                          </button>
                        </div>
                        <span className="hairstyle-match-score">
                          ★ {item.matchScore}% Harmony Match
                        </span>
                        <p className="hairstyle-reason">{item.editorialReason}</p>
                        <button
                          type="button"
                          className="btn-preview-hair"
                          onClick={() => handlePreviewHair(item.styleId)}
                        >
                          <Eye size={13} style={{ marginRight: 6 }} />
                          Preview in 3D
                        </button>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          {/* TAB 4: Occasion & Wardrobe */}
          {activeTab === 'occasions' && (
            <div className="occasions-tab-container">
              {/* Weather Simulator */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--ai-surface-subtle, rgba(255,255,255,0.03))', padding: '12px 16px', borderRadius: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <ThermometerSimple size={20} color="#38bdf8" />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--ai-text-main, #ffffff)' }}>Weather Context Simulator</div>
                    <div style={{ fontSize: 11.5, color: 'var(--ai-text-sub, #9ca3af)' }}>Adapts fabric weights and layering recommendations</div>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: '#0284c7' }}>{temperatureCelsius}°C</span>
                  <input
                    type="range"
                    min="5"
                    max="35"
                    value={temperatureCelsius}
                    onChange={(e) => setTemperatureCelsius(Number(e.target.value))}
                    style={{ width: 100 }}
                  />
                </div>
              </div>

              {/* Occasion Cards */}
              <div className="occasions-grid">
                {occasionsData.map((occ, idx) => (
                  <div
                    key={occ.id}
                    className="occasion-card"
                    onClick={() => handlePreviewOccasion(idx)}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--ai-text-main, #ffffff)' }}>{occ.title}</span>
                      {selectedOccasionIndex === idx && (
                        <span className="ai-proposal-card-confidence">Active</span>
                      )}
                    </div>
                    <span style={{ fontSize: 12, color: 'var(--ai-accent, #a5b4fc)', fontWeight: 500 }}>{occ.aesthetic}</span>
                    <p style={{ fontSize: 11.5, color: 'var(--ai-text-sub, #9ca3af)', margin: 0 }}>{occ.description}</p>
                    
                    {/* Palette Swatches */}
                    <div className="occasion-palette-dots">
                      {occ.palette.map((color, cIdx) => (
                        <div
                          key={cIdx}
                          className="palette-swatch-dot"
                          style={{ background: color }}
                          title={color}
                        />
                      ))}
                    </div>

                    <button
                      type="button"
                      className="btn-preview-hair"
                      style={{ marginTop: 4 }}
                      onClick={(e) => {
                        e.stopPropagation();
                        handlePreviewOccasion(idx);
                      }}
                    >
                      <Eye size={13} style={{ marginRight: 6 }} />
                      Preview Complete Look
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </motion.div>
  );

  if (embedded) {
    return modalBody;
  }

  return (
    <div className="avatar-ai-modal-backdrop" onClick={onClose}>
      {modalBody}
    </div>
  );
};
