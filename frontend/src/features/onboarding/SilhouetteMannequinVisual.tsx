import React from 'react';

interface SilhouetteMannequinVisualProps {
  type: 'slender' | 'athletic' | 'regular' | 'curvy' | 'broad' | 'fuller' | 'petite' | 'classic' | 'studio' | 'statuesque';
  isSelected?: boolean;
  className?: string;
}

/**
 * High-fashion 3D-styled mannequin SVG visual component for body silhouette
 * and stature selection cards, inspired by luxury digital atelier & 3D character creators.
 */
export const SilhouetteMannequinVisual: React.FC<SilhouetteMannequinVisualProps> = ({
  type,
  isSelected = false,
  className = '',
}) => {
  // Determine anatomical scaling parameters based on silhouette type
  let shoulderWidth = 42;
  let waistWidth = 26;
  let hipWidth = 34;
  let chestWidth = 38;
  let thighWidth = 14;
  let scaleY = 1.0;
  let headRadiusY = 13;

  switch (type) {
    case 'slender':
      shoulderWidth = 36;
      chestWidth = 32;
      waistWidth = 22;
      hipWidth = 30;
      thighWidth = 12;
      break;
    case 'athletic': // V-Taper
      shoulderWidth = 48;
      chestWidth = 44;
      waistWidth = 24;
      hipWidth = 32;
      thighWidth = 15;
      break;
    case 'regular': // Proportional
      shoulderWidth = 41;
      chestWidth = 37;
      waistWidth = 28;
      hipWidth = 35;
      thighWidth = 14;
      break;
    case 'curvy': // Hourglass
      shoulderWidth = 38;
      chestWidth = 39;
      waistWidth = 22;
      hipWidth = 40;
      thighWidth = 16;
      break;
    case 'broad': // Power Build
      shoulderWidth = 50;
      chestWidth = 48;
      waistWidth = 36;
      hipWidth = 40;
      thighWidth = 17;
      break;
    case 'fuller': // Full Frame
      shoulderWidth = 46;
      chestWidth = 46;
      waistWidth = 38;
      hipWidth = 44;
      thighWidth = 18;
      break;
    // Stature presets (height variation)
    case 'petite':
      scaleY = 0.84;
      shoulderWidth = 38;
      waistWidth = 25;
      hipWidth = 33;
      break;
    case 'classic':
      scaleY = 0.92;
      shoulderWidth = 41;
      waistWidth = 26;
      hipWidth = 34;
      break;
    case 'studio':
      scaleY = 1.0;
      shoulderWidth = 44;
      waistWidth = 26;
      hipWidth = 33;
      break;
    case 'statuesque':
      scaleY = 1.08;
      shoulderWidth = 46;
      waistWidth = 27;
      hipWidth = 35;
      break;
  }

  const primaryFill = isSelected ? 'url(#mannequinGradientActive)' : 'url(#mannequinGradient)';
  const strokeColor = isSelected ? '#0f172a' : '#475569';

  return (
    <div className={`silhouette-visual-container ${className}`}>
      <svg
        viewBox="20 6 60 142"
        className="mannequin-svg"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <defs>
          {/* Porcelain Mannequin Lighting Gradient */}
          <linearGradient id="mannequinGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="45%" stopColor="#f1f5f9" />
            <stop offset="85%" stopColor="#e2e8f0" />
            <stop offset="100%" stopColor="#cbd5e1" />
          </linearGradient>

          {/* Active Atelier Selected Lighting Gradient */}
          <linearGradient id="mannequinGradientActive" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="40%" stopColor="#f8fafc" />
            <stop offset="85%" stopColor="#e0f2fe" />
            <stop offset="100%" stopColor="#bae6fd" />
          </linearGradient>

          {/* Ambient Occlusion Drop Shadow */}
          <radialGradient id="mannequinGroundShadow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(15, 23, 42, 0.22)" />
            <stop offset="70%" stopColor="rgba(15, 23, 42, 0.05)" />
            <stop offset="100%" stopColor="rgba(15, 23, 42, 0)" />
          </radialGradient>

          {/* Torso Specular Glint */}
          <linearGradient id="specularGlint" x1="20%" y1="0%" x2="80%" y2="100%">
            <stop offset="0%" stopColor="rgba(255, 255, 255, 0.85)" />
            <stop offset="100%" stopColor="rgba(255, 255, 255, 0)" />
          </linearGradient>
        </defs>

        {/* Studio Floor Ambient Shadow */}
        <ellipse cx="50" cy="144" rx={24 * (hipWidth / 34)} ry="4" fill="url(#mannequinGroundShadow)" />

        <g transform={`translate(50, 75) scale(1, ${scaleY}) translate(-50, -75)`}>
          {/* Head & Neck */}
          <ellipse cx="50" cy="18" rx="8.5" ry={headRadiusY} fill={primaryFill} stroke={strokeColor} strokeWidth="1" />
          {/* Neck */}
          <path d="M 46 29 L 46 34 L 54 34 L 54 29 Z" fill={primaryFill} stroke={strokeColor} strokeWidth="0.8" />

          {/* Torso (Sculpted Chest, Waist, Hips) */}
          <path
            d={`
              M ${50 - shoulderWidth / 2} 37
              C ${50 - chestWidth / 2} 48, ${50 - waistWidth / 2} 60, ${50 - waistWidth / 2} 66
              C ${50 - waistWidth / 2} 72, ${50 - hipWidth / 2} 78, ${50 - hipWidth / 2} 86
              L ${50 + hipWidth / 2} 86
              C ${50 + hipWidth / 2} 78, ${50 + waistWidth / 2} 72, ${50 + waistWidth / 2} 66
              C ${50 + waistWidth / 2} 60, ${50 + chestWidth / 2} 48, ${50 + shoulderWidth / 2} 37
              C ${50 + shoulderWidth / 3} 34, 53 34, 50 34
              C 47 34, ${50 - shoulderWidth / 3} 34, ${50 - shoulderWidth / 2} 37
              Z
            `}
            fill={primaryFill}
            stroke={strokeColor}
            strokeWidth="1.1"
          />

          {/* Torso Specular Highlight Stripe */}
          <path
            d={`
              M 48 38
              C 48 48, 47 62, 47 67
              C 47 72, 46 80, 46 84
              L 49 84
              C 49 80, 50 72, 50 67
              C 50 62, 51 48, 51 38
              Z
            `}
            fill="url(#specularGlint)"
            opacity="0.45"
          />

          {/* Left Arm (Relaxed Fashion Drape) */}
          <path
            d={`
              M ${50 - shoulderWidth / 2 + 1} 37
              C ${50 - shoulderWidth / 2 - 5} 52, ${50 - waistWidth / 2 - 7} 66, ${50 - hipWidth / 2 - 6} 84
              L ${50 - hipWidth / 2 - 3} 84
              C ${50 - waistWidth / 2 - 4} 66, ${50 - shoulderWidth / 2 - 2} 52, ${50 - shoulderWidth / 2 + 3} 39
              Z
            `}
            fill={primaryFill}
            stroke={strokeColor}
            strokeWidth="0.8"
          />

          {/* Right Arm (Relaxed Fashion Drape) */}
          <path
            d={`
              M ${50 + shoulderWidth / 2 - 1} 37
              C ${50 + shoulderWidth / 2 + 5} 52, ${50 + waistWidth / 2 + 7} 66, ${50 + hipWidth / 2 + 6} 84
              L ${50 + hipWidth / 2 + 3} 84
              C ${50 + waistWidth / 2 + 4} 66, ${50 + shoulderWidth / 2 + 2} 52, ${50 + shoulderWidth / 2 - 3} 39
              Z
            `}
            fill={primaryFill}
            stroke={strokeColor}
            strokeWidth="0.8"
          />

          {/* Pelvis / Inseam divider */}
          <path
            d="M 50 82 L 50 87"
            stroke={strokeColor}
            strokeWidth="1.2"
            strokeLinecap="round"
          />

          {/* Left Leg */}
          <path
            d={`
              M ${50 - hipWidth / 2 + 1} 86
              C ${50 - hipWidth / 2} 98, ${49 - thighWidth} 112, ${47 - thighWidth / 2} 126
              C ${47 - thighWidth / 2} 132, 45 138, 45 142
              L 49 142
              C 49 138, 50 132, 50 126
              C 50 112, 50 98, 50 86
              Z
            `}
            fill={primaryFill}
            stroke={strokeColor}
            strokeWidth="1"
          />

          {/* Right Leg */}
          <path
            d={`
              M 50 86
              C 50 98, 50 112, 50 126
              C 50 132, 51 138, 51 142
              L 55 142
              C 55 138, ${53 + thighWidth / 2} 132, ${53 + thighWidth / 2} 126
              C ${51 + thighWidth} 112, ${50 + hipWidth / 2} 98, ${50 + hipWidth / 2 - 1} 86
              Z
            `}
            fill={primaryFill}
            stroke={strokeColor}
            strokeWidth="1"
          />

          {/* Anatomical Contours & Knee Hints */}
          <circle cx="47" cy="116" r="1.5" fill="rgba(148, 163, 184, 0.45)" />
          <circle cx="53" cy="116" r="1.5" fill="rgba(148, 163, 184, 0.45)" />
        </g>
      </svg>
    </div>
  );
};

/* ── STEP 2: Skin Tone Mannequin Bust Visual ── */
interface SkinToneMannequinVisualProps {
  hex: string;
  isSelected?: boolean;
  className?: string;
}

export const SkinToneMannequinVisual: React.FC<SkinToneMannequinVisualProps> = ({
  hex,
  isSelected = false,
  className = '',
}) => {
  const gradId = `skinGrad_${hex.replace('#', '')}`;
  const strokeColor = isSelected ? '#0f172a' : '#334155';

  return (
    <div className={`silhouette-visual-container ${className}`}>
      <svg
        viewBox="16 8 68 100"
        className="mannequin-svg"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id={gradId} x1="15%" y1="0%" x2="85%" y2="100%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.55" />
            <stop offset="28%" stopColor={hex} />
            <stop offset="85%" stopColor={hex} />
            <stop offset="100%" stopColor="#0f172a" stopOpacity="0.25" />
          </linearGradient>
          <radialGradient id={`shadow_${hex.replace('#', '')}`} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(15, 23, 42, 0.28)" />
            <stop offset="100%" stopColor="rgba(15, 23, 42, 0)" />
          </radialGradient>
        </defs>

        {/* Ambient base shadow */}
        <ellipse cx="50" cy="103" rx="25" ry="4" fill={`url(#shadow_${hex.replace('#', '')})`} />

        {/* Head with contour */}
        <ellipse cx="50" cy="30" rx="14" ry="18" fill={`url(#${gradId})`} stroke={strokeColor} strokeWidth="1.4" />
        {/* Crisp specular highlight on cheek & forehead */}
        <ellipse cx="46" cy="22" rx="4.5" ry="6" fill="#ffffff" opacity="0.45" />

        {/* Neck */}
        <path d="M 44 46 L 44 60 L 56 60 L 56 46 Z" fill={`url(#${gradId})`} stroke={strokeColor} strokeWidth="1.1" />

        {/* Clavicle & Shoulders (Sculpted Atelier Bust) */}
        <path
          d="
            M 20 78
            C 28 66, 40 60, 44 60
            L 56 60
            C 60 60, 72 66, 80 78
            C 76 96, 62 102, 50 102
            C 38 102, 24 96, 20 78
            Z
          "
          fill={`url(#${gradId})`}
          stroke={strokeColor}
          strokeWidth="1.5"
        />

        {/* Clavicle contour line */}
        <path d="M 38 68 Q 50 72 62 68" fill="none" stroke={strokeColor} strokeWidth="1.1" opacity="0.75" />
      </svg>
    </div>
  );
};

/* ── STEP 4: Styling Silhouette / Gender Presentation Visual ── */
interface PresentationVisualProps {
  presentation: 'feminine' | 'neutral' | 'masculine';
  isSelected?: boolean;
  className?: string;
}

export const PresentationVisual: React.FC<PresentationVisualProps> = ({
  presentation,
  isSelected = false,
  className = '',
}) => {
  const primaryFill = isSelected ? 'url(#presGradActive)' : 'url(#presGrad)';
  const strokeColor = isSelected ? '#0f172a' : '#334155';

  const shoulderW = presentation === 'masculine' ? 62 : presentation === 'feminine' ? 48 : 55;
  const waistW = presentation === 'masculine' ? 40 : presentation === 'feminine' ? 28 : 34;

  return (
    <div className={`silhouette-visual-container ${className}`}>
      <svg
        viewBox="16 8 68 100"
        className="mannequin-svg"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="presGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="45%" stopColor="#f1f5f9" />
            <stop offset="85%" stopColor="#e2e8f0" />
            <stop offset="100%" stopColor="#cbd5e1" />
          </linearGradient>
          <linearGradient id="presGradActive" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="40%" stopColor="#f0f9ff" />
            <stop offset="85%" stopColor="#e0f2fe" />
            <stop offset="100%" stopColor="#bae6fd" />
          </linearGradient>
          <radialGradient id="presShadow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(15, 23, 42, 0.26)" />
            <stop offset="100%" stopColor="rgba(15, 23, 42, 0)" />
          </radialGradient>
        </defs>

        <ellipse cx="50" cy="103" rx="25" ry="4" fill="url(#presShadow)" />

        {/* Head */}
        <ellipse cx="50" cy="26" rx="12" ry="16" fill={primaryFill} stroke={strokeColor} strokeWidth="1.4" />
        {/* Specular highlight */}
        <ellipse cx="46" cy="20" rx="3.5" ry="5" fill="#ffffff" opacity="0.5" />

        {/* Neck */}
        <path d="M 45 40 L 45 52 L 55 52 L 55 40 Z" fill={primaryFill} stroke={strokeColor} strokeWidth="1.1" />

        {/* Sculpted Torso Drape */}
        <path
          d={`
            M ${50 - shoulderW / 2} 66
            C ${50 - waistW / 2} 76, ${50 - waistW / 2} 88, ${50 - waistW / 2 + 2} 100
            L ${50 + waistW / 2 - 2} 100
            C ${50 + waistW / 2} 88, ${50 + waistW / 2} 76, ${50 + shoulderW / 2} 66
            C ${50 + shoulderW / 3} 56, 56 52, 50 52
            C 44 52, ${50 - shoulderW / 3} 56, ${50 - shoulderW / 2} 66
            Z
          `}
          fill={primaryFill}
          stroke={strokeColor}
          strokeWidth="1.5"
        />

        {/* Stylized Collar / Drape Line */}
        {presentation === 'masculine' ? (
          <path d="M 44 54 L 50 72 L 56 54" fill="none" stroke={strokeColor} strokeWidth="1.3" />
        ) : presentation === 'feminine' ? (
          <path d="M 42 54 Q 50 66 58 54" fill="none" stroke={strokeColor} strokeWidth="1.3" />
        ) : (
          <path d="M 43 54 L 50 64 L 57 54" fill="none" stroke={strokeColor} strokeWidth="1.3" />
        )}
      </svg>
    </div>
  );
};

/* ── STEP 4: Hair Color Luster Swatch Visual ── */
interface HairColorSwatchVisualProps {
  hex: string;
  name: string;
  isSelected?: boolean;
  className?: string;
}

export const HairColorSwatchVisual: React.FC<HairColorSwatchVisualProps> = ({
  hex,
  isSelected = false,
  className = '',
}) => {
  const strokeColor = isSelected ? '#0f172a' : '#334155';

  return (
    <div className={`silhouette-visual-container ${className}`}>
      <svg
        viewBox="18 10 64 85"
        className="mannequin-svg"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id={`hairGrad_${hex.replace('#', '')}`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.45" />
            <stop offset="35%" stopColor={hex} />
            <stop offset="80%" stopColor={hex} />
            <stop offset="100%" stopColor="#000000" stopOpacity="0.5" />
          </linearGradient>
          <linearGradient id={`sheen_${hex.replace('#', '')}`} x1="0%" y1="0%" x2="80%" y2="80%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.6" />
            <stop offset="40%" stopColor="#ffffff" stopOpacity="0.1" />
            <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
          </linearGradient>
          <radialGradient id={`hairShadow_${hex.replace('#', '')}`} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(15, 23, 42, 0.22)" />
            <stop offset="100%" stopColor="rgba(15, 23, 42, 0)" />
          </radialGradient>
        </defs>

        {/* Ambient shadow */}
        <ellipse cx="50" cy="92" rx="28" ry="4" fill={`url(#hairShadow_${hex.replace('#', '')})`} />

        {/* Sculpted High-Fashion Hair Strand Swatch with Natural Volume */}
        <path
          d="
            M 50 12
            C 68 12, 82 28, 80 48
            C 78 68, 62 82, 50 86
            C 38 82, 22 68, 20 48
            C 18 28, 32 12, 50 12
            Z
          "
          fill={`url(#hairGrad_${hex.replace('#', '')})`}
          stroke={strokeColor}
          strokeWidth="1.4"
        />

        {/* High-Gloss Hair Fiber Sheen & Wave Curve */}
        <path
          d="
            M 42 16
            C 58 18, 68 32, 66 48
            C 64 64, 54 74, 48 80
            C 52 72, 60 60, 60 48
            C 60 36, 52 24, 42 16
            Z
          "
          fill={`url(#sheen_${hex.replace('#', '')})`}
        />
        
        {/* Subtle inner luster core */}
        <ellipse cx="40" cy="38" rx="8" ry="16" fill="#ffffff" opacity="0.18" transform="rotate(-15 40 38)" />
      </svg>
    </div>
  );
};

/* ── STEP 4: Hairstyle Mannequin Visual (Matching Reference Avatar Cards) ── */
interface HairStyleMannequinVisualProps {
  styleId: string;
  hairColorHex?: string;
  isSelected?: boolean;
  className?: string;
}

export const HairStyleMannequinVisual: React.FC<HairStyleMannequinVisualProps> = ({
  styleId,
  hairColorHex = '#1c1d20',
  className = '',
}) => {
  const hairColor = hairColorHex || '#1c1d20';

  return (
    <div className={`silhouette-visual-container ${className}`}>
      <svg
        viewBox="16 10 68 92"
        className="mannequin-svg"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <defs>
          {/* Head Porcelain 3D Lighting */}
          <radialGradient id="faceGrad" cx="45%" cy="40%" r="55%">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="65%" stopColor="#f1f5f9" />
            <stop offset="100%" stopColor="#e2e8f0" />
          </radialGradient>
          {/* Hair Lighting & Depth */}
          <linearGradient id={`hairCutGrad_${styleId}`} x1="20%" y1="0%" x2="80%" y2="100%">
            <stop offset="0%" stopColor="#475569" stopOpacity="0.4" />
            <stop offset="30%" stopColor={hairColor} />
            <stop offset="100%" stopColor={hairColor} />
          </linearGradient>
          {/* Ambient Base Shadow */}
          <radialGradient id="faceShadow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(15, 23, 42, 0.14)" />
            <stop offset="100%" stopColor="rgba(15, 23, 42, 0)" />
          </radialGradient>
        </defs>

        {/* Ambient floor shadow */}
        <ellipse cx="50" cy="98" rx="22" ry="3" fill="url(#faceShadow)" />

        {/* Back Hair Layer (for long, bob, ponytail) */}
        {(styleId === 'long01' || styleId === 'bob01' || styleId === 'bob02' || styleId === 'ponytail01') && (
          <path
            d={
              styleId === 'long01'
                ? 'M 22 45 C 18 68, 16 88, 24 96 L 36 96 C 30 84, 28 66, 32 45 Z M 78 45 C 82 68, 84 88, 76 96 L 64 96 C 70 84, 72 66, 68 45 Z'
                : styleId === 'ponytail01'
                ? 'M 42 16 C 42 6, 58 6, 58 16 C 62 10, 68 18, 62 26 L 50 24 L 38 26 C 32 18, 38 10, 42 16 Z'
                : 'M 24 45 C 22 62, 24 74, 30 78 L 38 78 C 32 70, 30 58, 34 45 Z M 76 45 C 78 62, 76 74, 70 78 L 62 78 C 68 70, 70 58, 66 45 Z'
            }
            fill={`url(#hairCutGrad_${styleId})`}
          />
        )}

        {/* Neck */}
        <path d="M 44 68 L 44 86 L 56 86 L 56 68 Z" fill="url(#faceGrad)" stroke="#cbd5e1" strokeWidth="0.8" />

        {/* Ears */}
        <ellipse cx="29" cy="50" rx="3" ry="5.5" fill="url(#faceGrad)" stroke="#cbd5e1" strokeWidth="0.8" />
        <ellipse cx="71" cy="50" rx="3" ry="5.5" fill="url(#faceGrad)" stroke="#cbd5e1" strokeWidth="0.8" />

        {/* Mannequin Face Head Oval */}
        <ellipse cx="50" cy="48" rx="20.5" ry="25.5" fill="url(#faceGrad)" stroke="#cbd5e1" strokeWidth="1" />

        {/* Specular Cheek & Forehead Glint */}
        <ellipse cx="44" cy="42" rx="7" ry="9" fill="#ffffff" opacity="0.45" />

        {/* Front Hair Cut / Geometry */}
        {styleId !== 'none' && (
          <path
            d={
              styleId === 'short02' // Textured Crop
                ? 'M 28 44 C 28 26, 36 18, 50 18 C 64 18, 72 26, 72 44 C 70 36, 65 38, 60 36 C 56 40, 52 35, 48 37 C 44 34, 40 39, 36 36 C 32 38, 30 40, 28 44 Z'
                : styleId === 'short04' // Side Part
                ? 'M 28 44 C 28 26, 36 18, 50 18 C 64 18, 72 26, 72 44 C 70 34, 60 32, 50 34 C 42 36, 34 32, 28 44 Z'
                : styleId === 'short01' // Tapered Crop
                ? 'M 29 42 C 29 25, 37 20, 50 20 C 63 20, 71 25, 71 42 C 68 36, 62 36, 56 36 C 50 37, 44 35, 38 36 C 33 36, 30 40, 29 42 Z'
                : styleId === 'bob01' // Classic Bob
                ? 'M 26 48 C 26 24, 36 18, 50 18 C 64 18, 74 24, 74 48 C 74 64, 70 72, 68 76 L 62 76 C 65 68, 68 56, 66 42 C 60 38, 52 38, 48 38 C 42 38, 38 40, 34 42 C 32 56, 35 68, 38 76 L 32 76 C 30 72, 26 64, 26 48 Z'
                : styleId === 'bob02' // Wavy Bob
                ? 'M 26 50 C 24 24, 36 18, 50 18 C 64 18, 76 24, 74 50 C 76 66, 72 74, 68 78 L 62 76 C 66 66, 66 54, 64 42 C 58 38, 52 38, 48 38 C 42 38, 38 40, 36 42 C 34 54, 34 66, 38 76 L 32 78 C 28 74, 24 66, 26 50 Z'
                : styleId === 'long01' // Flowing Layers
                ? 'M 26 46 C 26 22, 36 16, 50 16 C 64 16, 74 22, 74 46 C 76 68, 78 86, 74 94 L 66 94 C 70 82, 70 66, 66 46 C 60 36, 52 36, 48 36 C 42 36, 36 38, 34 46 C 30 66, 30 82, 34 94 L 26 94 C 22 86, 24 68, 26 46 Z'
                : styleId === 'ponytail01' // Sleek Ponytail
                ? 'M 29 44 C 29 25, 38 20, 50 20 C 62 20, 71 25, 71 44 C 68 36, 60 35, 54 36 C 50 37, 44 36, 38 36 C 33 36, 30 40, 29 44 Z'
                : styleId === 'afro01' // Afro
                ? 'M 22 46 C 18 30, 28 12, 50 12 C 72 12, 82 30, 78 46 C 80 56, 76 66, 72 68 C 70 54, 70 42, 66 38 C 58 34, 52 34, 48 34 C 42 34, 36 36, 34 38 C 30 42, 30 54, 28 68 C 24 66, 20 56, 22 46 Z'
                : styleId === 'braid01' || styleId === 'cornrows' // Braids / Cornrows
                ? 'M 29 42 C 29 24, 37 19, 50 19 C 63 19, 71 24, 71 42 C 68 36, 62 34, 56 36 C 50 36, 44 35, 38 36 C 33 35, 30 38, 29 42 Z'
                : styleId === 'buzz' // Buzz
                ? 'M 30 40 C 30 26, 38 21, 50 21 C 62 21, 70 26, 70 40 C 68 34, 60 32, 50 32 C 40 32, 32 34, 30 40 Z'
                : styleId === 'receding' // Receding / Balding sides (matching row 3 col 2 in screenshot)
                ? 'M 28 42 C 28 36, 32 32, 36 34 L 34 46 Z M 72 42 C 72 36, 68 32, 64 34 L 66 46 Z'
                : 'M 30 38 C 32 26, 40 22, 50 22 C 60 22, 68 26, 70 38 Z'
            }
            fill={`url(#hairCutGrad_${styleId})`}
          />
        )}
      </svg>
    </div>
  );
};


