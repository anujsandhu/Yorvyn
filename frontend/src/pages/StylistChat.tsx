import React, { useState, useEffect, useRef } from 'react';
import { 
  Sparkles, 
  Send, 
  Thermometer, 
  ShoppingBag, 
  Heart
} from 'lucide-react';
import toast from 'react-hot-toast';
import { fashionApi } from '../services/fashionApi';
import { Outfit, UserProfile } from '../types/fashion';
import './StylistChat.css';

interface Message {
  id: string;
  sender: 'user' | 'stylist';
  text: string;
  outfits?: Outfit[];
  context?: any;
}

export const StylistChat: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'init_1',
      sender: 'stylist',
      text: "Hello Alex. I am your Yorvyn Personal Fashion Intelligence Stylist. I've analyzed your Autumn palette and digital wardrobe. Tell me your occasion, destination, or current weather, and I'll assemble tailored, layer-aware ensembles."
    }
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [currentTemp, setCurrentTemp] = useState<number>(18);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadProfile();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const loadProfile = async () => {
    try {
      const data = await fashionApi.getProfile();
      setProfile(data);
    } catch (err) {
      console.error('Failed to load profile', err);
    }
  };

  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || inputMessage;
    if (!text.trim() || loading) return;

    const userMsg: Message = {
      id: `user_${Date.now()}`,
      sender: 'user',
      text: text
    };

    setMessages(prev => [...prev, userMsg]);
    setInputMessage('');
    setLoading(true);

    try {
      const res = await fashionApi.chatWithStylist(text, currentTemp);
      const stylistMsg: Message = {
        id: `stylist_${Date.now()}`,
        sender: 'stylist',
        text: res.reply,
        outfits: res.outfits,
        context: res.context
      };
      setMessages(prev => [...prev, stylistMsg]);
    } catch (error) {
      toast.error('Stylist connection failed. Re-trying...');
      const errorMsg: Message = {
        id: `err_${Date.now()}`,
        sender: 'stylist',
        text: "I encountered a brief latency spike while scoring your wardrobe. Could you please re-phrase or ask again?"
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (outfitId: string, action: 'wear_today' | 'like') => {
    try {
      await fashionApi.sendFeedback(outfitId, action);
      if (action === 'wear_today') {
        toast.success('Logged as outfit of the day! Preference models updated.');
      } else if (action === 'like') {
        toast.success('Saved to your style preferences.');
      }
    } catch (e) {
      toast.error('Feedback recording failed');
    }
  };

  return (
    <div className="stylist-chat-container">
      {/* Left Sidebar - Personal Identity & Context */}
      <div className="stylist-sidebar">
        <div className="stylist-sidebar-section">
          <span className="stylist-sidebar-title">Digital Identity</span>
          <div className="profile-badge-card">
            <div className="profile-badge-header">
              <div className="profile-avatar-pill">
                {profile ? profile.name.charAt(0) : 'A'}
              </div>
              <div>
                <h4 style={{ margin: 0, fontSize: '0.9rem', color: '#f8fafc' }}>{profile?.name || 'Alex'}</h4>
                <span style={{ fontSize: '0.72rem', color: '#d4af37' }}>Autumn • Warm Bright</span>
              </div>
            </div>
            <div className="profile-stats-grid">
              <div className="stat-item">
                <span className="stat-label">Body Geometry</span>
                <span className="stat-val">{profile?.body_shape?.replace('_', ' ') || 'Athletic'}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Fit Preference</span>
                <span className="stat-val">{profile?.fit_preference?.replace('_', ' ') || 'Relaxed'}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="stylist-sidebar-section">
          <span className="stylist-sidebar-title">Simulate Weather Context</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(255,255,255,0.04)', padding: '10px', borderRadius: '8px' }}>
            <Thermometer size={18} color="#d4af37" />
            <input 
              type="range" 
              min="0" 
              max="35" 
              value={currentTemp}
              onChange={(e) => setCurrentTemp(Number(e.target.value))}
              style={{ flex: 1, accentColor: '#d4af37' }}
            />
            <span style={{ fontSize: '0.85rem', fontWeight: 600, minWidth: '40px' }}>{currentTemp}°C</span>
          </div>
        </div>

        <div className="stylist-sidebar-section">
          <span className="stylist-sidebar-title">Quick Styling Prompts</span>
          <div className="quick-prompts-list">
            <button 
              className="quick-prompt-btn"
              onClick={() => handleSendMessage("What should I wear for an important office client meeting?")}
            >
              💼 Business / Client Meeting
            </button>
            <button 
              className="quick-prompt-btn"
              onClick={() => handleSendMessage("Recommend an understated Quiet Luxury date night look.")}
            >
              🍸 Quiet Luxury Date Night
            </button>
            <button 
              className="quick-prompt-btn"
              onClick={() => handleSendMessage("Layered outfit for a chilly 8°C rainy morning")}
            >
              🌧️ 8°C Chilly & Rainy Morning
            </button>
            <button 
              className="quick-prompt-btn"
              onClick={() => handleSendMessage("Relaxed weekend minimalist coffee run")}
            >
              ☕ Minimalist Coffee Run
            </button>
          </div>
        </div>
      </div>

      {/* Main Chat Interface */}
      <div className="stylist-main">
        <div className="stylist-header">
          <div className="stylist-title-area">
            <div className="stylist-status-dot" />
            <div>
              <h3 style={{ margin: 0, fontSize: '1rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
                Yorvyn Fashion Intelligence <Sparkles size={16} color="#d4af37" />
              </h3>
              <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                Multi-objective outfit scoring • Personal Knowledge Graph Active
              </span>
            </div>
          </div>
        </div>

        {/* Message Thread */}
        <div className="chat-messages-area">
          {messages.map((msg) => (
            <div key={msg.id} className={`chat-message-row ${msg.sender}`}>
              <div className="message-bubble">
                <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{msg.text}</p>

                {/* Render Outfit Deck if attached */}
                {msg.outfits && msg.outfits.length > 0 && (
                  <div className="outfit-deck">
                    {msg.outfits.map((outfit) => (
                      <div key={outfit.outfit_id} className="outfit-card">
                        <div className="outfit-card-header">
                          <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f8fafc' }}>
                            {outfit.title}
                          </span>
                          <span className="match-badge">
                            {outfit.match_score}% Match
                          </span>
                        </div>

                        {/* Layer Breakdown */}
                        <div className="layer-items-stack">
                          {outfit.layer_breakdown.outerwear && (
                            <div className="layer-item-row">
                              <img 
                                src={outfit.layer_breakdown.outerwear.image_url} 
                                alt="outerwear" 
                                className="layer-item-thumb" 
                              />
                              <div className="layer-item-info">
                                <span className="layer-item-name">{outfit.layer_breakdown.outerwear.name}</span>
                                <span className="layer-item-tag">{outfit.layer_breakdown.outerwear.color} • Outerwear</span>
                              </div>
                            </div>
                          )}

                          <div className="layer-item-row">
                            <img 
                              src={outfit.layer_breakdown.top.image_url} 
                              alt="top" 
                              className="layer-item-thumb" 
                            />
                            <div className="layer-item-info">
                              <span className="layer-item-name">{outfit.layer_breakdown.top.name}</span>
                              <span className="layer-item-tag">{outfit.layer_breakdown.top.color} • Top</span>
                            </div>
                          </div>

                          <div className="layer-item-row">
                            <img 
                              src={outfit.layer_breakdown.bottom.image_url} 
                              alt="bottom" 
                              className="layer-item-thumb" 
                            />
                            <div className="layer-item-info">
                              <span className="layer-item-name">{outfit.layer_breakdown.bottom.name}</span>
                              <span className="layer-item-tag">{outfit.layer_breakdown.bottom.color} • Bottom</span>
                            </div>
                          </div>

                          <div className="layer-item-row">
                            <img 
                              src={outfit.layer_breakdown.footwear.image_url} 
                              alt="footwear" 
                              className="layer-item-thumb" 
                            />
                            <div className="layer-item-info">
                              <span className="layer-item-name">{outfit.layer_breakdown.footwear.name}</span>
                              <span className="layer-item-tag">{outfit.layer_breakdown.footwear.color} • Footwear</span>
                            </div>
                          </div>
                        </div>

                        {/* Commerce Gap Recommendation */}
                        {outfit.missing_piece_recommendation && (
                          <div className="gap-recommendation-box">
                            <ShoppingBag size={16} color="#d4af37" />
                            <div style={{ flex: 1 }}>
                              <span className="gap-rec-text">
                                Complete look: <strong>{outfit.missing_piece_recommendation.name}</strong> ({outfit.missing_piece_recommendation.price})
                              </span>
                            </div>
                            <a 
                              href={outfit.missing_piece_recommendation.affiliate_url} 
                              target="_blank" 
                              rel="noreferrer" 
                              style={{ fontSize: '0.7rem', color: '#d4af37', textDecoration: 'underline' }}
                            >
                              Shop
                            </a>
                          </div>
                        )}

                        <div className="outfit-card-actions">
                          <button 
                            className="card-action-btn wear"
                            onClick={() => handleFeedback(outfit.outfit_id, 'wear_today')}
                          >
                            ✓ Wear Today
                          </button>
                          <button 
                            className="card-action-btn"
                            onClick={() => handleFeedback(outfit.outfit_id, 'like')}
                          >
                            <Heart size={13} style={{ display: 'inline', marginRight: '4px' }} /> Save
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="chat-message-row stylist">
              <div className="message-bubble" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Sparkles size={18} color="#d4af37" className="animate-spin" />
                <span>Evaluating digital wardrobe harmony, weather matrices, and silhouette fit...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="chat-input-container">
          <div className="chat-input-wrapper">
            <input 
              type="text"
              className="chat-input-field"
              placeholder="Ask your personal stylist (e.g. 'What can I wear for an evening gallery opening in 12°C?')..."
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
              disabled={loading}
            />
            <button 
              className="send-btn"
              onClick={() => handleSendMessage()}
              disabled={loading || !inputMessage.trim()}
            >
              <Send size={16} /> Stylize
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
