import React, { useState, useEffect } from 'react';
import { 
  Sparkles, 
  Heart, 
  RefreshCw,
  Palette
} from 'lucide-react';
import toast from 'react-hot-toast';
import { fashionApi } from '../services/fashionApi';
import { Outfit } from '../types/fashion';
import './OutfitStudio.css';

export const OutfitStudio: React.FC = () => {
  const [outfits, setOutfits] = useState<Outfit[]>([]);
  const [loading, setLoading] = useState(false);

  // Filters
  const [occasion, setOccasion] = useState('work_office');
  const [temperature, setTemperature] = useState(16);
  const [condition, setCondition] = useState('clear');
  const [aesthetic, setAesthetic] = useState('quiet_luxury');

  useEffect(() => {
    fetchOutfits();
  }, []);

  const fetchOutfits = async () => {
    try {
      setLoading(true);
      const res = await fashionApi.generateOutfits({
        occasion,
        temperature_celsius: temperature,
        condition,
        target_aesthetic: aesthetic,
        max_outfits: 4
      });
      setOutfits(res.outfits || []);
    } catch (err) {
      toast.error('Failed to generate outfits');
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (outfitId: string, action: 'wear_today' | 'like') => {
    try {
      await fashionApi.sendFeedback(outfitId, action);
      if (action === 'wear_today') {
        toast.success('Logged as your look for today!');
      } else {
        toast.success('Saved to your favorites.');
      }
    } catch (e) {
      toast.error('Action failed');
    }
  };

  const getColorHex = (colorName: string): string => {
    const map: Record<string, string> = {
      black: '#000000',
      white: '#ffffff',
      cream: '#fef3c7',
      beige: '#e2d4b7',
      camel: '#c19a6b',
      navy: '#1e3a8a',
      charcoal: '#334155',
      grey: '#64748b',
      blue: '#3b82f6',
      'sky blue': '#7dd3fc',
      brown: '#78350f',
      olive: '#65a30d',
      tan: '#d97706',
      terracotta: '#c2410c'
    };
    return map[colorName.toLowerCase()] || '#94a3b8';
  };

  return (
    <div className="outfit-studio-page">
      {/* Header */}
      <div className="studio-header">
        <h1 className="studio-title-h1">2D Lookbook & Outfit Canvas</h1>
        <p className="studio-subtitle">
          Rule-grounded multi-piece outfit generation • Weather & Dress-code verified
        </p>
      </div>

      {/* Context Control Bar */}
      <div className="context-control-bar">
        <div className="ctrl-item">
          <label className="ctrl-label">Occasion / Dress Code</label>
          <select 
            className="ctrl-select"
            value={occasion}
            onChange={(e) => setOccasion(e.target.value)}
          >
            <option value="casual_day">Casual Day / Weekend</option>
            <option value="work_office">Office / Business Casual</option>
            <option value="date_night">Date Night / Evening Drinks</option>
            <option value="formal_event">Formal Event / Gala</option>
            <option value="summer_vacation">Summer Resort / Vacation</option>
          </select>
        </div>

        <div className="ctrl-item">
          <label className="ctrl-label">Style Aesthetic</label>
          <select 
            className="ctrl-select"
            value={aesthetic}
            onChange={(e) => setAesthetic(e.target.value)}
          >
            <option value="quiet_luxury">Quiet Luxury / Old Money</option>
            <option value="minimalist_scandi">Minimalist Scandinavian</option>
            <option value="streetwear_tech">Elevated Streetwear</option>
            <option value="smart_casual">Smart Casual</option>
            <option value="parisian_chic">Parisian Chic</option>
          </select>
        </div>

        <div className="ctrl-item">
          <label className="ctrl-label">Weather Condition</label>
          <select 
            className="ctrl-select"
            value={condition}
            onChange={(e) => setCondition(e.target.value)}
          >
            <option value="clear">☀️ Clear / Sunny</option>
            <option value="rainy">🌧️ Rainy / Wet</option>
            <option value="chilly">🍂 Chilly / Overcast</option>
            <option value="cold">❄️ Cold / Winter</option>
          </select>
        </div>

        <div className="ctrl-item">
          <label className="ctrl-label">Temperature: {temperature}°C</label>
          <input 
            type="range" 
            min="0" 
            max="35" 
            value={temperature}
            onChange={(e) => setTemperature(Number(e.target.value))}
            style={{ accentColor: '#d4af37' }}
          />
        </div>

        <button 
          className="generate-outfits-btn"
          onClick={fetchOutfits}
          disabled={loading}
        >
          <RefreshCw size={17} className={loading ? "animate-spin" : ""} />
          Generate Ensembles
        </button>
      </div>

      {/* Lookbook Canvas Grid */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '80px', color: '#94a3b8' }}>
          <Sparkles size={32} color="#d4af37" className="animate-spin" style={{ marginBottom: '14px' }} />
          <div>Synthesizing layer combinations and color harmonies...</div>
        </div>
      ) : (
        <div className="lookbook-grid">
          {outfits.map((outfit) => (
            <div key={outfit.outfit_id} className="lookbook-card">
              <div className="lookbook-card-header">
                <div>
                  <h3 style={{ margin: 0, fontSize: '1rem', color: '#f8fafc' }}>
                    {outfit.title}
                  </h3>
                  <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                    {outfit.layer_breakdown.top.material} • {outfit.layer_breakdown.bottom.material}
                  </span>
                </div>
                <span className="outfit-score-ring">
                  {outfit.match_score}% Harmony
                </span>
              </div>

              {/* 2D Visual Layer Canvas */}
              <div className="visual-layers-canvas">
                {outfit.layer_breakdown.outerwear ? (
                  <div className="canvas-slot">
                    <img 
                      src={outfit.layer_breakdown.outerwear.image_url} 
                      alt="outerwear" 
                      className="canvas-slot-img" 
                    />
                    <span className="canvas-slot-badge">Outerwear</span>
                  </div>
                ) : (
                  <div className="canvas-slot">
                    <img 
                      src={outfit.layer_breakdown.top.image_url} 
                      alt="top" 
                      className="canvas-slot-img" 
                    />
                    <span className="canvas-slot-badge">Primary Top</span>
                  </div>
                )}

                <div className="canvas-slot">
                  <img 
                    src={outfit.layer_breakdown.bottom.image_url} 
                    alt="bottom" 
                    className="canvas-slot-img" 
                  />
                  <span className="canvas-slot-badge">Bottom</span>
                </div>

                <div className="canvas-slot">
                  <img 
                    src={outfit.layer_breakdown.footwear.image_url} 
                    alt="footwear" 
                    className="canvas-slot-img" 
                  />
                  <span className="canvas-slot-badge">Footwear</span>
                </div>

                {outfit.layer_breakdown.accessory ? (
                  <div className="canvas-slot">
                    <img 
                      src={outfit.layer_breakdown.accessory.image_url} 
                      alt="accessory" 
                      className="canvas-slot-img" 
                    />
                    <span className="canvas-slot-badge">Accessory</span>
                  </div>
                ) : (
                  <div className="canvas-slot" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b', fontSize: '0.8rem' }}>
                    <span>Minimal Hardware</span>
                  </div>
                )}
              </div>

              {/* Breakdown Details */}
              <div className="lookbook-details">
                {/* Palette Bar */}
                <div className="palette-swatches-bar">
                  <Palette size={15} color="#94a3b8" />
                  <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Palette:</span>
                  {outfit.color_palette.map((c, i) => (
                    <div 
                      key={i} 
                      className="color-dot" 
                      style={{ background: getColorHex(c) }}
                      title={c}
                    />
                  ))}
                  <span style={{ fontSize: '0.72rem', color: '#cbd5e1', marginLeft: 'auto' }}>
                    {outfit.color_harmony_explanation}
                  </span>
                </div>

                <p className="rationale-quote">
                  "{outfit.styling_rationale}"
                </p>

                {/* Affiliate Missing Piece Recommendation */}
                {outfit.missing_piece_recommendation && (
                  <div className="gap-recommendation-box" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(212,175,55,0.3)', borderRadius: '8px', padding: '10px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <img 
                      src={outfit.missing_piece_recommendation.image_url} 
                      alt="gap piece" 
                      style={{ width: '38px', height: '38px', borderRadius: '6px', objectFit: 'cover' }}
                    />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#f8fafc' }}>
                        {outfit.missing_piece_recommendation.name}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: '#d4af37' }}>
                        {outfit.missing_piece_recommendation.brand} • {outfit.missing_piece_recommendation.price}
                      </div>
                    </div>
                    <a 
                      href={outfit.missing_piece_recommendation.affiliate_url} 
                      target="_blank" 
                      rel="noreferrer" 
                      style={{ background: 'rgba(212,175,55,0.15)', color: '#d4af37', padding: '4px 8px', borderRadius: '4px', fontSize: '0.72rem', textDecoration: 'none', fontWeight: 700 }}
                    >
                      Shop
                    </a>
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="lookbook-actions">
                <button 
                  className="lookbook-btn wear-now"
                  onClick={() => handleFeedback(outfit.outfit_id, 'wear_today')}
                >
                  ✓ Wear Today
                </button>
                <button 
                  className="lookbook-btn save-look"
                  onClick={() => handleFeedback(outfit.outfit_id, 'like')}
                >
                  <Heart size={14} style={{ display: 'inline', marginRight: '4px' }} /> Save Look
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
