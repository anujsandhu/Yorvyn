import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Sparkle, 
  PaperPlaneTilt, 
  ThermometerSimple, 
  ShoppingBag, 
  Heart,
  Microphone,
  MicrophoneSlash,
  SpeakerHigh,
  SpeakerSimpleSlash,
  Stop,
  ChatCircleText,
  Headphones,
  TShirt,
  CheckCircle,
  WarningCircle,
  SidebarSimple,
  Clock,
  ThumbsUp,
  ThumbsDown
} from '../components/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { fashionApi } from '../services/fashionApi';
import {
  intelligenceApi,
  type ExternalWebReference,
  type KnowledgeHint,
  type OutfitRecommendationResponse,
} from '../services/intelligenceApi';
import { aiSessionService, AISession, AIMessage } from '../services/aiSessionService';
import { learningService } from '../services/learningService';
import { SessionSidebar } from '../components/ai/SessionSidebar';
import { SearchHistoryModal } from '../components/ai/SearchHistoryModal';
import { Outfit, UserProfile } from '../types/fashion';
import { avatarPerformanceController } from '../engine/humanAvatar';
import './StylistChat.css';

interface Message {
  id: string;
  sender: 'user' | 'stylist';
  text: string;
  outfits?: Outfit[];
  context?: any;
  provider?: string;
  timestamp?: string;
  toolCalls?: Array<{ tool_name: string; success: boolean }>;
}

export const StylistChat: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const urlSessionId = searchParams.get('session');

  // Mode state: 'text' vs 'voice'
  const [chatMode, setChatMode] = useState<'text' | 'voice'>('text');

  // Persistent AI Session States
  const [activeSessionId, setActiveSessionId] = useState<string | null>(urlSessionId || null);
  const [activeSession, setActiveSession] = useState<AISession | null>(null);
  const [isSessionSidebarOpen, setIsSessionSidebarOpen] = useState(true);
  const [isSearchHistoryOpen, setIsSearchHistoryOpen] = useState(false);
  const [messageFeedback, setMessageFeedback] = useState<Record<string, 'positive' | 'negative'>>({});

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
  const [fashionDNA, setFashionDNA] = useState<any>(null);
  const [currentTemp, setCurrentTemp] = useState<number>(18);
  const [mlMetrics, setMlMetrics] = useState<any>(null);
  const [knowledgeHints, setKnowledgeHints] = useState<KnowledgeHint[]>([]);
  const [outfitInsights, setOutfitInsights] = useState<OutfitRecommendationResponse | null>(null);
  const [externalTrends, setExternalTrends] = useState<ExternalWebReference[]>([]);

  // Voice AI states
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState('');
  const [speechPermission, setSpeechPermission] = useState<'prompt' | 'granted' | 'denied'>('prompt');
  const [isSpeechSupported, setIsSpeechSupported] = useState(true);

  // References
  const conversationIdRef = useRef<string>(`conv_${Date.now()}`);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const abortControllerRef = useRef<AbortController | null>(null);

  // 1. Initialize component & speech recognition
  useEffect(() => {
    loadProfile();
    loadFashionDNA();
    loadMlMetrics();
    intelligenceApi.queryFashionKnowledge('garment ease construction weave fit', 2).then(setKnowledgeHints).catch(() => {});
    intelligenceApi.getOutfitRecommendations({ occasion: 'smart_casual', maxOutfits: 2 }).then(setOutfitInsights).catch(() => {});
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

  const loadFashionDNA = async () => {
    try {
      const res = await fashionApi.getFashionDNA();
      if (res && res.fashion_dna) {
        setFashionDNA(res.fashion_dna);
      }
    } catch (err) {
      console.warn('Fashion DNA not yet initialized; using baseline.');
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

  // ── Persistent AI Session Lifecycle Handlers ───────────────────────────────

  const loadSessionData = useCallback(async (sid: string) => {
    try {
      const sess = await aiSessionService.getSession(sid);
      setActiveSession(sess);
      setActiveSessionId(sess.id);
      conversationIdRef.current = sess.id;

      const historyRes = await aiSessionService.getSessionMessages(sid);
      if (historyRes.items && historyRes.items.length > 0) {
        const chatMsgs: Message[] = historyRes.items.map((m: AIMessage) => ({
          id: m.id,
          sender: m.role === 'user' ? 'user' : 'stylist',
          text: m.content,
          outfits: m.metadata?.outfits,
          toolCalls: m.metadata?.tool_calls,
          provider: m.metadata?.provider_used || 'Yorvyn AI',
          timestamp: new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }));
        setMessages(chatMsgs);
      } else {
        setMessages([{
          id: 'init_' + Date.now(),
          sender: 'stylist',
          text: `Welcome back to "${sess.title}". How would you like to refine your look today?`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }]);
      }
    } catch (err) {
      console.warn('Could not load session from database', err);
    }
  }, []);

  useEffect(() => {
    const initSessions = async () => {
      if (urlSessionId) {
        await loadSessionData(urlSessionId);
      } else {
        try {
          const list = await aiSessionService.listSessions('active', undefined, undefined, 1);
          if (list.items && list.items.length > 0) {
            const first = list.items[0];
            setActiveSessionId(first.id);
            setSearchParams({ session: first.id }, { replace: true });
            await loadSessionData(first.id);
          } else {
            const created = await aiSessionService.createSession('Autumn Styling Session', 'fashion_stylist');
            setActiveSessionId(created.id);
            setActiveSession(created);
            conversationIdRef.current = created.id;
            setSearchParams({ session: created.id }, { replace: true });
          }
        } catch (e) {
          console.warn('Could not initialize sessions from server; local session active.');
        }
      }
    };
    initSessions();
  }, [urlSessionId, loadSessionData, setSearchParams]);

  const handleSelectSession = (sid: string) => {
    setActiveSessionId(sid);
    setSearchParams({ session: sid });
    loadSessionData(sid);
  };

  const handleNewSession = async () => {
    try {
      const created = await aiSessionService.createSession('New conversation', 'fashion_stylist');
      setActiveSessionId(created.id);
      setActiveSession(created);
      conversationIdRef.current = created.id;
      setSearchParams({ session: created.id });
      setMessages([{
        id: 'init_' + Date.now(),
        sender: 'stylist',
        text: "Hello Alex. I am your Yorvyn Personal Fashion Intelligence Stylist. How can I assist with your styling today?",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }]);
      toast.success('Started new conversation');
    } catch (err) {
      toast.error('Failed to create new conversation');
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
            const voiceRes = await fashionApi.unifiedVoiceChat(audioBlob, conversationIdRef.current);
            if (voiceRes && voiceRes.transcribed_input) {
              const userMsg: Message = {
                id: `user_${Date.now()}`,
                sender: 'user',
                text: voiceRes.transcribed_input,
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              };
              const stylistMsg: Message = {
                id: `stylist_${Date.now()}`,
                sender: 'stylist',
                text: voiceRes.response_text,
                outfits: voiceRes.outfits,
                provider: voiceRes.provider_used || 'Yorvyn Voice AI',
                toolCalls: voiceRes.tool_calls_executed,
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              };
              setMessages(prev => [...prev, userMsg, stylistMsg]);
              if (voiceRes.animation_intent) {
                const speechDuration = Math.max(2.0, voiceRes.response_text.length * 0.065);
                avatarPerformanceController.playIntent(voiceRes.animation_intent, speechDuration);
              }
              if (chatMode === 'voice' || !isMuted) {
                speakText(voiceRes.response_text);
              }
            } else {
              const res = await fashionApi.transcribeAudio(audioBlob);
              if (res.text) {
                handleSendMessage(res.text);
              }
            }
          } catch (err) {
            toast.error('Voice conversation failed. You can type your request directly.');
          } finally {
            setLoading(false);
          }
        }
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setIsRecording(true);
      avatarPerformanceController.setState('listening');
      toast('Listening to your fashion request...');
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
    avatarPerformanceController.interrupt();
  };

  const toggleMute = () => {
    if (!isMuted) {
      stopSpeaking();
    }
    setIsMuted(!isMuted);
    toast(isMuted ? 'Voice stylist unmuted' : 'Voice stylist muted');
  };

  // ── Send Message & Orchestrator Flow ───────────────────────────────────────

  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || inputMessage;
    if (!text.trim() || loading) return;

    stopSpeaking();

    // Ensure we have an active session
    let currSessionId = activeSessionId;
    if (!currSessionId) {
      try {
        const newSess = await aiSessionService.createSession("New conversation", "fashion_stylist");
        currSessionId = newSess.id;
        setActiveSessionId(newSess.id);
        setActiveSession(newSess);
        setSearchParams({ session: newSess.id });
      } catch (err) {
        console.error("Failed creating session", err);
      }
    }

    const clientReqId = `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    const userMsg: Message = {
      id: `user_${Date.now()}`,
      sender: 'user',
      text: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMsg]);
    setInputMessage('');
    setLoading(true);
    avatarPerformanceController.setState('thinking');

    try {
      let handled = false;
      // 1. Persistent Session Service Execution (Supabase-backed)
      if (currSessionId) {
        try {
          const turnRes = await aiSessionService.sendMessage(currSessionId, text, clientReqId);
          if (turnRes && turnRes.response) {
            const resp = turnRes.response;
            const stylistMsg: Message = {
              id: turnRes.assistant_message_id || `stylist_${Date.now()}`,
              sender: 'stylist',
              text: resp.content,
              outfits: resp.outfits,
              provider: resp.provider_used || 'Yorvyn AI',
              toolCalls: resp.tool_calls,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            };
            setMessages(prev => [...prev, stylistMsg]);

            if (resp.animation_intent) {
              const speechDuration = Math.max(2.0, resp.content.length * 0.065);
              avatarPerformanceController.playIntent(resp.animation_intent as any, speechDuration);
            }

            if (chatMode === 'voice' || !isMuted) {
              speakText(resp.content);
            }
            handled = true;
          }
        } catch (sessErr) {
          console.warn('Persistent session endpoint unavailable, falling back to intelligent chat', sessErr);
        }
      }

      if (!handled) {
        // Fallback to unified intelligence endpoint
        const intelRes = await fashionApi.intelligentChat(text, conversationIdRef.current);
        if (intelRes && intelRes.response_text) {
          const stylistMsg: Message = {
            id: `stylist_${Date.now()}`,
            sender: 'stylist',
            text: intelRes.response_text,
            outfits: intelRes.outfits,
            provider: intelRes.provider_used || 'Yorvyn AI',
            toolCalls: intelRes.tool_calls_executed,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          };
          setMessages(prev => [...prev, stylistMsg]);

          if (intelRes.animation_intent) {
            const speechDuration = Math.max(2.0, intelRes.response_text.length * 0.065);
            avatarPerformanceController.playIntent(intelRes.animation_intent, speechDuration);
          }

          if (chatMode === 'voice' || !isMuted) {
            speakText(intelRes.response_text);
          }
        } else {
          // Fallback to legacy chat endpoint
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

          if (chatMode === 'voice' || !isMuted) {
            speakText(res.reply);
          }
        }
      }
    } catch (error) {
      // Offline graceful fallback
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
        if (chatMode === 'voice' || !isMuted) {
          speakText(res.reply);
        }
      } catch (err) {
        toast.error('Stylist connection failed. Re-trying with fallback...');
        const errorMsg: Message = {
          id: `err_${Date.now()}`,
          sender: 'stylist',
          text: "I experienced a brief latency spike while scoring your wardrobe. Could you please re-phrase or ask again?",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages(prev => [...prev, errorMsg]);
      }
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
    toast('Generation stopped');
  };

  const handleFeedback = async (outfitId: string, action: 'wear_today' | 'like') => {
    try {
      await fashionApi.sendFeedback(outfitId, action);
      learningService.submitFeedback({
        feedback_type: action === 'wear_today' ? 'accepted_recommendation' : 'positive',
        session_id: activeSessionId || undefined,
        rating: 5,
        metadata: { outfit_id: outfitId, action }
      }).catch(() => {});

      if (action === 'wear_today') {
        toast.success('Logged as outfit of the day! Preference models updated.');
      } else if (action === 'like') {
        toast.success('Saved to your style preferences.');
      }
    } catch (e) {
      toast.error('Feedback recording failed');
    }
  };

  const handleMessageFeedback = async (messageId: string, type: 'positive' | 'negative') => {
    setMessageFeedback(prev => ({ ...prev, [messageId]: type }));
    try {
      await learningService.submitFeedback({
        feedback_type: type,
        session_id: activeSessionId || undefined,
        message_id: messageId,
        rating: type === 'positive' ? 5 : 2,
        feedback_text: type === 'positive' ? 'Helpful styling recommendation' : 'Not preferred style'
      });
      toast.success(type === 'positive' ? 'Saved to your style preferences!' : 'Feedback recorded to refine future styles.');
    } catch (err) {
      console.error('Error submitting message feedback:', err);
    }
  };

  const handleTryOnAvatar = (outfit: Outfit) => {
    // Navigate directly to AvatarStudio with garment info
    toast.success(`Dressing 3D avatar with ${outfit.title}...`);
    navigate('/avatar');
  };

  return (
    <div className={`stylist-chat-container ${chatMode === 'voice' ? 'voice-mode-active' : ''}`}>
      {/* ChatGPT-Style Persistent Conversation History Sidebar */}
      <SessionSidebar
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        isOpen={isSessionSidebarOpen}
        onClose={() => setIsSessionSidebarOpen(false)}
        onOpenSearchHistory={() => setIsSearchHistoryOpen(true)}
      />

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

        {/* Persistent Fashion DNA Intelligence Badge */}
        {fashionDNA && (
          <div className="stylist-sidebar-section">
            <span className="stylist-sidebar-title">Fashion DNA</span>
            <div style={{ background: 'rgba(212, 175, 55, 0.08)', border: '1px solid rgba(212, 175, 55, 0.25)', borderRadius: '10px', padding: '10px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <span style={{ fontSize: '0.74rem', fontWeight: 700, color: '#f8fafc', textTransform: 'capitalize' }}>
                  {fashionDNA.colour_profile?.personal_palette?.replace('_', ' ') || 'Autumn Deep'}
                </span>
                <span style={{ fontSize: '0.66rem', color: '#10b981', fontWeight: 600 }}>
                  {Math.round((fashionDNA.confidence_scores?.overall_dna_confidence || 0.85) * 100)}% Conf.
                </span>
              </div>
              <div style={{ fontSize: '0.68rem', color: '#94a3b8', lineHeight: 1.4 }}>
                Undertone: <strong>{fashionDNA.colour_profile?.skin_undertone || 'Neutral'}</strong> • Silhouette: <strong>{fashionDNA.body_profile?.silhouette || 'Athletic'}</strong>
                <br />
                Favs: {fashionDNA.colour_profile?.preferred_colours?.slice(0, 3).join(', ') || 'Navy, Charcoal, Olive'}
              </div>
            </div>
          </div>
        )}

        {/* Real ML Model Benchmark Badge */}
        {mlMetrics && (
          <div className="stylist-sidebar-section">
            <span className="stylist-sidebar-title">Real Fashion ML Engine</span>
            <div className="ml-metrics-badge">
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                <CheckCircle size={14} color="#10b981" />
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
            <ThermometerSimple size={18} color="#d4af37" />
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

        {knowledgeHints.length > 0 && (
          <div className="stylist-sidebar-section" data-testid="stylist-knowledge-grounding">
            <span className="stylist-sidebar-title">Construction & Fit Notes</span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {knowledgeHints.map((hint, idx) => (
                <div
                  key={idx}
                  style={{
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: '8px',
                    padding: '8px 10px',
                    fontSize: '0.7rem',
                    color: '#cbd5e1',
                    lineHeight: 1.4,
                  }}
                >
                  <div style={{ fontWeight: 700, color: '#f8fafc', marginBottom: '2px' }}>{hint.title}</div>
                  <div>{hint.snippet.slice(0, 120)}...</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {outfitInsights && (outfitInsights.outfits.length > 0 || outfitInsights.wardrobe_gaps.length > 0) && (
          <div className="stylist-sidebar-section" data-testid="stylist-outfit-recommendations">
            <span className="stylist-sidebar-title">Recommended Outfits & Gaps</span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {outfitInsights.outfits.slice(0, 2).map((o) => (
                <div
                  key={o.outfit_id}
                  style={{
                    background: 'rgba(212,175,55,0.06)',
                    border: '1px solid rgba(212,175,55,0.2)',
                    borderRadius: '8px',
                    padding: '6px 9px',
                    fontSize: '0.68rem',
                    color: '#e2e8f0',
                  }}
                >
                  <div style={{ fontWeight: 700, color: '#f8fafc' }}>{o.title}</div>
                  <div>Compatibility prediction: {Math.round(o.compatibility_prediction * 100)}%</div>
                </div>
              ))}
              {outfitInsights.wardrobe_gaps.slice(0, 1).map((g, i) => (
                <div key={i} style={{ fontSize: '0.66rem', color: '#94a3b8' }}>
                  Gap suggestion: {g.suggestion}
                </div>
              ))}
              <button
                type="button"
                onClick={() => {
                  intelligenceApi
                    .executeWorkflow('fashion.discovery', { occasion: 'smart_casual', include_external_trends: true })
                    .then((wf) => setExternalTrends(wf.state?.external_trends || []))
                    .catch(() => {});
                }}
                style={{
                  marginTop: '4px',
                  fontSize: '0.68rem',
                  padding: '4px 8px',
                  borderRadius: '6px',
                  border: '1px solid rgba(255,255,255,0.12)',
                  background: 'rgba(15, 23, 42, 0.65)',
                  color: '#cbd5e1',
                  cursor: 'pointer',
                }}
              >
                Check External Trend Context
              </button>
              {externalTrends.slice(0, 2).map((ref, idx) => (
                <div key={idx} style={{ fontSize: '0.65rem', color: '#94a3b8', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '4px' }}>
                  <span>[External Web Reference — Unverified] </span>
                  <a href={ref.source_url} target="_blank" rel="noreferrer" style={{ color: '#93c5fd' }}>
                    {ref.source_title || ref.domain}
                  </a>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Main Stylist Area */}
      <div className="stylist-main">
        {/* Header with Mode Toggle, Persistent Session & Controls */}
        <div className="stylist-header">
          <div className="stylist-title-area">
            <button 
              className="session-sidebar-toggle-btn"
              onClick={() => setIsSessionSidebarOpen(!isSessionSidebarOpen)}
              title={isSessionSidebarOpen ? "Hide conversation history" : "Show conversation history"}
            >
              <SidebarSimple size={18} />
            </button>
            <div className={`stylist-status-dot ${isRecording ? 'recording' : isSpeaking ? 'speaking' : ''}`} />
            <div>
              <h3 style={{ margin: 0, fontSize: '0.96rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
                {activeSession?.title || 'Styling Session'} <Sparkle size={15} color="#d4af37" />
                <span className="session-status-badge">Persistent Session</span>
              </h3>
              <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
                {isRecording ? 'Listening to speech...' : isSpeaking ? 'Speaking response...' : 'Grounded multi-turn session with Supabase persistence'}
              </span>
            </div>
          </div>

          {/* Mode Switcher & Controls */}
          <div className="header-controls-group">
            <button
              className="header-action-pill"
              onClick={() => setIsSearchHistoryOpen(true)}
              title="Search History & Provenance"
            >
              <Clock size={14} /> Searches
            </button>

            <button 
              className={`mode-toggle-btn ${chatMode === 'text' ? 'active' : ''}`}
              onClick={() => setChatMode('text')}
              title="Switch to Text Chat"
            >
              <ChatCircleText size={14} /> Text
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
              {isMuted ? <SpeakerSimpleSlash size={16} /> : <SpeakerHigh size={16} />}
            </button>

            {isSpeaking && (
              <button 
                className="audio-control-btn stop-speaking"
                onClick={stopSpeaking}
                title="Stop audio playback"
              >
                <Stop size={14} />
              </button>
            )}
          </div>
        </div>

        {/* Voice Mode Big Waveform HUD (Rendered when in Voice Mode) */}
        {chatMode === 'voice' && (
          <div className="voice-mode-hud">
            <div className="voice-avatar-orb-container">
              <div className={`voice-avatar-orb ${isRecording ? 'pulse-listening' : isSpeaking ? 'pulse-speaking' : ''}`}>
                {isRecording ? <Microphone size={38} color="#d4af37" /> : isSpeaking ? <SpeakerHigh size={38} color="#d4af37" /> : <Sparkle size={38} color="#d4af37" />}
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
                <WarningCircle size={14} /> Microphone permission denied. Please allow microphone access in your browser bar.
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
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <button
                          className="msg-feedback-btn"
                          onClick={() => handleMessageFeedback(msg.id, 'positive')}
                          title="Helpful recommendation"
                          style={{
                            background: messageFeedback[msg.id] === 'positive' ? 'rgba(74, 222, 128, 0.2)' : 'transparent',
                            color: messageFeedback[msg.id] === 'positive' ? '#4ade80' : '#64748b',
                            border: 'none',
                            cursor: 'pointer',
                            padding: '2px 4px',
                            borderRadius: '4px',
                            display: 'flex',
                            alignItems: 'center',
                          }}
                        >
                          <ThumbsUp size={12} />
                        </button>
                        <button
                          className="msg-feedback-btn"
                          onClick={() => handleMessageFeedback(msg.id, 'negative')}
                          title="Not preferred style"
                          style={{
                            background: messageFeedback[msg.id] === 'negative' ? 'rgba(239, 68, 68, 0.2)' : 'transparent',
                            color: messageFeedback[msg.id] === 'negative' ? '#f87171' : '#64748b',
                            border: 'none',
                            cursor: 'pointer',
                            padding: '2px 4px',
                            borderRadius: '4px',
                            display: 'flex',
                            alignItems: 'center',
                          }}
                        >
                          <ThumbsDown size={12} />
                        </button>
                        <button 
                          className="msg-replay-btn" 
                          onClick={() => speakText(msg.text)}
                          title="Replay voice audio"
                        >
                          <SpeakerHigh size={12} />
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                <p style={{ margin: 0, whiteSpace: 'pre-wrap', lineHeight: 1.55 }}>{msg.text}</p>

                {/* Render Executed Tool Call Badges */}
                {msg.toolCalls && msg.toolCalls.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '8px' }}>
                    {msg.toolCalls.map((tc, idx) => (
                      <span
                        key={idx}
                        style={{
                          fontSize: '0.66rem',
                          background: 'rgba(212, 175, 55, 0.12)',
                          color: '#d4af37',
                          border: '1px solid rgba(212, 175, 55, 0.25)',
                          padding: '2px 8px',
                          borderRadius: '10px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px'
                        }}
                      >
                        ⚡ {tc.tool_name}
                      </span>
                    ))}
                  </div>
                )}

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
                            <TShirt size={13} style={{ display: 'inline', marginRight: '4px' }} /> Try on Avatar
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
                  <Sparkle size={18} color="#d4af37" className="animate-spin" />
                  <span>Consulting digital wardrobe harmony, weather matrices, and silhouette fit...</span>
                </div>
                <button 
                  className="stop-generation-btn"
                  onClick={handleStopGeneration}
                  title="Stop generating"
                >
                  <Stop size={12} /> Stop
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
              {isRecording ? <MicrophoneSlash size={18} /> : <Microphone size={18} />}
            </button>

            <input 
              type="text"
              className="chat-input-field"
              placeholder={isRecording ? "Listening to your voice..." : "Ask your personal stylist (e.g. 'What can I wear for a Sangeet in Mumbai at 26°C?')..."}
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
              <PaperPlaneTilt size={16} /> Stylize
            </button>
          </div>

          <div className="chat-privacy-footer">
            <span>🔒 Audio and photos are processed ephemerally and never retained without consent.</span>
          </div>
        </div>
      </div>

      {/* Search History & Provenance Modal */}
      <SearchHistoryModal
        isOpen={isSearchHistoryOpen}
        onClose={() => setIsSearchHistoryOpen(false)}
        onSelectSearchQuery={(query) => handleSendMessage(query)}
      />
    </div>
  );
};
