import React, { useState, useEffect, useRef } from 'react';
import { 
  Sliders, 
  Layers, 
  Check 
} from 'lucide-react';
import './AvatarStudio.css';

export const AvatarStudio: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  
  // Parametric Avatar state
  const [shoulderWidth, setShoulderWidth] = useState(1.1);
  const [waistTaper, setWaistTaper] = useState(0.9);
  const [torsoHeight, setTorsoHeight] = useState(1.0);
  const [skinTone] = useState('#d4a373');
  const [rotationAngle, setRotationAngle] = useState(0);
  const [lightingLevel, setLightingLevel] = useState(1.0);

  // Selected Draped Garment
  const [activeOuterwear, setActiveOuterwear] = useState(true);
  const [activeTop, setActiveTop] = useState(true);
  const [activeBottom, setActiveBottom] = useState(true);

  // Drag rotation state
  const isDraggingRef = useRef(false);
  const previousMouseXRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const render = () => {
      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);

      // Center Coordinate
      const cx = width / 2;
      const cy = height / 2 + 20;

      // Lighting gradient background
      const grad = ctx.createRadialGradient(cx, cy - 80, 20, cx, cy, 260);
      grad.addColorStop(0, `rgba(212, 175, 55, ${0.12 * lightingLevel})`);
      grad.addColorStop(1, 'rgba(15, 23, 42, 0)');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, width, height);

      // Floor Shadow
      ctx.beginPath();
      ctx.ellipse(cx, cy + 180, 90 * shoulderWidth, 20, 0, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(0, 0, 0, 0.4)';
      ctx.fill();

      ctx.save();
      ctx.translate(cx, cy);

      // Pseudo 3D perspective rotation scale
      const cosRot = Math.cos(rotationAngle);
      const rotFactor = Math.abs(cosRot);

      // --- Draw Head & Neck ---
      ctx.fillStyle = skinTone;
      // Neck
      ctx.fillRect(-12 * rotFactor, -155 * torsoHeight, 24 * rotFactor, 30);

      // Head
      ctx.beginPath();
      ctx.ellipse(0, -180 * torsoHeight, 28 * (0.8 + 0.2 * rotFactor), 36, 0, 0, Math.PI * 2);
      ctx.fill();

      // Hair feature
      ctx.fillStyle = '#2b2118';
      ctx.beginPath();
      ctx.arc(0, -192 * torsoHeight, 28, Math.PI, Math.PI * 2);
      ctx.fill();

      // --- Draw Torso / Top Layer ---
      const shoulderX = 65 * shoulderWidth * (0.7 + 0.3 * rotFactor);
      const waistX = 42 * waistTaper * (0.7 + 0.3 * rotFactor);

      if (activeTop) {
        ctx.fillStyle = '#fef3c7'; // Cream Merino Knit
      } else {
        ctx.fillStyle = skinTone;
      }

      ctx.beginPath();
      ctx.moveTo(-shoulderX, -130 * torsoHeight);
      ctx.lineTo(shoulderX, -130 * torsoHeight);
      ctx.lineTo(waistX, -20 * torsoHeight);
      ctx.lineTo(-waistX, -20 * torsoHeight);
      ctx.closePath();
      ctx.fill();
      ctx.strokeStyle = 'rgba(0,0,0,0.15)';
      ctx.stroke();

      // Arms
      ctx.lineWidth = 18;
      ctx.strokeStyle = activeTop ? '#fef3c7' : skinTone;
      ctx.lineCap = 'round';
      // Left Arm
      ctx.beginPath();
      ctx.moveTo(-shoulderX, -125 * torsoHeight);
      ctx.lineTo(-shoulderX - (15 * rotFactor), 10);
      ctx.stroke();
      // Right Arm
      ctx.beginPath();
      ctx.moveTo(shoulderX, -125 * torsoHeight);
      ctx.lineTo(shoulderX + (15 * rotFactor), 10);
      ctx.stroke();

      // --- Draw Outerwear Coat (if active) ---
      if (activeOuterwear) {
        ctx.fillStyle = 'rgba(193, 154, 107, 0.95)'; // Camel Overcoat
        ctx.beginPath();
        ctx.moveTo(-shoulderX - 10, -135 * torsoHeight);
        ctx.lineTo(shoulderX + 10, -135 * torsoHeight);
        ctx.lineTo(shoulderX + 25, 70);
        ctx.lineTo(-shoulderX - 25, 70);
        ctx.closePath();
        ctx.fill();

        // Lapels
        ctx.strokeStyle = '#8c6d48';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // --- Draw Bottoms / Trousers ---
      const hipY = -20 * torsoHeight;
      const ankleY = 160;
      ctx.fillStyle = activeBottom ? '#334155' : skinTone; // Charcoal Pleated Trousers

      // Left Leg
      ctx.beginPath();
      ctx.moveTo(-waistX, hipY);
      ctx.lineTo(-6, hipY + 15);
      ctx.lineTo(-14, ankleY);
      ctx.lineTo(-38, ankleY);
      ctx.closePath();
      ctx.fill();

      // Right Leg
      ctx.beginPath();
      ctx.moveTo(waistX, hipY);
      ctx.lineTo(6, hipY + 15);
      ctx.lineTo(14, ankleY);
      ctx.lineTo(38, ankleY);
      ctx.closePath();
      ctx.fill();

      // --- Shoes ---
      ctx.fillStyle = '#ffffff'; // White Leather Low-Tops
      ctx.beginPath();
      ctx.ellipse(-26, ankleY + 8, 16, 8, 0, 0, Math.PI * 2);
      ctx.ellipse(26, ankleY + 8, 16, 8, 0, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();
    };

    render();
  }, [shoulderWidth, waistTaper, torsoHeight, skinTone, rotationAngle, lightingLevel, activeOuterwear, activeTop, activeBottom]);

  const handleMouseDown = (e: React.MouseEvent) => {
    isDraggingRef.current = true;
    previousMouseXRef.current = e.clientX;
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDraggingRef.current) return;
    const deltaX = e.clientX - previousMouseXRef.current;
    setRotationAngle(prev => prev + deltaX * 0.02);
    previousMouseXRef.current = e.clientX;
  };

  const handleMouseUp = () => {
    isDraggingRef.current = false;
  };

  return (
    <div className="avatar-studio-page">
      <div className="avatar-header">
        <h1 className="avatar-title-h1">3D Parametric Avatar & Try-On Studio</h1>
        <p style={{ color: '#94a3b8', margin: 0, fontSize: '0.95rem' }}>
          Interactive digital twin viewport • Parametric body calibration • Live garment drape testing
        </p>
      </div>

      <div className="avatar-stage-container">
        {/* 3D Viewport */}
        <div 
          className="avatar-3d-viewport"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          <div className="canvas-floating-controls">
            <span className="canvas-ctrl-tag">YORVYN 3D TWIN ENGINE</span>
          </div>

          <canvas 
            ref={canvasRef} 
            width={720} 
            height={580} 
            className="avatar-canvas"
          />

          <div className="canvas-hint">
            ↔ Click and drag horizontally to rotate avatar 360°
          </div>
        </div>

        {/* Parametric Controls */}
        <div className="avatar-controls-panel">
          <div>
            <h3 className="panel-title">
              <Sliders size={18} color="#d4af37" /> Parametric Proportions
            </h3>
            
            <div className="parametric-slider-row">
              <div className="slider-header">
                <span>Shoulder Breadth</span>
                <span>{shoulderWidth.toFixed(2)}x</span>
              </div>
              <input 
                type="range" 
                min="0.8" 
                max="1.4" 
                step="0.05"
                value={shoulderWidth}
                onChange={e => setShoulderWidth(Number(e.target.value))}
                className="slider-input"
              />
            </div>

            <div className="parametric-slider-row">
              <div className="slider-header">
                <span>Waist Taper</span>
                <span>{waistTaper.toFixed(2)}x</span>
              </div>
              <input 
                type="range" 
                min="0.7" 
                max="1.3" 
                step="0.05"
                value={waistTaper}
                onChange={e => setWaistTaper(Number(e.target.value))}
                className="slider-input"
              />
            </div>

            <div className="parametric-slider-row">
              <div className="slider-header">
                <span>Torso Scale</span>
                <span>{torsoHeight.toFixed(2)}x</span>
              </div>
              <input 
                type="range" 
                min="0.85" 
                max="1.15" 
                step="0.02"
                value={torsoHeight}
                onChange={e => setTorsoHeight(Number(e.target.value))}
                className="slider-input"
              />
            </div>

            <div className="parametric-slider-row">
              <div className="slider-header">
                <span>Studio Key Lighting</span>
                <span>{lightingLevel.toFixed(1)}x</span>
              </div>
              <input 
                type="range" 
                min="0.5" 
                max="1.8" 
                step="0.1"
                value={lightingLevel}
                onChange={e => setLightingLevel(Number(e.target.value))}
                className="slider-input"
              />
            </div>
          </div>

          {/* Garment Fitting Layers */}
          <div>
            <h3 className="panel-title">
              <Layers size={18} color="#d4af37" /> Draped Garment Layers
            </h3>

            <div className="garment-select-list">
              <div 
                className={`garment-select-item ${activeOuterwear ? 'active' : ''}`}
                onClick={() => setActiveOuterwear(!activeOuterwear)}
              >
                <img 
                  src="https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?auto=format&fit=crop&w=150&q=80" 
                  alt="coat" 
                  className="select-item-img" 
                />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f8fafc' }}>Double-Breasted Overcoat</div>
                  <div style={{ fontSize: '0.72rem', color: '#d4af37' }}>Outerwear • Camel Wool</div>
                </div>
                {activeOuterwear && <Check size={16} color="#d4af37" />}
              </div>

              <div 
                className={`garment-select-item ${activeTop ? 'active' : ''}`}
                onClick={() => setActiveTop(!activeTop)}
              >
                <img 
                  src="https://images.unsplash.com/photo-1576566588028-4147f3842f27?auto=format&fit=crop&w=150&q=80" 
                  alt="knit" 
                  className="select-item-img" 
                />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f8fafc' }}>Merino Wool Crewneck</div>
                  <div style={{ fontSize: '0.72rem', color: '#d4af37' }}>Top • Cream Knitwear</div>
                </div>
                {activeTop && <Check size={16} color="#d4af37" />}
              </div>

              <div 
                className={`garment-select-item ${activeBottom ? 'active' : ''}`}
                onClick={() => setActiveBottom(!activeBottom)}
              >
                <img 
                  src="https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=150&q=80" 
                  alt="pants" 
                  className="select-item-img" 
                />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f8fafc' }}>Pleated Tailored Trousers</div>
                  <div style={{ fontSize: '0.72rem', color: '#d4af37' }}>Bottom • Charcoal Wool</div>
                </div>
                {activeBottom && <Check size={16} color="#d4af37" />}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
