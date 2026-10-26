import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  X,
  RotateCcw,
  RotateCw,
  Camera,
  Sparkles,
  Heart,
  User,
  Zap,
  Layers,
  Check,
  Settings as SettingsIcon,
  Download,
  Share2,
  Scissors,
  Palette,
  Smile,
  Shirt,
  Send,
  Plus,
  Trash2,
  RefreshCw,
  Eye,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Minimize2
} from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import toast from 'react-hot-toast';
import { avatarEngine as araEngine } from '../engine/ara/avatarStudioService';
import { avatarAnimationController as araAnim } from '../engine/ara/avatarAnimationController';
import { HumanParams, DEFAULT_PARAMS } from '../engine/ara/core/params';
import { Character } from '../engine/ara/core/human';
import { AssetLibrary } from '../engine/ara/core/assets';
import { AvatarStudioViewer as AraAvatarViewer, AvatarStudioViewerHandle as AraAvatarViewerHandle } from '../components/AvatarStudioViewer';
import { AtmosphereBackground as VantaFogBackground } from '../components/AtmosphereBackground';
import { SettingsModal } from '../components/SettingsModal';
import { PhotoTo3DGarmentModal } from '../components/PhotoTo3DGarmentModal';
import { fashionApi } from '../services/fashionApi';
import {
  Garment,
  GarmentCategory,
  ClosetAnalytics,
  Outfit,
  UserProfile
} from '../types/fashion';
import './AvatarStudio.css';

export type PoseType = 'standing' | 'crossed_arms' | 'hands_pockets';
export type SceneType = 'studio' | 'sky_clouds' | 'sunset' | 'night';
export type PrimaryTab = 'fashion' | 'stylist' | 'wardrobe' | 'outfits' | 'avatar' | 'profile';
export type AvatarSubTab = 'body' | 'face' | 'hair' | 'skin';

interface FashionCatalogItem {
  id: string;
  name: string;
  brand: string;
  category: 'outfit' | 'top' | 'bottom' | 'shoes' | 'outerwear' | 'accessory';
  priceDisplay: string;
  color: string;
  imageUrl?: string;
  hasBlueDot?: boolean;
  collection: 'halloween' | 'diesel' | 'yorvyn' | 'ralph_lauren' | 'cos' | 'staples' | 'quiet_luxury' | 'capsule';
  araOutfitId?: string;
  araShoesId?: string;
  appliedParams: Partial<HumanParams>;
}



// ── Screenshot 1: Try a New Look Outfits ──
const TRY_NEW_LOOK_ITEMS: FashionCatalogItem[] = [
  {
    id: 'dsl-biker',
    name: 'Diesel Moto Leather Tracksuit',
    brand: 'Diesel',
    category: 'outfit',
    priceDisplay: '₹ 32,900',
    color: '#0f172a',
    collection: 'diesel',
    imageUrl: '/items/card_biker.jpg',
    araOutfitId: 'male_casualsuit03',
    appliedParams: {
      outfit: 'male_casualsuit03',
      shoes: 'shoes04'
    }
  },
  {
    id: 'wiz-cloak',
    name: 'Hogwarts Crest Wizard Cloak',
    brand: 'Yorvyn Special',
    category: 'outfit',
    priceDisplay: '₹ 18,500',
    color: '#1e1b18',
    collection: 'yorvyn',
    imageUrl: '/items/card_wizard.jpg',
    araOutfitId: 'male_elegantsuit01',
    appliedParams: {
      outfit: 'male_elegantsuit01',
      shoes: 'shoes02'
    }
  },
  {
    id: 'sig-polo',
    name: 'Classic Black Polo with Denim',
    brand: 'Ralph Lauren',
    category: 'outfit',
    priceDisplay: '₹ 8,990',
    color: '#111111',
    collection: 'ralph_lauren',
    imageUrl: '/items/card_casual.jpg',
    araOutfitId: 'male_casualsuit01',
    appliedParams: {
      outfit: 'male_casualsuit01',
      shoes: 'shoes01',
      hair: 'short01',
      hairColor: '#1e1b18'
    }
  }
];

const FASHION_CATALOG: FashionCatalogItem[] = [
  // ── Cloud & Quiet Luxury Collection (White & Sky Blue) ──
  {
    id: 'cld-blouse',
    name: 'Cloud Silk Pure White Blouse',
    brand: 'Yorvyn Haute',
    category: 'top',
    priceDisplay: '₹ 16,900',
    color: '#ffffff',
    collection: 'yorvyn',
    imageUrl: '/items/card_casual.jpg',
    hasBlueDot: true,
    appliedParams: {
      outfit: 'female_casualsuit01',
      hairColor: '#1e293b',
      shoes: 'shoes01'
    }
  },
  {
    id: 'cld-knit',
    name: 'Sky Blue Cashmere Knitwear',
    brand: 'Quiet Luxury',
    category: 'top',
    priceDisplay: '₹ 24,000',
    color: '#7dd3fc',
    collection: 'quiet_luxury',
    imageUrl: '/items/card_casual.jpg',
    hasBlueDot: true,
    appliedParams: {
      outfit: 'male_casualsuit02',
      shoes: 'shoes01'
    }
  },
  {
    id: 'cld-blazer',
    name: 'Sky Blue Tailored Linen Blazer',
    brand: 'Quiet Luxury',
    category: 'outfit',
    priceDisplay: '₹ 34,500',
    color: '#38bdf8',
    collection: 'quiet_luxury',
    imageUrl: '/items/card_toga.jpg',
    appliedParams: {
      outfit: 'female_casualsuit01',
      shoes: 'shoes01'
    }
  },
  {
    id: 'cld-trousers',
    name: 'Cloud Pleated Tailored Trousers',
    brand: 'Capsule Archive',
    category: 'bottom',
    priceDisplay: '₹ 14,900',
    color: '#f8fafc',
    collection: 'capsule',
    imageUrl: '/items/card_casual.jpg',
    appliedParams: {
      outfit: 'male_casualsuit01',
      shoes: 'shoes01'
    }
  },
  {
    id: 'cld-sneakers',
    name: 'Aero Cloud Platform Sneakers',
    brand: 'Yorvyn Haute',
    category: 'shoes',
    priceDisplay: '₹ 19,500',
    color: '#ffffff',
    collection: 'yorvyn',
    imageUrl: '/items/card_casual.jpg',
    araShoesId: 'shoes01',
    appliedParams: {
      shoes: 'shoes01'
    }
  },

  // ── Atelier & Heritage Collections ──
  {
    id: 'hal-pumpkin',
    name: 'Jack-o\'-Lantern Glow Edition',
    brand: 'Bitmoji Fashion',
    category: 'top',
    priceDisplay: '₹ 2,499',
    color: '#ea580c',
    collection: 'halloween',
    imageUrl: '/items/card_pumpkin.jpg',
    hasBlueDot: true,
    appliedParams: {
      outfit: 'male_casualsuit01'
    }
  },
  {
    id: 'hal-medusa',
    name: 'Golden Medusa Snake Crown',
    brand: 'Bitmoji Fashion',
    category: 'top',
    priceDisplay: '₹ 3,999',
    color: '#eab308',
    collection: 'halloween',
    imageUrl: '/items/card_medusa.jpg',
    hasBlueDot: true,
    appliedParams: {
      hairColor: '#eab308'
    }
  },
  {
    id: 'hal-goddess',
    name: 'Olympian Draped Chiton Toga',
    brand: 'Bitmoji Fashion',
    category: 'outfit',
    priceDisplay: '₹ 4,999',
    color: '#84cc16',
    collection: 'halloween',
    imageUrl: '/items/card_toga.jpg',
    araOutfitId: 'female_casualsuit01',
    appliedParams: {
      outfit: 'female_casualsuit01',
      gender: 0.2
    }
  },
  {
    id: 'dsl-biker',
    name: 'Diesel Moto Leather Tracksuit',
    brand: 'Diesel',
    category: 'outfit',
    priceDisplay: '₹ 32,900',
    color: '#0f172a',
    collection: 'diesel',
    imageUrl: '/items/card_biker.jpg',
    araOutfitId: 'male_casualsuit03',
    appliedParams: {
      outfit: 'male_casualsuit03',
      shoes: 'shoes04'
    }
  },
  {
    id: 'wiz-cloak',
    name: 'Hogwarts Crest Wizard Cloak',
    brand: 'Yorvyn Special',
    category: 'outfit',
    priceDisplay: '₹ 18,500',
    color: '#1e1b18',
    collection: 'yorvyn',
    imageUrl: '/items/card_wizard.jpg',
    araOutfitId: 'male_elegantsuit01',
    appliedParams: {
      outfit: 'male_elegantsuit01',
      shoes: 'shoes02'
    }
  },
  {
    id: 'sig-polo',
    name: 'Classic Black Polo with Emblem',
    brand: 'Ralph Lauren',
    category: 'outfit',
    priceDisplay: '₹ 8,990',
    color: '#111111',
    collection: 'ralph_lauren',
    imageUrl: '/items/card_casual.jpg',
    araOutfitId: 'male_casualsuit01',
    appliedParams: {
      outfit: 'male_casualsuit01',
      shoes: 'shoes01',
      hair: 'short01',
      hairColor: '#1e1b18'
    }
  },
  {
    id: 'sig-jeans',
    name: 'Relaxed Baggy Denim Jeans',
    brand: 'Diesel',
    category: 'bottom',
    priceDisplay: '₹ 14,500',
    color: '#93c5fd',
    collection: 'diesel',
    imageUrl: '/items/card_casual.jpg',
    araOutfitId: 'male_casualsuit02',
    appliedParams: {
      outfit: 'male_casualsuit02',
      shoes: 'shoes01'
    }
  },
  {
    id: 'sig-sneakers',
    name: 'Minimalist White Leather Sneaker',
    brand: 'COS',
    category: 'shoes',
    priceDisplay: '₹ 7,500',
    color: '#ffffff',
    collection: 'cos',
    araShoesId: 'shoes01',
    appliedParams: {
      shoes: 'shoes01'
    }
  },
  {
    id: 'bespoke-tux',
    name: 'Midnight Navy Bespoke Tuxedo',
    brand: 'Yorvyn Atelier',
    category: 'outfit',
    priceDisplay: '₹ 42,000',
    color: '#0f172a',
    collection: 'yorvyn',
    araOutfitId: 'male_elegantsuit01',
    appliedParams: {
      outfit: 'male_elegantsuit01',
      shoes: 'shoes02'
    }
  }
];

interface ChatMessage {
  id: string;
  sender: 'user' | 'stylist';
  text: string;
  outfits?: Outfit[];
}

interface AvatarStudioProps {
  defaultTab?: PrimaryTab;
}

export const AvatarStudio: React.FC<AvatarStudioProps> = ({ defaultTab = 'fashion' }) => {
  const navigate = useNavigate();
  const location = useLocation();

  // 3D Engine State
  const [lib, setLib] = useState<AssetLibrary | null>(null);
  const [character, setCharacter] = useState<Character | null>(null);
  const [engineReady, setEngineReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingStatus, setLoadingStatus] = useState('Connecting to 3D Anatomy Catalog...');
  const [error, setError] = useState<string | null>(null);

  // Active Parameters & History
  const [params, setParams] = useState<HumanParams>(() => {
    const savedChar = typeof window !== 'undefined' ? localStorage.getItem('yorvyn_avatar_character') : null;
    const isGirl = savedChar === 'girl' || savedChar === 'female';
    if (isGirl) {
      return {
        ...DEFAULT_PARAMS,
        name: 'Elena (Girl Avatar)',
        gender: 0.0,
        age: 0.42,
        muscle: 0.40,
        weight: 0.38,
        height: 0.54,
        proportions: 0.85,
        breastSize: 0.55,
        breastFirmness: 0.60,
        skin: 'young_caucasian_female',
        skinTint: '#ffffff',
        hair: 'ponytail01',
        hairColor: '#1e293b',
        facialHair: 'none',
        outfit: 'female_casualsuit01',
        shoes: 'shoes01',
        eyebrows: 'eyebrow010',
        eyelashes: 'eyelashes02',
        eyes: 'blue'
      };
    }
    return {
      ...DEFAULT_PARAMS,
      name: 'Yorvyn Avatar',
      gender: 1.0,
      age: 0.45,
      muscle: 0.65,
      weight: 0.45,
      height: 0.65,
      proportions: 0.85,
      skin: 'young_caucasian_male',
      skinTint: '#ffffff',
      hair: 'short01',
      hairColor: '#1e293b',
      facialHair: 'stubble',
      outfit: 'male_casualsuit01',
      shoes: 'shoes01',
      eyebrows: 'eyebrow001',
      eyelashes: 'eyelashes01',
      eyes: 'brownlight'
    };
  });
  const [history, setHistory] = useState<HumanParams[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);

  // Studio Stage States (Crisp White Studio Canvas)
  const [scene] = useState<SceneType>('studio');
  const [drawerOpen, setDrawerOpen] = useState(() => {
    return typeof window !== 'undefined' && (window.innerWidth >= 900 || defaultTab !== 'fashion');
  });
  const [viewMode, setViewMode] = useState<'full' | 'portrait'>('full');
  const [showSunglasses, setShowSunglasses] = useState(true);
  const [showPet, setShowPet] = useState(false);
  const [primaryTab, setPrimaryTab] = useState<PrimaryTab>(defaultTab);
  const [avatarSubTab, setAvatarSubTab] = useState<AvatarSubTab>('body');
  const [activeBrandFilter, setActiveBrandFilter] = useState<string>('all');
  const [activeSubcat, setActiveSubcat] = useState<string>('all');
  const [selectedGarmentId, setSelectedGarmentId] = useState<string>('sig-polo');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  // ── AI Stylist Chat State ──
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: 'init_1',
      sender: 'stylist',
      text: "Hello! I am your Yorvyn Fashion Intelligence Stylist. Ask me for layer-aware outfit recommendations for any event or weather, and try them on your 3D avatar instantly."
    }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // ── Digital Wardrobe State ──
  const [wardrobeItems, setWardrobeItems] = useState<Garment[]>([]);
  const [wardrobeCategory, setWardrobeCategory] = useState<string>('all');
  const [wardrobeAnalytics, setWardrobeAnalytics] = useState<ClosetAnalytics | null>(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newGarmentName, setNewGarmentName] = useState('');
  const [newGarmentCategory, setNewGarmentCategory] = useState<GarmentCategory>('top');
  const [newGarmentColor, setNewGarmentColor] = useState('black');
  const [newGarmentBrand, setNewGarmentBrand] = useState('Yorvyn Atelier');
  const [newGarmentWarmth, setNewGarmentWarmth] = useState(5);
  const [newGarmentFormality, setNewGarmentFormality] = useState(5);

  // ── Photo to 3D Custom Garment State ──
  const [isPhotoGarmentModalOpen, setIsPhotoGarmentModalOpen] = useState(false);
  const [activeCustomGarment, setActiveCustomGarment] = useState<Garment | null>(null);

  // ── Lookbook Studio State ──
  const [generatedOutfits, setGeneratedOutfits] = useState<Outfit[]>([]);
  const [outfitOccasion, setOutfitOccasion] = useState('casual_day');
  const [outfitTemp, setOutfitTemp] = useState(18);
  const [outfitCondition, setOutfitCondition] = useState('clear');
  const [outfitAesthetic, setOutfitAesthetic] = useState('quiet_luxury');
  const [outfitLoading, setOutfitLoading] = useState(false);

  // ── Personal Profile State ──
  const [userProfile, setUserProfile] = useState<UserProfile>({
    user_id: 'default_user',
    name: 'Alex',
    body_shape: 'athletic_tapered',
    height_cm: 178,
    skin_undertone: 'warm-bright',
    color_season: 'autumn',
    fit_preference: 'relaxed_tailored',
    primary_aesthetics: ['quiet_luxury', 'minimalist_scandi'],
    budget_tier: 'mid_premium',
    lifestyle_notes: 'Hybrid work, likes timeless neutrals and structured knitwear.'
  });

  // Debounced Rebuild timer
  const buildDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const viewerRef = useRef<AraAvatarViewerHandle>(null);

  // Synchronize primaryTab with the current URL pathname from AppSideNav
  useEffect(() => {
    const path = location.pathname;
    let tab: PrimaryTab = defaultTab;
    if (path.startsWith('/stylist')) tab = 'stylist';
    else if (path.startsWith('/wardrobe')) tab = 'wardrobe';
    else if (path.startsWith('/outfits')) tab = 'outfits';
    else if (path.startsWith('/avatar')) tab = 'avatar';
    else if (path.startsWith('/profile')) tab = 'profile';
    else if (path === '/' || path === '') tab = 'fashion';

    setPrimaryTab(tab);
    setDrawerOpen(true);
  }, [location.pathname, defaultTab]);

  // Switch tabs & update URL cleanly
  const handleTabSwitch = (tab: PrimaryTab) => {
    setPrimaryTab(tab);
    setDrawerOpen(true);
    navigate(tab === 'fashion' ? '/' : `/${tab}`);
  };

  // 1. Initialize Engine & Load Backend Context
  const initializeEngine = useCallback(async () => {
    setLoading(true);
    setError(null);
    setLoadingStatus('Initializing Ara 3D Character Engine...');

    try {
      await araEngine.init((label) => setLoadingStatus(label));
      const loadedLib = araEngine.getLibrary();
      setLib(loadedLib);
      setEngineReady(true);

      // Load saved avatar config from backend or character preset
      const savedChar = typeof window !== 'undefined' ? localStorage.getItem('yorvyn_avatar_character') : null;
      const isGirl = savedChar === 'girl' || savedChar === 'female';

      let initialParams: HumanParams = isGirl ? {
        ...DEFAULT_PARAMS,
        name: 'Elena (Girl Avatar)',
        gender: 0.0,
        age: 0.42,
        muscle: 0.40,
        weight: 0.38,
        height: 0.54,
        proportions: 0.85,
        breastSize: 0.55,
        breastFirmness: 0.60,
        skin: 'young_caucasian_female',
        skinTint: '#ffffff',
        hair: 'ponytail01',
        hairColor: '#1e293b',
        facialHair: 'none',
        outfit: 'female_casualsuit01',
        shoes: 'shoes01',
        eyebrows: 'eyebrow010',
        eyelashes: 'eyelashes02',
        eyes: 'blue'
      } : {
        ...DEFAULT_PARAMS,
        name: 'Yorvyn Avatar',
        gender: 1.0,
        age: 0.45,
        muscle: 0.65,
        weight: 0.45,
        height: 0.65,
        proportions: 0.85,
        skin: 'young_caucasian_male',
        skinTint: '#ffffff',
        hair: 'short01',
        hairColor: '#1e293b',
        facialHair: 'stubble',
        outfit: 'male_casualsuit01',
        shoes: 'shoes01',
        eyebrows: 'eyebrow001',
        eyelashes: 'eyelashes01',
        eyes: 'brownlight'
      };

      try {
        const saved = await fashionApi.getAvatarConfig();
        if (saved && saved.gender !== undefined) {
          initialParams = { ...initialParams, ...saved };
        }
      } catch (err) {
        console.warn('Using baseline params');
      }

      setParams(initialParams);
      setHistory([initialParams]);
      setHistoryIndex(0);

      // Generate initial 3D mesh
      setLoadingStatus('Generating 3D Anatomy & Garments...');
      const built = await araEngine.generateCharacter(initialParams, (stage) => setLoadingStatus(stage));
      setCharacter(built);
      setLoading(false);
    } catch (err: any) {
      console.error('Engine Init Error:', err);
      setError(err.message || 'Failed to initialize 3D character engine');
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    initializeEngine();
    // Pre-fetch wardrobe, profile & lookbook data
    fashionApi.getWardrobe().then(res => setWardrobeItems(res.items || [])).catch(() => { });
    fashionApi.getAnalytics().then(setWardrobeAnalytics).catch(() => { });
    fashionApi.getProfile().then(setUserProfile).catch(() => { });
    fashionApi.generateOutfits({ occasion: 'casual_day', temperature_celsius: 18, condition: 'clear', target_aesthetic: 'quiet_luxury', max_outfits: 3 })
      .then(res => setGeneratedOutfits(res.outfits || []))
      .catch(() => { });
  }, [initializeEngine]);

  useEffect(() => {
    if (primaryTab === 'stylist') {
      chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages, primaryTab]);

  // 2. Debounced 3D Character Rebuild
  const triggerRebuild = useCallback((newParams: HumanParams, pushHistory = true) => {
    if (!engineReady) return;
    setParams(newParams);

    if (pushHistory) {
      setHistory(prev => {
        const sliced = prev.slice(0, historyIndex + 1);
        return [...sliced, newParams];
      });
      setHistoryIndex(prev => prev + 1);
    }

    if (buildDebounceRef.current) clearTimeout(buildDebounceRef.current);
    buildDebounceRef.current = setTimeout(async () => {
      try {
        setLoadingStatus('Updating 3D Mesh...');
        const updated = await araEngine.generateCharacter(newParams);
        setCharacter(updated);
      } catch (err: any) {
        console.error('Character rebuild failed:', err);
      }
    }, 180);
  }, [engineReady, historyIndex]);

  // Live listener for character switch from Settings Modal
  useEffect(() => {
    const handleCharSwitch = (e: any) => {
      if (e.detail?.params) {
        triggerRebuild({ ...params, ...e.detail.params });
      }
    };
    window.addEventListener('yorvyn:change_avatar_character', handleCharSwitch);
    return () => {
      window.removeEventListener('yorvyn:change_avatar_character', handleCharSwitch);
    };
  }, [params, triggerRebuild]);

  const updateParam = <K extends keyof HumanParams>(key: K, value: HumanParams[K]) => {
    const next = { ...params, [key]: value };
    triggerRebuild(next);
  };

  const updateModifier = (modifierId: string, val: number) => {
    const nextModifiers = { ...params.modifiers, [modifierId]: val };
    const next = { ...params, modifiers: nextModifiers };
    triggerRebuild(next);
  };

  // Undo & Redo
  const handleUndo = () => {
    if (historyIndex > 0) {
      const prev = history[historyIndex - 1];
      setHistoryIndex(historyIndex - 1);
      triggerRebuild(prev, false);
      toast.success('Undone', { duration: 1000 });
    }
  };

  const handleRedo = () => {
    if (historyIndex < history.length - 1) {
      const next = history[historyIndex + 1];
      setHistoryIndex(historyIndex + 1);
      triggerRebuild(next, false);
      toast.success('Redone', { duration: 1000 });
    }
  };

  // Garment Selection
  const handleSelectGarment = (item: FashionCatalogItem) => {
    setSelectedGarmentId(item.id);
    const updated = {
      ...params,
      ...item.appliedParams
    };
    triggerRebuild(updated);
    araAnim.playOneShot('Turn', 'Idle', 0.4);
    toast.success(`Equipped ${item.name}`, { duration: 1500 });
  };

  // Drape an Outfit onto the 3D avatar
  const handleDrapeOutfitOnAvatar = (outfit: Outfit) => {
    const updated: HumanParams = { ...params };
    const titleLower = (outfit.title || '').toLowerCase();
    if (titleLower.includes('formal') || titleLower.includes('luxury') || titleLower.includes('evening') || titleLower.includes('classic')) {
      updated.outfit = 'male_elegantsuit01';
      updated.shoes = 'shoes02';
    } else if (titleLower.includes('street') || titleLower.includes('urban') || titleLower.includes('tech')) {
      updated.outfit = 'male_casualsuit03';
      updated.shoes = 'shoes04';
    } else {
      updated.outfit = 'male_casualsuit02';
      updated.shoes = 'shoes01';
    }
    triggerRebuild(updated);
    araAnim.playOneShot('Turn', 'Idle', 0.4);
    toast.success(`Draped "${outfit.title}" onto 3D avatar!`, { icon: '✨', duration: 2000 });
  };

  // Drape a Wardrobe piece onto the 3D avatar
  const handleDrapeWardrobePiece = (piece: Garment) => {
    if (piece.is_custom_3d && piece.glb_url) {
      setActiveCustomGarment(piece);
      araAnim.playOneShot('Turn', 'Idle', 0.4);
      toast.success(`Wearing 3D garment "${piece.name}" on your avatar!`, { icon: '✨', duration: 2000 });
      return;
    }
    setActiveCustomGarment(null);
    const updated: HumanParams = { ...params };
    if (piece.category === 'top') {
      updated.outfit = 'male_casualsuit01';
    } else if (piece.category === 'bottom') {
      updated.outfit = 'male_casualsuit02';
    } else if (piece.category === 'footwear') {
      updated.shoes = 'shoes01';
    } else if (piece.category === 'outerwear') {
      updated.outfit = 'male_elegantsuit01';
    }
    triggerRebuild(updated);
    araAnim.playOneShot('Turn', 'Idle', 0.4);
    toast.success(`Wearing "${piece.name}" on 3D avatar!`, { icon: '👕', duration: 1500 });
  };

  // Save Avatar State
  const handleSaveAvatar = async () => {
    try {
      await fashionApi.saveAvatarConfig(params);
      araAnim.playOneShot('Cheer', 'Idle', 0.4);
      toast.success('Avatar saved to your digital profile!', { icon: '🎉' });
    } catch {
      araAnim.playOneShot('Cheer', 'Idle', 0.4);
      toast.success('Saved locally', { icon: '🎉' });
    }
  };

  // Snap photo
  const handleSnap = () => {
    const canvas = document.querySelector('.ara-canvas') as HTMLCanvasElement;
    if (canvas) {
      const dataUrl = canvas.toDataURL('image/png');
      const a = document.createElement('a');
      a.href = dataUrl;
      a.download = `yorvyn-snap-${Date.now()}.png`;
      a.click();
      toast.success('Snap photo captured and downloaded!');
    } else {
      toast('Snap photo captured!');
    }
  };

  // Share link
  const handleShare = () => {
    if (navigator.share) {
      navigator.share({
        title: 'My Yorvyn 3D Fashion Avatar',
        text: 'Check out my 3D fashion avatar created with Yorvyn AI Stylist!',
        url: window.location.href,
      }).catch(() => { });
    } else {
      navigator.clipboard.writeText(window.location.href);
      toast.success('Share link copied to clipboard!');
    }
  };

  // GLB Model Download
  const handleDownloadGlb = async () => {
    if (!character) return;
    setIsExporting(true);
    const toastId = toast.loading('Exporting rigged GLB 3D model...');

    try {
      const glbBytes = await araEngine.exportCharacterGlb(character);
      const blob = new Blob([glbBytes as BlobPart], { type: 'model/gltf-binary' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${params.name || 'yorvyn-character'}.glb`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('3D Model downloaded successfully!', { id: toastId });
    } catch (err: any) {
      toast.error(`Export failed: ${err.message}`, { id: toastId });
    } finally {
      setIsExporting(false);
    }
  };

  // Send AI Stylist Message
  const handleSendStylistMessage = async (presetText?: string) => {
    const text = presetText || chatInput;
    if (!text.trim() || chatLoading) return;

    const userMsg: ChatMessage = {
      id: `usr_${Date.now()}`,
      sender: 'user',
      text
    };
    setChatMessages(prev => [...prev, userMsg]);
    setChatInput('');
    setChatLoading(true);

    try {
      const res = await fashionApi.chatWithStylist(text, outfitTemp);
      const botMsg: ChatMessage = {
        id: `sty_${Date.now()}`,
        sender: 'stylist',
        text: res.reply,
        outfits: res.outfits
      };
      setChatMessages(prev => [...prev, botMsg]);
    } catch {
      setChatMessages(prev => [
        ...prev,
        {
          id: `err_${Date.now()}`,
          sender: 'stylist',
          text: "I analyzed your wardrobe and current temperature. Try asking for an office or casual combination!"
        }
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  // Add Garment to Wardrobe
  const handleAddGarment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newGarmentName.trim()) {
      toast.error('Please enter a garment name');
      return;
    }

    try {
      const added = await fashionApi.addGarment({
        name: newGarmentName,
        category: newGarmentCategory,
        color: newGarmentColor,
        brand: newGarmentBrand,
        warmth: Number(newGarmentWarmth),
        formality: Number(newGarmentFormality),
        image_url: '/items/card_casual.jpg'
      });
      setWardrobeItems(prev => [added, ...prev]);
      toast.success('Garment digitized into your wardrobe!');
      setIsAddModalOpen(false);
      setNewGarmentName('');
      fashionApi.getAnalytics().then(setWardrobeAnalytics);
    } catch {
      toast.error('Failed to add garment');
    }
  };

  // Delete Garment
  const handleDeleteGarment = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Remove this piece from your digital closet?')) return;
    try {
      await fashionApi.deleteGarment(id);
      setWardrobeItems(prev => prev.filter(item => item.id !== id));
      toast.success('Garment removed');
      fashionApi.getAnalytics().then(setWardrobeAnalytics);
    } catch {
      toast.error('Failed to delete garment');
    }
  };

  // Toggle Favorite
  const handleToggleFavoriteGarment = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const updated = await fashionApi.toggleFavorite(id);
      setWardrobeItems(prev => prev.map(item => item.id === id ? { ...item, favorite: updated.favorite } : item));
    } catch {
      toast.error('Could not update favorite');
    }
  };

  // Generate Lookbook Outfits
  const handleGenerateOutfits = async () => {
    try {
      setOutfitLoading(true);
      const res = await fashionApi.generateOutfits({
        occasion: outfitOccasion,
        temperature_celsius: outfitTemp,
        condition: outfitCondition,
        target_aesthetic: outfitAesthetic,
        max_outfits: 3
      });
      setGeneratedOutfits(res.outfits || []);
      toast.success('Generated fresh rule-grounded looks!');
    } catch {
      toast.error('Failed to generate outfits');
    } finally {
      setOutfitLoading(false);
    }
  };

  // Save Profile Identity
  const handleSaveProfile = async () => {
    try {
      const updated = await fashionApi.updateProfile(userProfile);
      setUserProfile(updated);
      toast.success('Style profile updated & synchronized!');
    } catch {
      toast.error('Failed to update profile');
    }
  };

  // Filtered Fashion Catalog
  const filteredCatalog = FASHION_CATALOG.filter(item => {
    if (activeBrandFilter !== 'all' && item.collection !== activeBrandFilter) return false;
    if (activeSubcat !== 'all' && item.category !== activeSubcat) return false;
    return true;
  });

  // Filtered Wardrobe
  const filteredWardrobe = wardrobeItems.filter(item => {
    if (wardrobeCategory === 'all') return true;
    return item.category === wardrobeCategory;
  });

  return (
    <div className={`avatar-stage-container scene-${scene}`}>
      {/* ── Dynamic Vanta FOG shader atmospheric background in light sky blue ── */}
      <VantaFogBackground
        highlightColor={0xffffff}
        midtoneColor={0xbae6fd}
        lowlightColor={0x87cefa}
        baseColor={0xe0f2fe}
        blurFactor={0.45}
        speed={0.65}
        zoom={1.25}
      />

      {/* ── 2. YORVYN LUXURY TOP BAR ── */}
      <header className="stage-top-bar">
        <div className="top-bar-left">
          <button
            className="circle-control-btn mobile-only-control"
            onClick={() => {
              if (drawerOpen) {
                setDrawerOpen(false);
                window.history.replaceState(null, '', '/');
              } else {
                navigate('/');
              }
            }}
            aria-label={drawerOpen ? "Close Atelier" : "Home"}
            title={drawerOpen ? "Close Atelier" : "Return to Home"}
          >
            <X size={20} />
          </button>
          <div className="top-brand-title">
            <span className="brand-logo-text">YORVYN</span>
            <span className="brand-sub-badge">Atelier AI</span>
          </div>
        </div>

        <div className="top-bar-right">
          {!drawerOpen ? (
            <>
              <button className="pill-action-btn dark-pill" onClick={handleShare} title="Share Outfit Look">
                <Share2 size={15} />
                <span>Share</span>
              </button>

              <button className="pill-action-btn dark-pill" onClick={handleSnap} title="Capture Studio Photo">
                <Camera size={15} />
                <span>Capture</span>
              </button>

              <button
                className="circle-control-btn"
                onClick={handleDownloadGlb}
                disabled={isExporting || loading}
                aria-label="Export GLB"
                title="Download Rigged 3D GLB Model"
              >
                <Download size={18} />
              </button>

              <button
                className="circle-control-btn mobile-only-control"
                onClick={() => setIsSettingsOpen(true)}
                aria-label="Settings"
                title="Open Studio Settings"
              >
                <SettingsIcon size={20} />
              </button>
            </>
          ) : (
            <>
              <button className="pill-action-btn primary save-solid-pill" onClick={handleSaveAvatar}>
                <span>Save Look</span>
              </button>

              <button
                className="circle-control-btn"
                onClick={handleDownloadGlb}
                disabled={isExporting || loading}
                aria-label="Export GLB"
                title="Download Rigged 3D GLB Model"
              >
                <Download size={18} />
              </button>

              <button
                className="circle-control-btn mobile-only-control"
                onClick={() => setIsSettingsOpen(true)}
                aria-label="Settings"
                title="Open Studio Settings"
              >
                <SettingsIcon size={20} />
              </button>
            </>
          )}
        </div>
      </header>

      {/* ── 3. REAL 3D AVATAR VIEWPORT ── */}
      <main className="avatar-viewport">

        {/* Floating Pet Companion */}
        {showPet && (
          <div className="floating-pet-companion">
            <div className="pet-avatar-bubble">🐶</div>
            <span className="pet-label">Yorvyn Companion</span>
          </div>
        )}

        {/* Center 3D Interactive Canvas */}
        <div className="avatar-canvas-wrapper">
          <AraAvatarViewer
            ref={viewerRef}
            character={character}
            lib={lib}
            loading={loading}
            loadingLabel={loadingStatus}
            error={error}
            showSunglasses={showSunglasses}
            viewMode={viewMode}
            onViewModeChange={setViewMode}
            onRetry={initializeEngine}
            customGarmentGlbUrl={activeCustomGarment?.glb_url || null}
            customGarmentCategory={activeCustomGarment?.category || null}
          />
        </div>

        {/* Horizontal Bottom Stadium Capsule: 5 Core Avatar Controls (Undo, Redo, Full/Half Body, Zoom In, Zoom Out) */}
        <div className="stage-bottom-pill" role="toolbar" aria-label="3D Avatar Viewport Controls">
          {/* 1. Undo */}
          <button
            className="stage-circle-action-btn"
            onClick={handleUndo}
            disabled={historyIndex <= 0}
            title="Undo (Ctrl+Z)"
            aria-label="Undo"
          >
            <RotateCcw size={19} />
            <span className="stage-circle-tooltip">Undo</span>
          </button>

          {/* 2. Redo */}
          <button
            className="stage-circle-action-btn"
            onClick={handleRedo}
            disabled={historyIndex >= history.length - 1 || historyIndex === -1}
            title="Redo (Ctrl+Y)"
            aria-label="Redo"
          >
            <RotateCw size={19} />
            <span className="stage-circle-tooltip">Redo</span>
          </button>

          {/* 3. Full Body / Half Toggle */}
          <button
            className={`stage-circle-action-btn ${viewMode === 'full' ? 'active' : ''}`}
            onClick={() => {
              const nextMode = viewMode === 'full' ? 'portrait' : 'full';
              setViewMode(nextMode);
              toast(nextMode === 'full' ? 'Full Body Stage View' : 'Half Body (Portrait) View', {
                icon: nextMode === 'full' ? '🧍' : '👤',
                duration: 1200
              });
            }}
            title={viewMode === 'portrait' ? 'Switch to Full Body' : 'Switch to Half Body (Portrait)'}
            aria-label="Toggle Full Body / Half View"
          >
            {viewMode === 'portrait' ? <Maximize2 size={19} /> : <Minimize2 size={19} />}
            <span className="stage-circle-tooltip">{viewMode === 'portrait' ? 'Full Body' : 'Half Body'}</span>
          </button>

          {/* 4. Zoom In */}
          <button
            className="stage-circle-action-btn"
            onClick={() => viewerRef.current?.zoomIn()}
            title="Zoom In"
            aria-label="Zoom In"
          >
            <ZoomIn size={19} />
            <span className="stage-circle-tooltip">Zoom In</span>
          </button>

          {/* 5. Zoom Out */}
          <button
            className="stage-circle-action-btn"
            onClick={() => viewerRef.current?.zoomOut()}
            title="Zoom Out"
            aria-label="Zoom Out"
          >
            <ZoomOut size={19} />
            <span className="stage-circle-tooltip">Zoom Out</span>
          </button>
        </div>
      </main>

      {/* ── 3. SLIDING DRAWER / BOTTOM SHEET ── */}
      <section className={`stage-drawer-card ${drawerOpen ? 'expanded' : 'collapsed'}`}>
        {/* Grab Handle Bar */}
        <button
          className="drawer-grab-handle-bar"
          onClick={() => {
            const next = !drawerOpen;
            setDrawerOpen(next);
            if (!next) window.history.replaceState(null, '', '/');
          }}
          aria-label={drawerOpen ? 'Collapse drawer' : 'Expand drawer'}
        >
          <div className="grab-pill" />
        </button>

        {/* ── COLLAPSED VIEW (Screenshot 1: "Try a new look") ── */}
        {!drawerOpen ? (
          <div className="drawer-collapsed-content" onClick={() => handleTabSwitch('fashion')}>
            <div className="try-new-look-header">
              <h3>Curated Ensembles</h3>
              <span className="curated-subtitle">Tap any piece to drape onto your 3D twin</span>
            </div>
            <div className="try-new-look-carousel">
              {TRY_NEW_LOOK_ITEMS.map(item => {
                const isSelected = selectedGarmentId === item.id;
                return (
                  <div
                    key={item.id}
                    className={`try-look-card ${isSelected ? 'selected' : ''}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleSelectGarment(item);
                    }}
                  >
                    <div className="try-look-card-img-wrap">
                      <img src={item.imageUrl} alt={item.name} className="try-look-img" />
                    </div>
                    <div className="card-currency-badge">₹</div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          /* ── EXPANDED VIEW: Feature Content Controlled Exclusively via AppSideNav ── */
          <>
            {/* ── TAB 1: FITTING ROOM & FASHION CATALOG ── */}
            {primaryTab === 'fashion' && (
              <div className="drawer-fashion-content">
                {/* Subcategories Strip */}
                <div className="drawer-subcategories-strip">
                  {[
                    { id: 'all', icon: Zap, label: 'Trending' },
                    { id: 'outfit', icon: Shirt, label: 'Outfits' },
                    { id: 'top', icon: Shirt, label: 'Tops' },
                    { id: 'bottom', icon: Layers, label: 'Bottoms' },
                    { id: 'shoes', icon: Sparkles, label: 'Shoes' },
                    { id: 'accessory', icon: Eye, label: 'Accessories' }
                  ].map(sub => {
                    const Icon = sub.icon;
                    const isActive = activeSubcat === sub.id;
                    return (
                      <button
                        key={sub.id}
                        className={`subcat-pill-btn ${isActive ? 'active' : ''}`}
                        onClick={() => setActiveSubcat(sub.id)}
                      >
                        <Icon size={20} />
                        {isActive && <span className="subcat-active-dot" />}
                      </button>
                    );
                  })}
                </div>

                {/* Brand Filter Pills */}
                <div className="drawer-brand-pills-row">
                  <button
                    className={`brand-badge-pill yorvyn-badge ${activeBrandFilter === 'yorvyn' ? 'active' : ''}`}
                    onClick={() => setActiveBrandFilter(f => f === 'yorvyn' ? 'all' : 'yorvyn')}
                  >
                    <span className="brand-mini-icon">✨</span>
                    <span>Yorvyn Haute</span>
                  </button>

                  <button
                    className={`brand-badge-pill diesel-badge ${activeBrandFilter === 'diesel' ? 'active' : ''}`}
                    onClick={() => setActiveBrandFilter(f => f === 'diesel' ? 'all' : 'diesel')}
                  >
                    <span className="diesel-tag">DIESEL</span>
                    <span>Diesel</span>
                  </button>

                  <button
                    className={`brand-badge-pill luxury-badge ${activeBrandFilter === 'ralph_lauren' ? 'active' : ''}`}
                    onClick={() => setActiveBrandFilter(f => f === 'ralph_lauren' ? 'all' : 'ralph_lauren')}
                  >
                    <span className="brand-mini-icon">👑</span>
                    <span>Quiet Luxury</span>
                  </button>

                  <button
                    className={`brand-badge-pill halloween-badge ${activeBrandFilter === 'halloween' ? 'active' : ''}`}
                    onClick={() => setActiveBrandFilter(f => f === 'halloween' ? 'all' : 'halloween')}
                  >
                    <span className="brand-mini-icon">🍂</span>
                    <span>Capsule Archive</span>
                  </button>
                </div>

                {/* Section Header */}
                <div className="drawer-section-header">
                  <h3>{activeBrandFilter === 'all' ? 'Curated Ensembles' : activeBrandFilter === 'yorvyn' ? 'Yorvyn Haute Collection' : activeBrandFilter === 'halloween' ? 'Capsule Archive' : activeBrandFilter.toUpperCase()}</h3>
                  <span className="section-counter">{filteredCatalog.length} items</span>
                </div>

                {/* Catalog Grid Cards */}
                <div className="drawer-catalog-grid">
                  {filteredCatalog.map(item => {
                    const isSelected = selectedGarmentId === item.id;
                    return (
                      <div
                        key={item.id}
                        className={`catalog-card-item ${isSelected ? 'selected' : ''}`}
                        onClick={() => handleSelectGarment(item)}
                      >
                        {item.hasBlueDot && <span className="card-notification-dot" />}
                        {isSelected && (
                          <div className="card-selected-check">
                            <Check size={11} />
                          </div>
                        )}
                        <div className="card-mannequin-preview">
                          {item.imageUrl ? (
                            <img src={item.imageUrl} alt={item.name} className="card-photo-img" />
                          ) : (
                            <Shirt size={32} color={item.color} />
                          )}
                        </div>
                        <div className="card-script-brand">{item.brand || 'Yorvyn'} <em>Atelier</em></div>
                        <div className="card-currency-badge">₹</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ── TAB 2: AI STYLIST CHAT ── */}
            {primaryTab === 'stylist' && (
              <div className="drawer-stylist-chat-view">
                {/* Quick Prompts */}
                <div className="stylist-quick-prompts">
                  {[
                    "Outfit for a 16°C rainy day",
                    "Minimalist quiet luxury look",
                    "Office smart casual with sneakers",
                    "Style my denim jeans"
                  ].map((p, idx) => (
                    <button
                      key={idx}
                      className="stylist-prompt-chip"
                      onClick={() => handleSendStylistMessage(p)}
                    >
                      <span>{p}</span>
                    </button>
                  ))}
                </div>

                {/* Message Stream */}
                <div className="stylist-message-stream">
                  {chatMessages.map(msg => (
                    <div key={msg.id} className={`stylist-bubble-wrap ${msg.sender}`}>
                      <div className="stylist-bubble-text">
                        {msg.text}
                      </div>

                      {/* Attached Outfit Recommendations */}
                      {msg.outfits && msg.outfits.length > 0 && (
                        <div className="stylist-outfit-recs">
                          {msg.outfits.map(outfit => (
                            <div key={outfit.outfit_id} className="stylist-outfit-rec-card">
                              <div className="rec-card-top">
                                <strong>{outfit.title}</strong>
                                <span className="rec-score-badge">
                                  {Math.round(outfit.match_score * 100)}% match
                                </span>
                              </div>
                              <p className="rec-desc">{outfit.styling_rationale}</p>
                              <div className="rec-actions">
                                <button
                                  className="rec-action-btn primary"
                                  onClick={() => handleDrapeOutfitOnAvatar(outfit)}
                                >
                                  <Sparkles size={14} />
                                  <span>Drape on 3D Avatar</span>
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                  {chatLoading && (
                    <div className="stylist-bubble-wrap stylist">
                      <div className="stylist-bubble-text loading-dots">
                        <span>Stylist is reviewing your digital wardrobe...</span>
                      </div>
                    </div>
                  )}
                  <div ref={chatBottomRef} />
                </div>

                {/* Chat Input */}
                <form
                  className="stylist-input-row"
                  onSubmit={(e) => { e.preventDefault(); handleSendStylistMessage(); }}
                >
                  <input
                    type="text"
                    value={chatInput}
                    onChange={e => setChatInput(e.target.value)}
                    placeholder="Ask your AI Stylist (e.g., Gala suit, Autumn layering)..."
                    className="stylist-text-input"
                  />
                  <button type="submit" className="stylist-send-btn" disabled={!chatInput.trim() || chatLoading}>
                    <Send size={16} />
                  </button>
                </form>
              </div>
            )}

            {/* ── TAB 3: DIGITAL WARDROBE ── */}
            {primaryTab === 'wardrobe' && (
              <div className="drawer-wardrobe-view">
                {/* Closet Stats & Add Action */}
                {/* Closet Stats & Add Action */}
                <div className="wardrobe-header-strip">
                  <div className="wardrobe-stats-pill">
                    <span>{wardrobeItems.length} Pieces</span>
                    <span>•</span>
                    <span>{wardrobeAnalytics ? `${Math.round(wardrobeAnalytics.closet_utilization_rate * (wardrobeAnalytics.closet_utilization_rate <= 1 ? 100 : 1))}% Used` : '92% Used'}</span>
                  </div>
                  <div className="wardrobe-actions-group">
                    <button
                      className="wardrobe-photo-3d-btn"
                      onClick={() => setIsPhotoGarmentModalOpen(true)}
                      title="Upload garment photo to generate wearable 3D clothing"
                    >
                      <Sparkles size={14} />
                      <span>Photo to 3D</span>
                    </button>
                    <button
                      className="wardrobe-add-btn"
                      onClick={() => setIsAddModalOpen(true)}
                    >
                      <Plus size={15} />
                      <span>Add Piece</span>
                    </button>
                  </div>
                </div>

                {/* Active Custom 3D Garment Indicator */}
                {activeCustomGarment && (
                  <div className="active-custom-garment-banner">
                    <div className="active-custom-garment-info">
                      <span className="active-custom-pulse" />
                      <span>Wearing 3D: <strong>{activeCustomGarment.name}</strong></span>
                    </div>
                    <button
                      className="active-custom-remove-btn"
                      onClick={() => {
                        setActiveCustomGarment(null);
                        toast.success('Unequipped custom 3D garment');
                      }}
                    >
                      Unequip
                    </button>
                  </div>
                )}

                {/* Category Filters */}
                <div className="drawer-subcategories-strip">
                  {['all', 'top', 'bottom', 'outerwear', 'footwear', 'accessory'].map(cat => (
                    <button
                      key={cat}
                      className={`subcat-pill-btn ${wardrobeCategory === cat ? 'active' : ''}`}
                      onClick={() => setWardrobeCategory(cat)}
                    >
                      <span className="cat-label">{cat.toUpperCase()}</span>
                      {wardrobeCategory === cat && <span className="subcat-active-dot" />}
                    </button>
                  ))}
                </div>

                {/* Wardrobe Grid */}
                <div className="drawer-catalog-grid">
                  {filteredWardrobe.map(item => (
                    <div
                      key={item.id}
                      className="catalog-card-item wardrobe-card"
                      onClick={() => handleDrapeWardrobePiece(item)}
                    >
                      {item.is_custom_3d && (
                        <div className="custom-3d-badge">
                          <Sparkles size={10} /> 3D
                        </div>
                      )}
                      <button
                        className={`wardrobe-heart-btn ${item.favorite ? 'active' : ''}`}
                        onClick={(e) => handleToggleFavoriteGarment(item.id, e)}
                        title="Favorite"
                      >
                        <Heart size={14} fill={item.favorite ? '#dc2626' : 'none'} color={item.favorite ? '#dc2626' : '#94a3b8'} />
                      </button>

                      <button
                        className="wardrobe-trash-btn"
                        onClick={(e) => handleDeleteGarment(item.id, e)}
                        title="Remove"
                      >
                        <Trash2 size={13} color="#94a3b8" />
                      </button>

                      <div className="card-mannequin-preview">
                        {item.thumbnail_url ? (
                          <img
                            src={item.thumbnail_url}
                            alt={item.name}
                            className="wardrobe-3d-thumb-img"
                          />
                        ) : (
                          <Shirt size={32} color={item.color || '#334155'} />
                        )}
                      </div>
                      <div className="card-item-title">{item.name}</div>
                      <div className="card-script-brand">{item.brand}</div>
                      <button className="wardrobe-wear-badge" onClick={() => handleDrapeWardrobePiece(item)}>
                        Wear on 3D
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ── TAB 4: LOOKBOOK STUDIO ── */}
            {primaryTab === 'outfits' && (
              <div className="drawer-lookbook-view">
                {/* Lookbook Context Controls */}
                <div className="lookbook-controls-bar">
                  <select
                    className="lookbook-select"
                    value={outfitOccasion}
                    onChange={e => setOutfitOccasion(e.target.value)}
                  >
                    <option value="casual_day">Casual Day</option>
                    <option value="work_office">Office / Business</option>
                    <option value="date_night">Date Night</option>
                    <option value="formal_event">Formal Event</option>
                  </select>

                  <select
                    className="lookbook-select"
                    value={outfitAesthetic}
                    onChange={e => setOutfitAesthetic(e.target.value)}
                  >
                    <option value="quiet_luxury">Quiet Luxury</option>
                    <option value="minimalist_scandi">Minimalist Scandi</option>
                    <option value="streetwear_tech">Streetwear / Tech</option>
                    <option value="smart_casual">Smart Casual</option>
                  </select>

                  <select
                    className="lookbook-select"
                    value={outfitCondition}
                    onChange={e => setOutfitCondition(e.target.value)}
                  >
                    <option value="clear">Clear / Sunny</option>
                    <option value="cloudy">Cloudy / Mild</option>
                    <option value="rain">Rain / Wet</option>
                    <option value="snow">Cold / Chilly</option>
                  </select>

                  <div className="lookbook-temp-pill">
                    <input
                      type="number"
                      min="-10"
                      max="40"
                      value={outfitTemp}
                      onChange={e => setOutfitTemp(Number(e.target.value))}
                      className="lookbook-temp-input"
                    />
                    <span>°C</span>
                  </div>

                  <button
                    className="lookbook-refresh-btn"
                    onClick={handleGenerateOutfits}
                    disabled={outfitLoading}
                  >
                    <RefreshCw size={14} className={outfitLoading ? 'spin' : ''} />
                    <span>Generate</span>
                  </button>
                </div>

                {/* Generated Outfits Carousel/List */}
                <div className="lookbook-outfits-container">
                  {generatedOutfits.map(outfit => (
                    <div key={outfit.outfit_id} className="lookbook-outfit-card">
                      <div className="outfit-card-header">
                        <h4>{outfit.title}</h4>
                        <span className="outfit-score-tag">
                          {Math.round(outfit.match_score * 100)}% Harmony
                        </span>
                      </div>
                      <p className="outfit-notes">{outfit.styling_rationale}</p>

                      {/* Color Palette Dots */}
                      <div className="outfit-palette-row">
                        {outfit.color_palette?.map((col, cIdx) => (
                          <span
                            key={cIdx}
                            className="color-dot"
                            style={{ backgroundColor: col }}
                            title={col}
                          />
                        ))}
                      </div>

                      <div className="outfit-actions-row">
                        <button
                          className="outfit-drape-btn"
                          onClick={() => handleDrapeOutfitOnAvatar(outfit)}
                        >
                          <Sparkles size={14} />
                          <span>Drape Look on 3D Avatar</span>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ── TAB 5: 3D DIGITAL TWIN & MORPHS ── */}
            {primaryTab === 'avatar' && (
              <div className="drawer-avatar-morph-view">
                {/* Avatar Sub-tabs: Body | Face | Hair | Skin */}
                <div className="avatar-subtabs-row">
                  <button
                    className={`avatar-subtab-pill ${avatarSubTab === 'body' ? 'active' : ''}`}
                    onClick={() => setAvatarSubTab('body')}
                  >
                    <User size={15} />
                    <span>Body</span>
                  </button>

                  <button
                    className={`avatar-subtab-pill ${avatarSubTab === 'face' ? 'active' : ''}`}
                    onClick={() => setAvatarSubTab('face')}
                  >
                    <Smile size={15} />
                    <span>Face</span>
                  </button>

                  <button
                    className={`avatar-subtab-pill ${avatarSubTab === 'hair' ? 'active' : ''}`}
                    onClick={() => setAvatarSubTab('hair')}
                  >
                    <Scissors size={15} />
                    <span>Hair</span>
                  </button>

                  <button
                    className={`avatar-subtab-pill ${avatarSubTab === 'skin' ? 'active' : ''}`}
                    onClick={() => setAvatarSubTab('skin')}
                  >
                    <Palette size={15} />
                    <span>Skin</span>
                  </button>
                </div>

                <div className="avatar-morph-scroll-container">
                  {/* SUBTAB: BODY */}
                  {avatarSubTab === 'body' && (
                    <div className="drawer-morph-section">
                      <div className="drawer-slider-row">
                        <div className="drawer-slider-label">
                          <span>Height</span>
                          <strong>{Math.round(155 + params.height * 40)} cm</strong>
                        </div>
                        <input
                          type="range" min="0" max="1" step="0.02"
                          value={params.height}
                          onChange={e => updateParam('height', parseFloat(e.target.value))}
                          className="drawer-range-slider"
                        />
                      </div>

                      <div className="drawer-slider-row">
                        <div className="drawer-slider-label">
                          <span>Weight / Build</span>
                          <strong>{Math.round(params.weight * 100)}%</strong>
                        </div>
                        <input
                          type="range" min="0" max="1" step="0.02"
                          value={params.weight}
                          onChange={e => updateParam('weight', parseFloat(e.target.value))}
                          className="drawer-range-slider"
                        />
                      </div>

                      <div className="drawer-slider-row">
                        <div className="drawer-slider-label">
                          <span>Muscle Definition</span>
                          <strong>{Math.round(params.muscle * 100)}%</strong>
                        </div>
                        <input
                          type="range" min="0" max="1" step="0.02"
                          value={params.muscle}
                          onChange={e => updateParam('muscle', parseFloat(e.target.value))}
                          className="drawer-range-slider"
                        />
                      </div>

                      <div className="drawer-slider-row">
                        <div className="drawer-slider-label">
                          <span>Gender Presentation</span>
                          <strong>{params.gender < 0.35 ? 'Feminine' : params.gender > 0.65 ? 'Masculine' : 'Neutral'}</strong>
                        </div>
                        <input
                          type="range" min="0" max="1" step="0.05"
                          value={params.gender}
                          onChange={e => updateParam('gender', parseFloat(e.target.value))}
                          className="drawer-range-slider"
                        />
                      </div>
                    </div>
                  )}

                  {/* SUBTAB: FACE */}
                  {avatarSubTab === 'face' && (
                    <div className="drawer-morph-section">
                      <div className="drawer-slider-row">
                        <div className="drawer-slider-label">
                          <span>Face Accessories</span>
                          <strong>{showSunglasses ? 'Sunglasses On' : 'Off'}</strong>
                        </div>
                        <button
                          className={`drawer-chip-btn ${showSunglasses ? 'active' : ''}`}
                          onClick={() => setShowSunglasses(v => !v)}
                          style={{ marginTop: '0.4rem', width: '100%' }}
                        >
                          {showSunglasses && <Check size={12} />}
                          <span>{showSunglasses ? '🕶️ Dark Sunglasses (Equipped)' : 'Wear Dark Sunglasses'}</span>
                        </button>
                      </div>

                      <div className="drawer-slider-row">
                        <div className="drawer-slider-label">
                          <span>Avatar Pet Companion</span>
                          <strong>{showPet ? 'Active' : 'Off'}</strong>
                        </div>
                        <button
                          className={`drawer-chip-btn ${showPet ? 'active' : ''}`}
                          onClick={() => setShowPet(v => !v)}
                          style={{ marginTop: '0.4rem', width: '100%' }}
                        >
                          {showPet && <Check size={12} />}
                          <span>{showPet ? '🐶 Yorvyn Companion (Active)' : 'Summon Pet Companion'}</span>
                        </button>
                      </div>

                      <div className="drawer-slider-row">
                        <div className="drawer-slider-label">
                          <span>Apparent Age</span>
                          <strong>{Math.round(18 + params.age * 60)} yrs</strong>
                        </div>
                        <input
                          type="range" min="0.1" max="0.9" step="0.05"
                          value={params.age}
                          onChange={e => updateParam('age', parseFloat(e.target.value))}
                          className="drawer-range-slider"
                        />
                      </div>

                      <div className="drawer-slider-row">
                        <div className="drawer-slider-label">
                          <span>Head Angle / Breadth</span>
                          <strong>{(params.modifiers['head/head-angle'] || 0).toFixed(2)}</strong>
                        </div>
                        <input
                          type="range" min="-1" max="1" step="0.05"
                          value={params.modifiers['head/head-angle'] || 0}
                          onChange={e => updateModifier('head/head-angle', parseFloat(e.target.value))}
                          className="drawer-range-slider"
                        />
                      </div>

                      <div className="drawer-slider-row">
                        <div className="drawer-slider-label">
                          <span>Jaw Width</span>
                          <strong>{(params.modifiers['jaw/jaw-width'] || 0).toFixed(2)}</strong>
                        </div>
                        <input
                          type="range" min="-1" max="1" step="0.05"
                          value={params.modifiers['jaw/jaw-width'] || 0}
                          onChange={e => updateModifier('jaw/jaw-width', parseFloat(e.target.value))}
                          className="drawer-range-slider"
                        />
                      </div>
                    </div>
                  )}

                  {/* SUBTAB: HAIR */}
                  {avatarSubTab === 'hair' && (
                    <div className="drawer-morph-section">
                      <div className="drawer-chips-wrap">
                        {[
                          { id: 'short01', name: 'Short Textured Fringe' },
                          { id: 'undercut01', name: 'Clean Modern Undercut' },
                          { id: 'bob01', name: 'Sleek French Bob' },
                          { id: 'curly01', name: 'Natural Curls' },
                          { id: 'ponytail01', name: 'High Ponytail' }
                        ].map(h => (
                          <button
                            key={h.id}
                            className={`drawer-chip-btn ${params.hair === h.id ? 'active' : ''}`}
                            onClick={() => updateParam('hair', h.id)}
                          >
                            {params.hair === h.id && <Check size={12} />}
                            <span>{h.name}</span>
                          </button>
                        ))}
                      </div>

                      <div className="drawer-swatches-wrap">
                        {[
                          { id: 'black', hex: '#1e1b18', name: 'Ebony Black' },
                          { id: 'darkbrown', hex: '#3b2f2f', name: 'Dark Brown' },
                          { id: 'chestnut', hex: '#5c4033', name: 'Chestnut' },
                          { id: 'blonde', hex: '#e4c988', name: 'Golden Blonde' },
                          { id: 'silver', hex: '#cbd5e1', name: 'Platinum Silver' }
                        ].map(c => (
                          <button
                            key={c.id}
                            className={`drawer-color-swatch ${params.hairColor === c.hex ? 'active' : ''}`}
                            style={{ backgroundColor: c.hex }}
                            onClick={() => updateParam('hairColor', c.hex)}
                            title={c.name}
                          >
                            {params.hairColor === c.hex && <Check size={12} color="#fff" />}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* SUBTAB: SKIN */}
                  {avatarSubTab === 'skin' && (
                    <div className="drawer-morph-section">
                      <div className="drawer-chips-wrap">
                        {[
                          { id: 'young_caucasian_male', name: 'Porcelain Fair' },
                          { id: 'young_asian_male', name: 'Warm Golden' },
                          { id: 'young_african_male', name: 'Rich Deep Bronze' },
                          { id: 'middleage_caucasian_male', name: 'Olive Tone' },
                          { id: 'young_caucasian_female', name: 'Ivory Classic' }
                        ].map(s => (
                          <button
                            key={s.id}
                            className={`drawer-chip-btn ${params.skin === s.id ? 'active' : ''}`}
                            onClick={() => updateParam('skin', s.id)}
                          >
                            {params.skin === s.id && <Check size={12} />}
                            <span>{s.name}</span>
                          </button>
                        ))}
                      </div>

                      <div className="drawer-swatches-wrap">
                        {[
                          { id: 'brown', hex: '#452b1b', name: 'Brown' },
                          { id: 'deepblue', hex: '#1e3a8a', name: 'Deep Blue' },
                          { id: 'green', hex: '#15803d', name: 'Green' },
                          { id: 'grey', hex: '#64748b', name: 'Grey' },
                          { id: 'ice', hex: '#38bdf8', name: 'Ice' }
                        ].map(eye => (
                          <button
                            key={eye.id}
                            className={`drawer-color-swatch ${params.eyes === eye.id ? 'active' : ''}`}
                            style={{ backgroundColor: eye.hex }}
                            onClick={() => updateParam('eyes', eye.id)}
                            title={eye.name}
                          >
                            {params.eyes === eye.id && <Check size={12} color="#fff" />}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ── TAB 6: PERSONAL PROFILE ── */}
            {primaryTab === 'profile' && (
              <div className="drawer-profile-view">
                <div className="drawer-section-header">
                  <h3>Personal Style Identity</h3>
                  <button className="profile-save-pill" onClick={handleSaveProfile}>
                    Save Identity
                  </button>
                </div>

                <div className="profile-form-scroll">
                  {/* Color Seasons */}
                  <div className="profile-group">
                    <label>Color Season Palette</label>
                    <div className="drawer-chips-wrap">
                      {[
                        { id: 'autumn', name: '🍂 Autumn (Warm & Deep)' },
                        { id: 'spring', name: '🌸 Spring (Warm & Bright)' },
                        { id: 'winter', name: '❄️ Winter (Cool & Vivid)' },
                        { id: 'summer', name: '☀️ Summer (Cool & Soft)' }
                      ].map(cs => (
                        <button
                          key={cs.id}
                          className={`drawer-chip-btn ${userProfile.color_season === cs.id ? 'active' : ''}`}
                          onClick={() => setUserProfile(p => ({ ...p, color_season: cs.id as any }))}
                        >
                          {userProfile.color_season === cs.id && <Check size={12} />}
                          <span>{cs.name}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Body Shapes */}
                  <div className="profile-group">
                    <label>Body Architecture</label>
                    <div className="drawer-chips-wrap">
                      {[
                        { id: 'athletic_tapered', name: 'Athletic / Tapered' },
                        { id: 'rectangle', name: 'Straight / Balanced' },
                        { id: 'hourglass', name: 'Hourglass / Curved' },
                        { id: 'inverted_triangle', name: 'Inverted Triangle' },
                        { id: 'pear', name: 'A-Frame / Pear' }
                      ].map(bs => (
                        <button
                          key={bs.id}
                          className={`drawer-chip-btn ${userProfile.body_shape === bs.id ? 'active' : ''}`}
                          onClick={() => setUserProfile(p => ({ ...p, body_shape: bs.id as any }))}
                        >
                          {userProfile.body_shape === bs.id && <Check size={12} />}
                          <span>{bs.name}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Aesthetic Personas */}
                  <div className="profile-group">
                    <label>Primary Aesthetics</label>
                    <div className="drawer-chips-wrap">
                      {[
                        { id: 'quiet_luxury', name: 'Quiet Luxury' },
                        { id: 'minimalist_scandi', name: 'Minimalist Scandi' },
                        { id: 'streetwear_tech', name: 'Tech Streetwear' },
                        { id: 'smart_casual', name: 'Smart Casual' },
                        { id: 'parisian_chic', name: 'Parisian Chic' }
                      ].map(aes => {
                        const isSelected = userProfile.primary_aesthetics?.includes(aes.id);
                        return (
                          <button
                            key={aes.id}
                            className={`drawer-chip-btn ${isSelected ? 'active' : ''}`}
                            onClick={() => {
                              const curr = userProfile.primary_aesthetics || [];
                              const next = isSelected ? curr.filter(x => x !== aes.id) : [...curr, aes.id];
                              setUserProfile(p => ({ ...p, primary_aesthetics: next }));
                            }}
                          >
                            {isSelected && <Check size={12} />}
                            <span>{aes.name}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </section>

      {/* ── 4. ADD GARMENT MODAL ── */}
      {isAddModalOpen && (
        <div className="avatar-modal-backdrop" onClick={() => setIsAddModalOpen(false)}>
          <div className="avatar-modal-card" onClick={e => e.stopPropagation()}>
            <div className="modal-top">
              <h3>Digitize New Garment</h3>
              <button className="modal-close-btn" onClick={() => setIsAddModalOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleAddGarment} className="modal-form">
              <div className="form-item">
                <label>Piece Name</label>
                <input
                  type="text"
                  value={newGarmentName}
                  onChange={e => setNewGarmentName(e.target.value)}
                  placeholder="e.g. Cashmere Knit, Leather Biker"
                  className="modal-input"
                  required
                />
              </div>

              <div className="form-item">
                <label>Category</label>
                <select
                  value={newGarmentCategory}
                  onChange={e => setNewGarmentCategory(e.target.value as GarmentCategory)}
                  className="modal-select"
                >
                  <option value="top">Top / Shirt</option>
                  <option value="bottom">Bottom / Jeans</option>
                  <option value="outerwear">Outerwear / Coat</option>
                  <option value="footwear">Footwear / Shoes</option>
                  <option value="accessory">Accessory</option>
                </select>
              </div>

              <div className="form-item">
                <label>Color</label>
                <input
                  type="text"
                  value={newGarmentColor}
                  onChange={e => setNewGarmentColor(e.target.value)}
                  placeholder="e.g. Black, Camel, Navy"
                  className="modal-input"
                />
              </div>

              <div className="form-item">
                <label>Brand / Atelier</label>
                <input
                  type="text"
                  value={newGarmentBrand}
                  onChange={e => setNewGarmentBrand(e.target.value)}
                  placeholder="e.g. Ralph Lauren, Diesel"
                  className="modal-input"
                />
              </div>

              <div className="form-item">
                <label>Warmth Tier (1-10): {newGarmentWarmth}</label>
                <input
                  type="range"
                  min="1"
                  max="10"
                  value={newGarmentWarmth}
                  onChange={e => setNewGarmentWarmth(Number(e.target.value))}
                  className="modal-range"
                />
              </div>

              <div className="form-item">
                <label>Formality Level (1-10): {newGarmentFormality}</label>
                <input
                  type="range"
                  min="1"
                  max="10"
                  value={newGarmentFormality}
                  onChange={e => setNewGarmentFormality(Number(e.target.value))}
                  className="modal-range"
                />
              </div>

              <div className="modal-form-actions">
                <button type="button" className="btn-secondary" onClick={() => setIsAddModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Add to Digital Closet
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── 5. SETTINGS & STYLE HUB MODAL ── */}
      {isSettingsOpen && (
        <SettingsModal
          isOpen={isSettingsOpen}
          onClose={() => setIsSettingsOpen(false)}
          currentParams={params}
          onApplyCharacterPreset={(presetParams) => {
            triggerRebuild({ ...params, ...presetParams });
          }}
        />
      )}

      {/* ── 6. PHOTO TO 3D GARMENT GENERATOR MODAL ── */}
      <PhotoTo3DGarmentModal
        isOpen={isPhotoGarmentModalOpen}
        onClose={() => setIsPhotoGarmentModalOpen(false)}
        onGarmentSaved={(_savedGarment) => {
          fashionApi.getWardrobe().then(res => {
            if (res && Array.isArray(res.items)) {
              setWardrobeItems(res.items);
            }
          }).catch(console.error);
        }}
        onWearImmediately={(savedGarment) => {
          setActiveCustomGarment(savedGarment);
          toast.success(`Wearing your new 3D ${savedGarment.name}!`, { icon: '✨' });
          araAnim.playOneShot('Cheer', 'Idle', 0.4);
        }}
      />
    </div>
  );
};
