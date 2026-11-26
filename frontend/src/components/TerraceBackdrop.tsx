import React from 'react';
import './TerraceBackdrop.css';

/**
 * TerraceBackdrop Component — Yorvyn Studio Stage
 * Renders the sunlit luxury architectural terrace overlooking the ocean,
 * matching the primary reference design from Image 3.
 */
export const TerraceBackdrop: React.FC = () => {
  return (
    <div className="terrace-backdrop-container" aria-hidden="true">
      {/* 1. Sky & Horizon Gradient */}
      <div className="terrace-sky-layer" />

      {/* 2. Distant Ocean & Coastal Mountain Silhouette */}
      <div className="terrace-ocean-layer">
        <svg className="terrace-mountains-svg" viewBox="0 0 1440 320" preserveAspectRatio="none">
          <path
            d="M0,220 C180,210 320,180 520,200 C740,220 900,170 1120,195 C1280,215 1380,205 1440,210 L1440,320 L0,320 Z"
            fill="rgba(147, 197, 253, 0.45)"
          />
          <path
            d="M0,245 C220,235 480,210 720,230 C960,250 1200,220 1440,240 L1440,320 L0,320 Z"
            fill="rgba(125, 211, 252, 0.65)"
          />
        </svg>
      </div>

      {/* 3. Luxury Architecture Pavilion Arch & Balcony Pillars */}
      <div className="terrace-architecture-layer">
        {/* Modernist Arch Portal */}
        <div className="arch-portal-frame" />

        {/* Minimalist Balustrade Horizon Line */}
        <div className="terrace-balustrade-rail" />

        {/* Potted Architectural Olive Plant on Left */}
        <div className="terrace-potted-plant">
          <svg viewBox="0 0 160 300" className="potted-plant-svg">
            {/* Soft Shadow */}
            <ellipse cx="80" cy="285" rx="42" ry="10" fill="rgba(15, 23, 42, 0.08)" />
            {/* White Ceramic Planter */}
            <path d="M48,220 L112,220 L102,282 L58,282 Z" fill="#ffffff" stroke="rgba(203, 213, 225, 0.7)" strokeWidth="1.5" />
            {/* Olive Tree Trunk */}
            <path d="M80,220 Q76,170 82,130" stroke="#78716c" strokeWidth="5" fill="none" strokeLinecap="round" />
            <path d="M78,175 Q62,150 56,120" stroke="#78716c" strokeWidth="3" fill="none" strokeLinecap="round" />
            <path d="M80,150 Q96,130 106,105" stroke="#78716c" strokeWidth="3" fill="none" strokeLinecap="round" />
            {/* Soft Green Foliage Clusters */}
            <ellipse cx="78" cy="115" rx="36" ry="26" fill="rgba(101, 163, 13, 0.72)" />
            <ellipse cx="56" cy="110" rx="28" ry="20" fill="rgba(132, 204, 22, 0.65)" />
            <ellipse cx="102" cy="98" rx="30" ry="22" fill="rgba(101, 163, 13, 0.68)" />
            <ellipse cx="82" cy="78" rx="24" ry="18" fill="rgba(163, 230, 53, 0.6)" />
          </svg>
        </div>
      </div>

      {/* 4. Polished High-Gloss White Terrace Floor with Subtle Contact Sheen */}
      <div className="terrace-floor-layer">
        <div className="terrace-floor-gloss" />
      </div>
    </div>
  );
};

