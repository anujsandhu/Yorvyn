import React from 'react';
import './SkeletonLoader.css';

interface AvatarSkeletonLoaderProps {
  loadingLabel?: string;
  theme?: 'dark' | 'light';
  title?: string;
}

/**
 * Default 3D Dummy Character Loader.
 * Displays the authentic 3D mannequin figure in studio lighting with a breathing
 * pedestal float and luxury status glass capsule.
 */
export const AvatarSkeletonLoader: React.FC<AvatarSkeletonLoaderProps> = ({
  loadingLabel = 'Calibrating 3D Avatar Model...',
  theme = 'dark',
  title = 'Yorvyn 3D Studio'
}) => {
  return (
    <div className={`avatar-skeleton-container theme-${theme}`} aria-live="polite">
      <div className="avatar-dummy-stage">
        {/* Soft studio pedestal shadow */}
        <div className="avatar-dummy-pedestal-shadow" />

        {/* 3D Default Dummy Character Figure */}
        <div className="avatar-dummy-figure-wrap">
          <img
            src="/assets/avatar-dummy-loader.png"
            alt="Default 3D Mannequin"
            className="avatar-dummy-figure"
            draggable={false}
          />
          <div className="avatar-dummy-glimmer" />
        </div>
      </div>

      {/* Floating Status Glass Pill */}
      <div className="avatar-skeleton-status-pill">
        <span className="status-live-pulse-dot" />
        <span className="status-label-bold">{title}</span>
        <span className="status-separator-dot">•</span>
        <span className="status-stage-text" title={loadingLabel}>
          {loadingLabel}
        </span>
      </div>
    </div>
  );
};

/**
 * Squircle Garment / Outfit Card Skeleton for Catalog & Wardrobe grids.
 */
export const CardSkeleton: React.FC<{ className?: string }> = ({ className = '' }) => {
  return (
    <div className={`skeleton-card-item ${className}`}>
      <div className="card-skeleton-image shimmer-block" />
      <div className="card-skeleton-brand shimmer-block" />
      <div className="card-skeleton-price shimmer-block" />
    </div>
  );
};

/**
 * Grid of Card Skeletons matching the drawer catalog layout.
 */
export const CatalogGridSkeleton: React.FC<{ count?: number }> = ({ count = 8 }) => {
  return (
    <div className="drawer-catalog-grid" aria-label="Loading catalog garments...">
      {Array.from({ length: count }).map((_, idx) => (
        <CardSkeleton key={idx} />
      ))}
    </div>
  );
};

/**
 * AI Stylist Chat Message Skeleton.
 */
export const ChatSkeleton: React.FC = () => {
  return (
    <div className="stylist-chat-skeleton-bubble" aria-label="AI Stylist is thinking...">
      <div className="chat-skeleton-avatar shimmer-block" />
      <div className="chat-skeleton-body">
        <div className="chat-skeleton-line w-full shimmer-block" />
        <div className="chat-skeleton-line w-med shimmer-block" />
        <div className="chat-skeleton-line w-short shimmer-block" />
      </div>
    </div>
  );
};

/**
 * 3D Avatar Customization Presets Skeleton.
 */
export const AvatarCreatorSkeleton: React.FC = () => {
  return (
    <div className="avatar-creator-skeleton" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ display: 'flex', gap: '8px' }}>
        <div className="shimmer-block" style={{ width: '84px', height: '32px', borderRadius: '16px' }} />
        <div className="shimmer-block" style={{ width: '84px', height: '32px', borderRadius: '16px' }} />
        <div className="shimmer-block" style={{ width: '84px', height: '32px', borderRadius: '16px' }} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="shimmer-block" style={{ aspectRatio: '1/1', borderRadius: '16px' }} />
        ))}
      </div>
    </div>
  );
};

/**
 * Embedded In-Tray Workflow Skeleton (Upload / Profile / Category Manager).
 */
export const WorkflowSkeleton: React.FC<{ title?: string }> = ({ title = 'Loading...' }) => {
  return (
    <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }} aria-label={title}>
      <div className="shimmer-block" style={{ width: '140px', height: '24px', borderRadius: '8px' }} />
      <div className="shimmer-block" style={{ width: '100%', height: '180px', borderRadius: '16px' }} />
      <div className="shimmer-block" style={{ width: '70%', height: '36px', borderRadius: '12px' }} />
    </div>
  );
};
