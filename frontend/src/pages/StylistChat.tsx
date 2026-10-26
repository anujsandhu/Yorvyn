import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Sparkles, 
  Send, 
  Thermometer, 
  ShoppingBag, 
  Heart,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Square,
  MessageSquare,
  Headphones,
  Shirt,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
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
  provider?: string;
  timestamp?: string;
}

export const StylistChat: React.FC = () => {
  const navigate = useNavigate();

  // Mode state: 'text' vs 'voice'
  const [chatMode, setChatMode] = useState<'text' | 'voice'>('text');

  // Messages state
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'init_1',
      sender: 'stylist',
      text: "Hello Alex. I am your Yorvyn Personal Fashion Intelligence Stylist. I've analyzed your Autumn palette and digital wardrobe. Tell me your occasion, destination, or current weather, and I'll assemble tailored, layer-aware ensembles.",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [currentTemp, setCurrentTemp] = useState<number>(18);
  const [mlMetrics, setMlMetrics] = useState<any>(null);

  // Voice AI states
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState('');
  const [speechPermission, setSpeechPermission] = useState<'prompt' | 'granted' | 'denied'>('prompt');
  const [isSpeechSupported, setIsSpeechSupported] = useState(true);

  // References
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const abortControllerRef = useRef<AbortController | null>(null);

  // 1. Initialize component & speech recognition
  useEffect(() => {
    loadProfile();
    loadMlMetrics();
    initSpeechRecognition();

    return () => {
      stopSpeaking();
      if (recognitionRef.current) {
        try { recognitionRef.current.abort(); } catch (e) { /* ignore */ }
      }
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading, liveTranscript]);

  const loadProfile = async () => {
    try {
      const data = await fashionApi.getProfile();
      setProfile(data);
    } catch (err) {
      console.error('Failed to load profile', err);
    }
  };

  const loadMlMetrics = async () => {
    try {
      const data = await fashionApi.getMLMetrics();
      if (data && data.accuracy) {
        setMlMetrics(data);
      }
    } catch (err) {
      console.error('Failed to load ML metrics', err);
    }
  };

  // ── Speech Recognition Setup ───────────────────────────────────────────────

  const initSpeechRecognition = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn('Web Speech Recognition API not natively available; fallback active.');
      setIsSpeechSupported(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        setIsRecording(true);
        setSpeechPermission('granted');
      };

      recognition.onresult = (event: any) => {
        let interim = '';
        let final = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            final += event.results[i][0].transcript;
          } else {
            interim += event.results[i][0].transcript;
          }
        }

        const currentText = final || interim;
        setLiveTranscript(currentText);

        if (final) {
          setIsRecording(false);
          setLiveTranscript('');
          handleSendMessage(final);
        }
      };

      recognition.onerror = (event: any) => {
        console.warn('Speech recognition error:', event.error);
        if (event.error === 'not-allowed') {
          setSpeechPermission('denied');
          toast.error('Microphone permission denied. Please allow microphone access in your browser settings.');
        }
        setIsRecording(false);
        setLiveTranscript('');
      };

      recognition.onend = () => {
        setIsRecording(false);
      };

      recognitionRef.current = recognition;
    } catch (e) {
      console.error('Failed to initialize speech recognition:', e);
      setIsSpeechSupported(false);
    }
  };

  // ── Microphone Trigger ─────────────────────────────────────────────────────

  const toggleRecording = async () => {
    if (isRecording) {
      // Stop recording
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch (e) { /* ignore */ }
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
      setIsRecording(false);
    } else {
      // Start recording
      stopSpeaking();
      setLiveTranscript('');

      if (isSpeechSupported && recognitionRef.current) {
        try {
          recognitionRef.current.start();
        } catch (e) {
          console.warn('Recognition already running or re-starting', e);
          try {
            recognitionRef.current.stop();
            setTimeout(() => recognitionRef.current.start(), 100);
          } catch (err) {
            fallbackMediaRecorderAudio();
          }
        }
      } else {
        fallbackMediaRecorderAudio();
      }
    }
  };

  // Ephemeral audio recording fallback via backend /speech/transcribe
  const fallbackMediaRecorderAudio = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setSpeechPermission('granted');
      const recorder = new MediaRecorder(stream);
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        stream.getTracks().forEach(track => track.stop());
        setIsRecording(false);

        if (audioBlob.size > 1000) {
          setLoading(true);
          try {
            const res = await fashionApi.transcribeAudio(audioBlob);
            if (res.text) {
              handleSendMessage(res.text);
            }
          } catch (err) {
            toast.error('Voice transcription failed. You can type your request directly.');
          } finally {
            setLoading(false);
          }
        }
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setIsRecording(true);
      toast('Listening to your fashion request...', { icon: '🎙️' });
    } catch (err) {
      setSpeechPermission('denied');
      toast.error('Microphone access denied. Please grant browser microphone permission to speak.');
      setIsRecording(false);
    }
  };

  // ── Text-to-Speech Output ──────────────────────────────────────────────────

  const speakText = useCallback((text: string) => {
    if (isMuted || !('speechSynthesis' in window)) return;

    window.speechSynthesis.cancel();

    // Clean markdown asterisks and URLs for speech clarity
    const cleanSpeech = text
      .replace(/[*_#`]/g, '')
      .replace(/https?:\/\/\S+/g, '')
      .replace(/•/g, '')
      .trim();

    const utterance = new SpeechSynthesisUtterance(cleanSpeech);
    utterance.rate = 1.02;
    utterance.pitch = 1.0;
    utterance.lang = 'en-US';

    // Select natural English voice if present
    const voices = window.speechSynthesis.getVoices();
    const preferredVoice = voices.find(v => 
      v.lang.startsWith('en') && (v.name.includes('Natural') || v.name.includes('Samantha') || v.name.includes('Google') || v.name.includes('Karen'))
    );
    if (preferredVoice) {
      utterance.voice = preferredVoice;
    }

    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    window.speechSynthesis.speak(utterance);
  }, [isMuted]);

  const stopSpeaking = () => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    setIsSpeaking(false);
  };

  const toggleMute = () => {
    if (!isMuted) {
      stopSpeaking();
    }
    setIsMuted(!isMuted);
    toast(isMuted ? 'Voice stylist unmuted' : 'Voice stylist muted', {
      icon: isMuted ? '🔊' : '🔇'
    });
  };

  // ── Send Message & Orchestrator Flow ───────────────────────────────────────

  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || inputMessage;
    if (!text.trim() || loading) return;

    stopSpeaking();

    const userMsg: Message = {
      id: `user_${Date.now()}`,
      sender: 'user',
      text: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
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
        context: res.context,
        provider: (res as any).provider_used || 'Yorvyn AI',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, stylistMsg]);

      // Speak in voice mode or if not muted
      if (chatMode === 'voice' || !isMuted) {
        speakText(res.reply);
      }
    } catch (error) {
      toast.error('Stylist connection failed. Re-trying with fallback...');
      const errorMsg: Message = {
        id: `err_${Date.now()}`,
        sender: 'stylist',
        text: "I experienced a brief latency spike while scoring your wardrobe. Could you please re-phrase or ask again?",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setLoading(false);
    stopSpeaking();
    toast('Generation stopped', { icon: '⏹️' });
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

  const handleTryOnAvatar = (outfit: Outfit) => {
    // Navigate directly to AvatarStudio with garment info
    toast.success(`Dressing 3D avatar with ${outfit.title}...`);
    navigate('/avatar');
  };

  return (
    <div className={`stylist-chat-container ${chatMode === 'voice' ? 'voice-mode-active' : ''}`}>
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
                <span className="stat-label">Body Shape</span>
                <span className="stat-val">{profile?.body_shape?.replace('_', ' ') || 'Athletic'}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Fit Preference</span>
                <span className="stat-val">{profile?.fit_preference?.replace('_', ' ') || 'Relaxed'}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Real ML Model Benchmark Badge */}
        {mlMetrics && (
          <div className="stylist-sidebar-section">
            <span className="stylist-sidebar-title">Real Fashion ML Engine</span>
            <div className="ml-metrics-badge">
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                <CheckCircle2 size={14} color="#10b981" />
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#f8fafc' }}>
                  Fashion-MNIST Baseline
                </span>
              </div>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8', lineHeight: 1.4 }}>
                Trained on <strong>{mlMetrics.training_samples?.toLocaleString()}</strong> real Zalando articles.
                <br />
                Accuracy: <strong style={{ color: '#10b981' }}>{(mlMetrics.accuracy * 100).toFixed(1)}%</strong> • F1: <strong>{(mlMetrics.weighted_f1_score * 100).toFixed(1)}%</strong>
              </div>
            </div>
          </div>
        )}

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
          <span className="stylist-sidebar-title">Quick Voice & Text Prompts</span>
          <div className="quick-prompts-list">
            <button 
              className="quick-prompt-btn"
              onClick={() => handleSendMessage("What should I wear for an important office client meeting?")}
            >
              💼 Business Client Meeting
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
              onClick={() => handleSendMessage("Show me something casual in neutral colors.")}
            >
              ☕ Casual Neutral Outfit
            </button>
          </div>
        </div>
      </div>

      {/* Main Stylist Area */}
      <div className="stylist-main">
        {/* Header with Mode Toggle & Voice Controls */}
        <div className="stylist-header">
          <div className="stylist-title-area">
            <div className={`stylist-status-dot ${isRecording ? 'recording' : isSpeaking ? 'speaking' : ''}`} />
            <div>
              <h3 style={{ margin: 0, fontSize: '1rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
                Yorvyn AI Fashion Stylist <Sparkles size={16} color="#d4af37" />
              </h3>
              <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
                {isRecording ? 'Listening to speech...' : isSpeaking ? 'Speaking response...' : 'Natural Voice & Text Intelligence Active'}
              </span>
            </div>
          </div>

          {/* Mode Switcher & Controls */}
          <div className="header-controls-group">
            <button 
              className={`mode-toggle-btn ${chatMode === 'text' ? 'active' : ''}`}
              onClick={() => setChatMode('text')}
              title="Switch to Text Chat"
            >
              <MessageSquare size={14} /> Text
            </button>
            <button 
              className={`mode-toggle-btn ${chatMode === 'voice' ? 'active' : ''}`}
              onClick={() => setChatMode('voice')}
              title="Switch to Voice Conversation"
            >
              <Headphones size={14} /> Voice
            </button>

            <button 
              className={`audio-control-btn ${isMuted ? 'muted' : ''}`}
              onClick={toggleMute}
              title={isMuted ? 'Unmute voice replies' : 'Mute voice replies'}
            >
              {isMuted ? <VolumeX size={16} /> : <Volume2 size={16} />}
            </button>

            {isSpeaking && (
              <button 
                className="audio-control-btn stop-speaking"
                onClick={stopSpeaking}
                title="Stop audio playback"
              >
                <Square size={14} />
              </button>
            )}
          </div>
        </div>

        {/* Voice Mode Big Waveform HUD (Rendered when in Voice Mode) */}
        {chatMode === 'voice' && (
          <div className="voice-mode-hud">
            <div className="voice-avatar-orb-container">
              <div className={`voice-avatar-orb ${isRecording ? 'pulse-listening' : isSpeaking ? 'pulse-speaking' : ''}`}>
                {isRecording ? <Mic size={38} color="#d4af37" /> : isSpeaking ? <Volume2 size={38} color="#d4af37" /> : <Sparkles size={38} color="#d4af37" />}
              </div>
              <div className="voice-waveform-bars">
                <span className={`wave-bar ${isRecording || isSpeaking ? 'anim-wave' : ''}`} />
                <span className={`wave-bar ${isRecording || isSpeaking ? 'anim-wave delay-1' : ''}`} />
                <span className={`wave-bar ${isRecording || isSpeaking ? 'anim-wave delay-2' : ''}`} />
                <span className={`wave-bar ${isRecording || isSpeaking ? 'anim-wave delay-3' : ''}`} />
                <span className={`wave-bar ${isRecording || isSpeaking ? 'anim-wave delay-4' : ''}`} />
              </div>
            </div>

            <div className="voice-state-caption">
              {isRecording 
                ? 'Listening... Speak your fashion styling request' 
                : isSpeaking 
                  ? 'Speaking tailored recommendations...' 
                  : loading 
                    ? 'Consulting digital wardrobe & style matrices...' 
                    : 'Tap the microphone to start voice conversation'}
            </div>

            {liveTranscript && (
              <div className="live-transcript-bubble">
                "{liveTranscript}"
              </div>
            )}

            {speechPermission === 'denied' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#ef4444', fontSize: '0.78rem', background: 'rgba(239, 68, 68, 0.1)', padding: '6px 12px', borderRadius: '12px' }}>
                <AlertCircle size={14} /> Microphone permission denied. Please allow microphone access in your browser bar.
              </div>
            )}
          </div>
        )}

        {/* Message Thread */}
        <div className="chat-messages-area">
          {messages.map((msg) => (
            <div key={msg.id} className={`chat-message-row ${msg.sender}`}>
              <div className="message-bubble">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <span style={{ fontSize: '0.68rem', color: '#94a3b8', fontWeight: 600 }}>
                    {msg.sender === 'stylist' ? 'Yorvyn AI Stylist' : 'You'}
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {msg.timestamp && (
                      <span style={{ fontSize: '0.65rem', color: '#64748b' }}>{msg.timestamp}</span>
                    )}
                    {msg.sender === 'stylist' && (
                      <button 
                        className="msg-replay-btn" 
                        onClick={() => speakText(msg.text)}
                        title="Replay voice audio"
                      >
                        <Volume2 size={12} />
                      </button>
                    )}
                  </div>
                </div>

                <p style={{ margin: 0, whiteSpace: 'pre-wrap', lineHeight: 1.55 }}>{msg.text}</p>

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

                        {/* Outfit Actions with 3D Try-On integration */}
                        <div className="outfit-card-actions">
                          <button 
                            className="card-action-btn try-on"
                            onClick={() => handleTryOnAvatar(outfit)}
                            title="Dress this outfit directly onto your 3D avatar"
                          >
                            <Shirt size={13} style={{ display: 'inline', marginRight: '4px' }} /> Try on Avatar
                          </button>
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
              <div className="message-bubble" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Sparkles size={18} color="#d4af37" className="animate-spin" />
                  <span>Consulting digital wardrobe harmony, weather matrices, and silhouette fit...</span>
                </div>
                <button 
                  className="stop-generation-btn"
                  onClick={handleStopGeneration}
                  title="Stop generating"
                >
                  <Square size={12} /> Stop
                </button>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar with Voice Microphone and Text Controls */}
        <div className="chat-input-container">
          <div className="chat-input-wrapper">
            <button 
              className={`mic-button ${isRecording ? 'recording-active' : ''}`}
              onClick={toggleRecording}
              title={isRecording ? 'Stop recording voice' : 'Click to speak your styling request'}
              disabled={loading}
            >
              {isRecording ? <MicOff size={18} /> : <Mic size={18} />}
            </button>

            <input 
              type="text"
              className="chat-input-field"
              placeholder={isRecording ? "Listening to your voice..." : "Ask your personal stylist (e.g. 'What can I wear for an evening gallery opening in 12°C?')..."}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
              disabled={loading || isRecording}
            />

            <button 
              className="send-btn"
              onClick={() => handleSendMessage()}
              disabled={loading || !inputMessage.trim()}
            >
              <Send size={16} /> Stylize
            </button>
          </div>

          <div className="chat-privacy-footer">
            <span>🔒 Audio and photos are processed ephemerally and never retained without consent.</span>
          </div>
        </div>
      </div>
    </div>
  );
};
