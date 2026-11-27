import React, { useState, useEffect, useRef, useCallback, Suspense, lazy } from 'react';
import {
  X,
  ArrowCounterClockwise,
  ArrowClockwise,
  Sparkle,
  Heart,
  User,
  Check,
  TShirt,
  PaperPlaneTilt,
  Plus,
  MagnifyingGlassPlus,
  MagnifyingGlassMinus,
  ArrowsOut,
  CoatHanger,
  FloppyDisk,
  UploadSimple,
  BookmarkSimple,
  ShoppingBag,
  CaretDown,
  Trash,
  CaretLeft,
  ThumbsDown
} from '../components/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion, LayoutGroup } from 'framer-motion';
import toast from 'react-hot-toast';
import { luxuryToast } from '../utils/luxuryToast';
import { useDeviceCommands } from '../utils/deviceCommands';
import { avatarEngine as araEngine } from '../engine/ara/avatarStudioService';
import { avatarAnimationController as araAnim } from '../engine/ara/avatarAnimationController';
import { HumanParams, DEFAULT_PARAMS } from '../engine/ara/core/params';
import { Character } from '../engine/ara/core/human';
import { AssetLibrary } from '../engine/ara/core/assets';
import { AvatarStudioViewer as AraAvatarViewer, AvatarStudioViewerHandle as AraAvatarViewerHandle } from '../components/AvatarStudioViewer';
import { validateAnimatedGLBExport, type MotionState } from '../engine/motionCore';
import {
  ChatSkeleton,
  AvatarCreatorSkeleton,
  WorkflowSkeleton
} from '../components/SkeletonLoader';
import { CategoryIcon } from '../components/category/CategoryIcon';
import { wardrobeCategoryService } from '../services/wardrobeCategoryService';
import { fashionApi, invalidateApiCache } from '../services/fashionApi';
import { intelligenceApi } from '../services/intelligenceApi';
import {
  Garment,
  GarmentCategory,
  GarmentAssetType,
  ClosetAnalytics,
  Outfit,
  WardrobeCategory
} from '../types/fashion';
import { aiSessionService, type GarmentArtifact } from '../services/aiSessionService';
import { GarmentJobMessage, GarmentPhotoStrip } from '../components/ai/GarmentJobMessage';
import { useAuth } from '../context/AuthContext';
import { fittingDiagnostics } from '../utils/fittingDiagnostics';
import { profileService } from '../services/profile/profileService';
import { runSingleFlight } from '../utils/runSingleFlight';
import { 
  avatarProfileToHumanParams,
  humanParamsToAvatarProfile,
  AvatarProfile
} from '../types/avatarProfile';
import { AvatarCreatorEngine } from '../engine/avatarCreator';
import { AvatarCreatorCategory } from '../engine/avatarCreator/avatarCreatorTypes';
import { AvatarPreviewBanner } from '../components/avatarAI/AvatarPreviewBanner';
import { avatarPreviewOrchestrator } from '../engine/avatarAI/avatarPreviewOrchestrator';
import { SimulationQualityMode } from '../engine/clothPhysics';

// Dynamic progressive code splitting for heavy modals and sub-panels
const SettingsModal = lazy(() => import('../components/SettingsModal').then(m => ({ default: m.SettingsModal })));
const PhotoTo3DGarmentModal = lazy(() => import('../components/PhotoTo3DGarmentModal').then(m => ({ default: m.PhotoTo3DGarmentModal })));
const CategoryManagerModal = lazy(() => import('../components/category/CategoryManagerModal').then(m => ({ default: m.CategoryManagerModal })));
const AvatarCreatorStudio = lazy(() => import('../components/avatarCreator/AvatarCreatorStudio').then(m => ({ default: m.AvatarCreatorStudio })));
import type {
  FashionProfileManager,
  FashionFeedbackManager,
  AIStylistConversationManager,
  DislikeReason
} from '../engine/stylistAI';
import './AvatarStudio.css';

export type PoseType = 'standing' | 'crossed_arms' | 'hands_pockets';
export type SceneType = 'studio' | 'sky_clouds' | 'sunset' | 'night';
export type PrimaryTab = 'fashion' | 'stylist' | 'wardrobe' | 'outfits' | 'avatar' | 'profile' | 'settings';
export type PrimaryNavSection = 'fashion' | 'wardrobe' | 'avatar';
export type AvatarSubTab = 'body' | 'face' | 'hair' | 'skin';
export type StudioSourceMode = 'catalog' | 'wardrobe' | 'avatar';
export type TrayPreset = 'compact' | 'default' | 'expanded' | 'custom';

export interface SecondaryCategoryItem {
  id: string;
  label: string;
  iconKey: string;
  isCustom?: boolean;
}

export const FASHION_SECONDARY_CATEGORIES: SecondaryCategoryItem[] = [
  { id: 'all', label: 'All', iconKey: 'SquaresFour' },
  { id: 'tops', label: 'Tops', iconKey: 'CoatHanger' },
  { id: 'shirts', label: 'Shirts', iconKey: 'CoatHanger' },
  { id: 't-shirts', label: 'T-shirts', iconKey: 'TShirt' },
  { id: 'hoodies', label: 'Hoodies', iconKey: 'TShirt' },
  { id: 'outerwear', label: 'Outerwear', iconKey: 'CoatHanger' },
  { id: 'jackets', label: 'Jackets', iconKey: 'CoatHanger' },
  { id: 'bottoms', label: 'Bottoms', iconKey: 'Pants' },
  { id: 'trousers', label: 'Trousers', iconKey: 'Pants' },
  { id: 'jeans', label: 'Jeans', iconKey: 'Pants' },
  { id: 'shorts', label: 'Shorts', iconKey: 'Pants' },
  { id: 'dresses', label: 'Dresses', iconKey: 'Dress' },
  { id: 'skirts', label: 'Skirts', iconKey: 'Dress' },
  { id: 'shoes', label: 'Shoes', iconKey: 'Sneaker' },
  { id: 'accessories', label: 'Accessories', iconKey: 'Watch' }
];

export const WARDROBE_SECONDARY_CATEGORIES: SecondaryCategoryItem[] = [
  { id: 'all', label: 'All Items', iconKey: 'ShoppingBag' },
  { id: 'top', label: 'Tops', iconKey: 'CoatHanger' },
  { id: 'bottom', label: 'Bottoms', iconKey: 'Pants' },
  { id: 'outerwear', label: 'Outerwear', iconKey: 'CoatHanger' },
  { id: 'footwear', label: 'Shoes', iconKey: 'Sneaker' },
  { id: 'accessory', label: 'Accessories', iconKey: 'Watch' },
  { id: 'saved_outfits', label: 'Saved Outfits', iconKey: 'BookmarkSimple' },
  { id: 'collections', label: 'Collections', iconKey: 'Package' }
];

export const AVATAR_SECONDARY_CATEGORIES: Array<{
  id: AvatarCreatorCategory;
  label: string;
  iconKey: string;
}> = [
  { id: 'body', label: 'Body', iconKey: 'ArrowsOut' },
  { id: 'face', label: 'Face', iconKey: 'User' },
  { id: 'hair', label: 'Hair', iconKey: 'Scissors' },
  { id: 'skin', label: 'Skin', iconKey: 'Palette' },
  { id: 'eyes', label: 'Eyes', iconKey: 'Eye' },
  { id: 'eyebrows', label: 'Eyebrows', iconKey: 'Eye' },
  { id: 'nose', label: 'Nose', iconKey: 'SlidersHorizontal' },
  { id: 'mouth', label: 'Lips', iconKey: 'Smiley' },
  { id: 'facial_hair', label: 'Facial Hair', iconKey: 'User' },
  { id: 'accessories', label: 'Accessories', iconKey: 'Watch' },
  { id: 'expressions', label: 'Expressions', iconKey: 'Smiley' }
];

export interface PrimaryNavSectionMeta {
  id: PrimaryNavSection;
  label: string;
  icon: React.ComponentType<any>;
}

export const PRIMARY_NAV_SECTIONS: PrimaryNavSectionMeta[] = [
  { id: 'fashion', label: 'Fashion', icon: CoatHanger },
  { id: 'wardrobe', label: 'Wardrobe', icon: ShoppingBag },
  { id: 'avatar', label: 'Avatar', icon: User }
];

export const getPresetWidth = (preset: TrayPreset, winW = typeof window !== 'undefined' ? window.innerWidth : 1440): number => {
  // Controlled desktop sizing adhering to Section 4:
  // Default: 380–420px (target 400px), Min: 340px, Max: 460px
  if (preset === 'compact') {
    return 340;
  }
  if (preset === 'expanded') {
    return 460;
  }
  // Default preset: responsive 380px–420px based on available display width
  if (winW <= 1024) return 360;
  if (winW <= 1280) return 380;
  if (winW >= 1920) return 420;
  return 400; // Standard 1440px desktop
};

import {
  FashionCatalogItem,
  FASHION_CATALOG,
  CURATED_ENSEMBLES,
  DEFAULT_FALLBACK_WARDROBE,
  TRY_NEW_LOOK_ITEMS,
  OUTFIT_SUGGESTIONS,
  OutfitSuggestionItem
} from '../data/fashionCatalogData';
export type { FashionCatalogItem, OutfitSuggestionItem };

export interface InspectedItem {
  id: string;
  name: string;
  brand?: string;
  category: string;
  subcategory?: string;
  color?: string;
  material?: string;
  userNotes?: string;
  priceDisplay?: string;
  imageUrl?: string;
  thumbnailUrl?: string;
  galleryImages?: string[];
  assetType: GarmentAssetType;
  appliedParams?: Partial<HumanParams>;
  isCustom?: boolean;
  wearCount?: number;
}

export interface SavedOutfit {
  id: string;
  title: string;
  date: string;
  tag: string;
  imageUrl?: string;
  isCustom?: boolean;
  appliedParams: Partial<HumanParams>;
}


export interface ActiveOutfitState {
  slotType: 'full_outfit' | 'separate_layers';
  fullOutfitId?: string | null;
  ensembleId?: string | null;
  topId?: string | null;
  bottomId?: string | null;
  shoesId?: string | null;
  outerwearId?: string | null;
  accessories: string[];
  custom3DGarment?: Garment | null;
  displayNames: {
    fullOutfit?: string;
    ensemble?: string;
    top?: string;
    bottom?: string;
    shoes?: string;
    outerwear?: string;
    custom3D?: string;
  };
}

export type EquippedOutfitState = ActiveOutfitState;

interface ChatMessage {
  garment?: GarmentArtifact;
  session?: string;
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
  const { user, profile, session: signedInSession } = useAuth();

  // 3D Engine State
  const [lib, setLib] = useState<AssetLibrary | null>(null);
  const [character, setCharacter] = useState<Character | null>(null);
  const [engineReady, setEngineReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingStatus, setLoadingStatus] = useState('Connecting to 3D Anatomy Catalog...');
  const [error, setError] = useState<string | null>(null);
  const engineInitializationRef = useRef<Promise<void> | null>(null);

  // Active Parameters & History
  const [params, setParams] = useState<HumanParams>(() => {
    const savedChar = typeof window !== 'undefined' ? localStorage.getItem('yorvyn_avatar_character') : null;
    const isGirl = savedChar === 'girl' || savedChar === 'female';
    if (isGirl) {
      return {
        ...DEFAULT_PARAMS,
        name: 'Elena (Girl Avatar)',
        gender: 0.0,
        age: 0.25,
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
      name: 'Yorvyn Digital Model',
      gender: 0.95,
      age: 0.25,
      muscle: 0.55,
      weight: 0.45,
      height: 0.65,
      proportions: 0.85,
      skin: 'young_asian_male',
      skinTint: '#ffffff',
      hair: 'short02',
      hairColor: '#1e293b',
      facialHair: 'none',
      outfit: 'male_elegantsuit01',
      top: 'none',
      bottom: 'none',
      shoes: 'shoes02',
      garmentStyles: {},
      eyebrows: 'eyebrow001',
      eyelashes: 'eyelashes01',
      eyes: 'brownlight'
    };
  });
  const [history, setHistory] = useState<HumanParams[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);

  // Device & Platform Adaptive Commands
  const deviceCommands = useDeviceCommands();

  // Studio Stage States (Crisp White Studio Canvas)
  const [scene] = useState<SceneType>('studio');
  const [drawerOpen, setDrawerOpen] = useState<boolean>(true);
  const [viewMode, setViewMode] = useState<'full' | 'portrait'>('full');
  const [showSunglasses, setShowSunglasses] = useState(false);
  const [showPet] = useState(false);
  const [primaryTab, setPrimaryTab] = useState<PrimaryTab>(defaultTab || 'fashion');

  // ── Two-Level Tray Navigation Architecture ──
  // Exactly THREE primary navigation sections: Fashion, Wardrobe, Avatar
  const [activePrimaryTab, setActivePrimaryTab] = useState<PrimaryNavSection>(() => {
    if (defaultTab === 'wardrobe') return 'wardrobe';
    if (defaultTab === 'avatar') return 'avatar';
    return 'fashion';
  });

  // ── Morphing Exclusive Primary Navigation State ──
  // One state: null | 'fashion' | 'wardrobe' | 'avatar'
  // Initially null: all three controls appear as individual circular icon buttons
  const [expandedPrimarySection, setExpandedPrimarySection] = useState<PrimaryNavSection | null>(null);

  // Independent secondary navigation state (preserves selection across primary tab switches)
  const [activeFashionCategory, setActiveFashionCategory] = useState<string>('tops');
  const [activeWardrobeCategory, setActiveWardrobeCategory] = useState<string>('all');
  const [activeAvatarCategory, setActiveAvatarCategory] = useState<AvatarCreatorCategory>('hair');

  const [selectedGarmentId, setSelectedGarmentId] = useState<string>('relaxed-shirt');
  const [isExporting, setIsExporting] = useState(false);
  const [motionPreviewState, setMotionPreviewState] = useState<MotionState>('IDLE');
  const [motionPaused, setMotionPaused] = useState(false);
  const [inspectedItem, setInspectedItem] = useState<InspectedItem | null>(null);

  // Customizable Wardrobe Categories & Favorites State
  const [categories, setCategories] = useState<WardrobeCategory[]>(() =>
    wardrobeCategoryService.getCategories(user?.id)
  );
  const [favorites, setFavorites] = useState<Set<string>>(() => {
    try {
      const saved = typeof window !== 'undefined' ? localStorage.getItem('yorvyn_favorites') : null;
      return saved ? new Set(JSON.parse(saved)) : new Set(['relaxed-shirt', 'oversized-hoodie', 'denim-jacket']);
    } catch {
      return new Set(['relaxed-shirt', 'oversized-hoodie', 'denim-jacket']);
    }
  });

  const toggleFavorite = (itemId: string) => {
    setFavorites(prev => {
      const next = new Set(prev);
      if (next.has(itemId)) {
        next.delete(itemId);
        luxuryToast.favorite('Removed from favorites', false);
      } else {
        next.add(itemId);
        luxuryToast.favorite('Saved to favorites', true);
      }
      try {
        localStorage.setItem('yorvyn_favorites', JSON.stringify(Array.from(next)));
      } catch {
        // ignore
      }
      return next;
    });
  };

  useEffect(() => {
    const unsub = wardrobeCategoryService.subscribe(() => {
      setCategories(wardrobeCategoryService.getCategories(user?.id));
    });
    return unsub;
  }, [user?.id]);
  const [equippedOutfit, setEquippedOutfit] = useState<ActiveOutfitState>({
    slotType: 'full_outfit',
    fullOutfitId: 'sig-polo',
    topId: null,
    bottomId: null,
    shoesId: 'shoes01',
    outerwearId: null,
    accessories: [],
    custom3DGarment: null,
    displayNames: {
      fullOutfit: 'Minimalist Midnight Relaxed Suit'
    }
  });
  const [clothQuality] = useState<SimulationQualityMode>('balanced');

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
  const [garmentPhotos, setGarmentPhotos] = useState<File[]>([]);
  const [garmentBusy, setGarmentBusy] = useState('');
  const garmentOwner = useRef(user?.id);
  garmentOwner.current = user?.id;
  const garmentSession = useRef<string>();
  const garmentPending = useRef(false);
  const lastGarment = useRef<GarmentArtifact>();
  useEffect(() => {
    let active = true;
    lastGarment.current = undefined;
    garmentSession.current = undefined;
    setGarmentPhotos([]);
    setActiveCustomGarment(null);
    setChatMessages(prev => prev.filter(m => m.id === 'init_1'));
    if (!user?.id) return;
    const sid = localStorage.getItem('yorvyn_garment_chat_' + user.id);
    if (sid) {
      garmentSession.current = sid;
      const restore = async () => {
        let cursor: string | undefined;
        const restored: ChatMessage[] = [];
        do {
          const page = await aiSessionService.getSessionMessages(sid, 100, cursor);
          if (!active) return;
          for (const m of page.items) {
            restored.push({id:m.id, sender:m.role === 'user' ? 'user' : 'stylist',
              text:m.content, session:sid, garment:m.metadata?.garment});
          }
          cursor = page.next_cursor;
        } while (cursor);
        const latest = restored.filter(m=>m.garment).pop()?.garment;
        if (!lastGarment.current) lastGarment.current = latest;
        setChatMessages(prev=>[...prev.slice(0,1), ...restored, ...prev.slice(1).filter(m=>!restored.some(r=>r.id===m.id))]);
      };
      restore().catch(()=>{ if(active) toast.error('Could not restore the garment conversation.'); });
    }
    return () => {active=false;};
  }, [user?.id]);
  const chatBottomRef = useRef<HTMLDivElement>(null);
  const profileManagerRef = useRef<FashionProfileManager | null>(null);
  const feedbackManagerRef = useRef<FashionFeedbackManager | null>(null);
  const conversationManagerRef = useRef<AIStylistConversationManager | null>(null);
  const ensureStylistEngine = useCallback(async () => {
    if (!profileManagerRef.current || !feedbackManagerRef.current || !conversationManagerRef.current) {
      const stylistEngine = await import('../engine/stylistAI');
      if (!profileManagerRef.current) {
        profileManagerRef.current = new stylistEngine.FashionProfileManager();
        feedbackManagerRef.current = new stylistEngine.FashionFeedbackManager(profileManagerRef.current);
        conversationManagerRef.current = new stylistEngine.AIStylistConversationManager();
      }
      return stylistEngine;
    }
    return import('../engine/stylistAI');
  }, []);

  // ── Digital Wardrobe State ──
  const [wardrobeItems, setWardrobeItems] = useState<Garment[]>([]);
  const [wardrobeAnalytics, setWardrobeAnalytics] = useState<ClosetAnalytics | null>(null);
  const [newGarmentName, setNewGarmentName] = useState('');
  const [newGarmentCategory, setNewGarmentCategory] = useState<GarmentCategory>('top');
  const [newGarmentColor, setNewGarmentColor] = useState('black');
  const [newGarmentBrand, setNewGarmentBrand] = useState('Yorvyn Atelier');
  const [newGarmentWarmth, setNewGarmentWarmth] = useState(5);
  const [newGarmentFormality, setNewGarmentFormality] = useState(5);
  const [newGarmentImage, setNewGarmentImage] = useState<string>('');
  const [newGarmentImageName, setNewGarmentImageName] = useState<string>('');
  const [newGarmentInputMode, setNewGarmentInputMode] = useState<'upload' | 'url'>('upload');
  const garmentFileInputRef = useRef<HTMLInputElement>(null);

  // ── In-Tray Embedded Workflows (Strictly inside right tray, zero popups) ──
  const [trayWorkflow, setTrayWorkflow] = useState<'none' | 'photo3d' | 'addPiece' | 'categories' | 'profile' | 'stylist'>('none');
  const openPhoto3DWorkflow = () => { setTrayWorkflow('photo3d'); setInspectedItem(null); };
  const openAddPieceWorkflow = () => { setTrayWorkflow('addPiece'); setInspectedItem(null); };
  const openCategoriesWorkflow = () => { setTrayWorkflow('categories'); setInspectedItem(null); };
  const openStylistWorkflow = () => {
    if (trayWorkflow === 'stylist') {
      closeTrayWorkflow();
    } else {
      setTrayWorkflow('stylist');
      setInspectedItem(null);
      setDrawerOpen(true);
      if (location.pathname !== '/stylist') {
        window.history.pushState(null, '', '/stylist');
      }
    }
  };

  const closeTrayWorkflow = () => {
    const closingWorkflow = trayWorkflow;
    setTrayWorkflow('none');
    if ((closingWorkflow === 'stylist' || closingWorkflow === 'profile') && location.pathname !== '/') {
      navigate('/');
    }
  };

  // ── Photo to 3D Custom Garment State ──
  const [activeCustomGarment, setActiveCustomGarment] = useState<Garment | null>(null);
  const chatTryOnUrl = useRef<string | null>(null);
  useEffect(() => {
    const url = activeCustomGarment?.glb_url;
    if (url && url === chatTryOnUrl.current) return () => URL.revokeObjectURL(url);
  }, [activeCustomGarment?.glb_url]);

  // ── Lookbook Studio State ──
  const [generatedOutfits, setGeneratedOutfits] = useState<Outfit[]>([]);
  const [outfitOccasion, setOutfitOccasion] = useState('casual_day');
  const [outfitTemp, setOutfitTemp] = useState(18);
  const [outfitCondition, setOutfitCondition] = useState('clear');
  const [outfitAesthetic, setOutfitAesthetic] = useState('quiet_luxury');
  const [outfitLoading, setOutfitLoading] = useState(false);

  // ── Progressive Wardrobe Windowing (Stage 3) ──
  const [visibleWardrobeCount, setVisibleWardrobeCount] = useState(10);
  const wardrobeSentinelRef = useRef<HTMLDivElement | null>(null);

  // ── Streamlined Fashion State: Saved Outfits & AI Recommendations Only ──
  const [fashionFilterTab, setFashionFilterTab] = useState<'saved' | 'ai'>('saved');
  const [aiOccasionFilter, setAiOccasionFilter] = useState<string>('all');
  const [savedOutfits, setSavedOutfits] = useState<SavedOutfit[]>(() => {
    try {
      const stored = typeof window !== 'undefined' ? localStorage.getItem('yorvyn_saved_outfits') : null;
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {
      // fallback
    }
    return CURATED_ENSEMBLES.map(c => ({
      id: c.id,
      title: c.name,
      date: 'Curated Ensemble',
      tag: c.collection === 'quiet_luxury' ? 'Quiet Luxury' : 'Ensemble',
      imageUrl: c.imageUrl,
      isCustom: false,
      appliedParams: c.appliedParams
    }));
  });


  // ── Resizable Tray & Presets State ──
  const userStoragePrefix = user?.id ? `yorvyn_tray_${user.id}` : 'yorvyn_tray';

  const [trayPreset, setTrayPreset] = useState<TrayPreset>(() => {
    if (typeof window === 'undefined') return 'default';
    const saved = localStorage.getItem(`${userStoragePrefix}_preset`) || localStorage.getItem('yorvyn_tray_preset');
    if (saved === 'compact' || saved === 'default' || saved === 'expanded' || saved === 'custom') {
      return saved as TrayPreset;
    }
    return 'default';
  });

  const [trayWidth, setTrayWidth] = useState<number>(() => {
    if (typeof window === 'undefined') return 520;
    const winW = window.innerWidth;
    const savedPreset = (localStorage.getItem(`${userStoragePrefix}_preset`) || localStorage.getItem('yorvyn_tray_preset')) as TrayPreset | null;
    const savedWidth = localStorage.getItem(`${userStoragePrefix}_width_px`) || localStorage.getItem('yorvyn_tray_width_px');

    if (savedPreset && savedPreset !== 'custom') {
      return getPresetWidth(savedPreset, winW);
    }
    if (savedWidth) {
      const parsed = parseInt(savedWidth, 10);
      const minW = 340;
      const maxW = 460;
      if (!isNaN(parsed) && parsed >= minW && parsed <= maxW) {
        return parsed;
      }
    }
    return getPresetWidth('default', winW);
  });

  const [isResizingTray, setIsResizingTray] = useState(false);
  const isResizingRef = useRef(false);

  // Synchronize tray width when window resizes
  useEffect(() => {
    const handleWindowResize = () => {
      const winW = window.innerWidth;
      if (winW < 900) return;
      const minW = 340;
      const maxW = 460;

      setTrayWidth(currentW => {
        if (trayPreset !== 'custom') {
          return getPresetWidth(trayPreset, winW);
        }
        return Math.max(minW, Math.min(maxW, currentW));
      });
    };

    window.addEventListener('resize', handleWindowResize);
    return () => window.removeEventListener('resize', handleWindowResize);
  }, [trayPreset]);

  const saveWidthAndPreset = (width: number, preset: TrayPreset) => {
    try {
      localStorage.setItem(`${userStoragePrefix}_width_px`, width.toString());
      localStorage.setItem(`${userStoragePrefix}_preset`, preset);
      localStorage.setItem('yorvyn_tray_width_px', width.toString());
      localStorage.setItem('yorvyn_tray_preset', preset);
    } catch {}
  };

  const applyPreset = (preset: 'compact' | 'default' | 'expanded') => {
    const w = getPresetWidth(preset);
    setTrayWidth(w);
    setTrayPreset(preset);
    saveWidthAndPreset(w, preset);
    toast.success(`${preset.charAt(0).toUpperCase() + preset.slice(1)} Panel (${w}px)`, {
      duration: 1200
    });
  };

  const handleResetToDefault = () => {
    applyPreset('default');
  };

  const handleResizeStart = () => {
    isResizingRef.current = true;
    setIsResizingTray(true);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const onMove = (currentX: number) => {
      if (!isResizingRef.current) return;
      const winW = window.innerWidth;
      const minW = 340;
      const maxW = Math.min(720, winW - 480);
      const newWidth = Math.round(winW - currentX);
      const clampedWidth = Math.max(minW, Math.min(maxW, newWidth));
      setTrayWidth(clampedWidth);
      setTrayPreset('custom');
    };

    const handleMouseMove = (e: MouseEvent) => {
      onMove(e.clientX);
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (e.touches.length > 0) {
        onMove(e.touches[0].clientX);
      }
    };

    const handleEnd = () => {
      isResizingRef.current = false;
      setIsResizingTray(false);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleEnd);
      window.removeEventListener('touchmove', handleTouchMove);
      window.removeEventListener('touchend', handleEnd);

      setTrayWidth(finalW => {
        saveWidthAndPreset(finalW, 'custom');
        return finalW;
      });
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleEnd);
    window.addEventListener('touchmove', handleTouchMove);
    window.addEventListener('touchend', handleEnd);
  };

  const handleMouseDownResize = (e: React.MouseEvent) => {
    e.preventDefault();
    handleResizeStart();
  };

  const handleTouchStartResize = (e: React.TouchEvent) => {
    if (e.touches.length > 0) {
      handleResizeStart();
    }
  };

  const handleKeyDownResize = (e: React.KeyboardEvent) => {
    const winW = window.innerWidth;
    const minW = Math.max(320, Math.round(winW * 0.22));
    const maxW = Math.min(Math.round(winW * 0.65), winW - 380);
    const step = e.shiftKey ? 40 : 16;

    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      setTrayWidth(w => {
        const next = Math.min(maxW, w + step);
        saveWidthAndPreset(next, 'custom');
        return next;
      });
      setTrayPreset('custom');
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      setTrayWidth(w => {
        const next = Math.max(minW, w - step);
        saveWidthAndPreset(next, 'custom');
        return next;
      });
      setTrayPreset('custom');
    } else if (e.key === 'Home') {
      e.preventDefault();
      applyPreset('compact');
    } else if (e.key === 'End') {
      e.preventDefault();
      applyPreset('expanded');
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      applyPreset('default');
    }
  };

  // Debounced Rebuild timer
  const buildDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const viewerRef = useRef<AraAvatarViewerHandle>(null);
  const creatorEngineRef = useRef<AvatarCreatorEngine>(new AvatarCreatorEngine());

  const handleCreatorProfileChange = useCallback((newProfile: AvatarProfile) => {
    const newParams = avatarProfileToHumanParams(newProfile);
    setParams(newParams);
    setShowSunglasses(Boolean(newProfile.wardrobe.sunglasses));

    if (buildDebounceRef.current) {
      clearTimeout(buildDebounceRef.current);
    }

    buildDebounceRef.current = setTimeout(async () => {
      try {
        const built = await araEngine.generateCharacter(newParams);
        setCharacter(built);
      } catch (err) {
        console.warn('[AvatarCreator] 3D mesh morph update error:', err);
      }
    }, 120);
  }, []);

  // Connect AvatarPreviewOrchestrator to creatorEngineRef and sync live 3D preview
  useEffect(() => {
    avatarPreviewOrchestrator.setCreatorEngine(creatorEngineRef.current);
    const unsubscribe = avatarPreviewOrchestrator.subscribe((previewState) => {
      if (previewState.isPreviewActive) {
        const effective = avatarPreviewOrchestrator.getEffectiveProfile();
        if (effective) {
          handleCreatorProfileChange(effective);
        }
      }
    });
    return unsubscribe;
  }, [handleCreatorProfileChange]);

  // Synchronize primaryTab with the 4 Core Unified Hubs
  useEffect(() => {
    const path = location.pathname;
    let tab: PrimaryTab = defaultTab;
    if (path.startsWith('/stylist')) {
      tab = 'stylist';
      setTrayWorkflow('stylist');
      setInspectedItem(null);
      setExpandedPrimarySection(null);
    } else if (path.startsWith('/profile') || path.startsWith('/settings')) {
      tab = 'profile';
      setTrayWorkflow('profile');
      setInspectedItem(null);
      setExpandedPrimarySection(null);
    } else if (path.startsWith('/wardrobe')) {
      tab = 'wardrobe';
      setActivePrimaryTab('wardrobe');
      setExpandedPrimarySection('wardrobe');
      setTrayWorkflow('none');
      setInspectedItem(null);
    } else if (path.startsWith('/outfits')) {
      tab = 'outfits';
      setActivePrimaryTab('fashion');
      setExpandedPrimarySection('fashion');
      setTrayWorkflow('none');
      setInspectedItem(null);
    } else if (path.startsWith('/twin') || path.startsWith('/avatar')) {
      tab = 'avatar';
      setActivePrimaryTab('avatar');
      setExpandedPrimarySection('avatar');
      setTrayWorkflow('none');
      setInspectedItem(null);
    } else {
      tab = 'fashion';
      setActivePrimaryTab('fashion');
      setExpandedPrimarySection(null);
      setTrayWorkflow('none');
      setInspectedItem(null);
    }

    setPrimaryTab(tab);
    setDrawerOpen(true);
  }, [location.pathname, defaultTab]);

  // Morphing animation physics:
  // Smooth, luxurious Apple-inspired easing (duration: 0.52s, ease: [0.16, 1, 0.3, 1])
  // Replaces harsh popping spring physics with a graceful, unhurried glide
  const prefersReducedMotion = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const morphTransition = prefersReducedMotion
    ? { duration: 0 }
    : { duration: 0.52, ease: [0.16, 1, 0.3, 1] };

  // Morphing Exclusive Navigation Toggle:
  // - If clicked section is collapsed, expand it into capsule and collapse any other section
  // - If clicked section is already expanded, collapse it back into a circle (null)
  // - Only ONE section expanded at any time
  const handlePrimaryToggle = (section: PrimaryNavSection) => {
    if (trayWorkflow !== 'none' || inspectedItem) {
      setTrayWorkflow('none');
      setInspectedItem(null);
    }
    if (expandedPrimarySection === section) {
      setExpandedPrimarySection(null);
    } else {
      setExpandedPrimarySection(section);
      setActivePrimaryTab(section);
      setPrimaryTab(section);
      setDrawerOpen(true);

      if (section === 'fashion') {
        window.history.replaceState(null, '', '/');
      } else if (section === 'wardrobe') {
        window.history.replaceState(null, '', '/wardrobe');
      } else if (section === 'avatar') {
        window.history.replaceState(null, '', '/avatar');
        viewerRef.current?.focusFullBody?.();
      }
    }
  };

  // Avatar Secondary Category Select with camera framing adaptation
  const handleAvatarCategorySelect = (catId: AvatarCreatorCategory) => {
    setActiveAvatarCategory(catId);
    if (['face', 'hair', 'skin', 'eyes', 'eyebrows', 'nose', 'mouth', 'facial_hair'].includes(catId)) {
      viewerRef.current?.focusHead?.();
    } else if (catId === 'accessories') {
      viewerRef.current?.focusTorso?.();
    } else {
      viewerRef.current?.focusFullBody?.();
    }
  };

  // Switch tabs & update URL cleanly without unmounting avatar stage
  const handleTabSwitch = (tab: PrimaryTab) => {
    setPrimaryTab(tab);
    if (tab === 'fashion' || tab === 'wardrobe' || tab === 'avatar') {
      setActivePrimaryTab(tab);
    }
    setDrawerOpen(true);
    if (tab === 'fashion') navigate('/');
    else if (tab === 'profile') navigate('/profile');
    else if (tab === 'settings') navigate('/settings');
    else navigate(`/${tab}`);
  };

  // 1. Initialize Engine & Load Backend Context
  const initializeEngine = useCallback(() => {
    // React StrictMode replays mount effects in development. Share an in-flight
    // initialization so the shared Ara engine and first avatar are built once.
    return runSingleFlight(engineInitializationRef, async () => {
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
        age: 0.25,
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
        name: 'Yorvyn Digital Model',
        gender: 0.95,
        age: 0.25,
        muscle: 0.55,
        weight: 0.45,
        height: 0.65,
        proportions: 0.85,
        skin: 'young_asian_male',
        skinTint: '#ffffff',
        hair: 'short02',
        hairColor: '#1e293b',
        facialHair: 'none',
        outfit: 'male_elegantsuit01',
        top: 'none',
        bottom: 'none',
        shoes: 'shoes02',
        garmentStyles: {},
        eyebrows: 'eyebrow001',
        eyelashes: 'eyelashes01',
        eyes: 'brownlight'
      };

      try {
        const profile = await profileService.getAvatarProfile(user?.id || '');
        if (profile) {
          const loadedParams = avatarProfileToHumanParams(profile);
          initialParams = {
            ...initialParams,
            ...loadedParams,
            modifiers: { ...(initialParams.modifiers || {}), ...(loadedParams.modifiers || {}) }
          };
        } else {
          const saved = await fashionApi.getAvatarConfig();
          if (saved && saved.gender !== undefined) {
            initialParams = {
              ...initialParams,
              ...saved,
              modifiers: { ...(initialParams.modifiers || {}), ...(saved.modifiers || {}) }
            };
          }
        }
      } catch (err) {
        console.warn('Using baseline params', err);
      }

      setParams(initialParams);
      setHistory([initialParams]);
      setHistoryIndex(0);
      creatorEngineRef.current.setProfile(humanParamsToAvatarProfile(initialParams, user?.id), true);

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
    });
  }, []);

  useEffect(() => {
    initializeEngine();
    // Phase 9: Sync Saved Looks from Backend
    fashionApi.getLooks()
      .then((looks: any[]) => {
        if (Array.isArray(looks) && looks.length > 0) {
          const mapped: SavedOutfit[] = looks.map(l => ({
            id: l.id,
            title: l.name,
            date: l.created_at ? new Date(l.created_at).toLocaleDateString() : 'Saved look',
            tag: (l.tags && l.tags[0]) || 'Custom Look',
            imageUrl: l.preview_thumbnail_url || '/items/dummy_outfit_1.png',
            isCustom: true,
            appliedParams: l.avatar_snapshot || {}
          }));
          setSavedOutfits(mapped);
          try {
            localStorage.setItem('yorvyn_saved_outfits', JSON.stringify(mapped));
          } catch {}
        }
      })
      .catch(() => {});
  }, [initializeEngine]);

  // Reload user-scoped wardrobe when authenticated session resolves or changes
  useEffect(() => {
    const uid = user?.id || 'default_user';
    fashionApi.getWardrobe(undefined, uid)
      .then(res => {
        if (res.items && res.items.length > 0) {
          setWardrobeItems(res.items);
        } else {
          setWardrobeItems(DEFAULT_FALLBACK_WARDROBE);
        }
      })
      .catch(() => {
        setWardrobeItems(DEFAULT_FALLBACK_WARDROBE);
      });
  }, [user?.id]);

  // Stage 5: On-Demand AI Outfit Generation (only executed when user enters AI Recommendations or Lookbook)
  useEffect(() => {
    if ((fashionFilterTab === 'ai' || primaryTab === 'outfits') && generatedOutfits.length === 0 && !outfitLoading) {
      setOutfitLoading(true);
      fashionApi.generateOutfits({
        occasion: outfitOccasion,
        temperature_celsius: outfitTemp,
        condition: outfitCondition,
        target_aesthetic: outfitAesthetic,
        max_outfits: 3
      })
      .then(res => setGeneratedOutfits(res.outfits || []))
      .catch(() => {})
      .finally(() => setOutfitLoading(false));
    }
  }, [fashionFilterTab, primaryTab, generatedOutfits.length, outfitLoading, outfitOccasion, outfitTemp, outfitCondition, outfitAesthetic]);

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

  // Apply complete curated outfit suggestion from carousel
  const handleApplyOutfitSuggestion = (sugg: OutfitSuggestionItem) => {
    if (!sugg.appliedParams) return;
    const updated: HumanParams = {
      ...params,
      ...sugg.appliedParams,
      garmentStyles: {
        ...params.garmentStyles,
        ...(sugg.appliedParams.garmentStyles || {})
      }
    };
    setParams(updated);
    if (buildDebounceRef.current) clearTimeout(buildDebounceRef.current);
    buildDebounceRef.current = setTimeout(async () => {
      try {
        const built = await araEngine.generateCharacter(updated);
        setCharacter(built);
      } catch (e) {
        console.warn('Outfit suggestion generation error:', e);
      }
    }, 120);
    luxuryToast.draped(`Equipped ${sugg.title}!`);
    viewerRef.current?.playReaction?.('Present Outfit');
  };

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

  // Global Keyboard Shortcuts (adaptive by OS: Cmd for macOS, Ctrl for Windows / Linux / Chromebook)
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
        return;
      }

      const isMac = deviceCommands.isMac;
      const modPressed = isMac ? e.metaKey : e.ctrlKey;

      // Undo: ⌘Z (Mac) or Ctrl+Z (Windows / Linux / Chromebook)
      if (modPressed && e.key.toLowerCase() === 'z' && !e.shiftKey) {
        e.preventDefault();
        if (historyIndex > 0) {
          handleUndo();
        }
        return;
      }

      // Redo: ⇧⌘Z or ⌘Y (Mac) / Ctrl+Y or Ctrl+Shift+Z (Windows / Linux / Chromebook)
      const isRedoWin = !isMac && modPressed && e.key.toLowerCase() === 'y';
      const isRedoShiftZ = modPressed && e.shiftKey && e.key.toLowerCase() === 'z';
      if (isRedoWin || isRedoShiftZ) {
        e.preventDefault();
        if (historyIndex < history.length - 1 && historyIndex !== -1) {
          handleRedo();
        }
        return;
      }

      // Center / Fit Frame: Space or 'f'
      if (!modPressed && (e.code === 'Space' || e.key.toLowerCase() === 'f')) {
        e.preventDefault();
        if (viewMode !== 'full') {
          setViewMode('full');
        }
        viewerRef.current?.focusFullBody?.();
        luxuryToast.centerFrame('Centered avatar on stage');
        return;
      }

      // Zoom in: '+' or '='
      if (!modPressed && (e.key === '+' || e.key === '=')) {
        e.preventDefault();
        viewerRef.current?.zoomIn();
        return;
      }

      // Zoom out: '-' or '_'
      if (!modPressed && (e.key === '-' || e.key === '_')) {
        e.preventDefault();
        viewerRef.current?.zoomOut();
        return;
      }
    };

    window.addEventListener('keydown', handleGlobalKeyDown);
    return () => window.removeEventListener('keydown', handleGlobalKeyDown);
  }, [deviceCommands.isMac, historyIndex, history.length]);

  // Garment Selection: persistent personalized mannequin try-on with explicit layer replacement
  const handleSelectGarment = (item: FashionCatalogItem) => {
    setSelectedGarmentId(item.id);

    // 1. Asset Type Enforcement: Do not claim 2D photo is 3D fitted
    if (item.assetType === '2d_image' || item.assetType === 'unavailable') {
      fittingDiagnostics.logSelection({
        garmentId: item.id,
        garmentName: item.name,
        category: item.category,
        assetType: item.assetType,
        targetSlot: item.category === 'outfit' ? 'full_outfit' : (item.category as any),
        previousOutfitState: {
          slotType: equippedOutfit.slotType,
          outfitId: equippedOutfit.fullOutfitId || equippedOutfit.ensembleId,
          topId: equippedOutfit.topId,
          bottomId: equippedOutfit.bottomId,
          shoesId: equippedOutfit.shoesId
        },
        replacementAction: {
          removedGarments: [],
          appliedGarment: item.name,
          preservedSlots: ['avatar_appearance']
        },
        meshValidation: {
          status: 'not_applicable',
          reason: 'Garment asset is 2D photograph. 3D geometry fitting bypassed; 2D preview opened.'
        },
        fittingStatus: 'rejected_2d_only'
      });
      setInspectedItem({
        id: item.id,
        name: item.name,
        brand: item.brand,
        category: item.category,
        subcategory: item.subcategory,
        color: item.color,
        material: item.material,
        userNotes: item.userNotes,
        priceDisplay: item.priceDisplay,
        imageUrl: item.imageUrl,
        assetType: item.assetType,
        appliedParams: item.appliedParams,
        isCustom: false
      });
      luxuryToast.info('2D photograph selected — previewing item details. Click "Generate 3D" to fit in 3D.', {
        duration: 2500
      });
      return;
    }

    // 2. Clear any custom user-uploaded GLB overlay so catalog piece takes precedence
    setActiveCustomGarment(null);

    // 3. Preserve User's Avatar Identity & Appearance
    // (skinTone, hair, hairColor, gender, muscle, weight, height, proportions, face, age, modifiers)
    const updated: HumanParams = {
      ...params,
      garmentStyles: {
        ...params.garmentStyles,
        ...(item.appliedParams.garmentStyles || {})
      }
    };

    // 4. Explicit Slot Replacement Rules
    let removedLayers: string[] = [];
    const preservedSlots: string[] = ['skin', 'hair', 'body_proportions'];
    let nextOutfitState: ActiveOutfitState = { ...equippedOutfit };

    if (item.category === 'outfit') {
      // Replaces top, bottom, outerwear with full ensemble
      removedLayers = ['top', 'bottom', 'outerwear'];
      updated.outfit = item.appliedParams.outfit ?? (params.gender >= 0.5 ? 'male_elegantsuit01' : 'female_casualsuit01');
      updated.top = item.appliedParams.top ?? 'none';
      updated.bottom = item.appliedParams.bottom ?? 'none';
      updated.shoes = item.appliedParams.shoes === 'none' ? 'none' : (item.araShoesId || item.appliedParams.shoes || params.shoes || 'shoes01');
      if (updated.outfit === 'none') {
        updated.underwear = true;
      }

      nextOutfitState = {
        slotType: 'full_outfit',
        fullOutfitId: item.id,
        ensembleId: item.id,
        topId: null,
        bottomId: null,
        shoesId: updated.shoes,
        outerwearId: null,
        accessories: [],
        displayNames: {
          fullOutfit: item.name,
          ensemble: item.name,
          shoes: item.araShoesId ? `${item.name} Footwear` : equippedOutfit.displayNames.shoes
        }
      };
    } else if (item.category === 'top') {
      // Replaces previous top; removes whole-body proxy suit
      if (params.outfit && params.outfit !== 'none') {
        removedLayers.push('full_outfit');
      }
      if (equippedOutfit.topId) {
        removedLayers.push('top');
      }
      updated.outfit = 'none';
      updated.top = item.appliedParams.top || 'uniform_shirt';

      // Ensure lower half is covered with trousers if avatar was in a suit or bottom is 'none'
      if (!params.bottom || params.bottom === 'none') {
        updated.bottom = 'uniform_trousers';
      } else {
        updated.bottom = params.bottom;
      }
      updated.shoes = params.shoes || 'shoes01';
      preservedSlots.push('bottom', 'shoes');

      nextOutfitState = {
        slotType: 'separate_layers',
        fullOutfitId: null,
        ensembleId: null,
        topId: item.id,
        bottomId: equippedOutfit.bottomId || 'baseline_trousers',
        shoesId: updated.shoes,
        outerwearId: equippedOutfit.outerwearId,
        accessories: equippedOutfit.accessories,
        displayNames: {
          ...equippedOutfit.displayNames,
          fullOutfit: undefined,
          ensemble: undefined,
          top: item.name,
          bottom: equippedOutfit.displayNames.bottom || 'Classic Trousers'
        }
      };
    } else if (item.category === 'bottom') {
      // Replaces previous bottom; removes whole-body proxy suit
      if (params.outfit && params.outfit !== 'none') {
        removedLayers.push('full_outfit');
      }
      if (equippedOutfit.bottomId) {
        removedLayers.push('bottom');
      }
      updated.outfit = 'none';
      updated.bottom = item.appliedParams.bottom || 'uniform_trousers';

      // Ensure upper half is covered with a shirt if avatar was in a suit or top is 'none'
      if (!params.top || params.top === 'none') {
        updated.top = 'uniform_shirt_long';
      } else {
        updated.top = params.top;
      }
      updated.shoes = params.shoes || 'shoes01';
      preservedSlots.push('top', 'shoes');

      nextOutfitState = {
        slotType: 'separate_layers',
        fullOutfitId: null,
        ensembleId: null,
        topId: equippedOutfit.topId || 'baseline_shirt',
        bottomId: item.id,
        shoesId: updated.shoes,
        outerwearId: equippedOutfit.outerwearId,
        accessories: equippedOutfit.accessories,
        displayNames: {
          ...equippedOutfit.displayNames,
          fullOutfit: undefined,
          ensemble: undefined,
          bottom: item.name,
          top: equippedOutfit.displayNames.top || 'Classic Shirt'
        }
      };
    } else if (item.category === 'outerwear') {
      // Replaces previous outerwear, sits over top and bottom
      if (equippedOutfit.outerwearId) {
        removedLayers.push('outerwear');
      }
      updated.outfit = 'none';
      updated.top = item.appliedParams.top || 'techwear_jacket';
      if (!params.bottom || params.bottom === 'none') {
        updated.bottom = 'uniform_trousers';
      }
      updated.shoes = params.shoes || 'shoes01';
      preservedSlots.push('bottom', 'shoes');

      nextOutfitState = {
        slotType: 'separate_layers',
        fullOutfitId: null,
        ensembleId: null,
        topId: item.id,
        bottomId: equippedOutfit.bottomId || 'baseline_trousers',
        shoesId: updated.shoes,
        outerwearId: item.id,
        accessories: equippedOutfit.accessories,
        displayNames: {
          ...equippedOutfit.displayNames,
          fullOutfit: undefined,
          ensemble: undefined,
          outerwear: item.name,
          top: item.name,
          bottom: equippedOutfit.displayNames.bottom || 'Classic Trousers'
        }
      };
    } else if (item.category === 'shoes') {
      // Replaces shoes only
      if (equippedOutfit.shoesId) {
        removedLayers.push('shoes');
      }
      updated.shoes = item.araShoesId || item.appliedParams.shoes || 'shoes01';
      preservedSlots.push('top', 'bottom', 'outerwear');

      nextOutfitState = {
        ...equippedOutfit,
        shoesId: updated.shoes,
        displayNames: {
          ...equippedOutfit.displayNames,
          shoes: item.name
        }
      };
    }

    // 5. Diagnostics Logging
    fittingDiagnostics.logSelection({
      garmentId: item.id,
      garmentName: item.name,
      category: item.category,
      assetType: item.assetType,
      targetSlot: item.category === 'outfit' ? 'full_outfit' : (item.category as any),
      previousOutfitState: {
        slotType: equippedOutfit.slotType,
        outfitId: equippedOutfit.fullOutfitId || equippedOutfit.ensembleId,
        topId: equippedOutfit.topId,
        bottomId: equippedOutfit.bottomId,
        shoesId: equippedOutfit.shoesId
      },
      replacementAction: {
        removedGarments: removedLayers,
        appliedGarment: item.name,
        preservedSlots
      },
      meshValidation: {
        status: 'passed',
        reason: '3D geometry mesh validated and bound to avatar skeleton'
      },
      fittingStatus: 'success'
    });

    setEquippedOutfit(nextOutfitState);

    try {
      const paramsChanged = updated.top !== params.top ||
      updated.bottom !== params.bottom ||
      updated.outfit !== params.outfit ||
      updated.shoes !== params.shoes;

    if (paramsChanged) {
      triggerRebuild(updated);
    }
      if (viewerRef.current?.onGarmentEquipped) {
        viewerRef.current.onGarmentEquipped(item.category);
      } else {
        araAnim.playOneShot('Turn', 'Idle', 0.4);
      }
      intelligenceApi.analyzeFit((item as any).reconstructionJobId || undefined, item.category || 'tops').then((fitRep) => {
        if (fitRep?.fit_classification) {
          toast(`Fit Intelligence: ${fitRep.fit_classification} (${Math.round(fitRep.overall_fit_score || 0)}/100)`, { duration: 2200 });
        }
      }).catch(() => {});
      toast.success(`Fitted "${item.name}" onto your 3D avatar`, { duration: 1600 });
    } catch (err: any) {
      console.error('Fitting error:', err);
      toast.error('Unable to fit garment to avatar');
    }
  };

  // Unequip & Reset to clean baseline attire without resetting avatar body/hair/skin
  const handleResetOutfit = () => {
    setActiveCustomGarment(null);
    setSelectedGarmentId('');
    setEquippedOutfit({
      slotType: 'full_outfit',
      fullOutfitId: null,
      ensembleId: null,
      topId: null,
      bottomId: null,
      shoesId: 'shoes01',
      outerwearId: null,
      accessories: [],
      displayNames: {}
    });

    const neutralOutfit = params.gender < 0.5 ? 'female_casualsuit01' : 'male_elegantsuit01';
    const updated: HumanParams = {
      ...params,
      outfit: neutralOutfit,
      top: 'none',
      bottom: 'none',
      shoes: 'shoes01'
    };
    const paramsChanged = updated.top !== params.top ||
      updated.bottom !== params.bottom ||
      updated.outfit !== params.outfit ||
      updated.shoes !== params.shoes;

    if (paramsChanged) {
      triggerRebuild(updated);
    }
    araAnim.playOneShot('Turn', 'Idle', 0.4);
    toast.success('Reset to neutral studio attire');
  };

  // Undress avatar to bare neutral mannequin base (neutral modesty briefs, inspect body silhouette)
  const handleUndressToMannequin = () => {
    setActiveCustomGarment(null);
    setSelectedGarmentId('');
    setEquippedOutfit({
      slotType: 'separate_layers',
      fullOutfitId: null,
      ensembleId: null,
      topId: null,
      bottomId: null,
      shoesId: null,
      outerwearId: null,
      accessories: [],
      displayNames: {
        top: 'None (Bare)',
        bottom: 'Neutral Briefs',
        shoes: 'Barefoot'
      }
    });

    const updated: HumanParams = {
      ...params,
      outfit: 'none',
      top: 'none',
      bottom: 'none',
      shoes: 'none',
      accessories: [],
      underwear: true
    };
    const paramsChanged = updated.top !== params.top ||
      updated.bottom !== params.bottom ||
      updated.outfit !== params.outfit ||
      updated.shoes !== params.shoes;

    if (paramsChanged) {
      triggerRebuild(updated);
    }
    araAnim.playOneShot('Turn', 'Idle', 0.4);
    toast.success('Undressed to bare mannequin base');
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
    updated.top = 'none';
    updated.bottom = 'none';

    setEquippedOutfit({
      slotType: 'full_outfit',
      fullOutfitId: outfit.outfit_id,
      ensembleId: outfit.outfit_id,
      topId: null,
      bottomId: null,
      shoesId: updated.shoes,
      outerwearId: null,
      accessories: [],
      displayNames: { fullOutfit: outfit.title, ensemble: outfit.title }
    });
    const paramsChanged = updated.top !== params.top ||
      updated.bottom !== params.bottom ||
      updated.outfit !== params.outfit ||
      updated.shoes !== params.shoes;

    if (paramsChanged) {
      triggerRebuild(updated);
    }
    araAnim.playOneShot('Turn', 'Idle', 0.4);
    luxuryToast.draped(`Draped "${outfit.title}" onto 3D avatar!`, { duration: 2000 });
  };

  // Drape a Wardrobe piece onto the persistent 3D mannequin
  const handleDrapeWardrobePiece = (piece: Garment) => {
    const isCustom3D = Boolean(piece.glb_url || piece.is_custom_3d || piece.asset_type === '3d_mesh');

    if (isCustom3D) {
      const rawJobId = (piece.id || '').replace(/^3d_/, '');
      const guaranteedPiece: Garment = {
        ...piece,
        glb_url: piece.glb_url || (rawJobId ? `/api/fashion/garment-gen/assets/${rawJobId}/garment.glb` : undefined),
        is_custom_3d: true
      };
      setActiveCustomGarment(guaranteedPiece);
    } else {
      setActiveCustomGarment(null);
    }
    setSelectedGarmentId(piece.id);

    // Rigged Ara procedural garment fitting for all digital wardrobe pieces
    const cat = (piece.category || 'top').toLowerCase();
    const updated: HumanParams = { ...params };
    let targetSlot: 'full_outfit' | 'top' | 'bottom' | 'shoes' | 'outerwear' | 'custom_3d' = 'top';
    const isBottom = cat === 'bottom' || cat === 'bottoms' || cat === 'pants' || cat === 'trousers' || cat === 'jeans' || cat === 'shorts';
    const isOuterwear = cat === 'outerwear' || cat === 'jacket' || cat === 'coat';
    const isDress = cat === 'dress' || cat === 'dresses' || cat === 'dresses_and_skirts' || cat === 'skirt';

    if (isBottom) {
      targetSlot = 'bottom';
      updated.outfit = 'none';
      if (isCustom3D) {
        // For custom 3D bottoms: do not generate procedural trousers that clip or fight with custom piece
        updated.bottom = 'none';
      } else {
        updated.bottom = cat === 'shorts' ? 'cargo_shorts' : 'uniform_trousers';
      }
      // Ensure upper body is properly covered with a shirt so torso is never invisible
      if (!params.top || params.top === 'none') {
        updated.top = 'uniform_shirt';
      }
      updated.shoes = params.shoes || 'shoes01';
      if (!isCustom3D) {
        updated.garmentStyles = {
          ...params.garmentStyles,
          [updated.bottom]: {
            color: piece.color || '#334155',
            pattern: (piece.pattern && ['solid', 'khaki', 'camo'].includes(piece.pattern)) ? (piece.pattern as any) : 'solid'
          }
        };
      }
    } else if (isOuterwear) {
      targetSlot = 'outerwear';
      updated.outfit = 'none';
      if (isCustom3D) {
        // For custom 3D outerwear: do not generate procedural jacket/shirt on upper body
        updated.top = 'none';
      } else {
        updated.top = 'techwear_jacket';
      }
      if (!params.bottom || params.bottom === 'none') {
        updated.bottom = 'uniform_trousers';
      }
      updated.shoes = params.shoes || 'shoes01';
      if (!isCustom3D) {
        updated.garmentStyles = {
          ...params.garmentStyles,
          techwear_jacket: {
            color: piece.color || '#0f172a',
            pattern: 'solid'
          }
        };
      }
    } else if (isDress) {
      targetSlot = 'top';
      updated.outfit = 'none';
      if (isCustom3D) {
        updated.top = 'none';
        updated.bottom = 'none';
      } else {
        updated.top = 'uniform_shirt';
        updated.bottom = 'uniform_trousers';
      }
      updated.shoes = params.shoes || 'shoes01';
    } else if (cat === 'footwear' || cat === 'shoes' || cat === 'boots') {
      targetSlot = 'shoes';
      updated.shoes = cat === 'boots' ? 'combat_boots' : 'shoes01';
    } else {
      // Top / Shirt / Knitwear / Hoodie / Polo / Tops
      targetSlot = 'top';
      updated.outfit = 'none';
      if (isCustom3D) {
        // FOR CUSTOM 3D TOPS: Set procedural top to 'none' so Ara does NOT build uniform_shirt_long!
        updated.top = 'none';
      } else {
        const isHoodieOrJacket = piece.subcategory === 'jacket' || 
          piece.subcategory === 'hoodie' || 
          piece.name.toLowerCase().includes('hoodie') ||
          piece.name.toLowerCase().includes('jacket');
        const isShortSleeve = piece.subcategory === 'shirts' || 
          piece.name.toLowerCase().includes('polo') ||
          piece.name.toLowerCase().includes('t-shirt') ||
          piece.name.toLowerCase().includes('tee');

        updated.top = isHoodieOrJacket ? 'techwear_jacket' : (isShortSleeve ? 'uniform_shirt' : 'uniform_shirt_long');
      }

      if (!params.bottom || params.bottom === 'none') {
        updated.bottom = 'uniform_trousers';
      }
      updated.shoes = params.shoes || 'shoes01';
      
      if (!isCustom3D) {
        const isHoodieOrJacket = piece.subcategory === 'jacket' || 
          piece.subcategory === 'hoodie' || 
          piece.name.toLowerCase().includes('hoodie') ||
          piece.name.toLowerCase().includes('jacket');
        const piecePattern = (piece.pattern && ['solid', 'striped', 'khaki', 'camo', 'techwear'].includes(piece.pattern)) 
          ? piece.pattern 
          : (isHoodieOrJacket ? 'techwear' : (piece.name.toLowerCase().includes('polo') ? 'striped' : 'solid'));

        updated.garmentStyles = {
          ...params.garmentStyles,
          [updated.top]: {
            color: piece.color || (isHoodieOrJacket ? '#16181d' : '#1e293b'),
            color2: isHoodieOrJacket ? '#00d2ff' : (piecePattern === 'striped' ? '#166534' : '#2a2c31'),
            pattern: piecePattern as any
          }
        };
      }
    }

    fittingDiagnostics.logSelection({
      garmentId: piece.id,
      garmentName: piece.name,
      category: piece.category,
      assetType: 'fitted_garment',
      targetSlot,
      previousOutfitState: {
        slotType: equippedOutfit.slotType,
        outfitId: equippedOutfit.fullOutfitId || equippedOutfit.ensembleId,
        topId: equippedOutfit.topId,
        bottomId: equippedOutfit.bottomId,
        shoesId: equippedOutfit.shoesId
      },
      replacementAction: {
        removedGarments: ['previous_garment'],
        appliedGarment: piece.name,
        preservedSlots: ['skin', 'hair', 'body_proportions']
      },
      meshValidation: {
        status: 'passed',
        reason: 'Rigged Ara 3D procedural garment fitted to avatar skeleton'
      },
      fittingStatus: 'success'
    });

    setEquippedOutfit({
      slotType: 'separate_layers',
      fullOutfitId: null,
      ensembleId: null,
      topId: updated.top,
      bottomId: updated.bottom,
      shoesId: updated.shoes,
      outerwearId: cat === 'outerwear' ? piece.id : equippedOutfit.outerwearId,
      accessories: equippedOutfit.accessories,
      displayNames: {
        ...equippedOutfit.displayNames,
        [targetSlot]: piece.name
      }
    });

    const paramsChanged = updated.top !== params.top ||
      updated.bottom !== params.bottom ||
      updated.outfit !== params.outfit ||
      updated.shoes !== params.shoes;

    // CRITICAL: For custom neural 3D garments (isCustom3D === true), NEVER trigger araEngine.generateCharacter.
    // The custom garment is already loaded and fitted in Three.js via GarmentAvatarFittingEngine.
    // Clear any pending rebuild debounce timers so an in-flight timer does not overwrite the custom garment.
    if (isCustom3D) {
      if (buildDebounceRef.current) {
        clearTimeout(buildDebounceRef.current);
        buildDebounceRef.current = null;
      }
      setParams(updated);
    } else if (paramsChanged) {
      triggerRebuild(updated);
    }
    araAnim.playOneShot('Turn', 'Idle', 0.4);
    luxuryToast.draped(`Fitted "${piece.name}" onto your 3D avatar!`);
  };

  // Save Avatar State
  const handleSaveAvatar = async () => {
    try {
      const v3Profile = humanParamsToAvatarProfile(params, user?.id);
      await profileService.saveAvatarProfile(user?.id || '', v3Profile);
      await fashionApi.saveAvatarConfig(params).catch(() => {});
      handleSaveCurrentOutfit();
      araAnim.playOneShot('Cheer', 'Idle', 0.4);
      luxuryToast.saved('Avatar identity saved to digital profile!');
    } catch {
      handleSaveCurrentOutfit();
      araAnim.playOneShot('Cheer', 'Idle', 0.4);
      luxuryToast.saved('Saved locally');
    }
  };

  // ── Saved Outfits Management ──
  const handleSaveCurrentOutfit = async () => {
    const lookName = `Look #${savedOutfits.length + 1} • ${params.gender === 0 ? 'Atelier Muse' : 'Atelier Mannequin'}`;
    const avatarSnapshot = {
      outfit: params.outfit,
      top: params.top,
      bottom: params.bottom,
      shoes: params.shoes,
      garmentStyles: params.garmentStyles ? { ...params.garmentStyles } : undefined
    };

    const activeGarments: string[] = [];
    if (params.outfit) activeGarments.push(params.outfit);
    if (params.top) activeGarments.push(params.top);
    if (params.bottom) activeGarments.push(params.bottom);
    if (params.shoes) activeGarments.push(params.shoes);

    const localId = `saved-look-${Date.now()}`;
    const newOutfit: SavedOutfit = {
      id: localId,
      title: lookName,
      date: 'Saved today',
      tag: 'Custom Look',
      imageUrl: '/items/dummy_outfit_1.png',
      isCustom: true,
      appliedParams: avatarSnapshot
    };

    const nextOutfits = [newOutfit, ...savedOutfits];
    setSavedOutfits(nextOutfits);
    try {
      localStorage.setItem('yorvyn_saved_outfits', JSON.stringify(nextOutfits));
    } catch {
      // ignore
    }

    // Phase 9: Persist to backend database
    try {
      const backendLook = await fashionApi.createLook({
        name: lookName,
        garment_ids: activeGarments.length > 0 ? activeGarments : ['default-garment'],
        avatar_snapshot: avatarSnapshot,
        tags: ['Custom Look'],
        is_favorite: false
      });
      if (backendLook && backendLook.id) {
        newOutfit.id = backendLook.id;
      }
    } catch (err) {
      console.warn('Backend look persistence fallback to local:', err);
    }

    araAnim.playOneShot('Cheer', 'Idle', 0.4);
    luxuryToast.saved('Current look added to Saved Outfits!');
  };

  const handleDeleteSavedOutfit = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSavedOutfits(prev => {
      const next = prev.filter(o => o.id !== id);
      try {
        localStorage.setItem('yorvyn_saved_outfits', JSON.stringify(next));
      } catch {
        // ignore
      }
      return next;
    });

    // Phase 9: Sync deletion with backend
    fashionApi.deleteLook(id).catch(err => {
      console.warn('Backend look deletion notice:', err);
    });

    luxuryToast.delete('Removed from saved outfits');
  };

  const handleApplySavedOutfit = (outfit: SavedOutfit) => {
    const updated: HumanParams = {
      ...params,
      ...outfit.appliedParams,
      garmentStyles: {
        ...params.garmentStyles,
        ...(outfit.appliedParams.garmentStyles || {})
      }
    };
    setParams(updated);
    setEquippedOutfit({
      slotType: 'full_outfit',
      fullOutfitId: outfit.id,
      ensembleId: outfit.id,
      topId: null,
      bottomId: null,
      shoesId: updated.shoes,
      outerwearId: null,
      accessories: [],
      displayNames: { fullOutfit: outfit.title, ensemble: outfit.title }
    });
    const paramsChanged = updated.top !== params.top ||
      updated.bottom !== params.bottom ||
      updated.outfit !== params.outfit ||
      updated.shoes !== params.shoes;

    if (paramsChanged) {
      triggerRebuild(updated);
    }
    araAnim.playOneShot('Turn', 'Idle', 0.4);
    luxuryToast.draped(`Draped "${outfit.title}" onto 3D twin!`);
  };

  // GLB Model Download
  const handleDownloadGlb = async () => {
    if (!character) return;
    setIsExporting(true);
    const toastId = toast.loading('Exporting rigged GLB 3D model...');

    try {
      const glbBytes = await araEngine.exportCharacterGlb(character);
      const val = validateAnimatedGLBExport(glbBytes);
      if (!val.isValid) {
        throw new Error(val.issues.join(' ') || 'Animated GLB validation failed');
      }
      const blob = new Blob([glbBytes as BlobPart], { type: 'model/gltf-binary' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${params.name || 'yorvyn-character'}.glb`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`Exported animated GLB (${val.clipCount} clips, ${val.exportKind.replace(/_/g, ' ')})!`, { id: toastId });
    } catch (err: any) {
      toast.error(`Export failed: ${err.message}`, { id: toastId });
    } finally {
      setIsExporting(false);
    }
  };

  useEffect(() => {
    if (typeof window !== 'undefined') {
      (window as any).yorvynStudio = {
        resetOutfit: handleResetOutfit,
        undressMannequin: handleUndressToMannequin,
        downloadGlb: handleDownloadGlb
      };
    }
  }, [isExporting]);

  // Send AI Stylist Message (Grounding in real catalog & digital wardrobe)
  const handleSendStylistMessage = async (presetText?: string) => {
    const text = presetText || chatInput.trim() || (garmentPhotos.length ? 'Identify this garment' : '');
    if (!text || chatLoading || garmentPending.current) return;
    const files = presetText ? [] : garmentPhotos;
    const followUp = lastGarment.current && /\b(garment|make it|make this|cancel|retry|status|progress|sleeves?|wider|shorten|denim|undo|export|preview|3d|try on|folds|oversized)\b/i.test(text);
    if (files.length || (!presetText && followUp)) {
      const owner = user?.id;
      if (!owner || !signedInSession) {toast.error('Sign in to work with garment photos.'); return;}
      const activity = new AbortController();
      garmentPending.current = true;
      setChatLoading(true);
      setGarmentBusy(files.length ? 'Analyzing garment photos…' : 'Checking your garment…');
      setChatMessages(prev=>[...prev,{id:crypto.randomUUID(),sender:'user',text}]);
      setChatInput('');
      try {
        const sid = garmentSession.current || (await aiSessionService.createSession('Garment conversation','fashion_stylist')).id;
        if (garmentOwner.current !== owner) return;
        garmentSession.current = sid;
        localStorage.setItem('yorvyn_garment_chat_' + owner,sid);
        const requestId = crypto.randomUUID();
        void aiSessionService.watchGarmentActivity(sid,requestId,activity.signal,label=>{
          if (garmentOwner.current === owner) setGarmentBusy(label);
        }).catch(()=>{/* The turn still returns its authoritative result. */});
        const reply = await aiSessionService.garmentTurn(sid,text,files,requestId,lastGarment.current?.turn_id);
        if (garmentOwner.current !== owner) return;
        const garment = reply.metadata.garment as GarmentArtifact;
        lastGarment.current = garment;
        if (garment.job_id) setGarmentPhotos([]);
        setChatMessages(prev=>[...prev,{id:reply.id,sender:'stylist',text:reply.content,session:sid,garment}]);
      } catch (err: any) {
        if (garmentOwner.current === owner) setChatMessages(prev=>[...prev,{id:crypto.randomUUID(),sender:'stylist',
          text:typeof err.response?.data?.detail === 'string' ? err.response.data.detail : 'The garment request could not finish. Check the connection and try again.'}]);
      } finally {activity.abort(); garmentPending.current=false; setChatLoading(false); setGarmentBusy('');}
      return;
    }

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
      if (res && res.outfits && res.outfits.length > 0) {
        const botMsg: ChatMessage = {
          id: `sty_${Date.now()}`,
          sender: 'stylist',
          text: res.reply,
          outfits: res.outfits
        };
        setChatMessages(prev => [...prev, botMsg]);
        setChatLoading(false);
        return;
      }
    } catch {
      // Seamlessly fall back to client-side AI stylist engine
    }

    try {
      const stylistEngine = await ensureStylistEngine();
      const proposal = await conversationManagerRef.current!.handleMessage(
        text,
        profileManagerRef.current!.getProfile(),
        params,
        {
          temperatureCelsius: outfitTemp,
          condition: 'mild',
          thermalTier: outfitTemp < 19 ? 'cold' : 'mild'
        }
      );

      const legacyOutfits = proposal.recommendations.map(r => stylistEngine.OutfitRecommendationEngine.toLegacyOutfit(r));

      const botMsg: ChatMessage = {
        id: `sty_${Date.now()}`,
        sender: 'stylist',
        text: proposal.explanation,
        outfits: legacyOutfits
      };
      setChatMessages(prev => [...prev, botMsg]);
    } catch (e) {
      console.error('[AvatarStudio] Client stylist error:', e);
      setChatMessages(prev => [
        ...prev,
        {
          id: `err_${Date.now()}`,
          sender: 'stylist',
          text: "I analyzed your wardrobe and current temperature. Try asking for a college casual ensemble, formal interview look, or minimal streetwear!"
        }
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const garmentAttachment = <><GarmentPhotoStrip files={garmentPhotos} remove={i=>setGarmentPhotos(prev=>prev.filter((_,j)=>i!==j))} disabled={chatLoading}/><label title="Attach garment photos" style={{cursor:'pointer'}}>
    <UploadSimple size={18}/><span>{garmentPhotos.length || ''}</span>
    <input aria-label="Attach garment photos" type="file" multiple accept="image/jpeg,image/png,image/webp"
      disabled={chatLoading} style={{width:1,height:1,opacity:0}}
      onChange={event=>{
        const files = [...garmentPhotos,...Array.from(event.target.files || [])];
        event.target.value = '';
        if(files.length > 10 || files.some(f=>f.size>15*1024*1024) || files.reduce((n,f)=>n+f.size,0)>60*1024*1024) {
          toast.error('Use up to 10 photos, 15 MB each and 60 MB total.'); return;
        }
        setGarmentPhotos(files);
      }}/>
  </label></>;
  const renderGarment = (msg: ChatMessage) => msg.garment && msg.session && <GarmentJobMessage
    session={msg.session} garment={msg.garment} wear={blob=>{
      const url = URL.createObjectURL(blob);
      chatTryOnUrl.current = url;
      handleDrapeWardrobePiece({
      id:msg.garment!.turn_id, name:msg.garment!.recognition?.garment?.subcategory || 'Chat garment',
      category:(msg.garment!.category || 'top') as Garment['category'], glb_url:url, is_custom_3d:true,
      subcategory:msg.garment!.recognition?.garment?.subcategory || '', color:'', material:'', pattern:'',
      formality:0, warmth:0, seasons:[], weather_tags:[], aesthetic:[], brand:'', image_url:'', wear_count:0,favorite:false
    }); }}/>;
  const handleLikeOutfit = async (outfitId: string) => {
    await ensureStylistEngine();
    feedbackManagerRef.current?.recordLike(outfitId);
    luxuryToast.success('Saved to preferences! Adapting styling models.', { duration: 1500 });
  };

  const handleDislikeOutfit = async (outfitId: string, reason: DislikeReason = 'too_formal') => {
    await ensureStylistEngine();
    feedbackManagerRef.current?.recordDislike(outfitId, reason);
    luxuryToast.info('Understood! Adapting future outfit recommendations.', { duration: 1500 });
  };

  // Handle garment image file selection
  const handleGarmentImageFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      toast.error('Please upload an image file (PNG, JPG, or WEBP)');
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      toast.error('Image file exceeds 15MB limit');
      return;
    }
    setNewGarmentImageName(file.name);
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        setNewGarmentImage(reader.result);
      }
    };
    reader.readAsDataURL(file);
  };

  const handleGarmentImageDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      toast.error('Please upload an image file (PNG, JPG, or WEBP)');
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      toast.error('Image file exceeds 15MB limit');
      return;
    }
    setNewGarmentImageName(file.name);
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        setNewGarmentImage(reader.result);
      }
    };
    reader.readAsDataURL(file);
  };

  const handleClearGarmentImage = () => {
    setNewGarmentImage('');
    setNewGarmentImageName('');
    if (garmentFileInputRef.current) {
      garmentFileInputRef.current.value = '';
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
        image_url: newGarmentImage || '/items/dummy_outfit_1.png'
      });
      setWardrobeItems(prev => [added, ...prev]);
      toast.success('Garment digitized into your wardrobe!');
      closeTrayWorkflow();
      setNewGarmentName('');
      setNewGarmentImage('');
      setNewGarmentImageName('');
      fashionApi.getAnalytics().then(setWardrobeAnalytics);
    } catch {
      toast.error('Failed to add garment');
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

  // Filtered Wardrobe (Mapped to Level 2 Wardrobe Navigation)
  const filteredWardrobe = wardrobeItems.filter(item => {
    if (activeWardrobeCategory === 'all') return true;
    if (activeWardrobeCategory === 'saved_outfits' || activeWardrobeCategory === 'collections') return true;
    const cat = (item.category || '').toLowerCase();
    const sub = (item.subcategory || '').toLowerCase();
    const target = activeWardrobeCategory.toLowerCase();
    if (target === 'top' || target === 'tops') return ['top', 'shirt', 'knitwear', 'tee', 'blouse', 'hoodie'].includes(cat) || ['hoodies', 'shirts', 't-shirts', 'tops'].includes(sub);
    if (target === 'bottom' || target === 'bottoms') return ['bottom', 'pants', 'trousers', 'denim', 'jeans', 'skirt', 'shorts'].includes(cat) || ['trousers', 'jeans', 'shorts', 'skirts'].includes(sub);
    if (target === 'outerwear') return ['outerwear', 'overcoat', 'jacket', 'coat', 'blazer'].includes(cat) || ['jackets'].includes(sub);
    if (target === 'footwear' || target === 'shoes') return ['shoes', 'footwear', 'sneakers', 'boots', 'heels'].includes(cat) || ['shoes', 'boots', 'sneakers'].includes(sub);
    if (target === 'accessory' || target === 'accessories') return ['accessory', 'accessories', 'watch', 'bag', 'sunglasses', 'jewelry'].includes(cat) || ['watches', 'sunglasses', 'bags', 'rings', 'necklaces', 'bracelets', 'earrings', 'belts', 'caps', 'scarves'].includes(sub);
    return cat === target || sub === target || cat.includes(target) || target.includes(cat);
  });

  // Progressive Wardrobe IntersectionObserver Windowing (Stage 3)
  useEffect(() => {
    setVisibleWardrobeCount(10);
  }, [activeWardrobeCategory]);

  useEffect(() => {
    const sentinel = wardrobeSentinelRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setVisibleWardrobeCount(prev => Math.min(prev + 8, filteredWardrobe.length));
        }
      },
      { rootMargin: '180px' }
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [filteredWardrobe.length, activePrimaryTab, drawerOpen, activeWardrobeCategory, visibleWardrobeCount]);

  const handleCatalogItemClick = (item: FashionCatalogItem) => {
    if (item.assetType === '2d_image') {
      setInspectedItem({
        id: item.id,
        name: item.name,
        brand: item.brand,
        category: item.category,
        subcategory: item.subcategory,
        color: item.color,
        material: item.material,
        userNotes: item.userNotes,
        priceDisplay: item.priceDisplay,
        imageUrl: item.imageUrl,
        assetType: item.assetType,
        appliedParams: item.appliedParams,
        isCustom: false
      });
      return;
    }

    if (selectedGarmentId === item.id) {
      setSelectedGarmentId('relaxed-shirt');
      luxuryToast.info(`Unequipped ${item.name}`);
      return;
    }

    setSelectedGarmentId(item.id);

    const updated: HumanParams = { ...params };

    if (item.appliedParams) {
      if (item.appliedParams.outfit && item.appliedParams.outfit !== 'none') {
        updated.outfit = item.appliedParams.outfit;
      }
      if (item.appliedParams.top) {
        updated.outfit = 'none';
        updated.top = item.appliedParams.top;
        if (!params.bottom || params.bottom === 'none') {
          updated.bottom = 'uniform_trousers';
        }
      }
      if (item.appliedParams.bottom) {
        updated.outfit = 'none';
        updated.bottom = item.appliedParams.bottom;
        if (!params.top || params.top === 'none') {
          updated.top = 'uniform_shirt_long';
        }
      }
      if (item.appliedParams.shoes) {
        updated.shoes = item.appliedParams.shoes;
      }
      if (item.appliedParams.garmentStyles) {
        updated.garmentStyles = {
          ...params.garmentStyles,
          ...item.appliedParams.garmentStyles
        };
      }
    }

    const paramsChanged = updated.top !== params.top ||
      updated.bottom !== params.bottom ||
      updated.outfit !== params.outfit ||
      updated.shoes !== params.shoes;

    if (paramsChanged) {
      triggerRebuild(updated);
    }
    luxuryToast.draped(`Fitted "${item.name}" onto your 3D avatar!`);
  };

  const renderInTrayItemDetails = () => {
    if (!inspectedItem) return null;

    const isFav = inspectedItem.id ? favorites.has(inspectedItem.id) : false;
    const isCurrentlyEquipped = selectedGarmentId === inspectedItem.id ||
      activeCustomGarment?.id === inspectedItem.id ||
      equippedOutfit.topId === inspectedItem.id ||
      equippedOutfit.bottomId === inspectedItem.id ||
      equippedOutfit.shoesId === inspectedItem.id;

    return (
      <div className="in-tray-item-details-panel">
        <div className="in-tray-details-header">
          <button
            type="button"
            className="in-tray-back-btn"
            onClick={() => setInspectedItem(null)}
            aria-label="Back to grid"
          >
            <CaretLeft size={16} weight="bold" />
            <span>Back</span>
          </button>
          <div className="in-tray-header-actions">
            <button
              type="button"
              className={`in-tray-fav-btn ${isFav ? 'active' : ''}`}
              onClick={() => toggleFavorite(inspectedItem.id)}
              aria-label="Toggle favorite"
            >
              <Heart size={16} weight={isFav ? 'fill' : 'regular'} color={isFav ? '#ef4444' : '#64748b'} />
            </button>
            <button
              type="button"
              className="in-tray-close-btn"
              onClick={() => setInspectedItem(null)}
              aria-label="Close details"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Large Visual Preview */}
        <div className="in-tray-preview-frame">
          {inspectedItem.imageUrl || inspectedItem.thumbnailUrl ? (
            <img
              src={inspectedItem.imageUrl || inspectedItem.thumbnailUrl}
              alt={inspectedItem.name}
              className="in-tray-large-img"
            />
          ) : (
            <div className="in-tray-img-placeholder">
              <CoatHanger size={48} color="#94a3b8" />
            </div>
          )}
        </div>

        {/* Item Details */}
        <div className="in-tray-details-body">
          <div className="in-tray-title-block">
            <span className="in-tray-brand-tag">{inspectedItem.brand || 'Yorvyn Studio'}</span>
            <h3 className="in-tray-item-title">{inspectedItem.name}</h3>
          </div>

          <div className="in-tray-attrs-grid">
            <div className="in-tray-attr-card">
              <span className="in-tray-attr-label">Category</span>
              <span className="in-tray-attr-val">{inspectedItem.category}</span>
            </div>
            {inspectedItem.subcategory && (
              <div className="in-tray-attr-card">
                <span className="in-tray-attr-label">Subcategory</span>
                <span className="in-tray-attr-val">{inspectedItem.subcategory}</span>
              </div>
            )}
            {inspectedItem.color && (
              <div className="in-tray-attr-card">
                <span className="in-tray-attr-label">Colour</span>
                <div className="in-tray-color-val">
                  <span className="in-tray-color-dot" style={{ backgroundColor: inspectedItem.color }} />
                  <span>{inspectedItem.color}</span>
                </div>
              </div>
            )}
            {inspectedItem.material && (
              <div className="in-tray-attr-card">
                <span className="in-tray-attr-label">Material</span>
                <span className="in-tray-attr-val">{inspectedItem.material}</span>
              </div>
            )}
            {inspectedItem.wearCount !== undefined && (
              <div className="in-tray-attr-card">
                <span className="in-tray-attr-label">Wear Count</span>
                <span className="in-tray-attr-val">{inspectedItem.wearCount} times</span>
              </div>
            )}
          </div>

          {inspectedItem.userNotes && (
            <div className="in-tray-notes-card">
              <span className="in-tray-notes-label">Editorial Notes</span>
              <p className="in-tray-notes-text">{inspectedItem.userNotes}</p>
            </div>
          )}

          {/* Actions */}
          <div className="in-tray-actions-footer">
            {inspectedItem.assetType === '3d_mesh' ? (
              <button
                type="button"
                className="in-tray-primary-cta"
                onClick={() => {
                  const catItem = FASHION_CATALOG.find(f => f.id === inspectedItem.id);
                  if (catItem) {
                    handleCatalogItemClick(catItem);
                  } else {
                    const wardItem = wardrobeItems.find(w => w.id === inspectedItem.id);
                    if (wardItem) handleDrapeWardrobePiece(wardItem);
                  }
                }}
              >
                <Sparkle size={15} />
                <span>{isCurrentlyEquipped ? 'Unequip from Avatar' : 'Wear on Avatar Twin'}</span>
              </button>
            ) : (
              <button
                type="button"
                className="in-tray-primary-cta"
                onClick={() => {
                  setInspectedItem(null);
                  openPhoto3DWorkflow();
                }}
              >
                <Sparkle size={15} />
                <span>Generate 3D Garment Mesh</span>
              </button>
            )}

            {inspectedItem.isCustom && (
              <button
                type="button"
                className="in-tray-delete-cta"
                onClick={() => {
                  setWardrobeItems(prev => prev.filter(w => w.id !== inspectedItem.id));
                  setInspectedItem(null);
                  toast.success('Garment removed from wardrobe');
                }}
              >
                <Trash size={15} />
                <span>Delete Piece</span>
              </button>
            )}
          </div>
        </div>
      </div>
    );
  };

  // ── IN-TRAY WORKSPACE: PERSONAL PROFILE & STUDIO SETTINGS ──
  const renderInTrayProfile = () => (
    <div className="in-tray-embedded-workflow in-tray-settings-workflow" role="region" aria-label="Settings and Profile">
      <Suspense fallback={<WorkflowSkeleton title="Loading Profile..." />}>
        <SettingsModal
          embedded={true}
          isOpen={true}
          onClose={closeTrayWorkflow}
          currentParams={params}
          onApplyCharacterPreset={(presetParams) => {
            triggerRebuild({ ...params, ...presetParams });
          }}
        />
      </Suspense>
    </div>
  );

  // ── IN-TRAY WORKSPACE: AI STYLIST CONSULTATION ──
  const renderInTrayStylist = () => (
    <div className="in-tray-embedded-workflow" role="region" aria-label="AI Stylist Consultation">
      <div className="in-tray-nav-topbar">
        <button
          type="button"
          className="in-tray-back-btn"
          onClick={closeTrayWorkflow}
          title="Back to Studio"
        >
          <CaretLeft size={16} weight="bold" />
          <span>Back</span>
        </button>
        <span className="in-tray-workflow-title">Yorvyn AI Stylist</span>
        <button
          type="button"
          className="in-tray-close-btn"
          onClick={closeTrayWorkflow}
          title="Close Stylist"
        >
          <X size={16} />
        </button>
      </div>
      <div className="in-tray-workflow-body">
        <div className="drawer-stylist-chat-view" style={{ height: '100%' }}>
          {/* Quick Prompts */}
          <div className="stylist-quick-prompts">
            {[
              "Premium casual look for college",
              "Formal outfit for job interview",
              "Modern streetwear layered look",
              "Quiet luxury dinner ensemble",
              "Festive wedding cocktail look",
              "Layered look from my wardrobe"
            ].map((p, idx) => (
              <button
                key={idx}
                type="button"
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

                {renderGarment(msg)}
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

                        {outfit.color_palette && outfit.color_palette.length > 0 && (
                          <div style={{ display: 'flex', gap: '4px', margin: '4px 0 8px 0', alignItems: 'center' }}>
                            <span style={{ fontSize: '0.65rem', color: '#94a3b8', marginRight: 4 }}>Palette:</span>
                            {outfit.color_palette.map((c, i) => (
                              <span
                                key={i}
                                style={{
                                  width: 14,
                                  height: 14,
                                  borderRadius: '50%',
                                  backgroundColor: c,
                                  border: '1px solid rgba(0,0,0,0.15)',
                                  display: 'inline-block'
                                }}
                              />
                            ))}
                          </div>
                        )}

                        <div className="rec-actions">
                          <button
                            type="button"
                            className="rec-action-btn primary"
                            onClick={() => handleDrapeOutfitOnAvatar(outfit)}
                          >
                            <Sparkle size={14} />
                            <span>Drape on 3D Avatar</span>
                          </button>
                          <button
                            type="button"
                            className="rec-action-btn secondary"
                            onClick={() => handleLikeOutfit(outfit.outfit_id)}
                            title="Love this look"
                            style={{ padding: '0.35rem 0.55rem' }}
                          >
                            <Heart size={14} />
                          </button>
                          <button
                            type="button"
                            className="rec-action-btn secondary"
                            onClick={() => handleDislikeOutfit(outfit.outfit_id, 'too_formal')}
                            title="Dislike this style"
                            style={{ padding: '0.35rem 0.55rem', fontSize: '0.72rem' }}
                          >
                            <ThumbsDown size={14} />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {chatLoading && (
              <>{garmentBusy && <p role="status">{garmentBusy}</p>}<ChatSkeleton /></>
            )}
            <div ref={chatBottomRef} />
          </div>

          {/* Chat Input */}
          <form
            className="stylist-input-row"
            onSubmit={(e) => { e.preventDefault(); handleSendStylistMessage(); }}
          >
            {garmentAttachment}
            {garmentPhotos.length > 0 && <button type="button" onClick={()=>setGarmentPhotos([])} disabled={chatLoading}>Clear photos</button>}
            <input
              type="text"
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              placeholder="Ask your AI Stylist (e.g. Wedding sherwani, Festive kurta, Linen shirt)..."
              className="stylist-text-input"
            />
            <button type="submit" className="stylist-send-btn" aria-label="Send message" disabled={(!chatInput.trim() && !garmentPhotos.length) || chatLoading}>
              <PaperPlaneTilt size={16} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );

  // ── IN-TRAY WORKSPACE: PHOTO TO 3D GARMENT RECONSTRUCTION ──
  const renderInTrayPhoto3D = () => (
    <div className="in-tray-embedded-workflow" role="region" aria-label="3D Garment Reconstruction">
      <div className="in-tray-nav-topbar">
        <button
          type="button"
          className="in-tray-back-btn"
          onClick={closeTrayWorkflow}
          title="Back to Wardrobe"
        >
          <CaretLeft size={16} weight="bold" />
          <span>Back</span>
        </button>
        <span className="in-tray-workflow-title">3D Garment Reconstruction</span>
        <button
          type="button"
          className="in-tray-close-btn"
          onClick={closeTrayWorkflow}
          title="Close Workspace"
        >
          <X size={16} />
        </button>
      </div>
      <div className="in-tray-workflow-body">
        <Suspense fallback={<WorkflowSkeleton title="Loading 3D Reconstruction..." />}>
          <PhotoTo3DGarmentModal
            isOpen={true}
            embedded={true}
            onClose={closeTrayWorkflow}
            onGarmentSaved={(savedGarment) => {
              if (savedGarment) {
                setWardrobeItems(prev => [
                  savedGarment,
                  ...prev.filter(item => item.id !== savedGarment.id)
                ]);
              }
              invalidateApiCache('wardrobe');
              fashionApi.getWardrobe(undefined, user?.id).then(res => {
                if (res && Array.isArray(res.items)) {
                  setWardrobeItems(res.items);
                }
              }).catch(console.error);
              closeTrayWorkflow();
            }}
            onWearImmediately={(savedGarment) => {
              if (savedGarment) {
                setWardrobeItems(prev => [
                  savedGarment,
                  ...prev.filter(item => item.id !== savedGarment.id)
                ]);
              }
              handleDrapeWardrobePiece(savedGarment);
              closeTrayWorkflow();
            }}
          />
        </Suspense>
      </div>
    </div>
  );

  // ── IN-TRAY WORKSPACE: DIGITIZE / ADD NEW GARMENT ──
  const renderInTrayAddPiece = () => (
    <div className="in-tray-embedded-workflow" role="region" aria-label="Add Garment">
      <div className="in-tray-nav-topbar">
        <button
          type="button"
          className="in-tray-back-btn"
          onClick={() => { closeTrayWorkflow(); handleClearGarmentImage(); }}
          title="Back to Wardrobe"
        >
          <CaretLeft size={16} weight="bold" />
          <span>Back</span>
        </button>
        <span className="in-tray-workflow-title">Digitize New Garment</span>
        <button
          type="button"
          className="in-tray-close-btn"
          onClick={() => { closeTrayWorkflow(); handleClearGarmentImage(); }}
          title="Close Workspace"
        >
          <X size={16} />
        </button>
      </div>

      <div className="in-tray-workflow-body">
        <form
          onSubmit={(e) => {
            handleAddGarment(e);
            closeTrayWorkflow();
          }}
          className="modal-form in-tray-add-form"
        >
          {/* Cloth Photograph Dropzone */}
          <div className="form-item garment-photo-form-item">
            <div className="form-item-header">
              <label>Cloth Photograph / Image <span className="required-star">*</span></label>
              <div className="image-mode-toggle">
                <button
                  type="button"
                  className={`mode-pill ${newGarmentInputMode === 'upload' ? 'active' : ''}`}
                  onClick={() => setNewGarmentInputMode('upload')}
                >
                  Upload Photo
                </button>
                <button
                  type="button"
                  className={`mode-pill ${newGarmentInputMode === 'url' ? 'active' : ''}`}
                  onClick={() => setNewGarmentInputMode('url')}
                >
                  Image URL
                </button>
              </div>
            </div>

            {newGarmentInputMode === 'upload' ? (
              <div
                className={`garment-image-dropzone ${newGarmentImage ? 'has-preview' : ''}`}
                onDragOver={e => e.preventDefault()}
                onDrop={handleGarmentImageDrop}
                onClick={() => !newGarmentImage && garmentFileInputRef.current?.click()}
              >
                <input
                  ref={garmentFileInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp,image/jpg"
                  style={{ display: 'none' }}
                  onChange={handleGarmentImageFileChange}
                />

                {newGarmentImage ? (
                  <div className="garment-upload-preview-card">
                    <img src={newGarmentImage} alt="Cloth Preview" className="garment-upload-preview-thumb" />
                    <div className="garment-upload-preview-info">
                      <span className="garment-upload-filename">{newGarmentImageName || 'Cloth Photograph'}</span>
                      <span className="garment-upload-badge">Ready for Closet</span>
                      <button
                        type="button"
                        className="garment-upload-change-link"
                        onClick={(e) => {
                          e.stopPropagation();
                          garmentFileInputRef.current?.click();
                        }}
                      >
                        Change image
                      </button>
                    </div>
                    <button
                      type="button"
                      className="garment-upload-remove-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleClearGarmentImage();
                      }}
                      title="Remove image"
                    >
                      <X size={14} />
                    </button>
                  </div>
                ) : (
                  <div className="garment-dropzone-prompt">
                    <div className="dropzone-icon-ring">
                      <UploadSimple size={22} />
                    </div>
                    <span className="dropzone-primary-text">Click to browse cloth photo, or drag & drop</span>
                    <span className="dropzone-hint-text">PNG, JPG, or WEBP up to 15MB</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="form-item-url-wrap">
                <input
                  type="url"
                  value={newGarmentImage}
                  onChange={e => setNewGarmentImage(e.target.value)}
                  placeholder="https://images.unsplash.com/... or paste image URL"
                  className="modal-input"
                />
                {newGarmentImage && (
                  <div className="url-preview-chip">
                    <img src={newGarmentImage} alt="Cloth Preview" onError={() => toast.error('Invalid image URL')} />
                    <span>Preview loaded</span>
                    <button type="button" onClick={handleClearGarmentImage} className="url-clear-btn">
                      <X size={12} />
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* AI 3D Prompt Link */}
          <div className="modal-3d-hint-card">
            <div className="modal-3d-hint-text">
              <Sparkle size={15} className="hint-sparkle-icon" />
              <span>Want your 3D avatar to wear this in real time?</span>
            </div>
            <button
              type="button"
              className="modal-3d-hint-btn"
              onClick={() => {
                handleClearGarmentImage();
                openPhoto3DWorkflow();
              }}
            >
              Photo-to-3D Studio
            </button>
          </div>

          <div className="form-item">
            <label>Piece Name <span className="required-star">*</span></label>
            <input
              type="text"
              value={newGarmentName}
              onChange={e => setNewGarmentName(e.target.value)}
              placeholder="e.g. Chikankari Kurta, Raw Silk Bandhgala, Structured Blazer"
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
              <option value="top">Top / Shirt / Knitwear</option>
              <option value="bottom">Bottom / Trousers / Jeans</option>
              <option value="outerwear">Outerwear / Coat / Jacket</option>
              <option value="footwear">Footwear / Shoes / Boots</option>
              <option value="accessory">Accessory / Watch / Bag</option>
            </select>
          </div>

          <div className="form-row-2col">
            <div className="form-item">
              <label>Primary Color</label>
              <input
                type="text"
                value={newGarmentColor}
                onChange={e => setNewGarmentColor(e.target.value)}
                placeholder="e.g. Navy Blue, Ivory, Camel"
                className="modal-input"
              />
            </div>
            <div className="form-item">
              <label>Brand / Atelier</label>
              <input
                type="text"
                value={newGarmentBrand}
                onChange={e => setNewGarmentBrand(e.target.value)}
                placeholder="e.g. Manyavar, Zara, Custom"
                className="modal-input"
              />
            </div>
          </div>

          <div className="form-row-2col">
            <div className="form-item">
              <label>Warmth (1-10): {newGarmentWarmth}</label>
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
              <label>Formality (1-10): {newGarmentFormality}</label>
              <input
                type="range"
                min="1"
                max="10"
                value={newGarmentFormality}
                onChange={e => setNewGarmentFormality(Number(e.target.value))}
                className="modal-range"
              />
            </div>
          </div>

          <div className="modal-form-actions">
            <button
              type="button"
              className="btn-secondary"
              onClick={() => { closeTrayWorkflow(); handleClearGarmentImage(); }}
            >
              Cancel
            </button>
            <button type="submit" className="btn-primary">
              Add to Digital Closet
            </button>
          </div>
        </form>
      </div>
    </div>
  );

  // ── IN-TRAY WORKSPACE: CUSTOMISE WARDROBE CATEGORIES ──
  const renderInTrayCategories = () => (
    <div className="in-tray-embedded-workflow" role="region" aria-label="Customise Categories">
      <div className="in-tray-nav-topbar">
        <button
          type="button"
          className="in-tray-back-btn"
          onClick={closeTrayWorkflow}
          title="Back to Wardrobe"
        >
          <CaretLeft size={16} weight="bold" />
          <span>Back</span>
        </button>
        <span className="in-tray-workflow-title">Customise Categories</span>
        <button
          type="button"
          className="in-tray-close-btn"
          onClick={closeTrayWorkflow}
          title="Close Workspace"
        >
          <X size={16} />
        </button>
      </div>
      <div className="in-tray-workflow-body">
        <Suspense fallback={<WorkflowSkeleton title="Loading Categories..." />}>
          <CategoryManagerModal
            isOpen={true}
            embedded={true}
            onClose={closeTrayWorkflow}
            userId={user?.id}
            onCategoryChanged={() => {
              setCategories(wardrobeCategoryService.getCategories(user?.id));
            }}
          />
        </Suspense>
      </div>
    </div>
  );

  const renderAvatarCustomizer = () => (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
      <Suspense fallback={<AvatarCreatorSkeleton />}>
        <AvatarCreatorStudio
          engine={creatorEngineRef.current}
          viewerRef={viewerRef}
          onProfileChange={handleCreatorProfileChange}
          userId={user?.id}
          selectedCategory={activeAvatarCategory}
          onCategoryChange={handleAvatarCategorySelect}
          hideInternalCategoryTabs={true}
          onSaveSuccess={() => {
            luxuryToast.saved('Avatar changes saved to your Yorvyn profile!');
          }}
        />
      </Suspense>
    </div>
  );

  // ── MORPHING SECONDARY NAVIGATION RENDERERS ──
  const renderFashionSecondaryNav = () => {
    const customCats = categories.filter(c => !c.isDefault && c.isVisible !== false);
    const combinedCats = [
      ...FASHION_SECONDARY_CATEGORIES,
      ...customCats.filter(cc => !FASHION_SECONDARY_CATEGORIES.some(f => f.id.toLowerCase() === cc.id.toLowerCase()))
    ];

    return (
      <>
        {combinedCats.map(cat => {
          const isActive = activeFashionCategory.toLowerCase() === cat.id.toLowerCase();
          return (
            <button
              key={cat.id}
              type="button"
              className={`morph-sec-item-btn icon-only-nav ${isActive ? 'active' : ''}`}
              onClick={(e) => {
                e.stopPropagation();
                setActiveFashionCategory(cat.id);
              }}
              aria-label={cat.label}
              role="tab"
              aria-selected={isActive}
            >
              <CategoryIcon
                category={'iconType' in cat ? (cat as WardrobeCategory) : undefined}
                iconKey={cat.iconKey}
                size={16}
                weight={isActive ? 'fill' : 'regular'}
              />
              {isActive && (
                <motion.span
                  layoutId="morph-sec-fashion-dot"
                  className="morph-sec-dot"
                  transition={{ duration: 0.38, ease: [0.16, 1, 0.3, 1] }}
                />
              )}
            </button>
          );
        })}

        {/* Category Management Button (+) */}
        <button
          type="button"
          className="morph-sec-add-btn"
          onClick={(e) => {
            e.stopPropagation();
            openCategoriesWorkflow();
          }}
          title="Add / Customise Wardrobe Categories"
          aria-label="Add or Customise Wardrobe Categories"
        >
          <Plus size={14} strokeWidth={2.5} />
        </button>
      </>
    );
  };

  const renderWardrobeSecondaryNav = () => {
    const customCats = categories.filter(c => !c.isDefault && c.isVisible !== false);
    const combinedCats = [
      ...WARDROBE_SECONDARY_CATEGORIES,
      ...customCats.filter(cc => !WARDROBE_SECONDARY_CATEGORIES.some(w => w.id.toLowerCase() === cc.id.toLowerCase()))
    ];

    return (
      <>
        {combinedCats.map(cat => {
          const isActive = activeWardrobeCategory.toLowerCase() === cat.id.toLowerCase();
          return (
            <button
              key={cat.id}
              type="button"
              className={`morph-sec-item-btn icon-only-nav ${isActive ? 'active' : ''}`}
              onClick={(e) => {
                e.stopPropagation();
                setActiveWardrobeCategory(cat.id);
              }}
              aria-label={cat.label}
              role="tab"
              aria-selected={isActive}
            >
              <CategoryIcon
                category={'iconType' in cat ? (cat as WardrobeCategory) : undefined}
                iconKey={cat.iconKey}
                size={16}
                weight={isActive ? 'fill' : 'regular'}
              />
              {isActive && (
                <motion.span
                  layoutId="morph-sec-wardrobe-dot"
                  className="morph-sec-dot"
                  transition={{ duration: 0.38, ease: [0.16, 1, 0.3, 1] }}
                />
              )}
            </button>
          );
        })}

        {/* Category Management Button (+) */}
        <button
          type="button"
          className="morph-sec-add-btn"
          onClick={(e) => {
            e.stopPropagation();
            openCategoriesWorkflow();
          }}
          title="Add / Customise Wardrobe Categories"
          aria-label="Add or Customise Wardrobe Categories"
        >
          <Plus size={14} strokeWidth={2.5} />
        </button>
      </>
    );
  };

  const renderAvatarSecondaryNav = () => {
    return (
      <>
        {AVATAR_SECONDARY_CATEGORIES.map(cat => {
          const isActive = activeAvatarCategory === cat.id;
          return (
            <button
              key={cat.id}
              type="button"
              className={`morph-sec-item-btn icon-only-nav ${isActive ? 'active' : ''}`}
              onClick={(e) => {
                e.stopPropagation();
                handleAvatarCategorySelect(cat.id);
              }}
              aria-label={cat.label}
              role="tab"
              aria-selected={isActive}
            >
              <CategoryIcon
                iconKey={cat.iconKey}
                size={16}
                weight={isActive ? 'fill' : 'regular'}
              />
              {isActive && (
                <motion.span
                  layoutId="morph-sec-avatar-dot"
                  className="morph-sec-dot"
                  transition={{ duration: 0.38, ease: [0.16, 1, 0.3, 1] }}
                />
              )}
            </button>
          );
        })}
      </>
    );
  };

  const renderOutfitsPanel = () => {
    const ensembleOutfits = FASHION_CATALOG.filter(c => c.category === 'outfit');

    return (
      <div className="drawer-outfits-view" role="region" aria-label="Outfits & Capsule Wardrobe">
        {/* 1. Currently Equipped Mannequin Look Breakdown */}
        <div className="outfits-equipped-summary-card">
          <div className="outfits-summary-header">
            <span className="outfits-summary-eyebrow">Mannequin Attire</span>
            <span className="outfits-summary-badge">
              {equippedOutfit.slotType === 'full_outfit' ? 'Full Ensemble' : 'Layered Separates'}
            </span>
          </div>

          <div className="outfits-layers-list">
            <div className="outfit-layer-row">
              <span className="layer-slot-label">Outfit / Top</span>
              <strong className="layer-slot-value">
                {equippedOutfit.displayNames?.fullOutfit || equippedOutfit.displayNames?.top || (params.outfit !== 'none' ? 'Studio Signature Attire' : 'None')}
              </strong>
            </div>

            {equippedOutfit.displayNames?.bottom && (
              <div className="outfit-layer-row">
                <span className="layer-slot-label">Trousers</span>
                <strong className="layer-slot-value">{equippedOutfit.displayNames.bottom}</strong>
              </div>
            )}

            {equippedOutfit.displayNames?.outerwear && (
              <div className="outfit-layer-row">
                <span className="layer-slot-label">Outerwear</span>
                <strong className="layer-slot-value">{equippedOutfit.displayNames.outerwear}</strong>
              </div>
            )}

            <div className="outfit-layer-row">
              <span className="layer-slot-label">Footwear</span>
              <strong className="layer-slot-value">
                {equippedOutfit.displayNames?.shoes || 'Atelier Minimalist Shoes'}
              </strong>
            </div>
          </div>

          <div className="outfits-actions-row">
            <button
              type="button"
              className="outfits-action-btn primary"
              onClick={handleSaveAvatar}
              title="Save current look to digital wardrobe"
            >
              <FloppyDisk size={16} />
              <span>Save Look</span>
            </button>

            <button
              type="button"
              className="outfits-action-btn secondary"
              onClick={handleResetOutfit}
              title="Reset avatar to neutral studio attire"
            >
              <ArrowCounterClockwise size={16} />
              <span>Reset Look</span>
            </button>

            <button
              type="button"
              className="outfits-action-btn outline"
              onClick={handleUndressToMannequin}
              title="Remove all clothing to bare neutral mannequin base"
            >
              <User size={16} />
              <span>Undress All</span>
            </button>
          </div>
        </div>

        {/* 2. Curated Capsule Ensembles Grid */}
        <div className="drawer-section-header" style={{ padding: '0.75rem 0.25rem 0.45rem' }}>
          <h3>Curated Ensembles</h3>
          <span className="section-counter">{ensembleOutfits.length} looks</span>
        </div>

        <div className="drawer-catalog-grid">
          {ensembleOutfits.map(item => {
            const isEquipped = equippedOutfit.fullOutfitId === item.id || selectedGarmentId === item.id;
            return (
              <div
                key={item.id}
                className={`clothing-card-item pure-white-card ${isEquipped ? 'selected' : ''}`}
                onClick={() => handleSelectGarment(item)}
                title={`Try on ${item.name}`}
              >
                {isEquipped && (
                  <div className="clothing-card-selected-badge" aria-label="Equipped">
                    <Check size={12} strokeWidth={3} />
                  </div>
                )}
                <div className="clothing-card-image-wrap">
                  {item.imageUrl ? (
                    <img
                      src={item.imageUrl}
                      alt={item.name}
                      className="clothing-card-img"
                      loading="lazy"
                    />
                  ) : (
                    <div className="clothing-card-placeholder">
                      <CoatHanger size={28} color="#64748b" />
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* 3. Custom Uploads / Wardrobe Archive */}
        {wardrobeItems.length > 0 && (
          <>
            <div className="drawer-section-header" style={{ padding: '0.85rem 0.25rem 0.45rem' }}>
              <h3>Wardrobe Pieces</h3>
              <span className="section-counter">{wardrobeItems.length} custom</span>
            </div>

            <div className="drawer-catalog-grid">
              {wardrobeItems.map(item => {
                const isEquipped = activeCustomGarment?.id === item.id;
                return (
                  <div
                    key={item.id}
                    className={`clothing-card-item pure-white-card ${isEquipped ? 'selected' : ''}`}
                    onClick={() => handleDrapeWardrobePiece(item)}
                    title={`Try on ${item.name}`}
                  >
                    {isEquipped && (
                      <div className="clothing-card-selected-badge" aria-label="Equipped">
                        <Check size={12} strokeWidth={3} />
                      </div>
                    )}
                    <div className="clothing-card-image-wrap">
                      <img
                        src={item.thumbnail_url || item.image_url || '/items/card_casual.jpg'}
                        alt={item.name}
                        className="clothing-card-img"
                        loading="lazy"
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    );
  };

  return (
    <div
      className={`avatar-stage-container scene-${scene} ${isResizingTray ? 'is-resizing' : ''}`}
      style={{
        '--drawer-w': `${trayWidth}px`,
        '--drawer-workflow-w': `${trayPreset === 'custom' ? Math.max(trayWidth, 540) : 580}px`
      } as React.CSSProperties}
    >
      {/* ── 1. ATMOSPHERIC LUXURY STUDIO (Pure CSS Sky Blue Gradient) ── */}

      {/* ── 2. YORVYN LUXURY TOP BAR (Matches Reference Screenshot) ── */}
      <header className="stage-top-bar" role="banner">
        {/* Left: Brand Wordmark */}
        <div className="top-bar-left">
          <button type="button" className="top-brand-wordmark" onClick={() => navigate('/')} aria-label="Yorvyn home">
            Yorvyn
          </button>
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
        </div>

        {/* Center: Save Look Pill Button (Centered relative to Studio Viewport) */}
        <div className="top-bar-center">
          <button
            type="button"
            className="top-save-look-pill"
            onClick={handleSaveAvatar}
            aria-label="Save Look"
          >
            <BookmarkSimple size={16} weight="regular" />
            <span>Save Look</span>
          </button>
        </div>

        {/* Right: Empty to match clean reference design */}
        <div className="top-bar-actions" />
      </header>

      {/* ── 3. MAIN STUDIO WORKSPACE (Unified Flex Row Layout) ── */}
      <div className="studio-workspace">
        {/* Central 3D Avatar Stage */}
        <main className="avatar-viewport">

        {/* Floating Pet Companion */}
        {showPet && (
          <div className="floating-pet-companion">
            <div className="pet-avatar-bubble">
              <Sparkle size={16} />
            </div>
            <span className="pet-label">Yorvyn Companion</span>
          </div>
        )}

        {/* Center 3D Interactive Canvas */}
        <div className="avatar-canvas-wrapper">
          <AvatarPreviewBanner
            onAccepted={() => {
              const accepted = creatorEngineRef.current.getProfile();
              handleCreatorProfileChange(accepted);
            }}
            onRejected={() => {
              const reverted = creatorEngineRef.current.getProfile();
              handleCreatorProfileChange(reverted);
            }}
          />
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
            customGarmentSubcategory={activeCustomGarment?.subcategory || null}
            onCustomGarmentFitResult={(result) => {
              if (!result.fitted) {
                setActiveCustomGarment((prev) => (prev?.glb_url === result.url ? null : prev));
                toast.error(result.error || 'Could not place garment on avatar.');
              } else if (result.majorPenetrationDetected) {
                toast(
                  `Garment fitted with minor body overlap (${(result.maxPenetrationMm ?? 0).toFixed(1)}mm).`,
                  { icon: '⚠️' }
                );
              }
            }}
            heightCm={(profile?.heightUnit === 'ft' ? Math.round(profile.heightValue * 30.48) : profile?.heightValue) || 178}
            bodySilhouetteId={profile?.bodyType || 'regular'}
            clothSimulationEnabled={true}
            clothQualityMode={clothQuality}
          />
          {character && !loading && (
            <div
              data-testid="avatar-motion-bar"
              role="toolbar"
              aria-label="Character Motion Preview"
              style={{
                position: 'absolute',
                top: 14,
                right: 14,
                display: 'flex',
                flexWrap: 'wrap',
                gap: 4,
                maxWidth: 360,
                justifyContent: 'flex-end',
                background: 'rgba(255, 255, 255, 0.86)',
                backdropFilter: 'blur(8px)',
                padding: '6px 8px',
                borderRadius: 12,
                border: '1px solid rgba(15, 23, 42, 0.1)',
                zIndex: 12,
              }}
            >
              {(
                [
                  ['IDLE', 'Idle'],
                  ['WALK', 'Walk'],
                  ['RUN', 'Run'],
                  ['TURN', 'Turn'],
                  ['RAISE_ARMS', 'Raise Arms'],
                  ['BEND', 'Bend'],
                  ['SIT', 'Sit'],
                  ['STAND', 'Stand'],
                ] as [MotionState, string][]
              ).map(([st, label]) => (
                <button
                  key={st}
                  type="button"
                  onClick={() => {
                    let ok = viewerRef.current?.setMotionState?.(st);
                    if (!ok && st !== 'IDLE') {
                      viewerRef.current?.setMotionState?.('IDLE');
                      ok = viewerRef.current?.setMotionState?.(st);
                    }
                    if (ok) {
                      setMotionPreviewState(st);
                      setMotionPaused(false);
                    }
                  }}
                  style={{
                    fontSize: 11,
                    padding: '3px 7px',
                    borderRadius: 8,
                    border: '1px solid #cbd5e1',
                    background: motionPreviewState === st && !motionPaused ? '#0f172a' : '#fff',
                    color: motionPreviewState === st && !motionPaused ? '#fff' : '#0f172a',
                    cursor: 'pointer',
                  }}
                >
                  {label}
                </button>
              ))}
              <button
                type="button"
                onClick={() => {
                  if (motionPaused) {
                    viewerRef.current?.resumeMotion?.();
                    setMotionPaused(false);
                  } else {
                    viewerRef.current?.pauseMotion?.();
                    setMotionPaused(true);
                  }
                }}
                style={{ fontSize: 11, padding: '3px 7px', borderRadius: 8, border: '1px solid #cbd5e1', background: '#fff', cursor: 'pointer' }}
              >
                {motionPaused ? 'Resume' : 'Pause'}
              </button>
              <button
                type="button"
                onClick={() => {
                  viewerRef.current?.resetMotionPose?.();
                  setMotionPreviewState('IDLE');
                  setMotionPaused(false);
                }}
                style={{ fontSize: 11, padding: '3px 7px', borderRadius: 8, border: '1px solid #cbd5e1', background: '#fff', cursor: 'pointer' }}
              >
                Reset Pose
              </button>
              <button
                type="button"
                onClick={handleDownloadGlb}
                disabled={isExporting}
                style={{ fontSize: 11, padding: '3px 7px', borderRadius: 8, border: '1px solid #0284c7', background: '#e0f2fe', color: '#0369a1', cursor: 'pointer' }}
              >
                Export Animated
              </button>
            </div>
          )}
        </div>



        {/* Horizontal Bottom Stadium Capsule: Core Avatar Controls (Matches Reference Screenshot) */}
        <div className="stage-bottom-pill" role="toolbar" aria-label="3D Avatar Viewport Controls">
          {/* 1. Undo */}
          <button
            className="stage-circle-action-btn"
            onClick={handleUndo}
            disabled={historyIndex <= 0}
            aria-label="Undo"
          >
            <ArrowCounterClockwise size={18} />
            <span className="stage-circle-tooltip pure-white-tooltip" role="tooltip">
              <span className="tooltip-action-title">Undo</span>
              {!deviceCommands.isSmallScreen && (
                <span className="tooltip-meta-group">
                  <kbd className="tooltip-kbd">{deviceCommands.shortcuts.undo.display}</kbd>
                </span>
              )}
            </span>
          </button>

          {/* 2. Redo */}
          <button
            className="stage-circle-action-btn"
            onClick={handleRedo}
            disabled={historyIndex >= history.length - 1 || historyIndex === -1}
            aria-label="Redo"
          >
            <ArrowClockwise size={18} />
            <span className="stage-circle-tooltip pure-white-tooltip" role="tooltip">
              <span className="tooltip-action-title">Redo</span>
              {!deviceCommands.isSmallScreen && (
                <span className="tooltip-meta-group">
                  <kbd className="tooltip-kbd">{deviceCommands.shortcuts.redo.display}</kbd>
                </span>
              )}
            </span>
          </button>

          {/* 3. Fit to Screen / Center (Neutral Liquid Glass) */}
          <button
            className="stage-circle-action-btn"
            onClick={() => {
              if (viewMode !== 'full') {
                setViewMode('full');
              }
              viewerRef.current?.focusFullBody?.();
              luxuryToast.centerFrame('Centered avatar on stage');
            }}
            aria-label="Fit to Screen"
          >
            <ArrowsOut size={18} weight="bold" />
            <span className="stage-circle-tooltip pure-white-tooltip" role="tooltip">
              <span className="tooltip-action-title">Fit Frame</span>
              {!deviceCommands.isSmallScreen && (
                <span className="tooltip-meta-group">
                  <kbd className="tooltip-kbd">{deviceCommands.shortcuts.center.display}</kbd>
                  <span className="tooltip-gesture-chip">
                    {deviceCommands.isMac || deviceCommands.isChromebook
                      ? 'Two-Finger Swipe Orbit'
                      : deviceCommands.isMobileOrTouch
                        ? 'Double Tap'
                        : 'Left Drag Orbit'}
                  </span>
                </span>
              )}
            </span>
          </button>

          {/* 4. Zoom Out */}
          <button
            className="stage-circle-action-btn"
            onClick={() => viewerRef.current?.zoomOut()}
            aria-label="Zoom Out"
          >
            <MagnifyingGlassMinus size={18} />
            <span className="stage-circle-tooltip pure-white-tooltip" role="tooltip">
              <span className="tooltip-action-title">Zoom Out</span>
              {!deviceCommands.isSmallScreen && (
                <span className="tooltip-meta-group">
                  <kbd className="tooltip-kbd">{deviceCommands.shortcuts.zoomOut.display}</kbd>
                  <span className="tooltip-gesture-chip">
                    {deviceCommands.isMac || deviceCommands.isChromebook
                      ? 'Pinch Trackpad Zoom'
                      : deviceCommands.isMobileOrTouch
                        ? 'Pinch Fingers'
                        : 'Pinch / Wheel Zoom'}
                  </span>
                </span>
              )}
            </span>
          </button>

          {/* 5. Zoom In */}
          <button
            className="stage-circle-action-btn"
            onClick={() => viewerRef.current?.zoomIn()}
            aria-label="Zoom In"
          >
            <MagnifyingGlassPlus size={18} />
            <span className="stage-circle-tooltip pure-white-tooltip" role="tooltip">
              <span className="tooltip-action-title">Zoom In</span>
              {!deviceCommands.isSmallScreen && (
                <span className="tooltip-meta-group">
                  <kbd className="tooltip-kbd">{deviceCommands.shortcuts.zoomIn.display}</kbd>
                  <span className="tooltip-gesture-chip">
                    {deviceCommands.isMac || deviceCommands.isChromebook
                      ? 'Pinch Trackpad Zoom'
                      : deviceCommands.isMobileOrTouch
                        ? 'Pinch Fingers'
                        : 'Pinch / Wheel Zoom'}
                  </span>
                </span>
              )}
            </span>
          </button>
        </div>
      </main>

      {/* ── 3. SLIDING DRAWER / BOTTOM SHEET ── */}
      <section className={`stage-drawer-card ${drawerOpen ? 'expanded' : 'collapsed'} ${trayWorkflow !== 'none' || Boolean(inspectedItem) ? 'workflow-active' : ''}`}>
        {/* ── DRAGGABLE RESIZE HANDLE (DESKTOP) ── */}
        <div
          className={`drawer-resize-handle ${isResizingTray ? 'dragging' : ''}`}
          onMouseDown={handleMouseDownResize}
          onTouchStart={handleTouchStartResize}
          onDoubleClick={handleResetToDefault}
          onKeyDown={handleKeyDownResize}
          tabIndex={0}
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize interactive tray"
          aria-valuenow={trayWidth}
          aria-valuemin={320}
          aria-valuemax={typeof window !== 'undefined' ? Math.round(window.innerWidth * 0.65) : 880}
          title="Drag left/right to resize tray, or use arrow keys (Home: Compact, End: Expanded, Enter: Default)"
        >
          <div className="resize-handle-bar">
            <div className="resize-handle-grip" />
          </div>
        </div>

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
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          /* ── EXPANDED VIEW: Single-Screen Liquid Glass Unified Tray ── */
          <>
            {/* ── MORPHING EXCLUSIVE PRIMARY NAVIGATION (Fashion, Wardrobe, Avatar) ── */}
            <div className="tray-morphing-nav-container" role="navigation" aria-label="Morphing Primary Tray Navigation">
              <LayoutGroup id="yorvyn-morphing-tray-nav">
                <motion.div
                  layout
                  transition={morphTransition}
                  className={`tray-morphing-nav-bar ${expandedPrimarySection ? 'has-expanded' : 'all-collapsed'}`}
                >
                  {PRIMARY_NAV_SECTIONS.map((sec) => {
                    const isExpanded = expandedPrimarySection === sec.id;
                    const Icon = sec.icon;

                    if (isExpanded) {
                      return (
                        <motion.div
                          key={sec.id}
                          layout
                          layoutId={`morph-control-${sec.id}`}
                          transition={morphTransition}
                          className="morph-nav-control expanded"
                        >
                          {/* Leading Button: Active Primary Section Pill (Icon only, clicking collapses) */}
                          <button
                            type="button"
                            className="morph-primary-lead-btn"
                            onClick={() => handlePrimaryToggle(sec.id)}
                            title={`Collapse ${sec.label}`}
                            aria-label={`Collapse ${sec.label}`}
                            aria-expanded="true"
                          >
                            <span className="morph-lead-icon">
                              <Icon size={16} weight="fill" />
                            </span>
                            <CaretDown size={11} weight="bold" className="morph-lead-caret" />
                          </button>

                          <div className="morph-lead-divider" />

                          {/* Secondary Navigation Scroll Strip */}
                          <div className="morph-secondary-strip" role="tablist" aria-label={`${sec.label} Categories`}>
                            {sec.id === 'fashion' && renderFashionSecondaryNav()}
                            {sec.id === 'wardrobe' && renderWardrobeSecondaryNav()}
                            {sec.id === 'avatar' && renderAvatarSecondaryNav()}
                          </div>
                        </motion.div>
                      );
                    }

                    // Circular Button (when not expanded)
                    return (
                      <motion.div
                        key={sec.id}
                        layout
                        layoutId={`morph-control-${sec.id}`}
                        transition={morphTransition}
                        className="morph-nav-control circle"
                      >
                        <button
                          type="button"
                          className="morph-circle-btn"
                          onClick={() => handlePrimaryToggle(sec.id)}
                          title={`Expand ${sec.label}`}
                          aria-label={`Expand ${sec.label}`}
                          aria-expanded="false"
                        >
                          <Icon size={20} weight={activePrimaryTab === sec.id ? 'bold' : 'regular'} />
                        </button>
                      </motion.div>
                    );
                  })}
                </motion.div>
              </LayoutGroup>
            </div>

            {/* ── SCROLLABLE CONTENT AREA (Underneath Secondary Navigation) ── */}
            <div className={`tray-scrollable-content-area ${trayWorkflow === 'profile' ? 'profile-mode' : ''}`}>
              {inspectedItem ? (
                renderInTrayItemDetails()
              ) : trayWorkflow === 'profile' ? (
                renderInTrayProfile()
              ) : trayWorkflow === 'stylist' ? (
                renderInTrayStylist()
              ) : trayWorkflow === 'photo3d' ? (
                renderInTrayPhoto3D()
              ) : trayWorkflow === 'addPiece' ? (
                renderInTrayAddPiece()
              ) : trayWorkflow === 'categories' ? (
                renderInTrayCategories()
              ) : (
                <>
                  {/* ── TAB 1: FASHION (Saved Outfits & AI Recommendations Only) ── */}
                  {activePrimaryTab === 'fashion' && (
                    <div className="drawer-fashion-content fashion-streamlined-view">
                      {/* Top Curation Sub-Bar: Filter Switcher & Quick Save Action */}
                      <div className="fashion-curation-subbar">
                        <div className="fashion-filter-capsule" role="tablist" aria-label="Fashion Display Filter">
                          <button
                            type="button"
                            className={`fashion-filter-btn ${fashionFilterTab === 'saved' ? 'active' : ''}`}
                            onClick={() => setFashionFilterTab('saved')}
                            role="tab"
                            aria-selected={fashionFilterTab === 'saved'}
                          >
                            {fashionFilterTab === 'saved' && (
                              <motion.div
                                layoutId="active-fashion-filter-pill"
                                className="fashion-filter-active-pill"
                                transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                              />
                            )}
                            <span className="fashion-filter-label">Saved Outfits ({savedOutfits.length})</span>
                          </button>

                          <button
                            type="button"
                            className={`fashion-filter-btn ${fashionFilterTab === 'ai' ? 'active' : ''}`}
                            onClick={() => setFashionFilterTab('ai')}
                            role="tab"
                            aria-selected={fashionFilterTab === 'ai'}
                          >
                            {fashionFilterTab === 'ai' && (
                              <motion.div
                                layoutId="active-fashion-filter-pill"
                                className="fashion-filter-active-pill"
                                transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                              />
                            )}
                            <span className="fashion-filter-label">AI Recommended ({OUTFIT_SUGGESTIONS.length + generatedOutfits.length})</span>
                          </button>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <button
                            type="button"
                            className="fashion-quick-save-btn"
                            onClick={openStylistWorkflow}
                            title="Consult with Yorvyn AI Stylist"
                          >
                            <Sparkle size={15} weight="regular" />
                            <span>Ask Stylist</span>
                          </button>
                          <button
                            type="button"
                            className="fashion-quick-save-btn"
                            onClick={handleSaveCurrentOutfit}
                            title="Save avatar's current look to Saved Outfits"
                          >
                            <BookmarkSimple size={15} weight="bold" />
                            <span>Save Current</span>
                          </button>
                        </div>
                      </div>

                      {/* ── SECTION 2: SAVED OUTFITS (When fashionFilterTab === 'saved') ── */}
                      {fashionFilterTab === 'saved' && (
                    <section className="fashion-section-block saved-outfits-section" aria-label="Saved Outfits">
                      <div className="fashion-section-header">
                        <div className="fashion-section-title-wrap">
                          <BookmarkSimple size={18} weight="fill" className="section-title-icon bookmark-icon" />
                          <h3 className="fashion-section-title">Saved Outfits</h3>
                          <span className="fashion-count-badge">{savedOutfits.length} looks</span>
                        </div>
                        <button
                          type="button"
                          className="fashion-add-outfit-link"
                          onClick={handleSaveCurrentOutfit}
                          title="Save current avatar styling as a new outfit"
                        >
                          <Plus size={13} weight="bold" />
                          <span>Save Current</span>
                        </button>
                      </div>

                      <div className="saved-outfits-grid">
                        {savedOutfits.map(outfit => {
                          const isEquipped = (equippedOutfit.fullOutfitId === outfit.id) ||
                            (outfit.appliedParams.outfit && outfit.appliedParams.outfit !== 'none' && params.outfit === outfit.appliedParams.outfit);
                          const isFavorite = favorites.has(outfit.id);

                          return (
                            <motion.div
                              key={outfit.id}
                              className={`saved-outfit-card pure-white-card ${isEquipped ? 'equipped' : ''}`}
                              onClick={() => handleApplySavedOutfit(outfit)}
                              whileHover={{ y: -3, scale: 1.015 }}
                              whileTap={{ scale: 0.97 }}
                              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                            >
                              {/* Top Action Pills: Favorite & Delete if custom */}
                              <div className="saved-card-top-actions">
                                <button
                                  type="button"
                                  className={`card-favorite-btn ${isFavorite ? 'active' : ''}`}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    toggleFavorite(outfit.id);
                                  }}
                                  title={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
                                  aria-label="Toggle favorite"
                                >
                                  <Heart size={14} weight={isFavorite ? 'fill' : 'regular'} color={isFavorite ? '#ef4444' : '#94a3b8'} />
                                </button>
                                {outfit.isCustom && (
                                  <button
                                    type="button"
                                    className="card-delete-btn"
                                    onClick={(e) => handleDeleteSavedOutfit(outfit.id, e)}
                                    title="Delete saved look"
                                    aria-label="Delete saved look"
                                  >
                                    <Trash size={13} color="#94a3b8" />
                                  </button>
                                )}
                              </div>

                              {/* Equipped Badge */}
                              {isEquipped && (
                                <motion.div
                                  className="outfit-equipped-pill"
                                  initial={{ scale: 0, opacity: 0 }}
                                  animate={{ scale: 1, opacity: 1 }}
                                  transition={{ type: 'spring', stiffness: 500, damping: 28 }}
                                >
                                  <Check size={11} strokeWidth={3} />
                                  <span>Wearing</span>
                                </motion.div>
                              )}

                              {/* Visual Preview */}
                              <div className="saved-outfit-visual">
                                {outfit.imageUrl ? (
                                  <img
                                    src={outfit.imageUrl}
                                    alt={outfit.title}
                                    className="saved-outfit-img"
                                    loading="lazy"
                                    decoding="async"
                                  />
                                ) : (
                                  <div className="saved-outfit-placeholder">
                                    <CoatHanger size={32} color="#94a3b8" />
                                  </div>
                                )}
                              </div>

                              {/* Info Footer */}
                              <div className="saved-outfit-info">
                                <span className="saved-outfit-tag">{outfit.tag}</span>
                                <h4 className="saved-outfit-title">{outfit.title}</h4>
                                <span className="saved-outfit-date">{outfit.date}</span>
                              </div>

                              {/* Wear Action Button */}
                              <button
                                type="button"
                                className={`saved-wear-btn ${isEquipped ? 'is-wearing' : ''}`}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleApplySavedOutfit(outfit);
                                }}
                              >
                                <Sparkle size={13} weight="fill" />
                                <span>{isEquipped ? 'Wearing on Twin' : 'Wear on Twin'}</span>
                              </button>
                            </motion.div>
                          );
                        })}
                      </div>
                    </section>
                  )}

                  {/* ── SECTION 3: AI RECOMMENDATIONS (When fashionFilterTab === 'ai') ── */}
                  {fashionFilterTab === 'ai' && (
                    <section className="fashion-section-block ai-recommendations-section" aria-label="AI Recommendations">
                      <div className="fashion-section-header">
                        <div className="fashion-section-title-wrap">
                          <Sparkle size={18} weight="fill" className="section-title-icon ai-sparkle-icon" />
                          <h3 className="fashion-section-title">AI Recommendations</h3>
                          <span className="fashion-count-badge">
                            {OUTFIT_SUGGESTIONS.length + generatedOutfits.length} curated
                          </span>
                        </div>
                        <button
                          type="button"
                          className="fashion-refresh-ai-btn"
                          onClick={handleGenerateOutfits}
                          disabled={outfitLoading}
                          title="Generate new AI outfit recommendations"
                        >
                          <ArrowClockwise size={13} className={outfitLoading ? 'spin' : ''} />
                          <span>Generate Looks</span>
                        </button>
                      </div>

                      {/* Occasion / Aesthetic Filter Pills */}
                      <div className="ai-occasion-filter-scroll" role="tablist" aria-label="Filter AI looks by occasion">
                        {[
                          { id: 'all', label: 'All Vibes' },
                          { id: 'quiet_luxury', label: 'Quiet Luxury' },
                          { id: 'casual_day', label: 'Casual Day' },
                          { id: 'work_office', label: 'Work & Office' },
                          { id: 'streetwear', label: 'Streetwear' },
                          { id: 'date_night', label: 'Date Night' }
                        ].map(occ => {
                          const isOccActive = aiOccasionFilter === occ.id;
                          return (
                            <button
                              key={occ.id}
                              type="button"
                              className={`ai-occasion-chip ${isOccActive ? 'active' : ''}`}
                              onClick={() => {
                                setAiOccasionFilter(occ.id);
                                if (occ.id !== 'all') {
                                  setOutfitOccasion(occ.id);
                                }
                              }}
                              role="tab"
                              aria-selected={isOccActive}
                            >
                              <span>{occ.label}</span>
                            </button>
                          );
                        })}
                      </div>

                      {/* AI Recommendations Cards */}
                      <div className="ai-recommendations-list">
                        {/* 1. Curated AI Outfit Suggestions */}
                        {OUTFIT_SUGGESTIONS.filter(sugg => {
                          if (aiOccasionFilter === 'all') return true;
                          const t = (sugg.title + ' ' + sugg.id).toLowerCase();
                          if (aiOccasionFilter === 'streetwear') return t.includes('street') || t.includes('monochrome');
                          if (aiOccasionFilter === 'casual_day') return t.includes('casual') || t.includes('ecru');
                          if (aiOccasionFilter === 'quiet_luxury') return t.includes('sage') || t.includes('earth') || t.includes('ecru');
                          return true;
                        }).map(sugg => {
                          const isSuggEquipped = (sugg.appliedParams.outfit && sugg.appliedParams.outfit !== 'none' && params.outfit === sugg.appliedParams.outfit) ||
                            (sugg.appliedParams.top && params.top === sugg.appliedParams.top);

                          return (
                            <motion.div
                              key={sugg.id}
                              className={`ai-recommendation-card pure-white-card ${isSuggEquipped ? 'equipped' : ''}`}
                              onClick={() => handleApplyOutfitSuggestion(sugg)}
                              whileHover={{ y: -3, scale: 1.01 }}
                              whileTap={{ scale: 0.98 }}
                              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                            >
                              <div className="ai-rec-card-main">
                                {/* Visual Composite with model + swatch pieces */}
                                <div className="ai-rec-visual-composite">
                                  <img
                                    src={sugg.modelImage}
                                    alt={sugg.title}
                                    className="ai-rec-model-img"
                                    loading="lazy"
                                  />
                                  <div className="ai-rec-pieces-column">
                                    {sugg.pieces.map((p, pIdx) => (
                                      <div key={pIdx} className="ai-rec-piece-thumb" title={p.name}>
                                        <img src={p.imageUrl} alt={p.name} />
                                      </div>
                                    ))}
                                  </div>
                                </div>

                                {/* Content Details */}
                                <div className="ai-rec-content-wrap">
                                  <div className="ai-rec-header-row">
                                    <h4 className="ai-rec-title">{sugg.title}</h4>
                                    <span className="ai-rec-score-pill">98% Harmony</span>
                                  </div>

                                  <p className="ai-rec-rationale">
                                    Curated AI ensemble fitted with proportional balance and palette harmony.
                                  </p>

                                  <div className="ai-rec-action-row">
                                    <button
                                      type="button"
                                      className={`ai-rec-drape-btn ${isSuggEquipped ? 'is-wearing' : ''}`}
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleApplyOutfitSuggestion(sugg);
                                      }}
                                    >
                                      <Sparkle size={13} weight="fill" />
                                      <span>{isSuggEquipped ? 'Wearing on 3D Twin' : 'Drape on 3D Twin'}</span>
                                    </button>
                                  </div>
                                </div>
                              </div>
                            </motion.div>
                          );
                        })}

                        {/* 2. Dynamically Generated AI Outfits from Stylist Engine */}
                        {generatedOutfits.map(outfit => (
                          <motion.div
                            key={outfit.outfit_id}
                            className="ai-recommendation-card pure-white-card dynamic-ai-card"
                            onClick={() => handleDrapeOutfitOnAvatar(outfit)}
                            whileHover={{ y: -3, scale: 1.01 }}
                            whileTap={{ scale: 0.98 }}
                            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                          >
                            <div className="ai-rec-card-main">
                              <div className="ai-rec-content-wrap full-width">
                                <div className="ai-rec-header-row">
                                  <h4 className="ai-rec-title">{outfit.title}</h4>
                                  <span className="ai-rec-score-pill">{Math.round(outfit.match_score * 100)}% Harmony</span>
                                </div>

                                <p className="ai-rec-rationale">{outfit.styling_rationale}</p>

                                {/* Color Palette Dots */}
                                {outfit.color_palette && outfit.color_palette.length > 0 && (
                                  <div className="outfit-palette-row">
                                    {outfit.color_palette.map((col, cIdx) => (
                                      <span
                                        key={cIdx}
                                        className="color-dot"
                                        style={{ backgroundColor: col }}
                                        title={col}
                                      />
                                    ))}
                                  </div>
                                )}

                                <div className="ai-rec-action-row">
                                  <button
                                    type="button"
                                    className="ai-rec-drape-btn"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleDrapeOutfitOnAvatar(outfit);
                                    }}
                                  >
                                    <Sparkle size={13} weight="fill" />
                                    <span>Drape on 3D Avatar</span>
                                  </button>
                                </div>
                              </div>
                            </div>
                          </motion.div>
                        ))}
                      </div>
                    </section>
                  )}
                </div>
              )}

            {/* ── TAB 2: AI STYLIST CHAT ── */}
            {primaryTab === 'stylist' && (
              <div className="drawer-stylist-chat-view">
                {/* Quick Prompts */}
                <div className="stylist-quick-prompts">
                  {[
                    "Premium casual look for college",
                    "Formal outfit for job interview",
                    "Streetwear under ₹15,000",
                    "Quiet luxury dinner ensemble",
                    "Festive wedding cocktail look",
                    "Layered look from my wardrobe"
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

                      {renderGarment(msg)}
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

                              {/* Color Palette Swatches */}
                              {outfit.color_palette && outfit.color_palette.length > 0 && (
                                <div style={{ display: 'flex', gap: '4px', margin: '4px 0 8px 0', alignItems: 'center' }}>
                                  <span style={{ fontSize: '0.65rem', color: '#94a3b8', marginRight: 4 }}>Palette:</span>
                                  {outfit.color_palette.map((c, i) => (
                                    <span
                                      key={i}
                                      style={{
                                        width: 14,
                                        height: 14,
                                        borderRadius: '50%',
                                        backgroundColor: c,
                                        border: '1px solid rgba(0,0,0,0.15)',
                                        display: 'inline-block'
                                      }}
                                    />
                                  ))}
                                </div>
                              )}

                              <div className="rec-actions">
                                <button
                                  className="rec-action-btn primary"
                                  onClick={() => handleDrapeOutfitOnAvatar(outfit)}
                                >
                                  <Sparkle size={14} />
                                  <span>Drape on 3D Avatar</span>
                                </button>
                                <button
                                  className="rec-action-btn secondary"
                                  onClick={() => handleLikeOutfit(outfit.outfit_id)}
                                  title="Love this look"
                                  style={{ padding: '0.35rem 0.55rem' }}
                                >
                                  <Heart size={14} />
                                </button>
                                <button
                                  className="rec-action-btn secondary"
                                  onClick={() => handleDislikeOutfit(outfit.outfit_id, 'too_formal')}
                                  title="Dislike this style"
                                  style={{ padding: '0.35rem 0.55rem', fontSize: '0.72rem' }}
                                >
                                  <ThumbsDown size={14} />
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                  {chatLoading && (
                    <>{garmentBusy && <p role="status">{garmentBusy}</p>}<ChatSkeleton /></>
                  )}
                  <div ref={chatBottomRef} />
                </div>

                {/* Chat Input */}
                <form
                  className="stylist-input-row"
                  onSubmit={(e) => { e.preventDefault(); handleSendStylistMessage(); }}
                >
                  {garmentAttachment}
            {garmentPhotos.length > 0 && <button type="button" onClick={()=>setGarmentPhotos([])} disabled={chatLoading}>Clear photos</button>}
            <input
                    type="text"
                    value={chatInput}
                    onChange={e => setChatInput(e.target.value)}
                    placeholder="Ask your AI Stylist (e.g. Wedding sherwani, Festive kurta, Linen shirt)..."
                    className="stylist-text-input"
                  />
                  <button type="submit" className="stylist-send-btn" aria-label="Send message" disabled={(!chatInput.trim() && !garmentPhotos.length) || chatLoading}>
                    <PaperPlaneTilt size={16} />
                  </button>
                </form>
              </div>
            )}

            {/* ── TAB 2: DIGITAL WARDROBE ── */}
            {activePrimaryTab === 'wardrobe' && (
              <div className="drawer-wardrobe-view">
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
                      onClick={openPhoto3DWorkflow}
                      title="Upload garment photo to generate wearable 3D clothing"
                    >
                      <Sparkle size={14} />
                      <span>Photo to 3D</span>
                    </button>
                    <button
                      className="wardrobe-add-btn"
                      onClick={openAddPieceWorkflow}
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
                      <span>Wearing: <strong>{activeCustomGarment.name}</strong></span>
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

                {/* When saved_outfits or collections is selected */}
                {activeWardrobeCategory === 'saved_outfits' || activeWardrobeCategory === 'collections' ? (
                  renderOutfitsPanel()
                ) : (
                  /* Wardrobe Grid with Progressive Windowing (Stage 3) */
                  <div className="drawer-catalog-grid visual-clothing-grid">
                  {filteredWardrobe.slice(0, visibleWardrobeCount).map(item => {
                    const isEquipped = activeCustomGarment?.id === item.id ||
                      equippedOutfit.topId === item.id ||
                      equippedOutfit.bottomId === item.id ||
                      equippedOutfit.outerwearId === item.id ||
                      equippedOutfit.shoesId === item.id;
                    const isFav = item.favorite || favorites.has(item.id);

                    return (
                      <div
                        key={item.id}
                        className={`clothing-card-item pure-white-card visual-first-card ${isEquipped ? 'selected' : ''}`}
                        onClick={() => {
                          if (item.asset_type === '3d_mesh' || item.is_custom_3d || item.glb_url) {
                            handleDrapeWardrobePiece(item);
                          } else {
                            setInspectedItem({
                              id: item.id,
                              name: item.name,
                              brand: item.brand,
                              category: item.category,
                              subcategory: item.subcategory,
                              color: item.color,
                              material: item.material,
                              userNotes: item.pattern ? `Pattern: ${item.pattern} • Formality: ${item.formality}/10 • Warmth: ${item.warmth}/10` : undefined,
                              imageUrl: item.image_url || item.thumbnail_url,
                              thumbnailUrl: item.thumbnail_url,
                              assetType: item.asset_type || '2d_image',
                              isCustom: !DEFAULT_FALLBACK_WARDROBE.some(d => d.id === item.id),
                              wearCount: item.wear_count
                            });
                          }
                        }}
                        title={`${item.name} (${item.brand || 'Personal Wardrobe'})`}
                        aria-label={item.name}
                      >
                        {/* Equipped checkmark badge */}
                        {isEquipped && (
                          <div className="clothing-card-selected-badge" aria-label="Equipped">
                            <Check size={12} strokeWidth={3} />
                          </div>
                        )}

                        {/* Favorite Heart Button */}
                        <button
                          type="button"
                          className={`card-favorite-btn ${isFav ? 'active' : ''}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleToggleFavoriteGarment(item.id, e);
                          }}
                          title={isFav ? 'Remove from favorites' : 'Add to favorites'}
                          aria-label="Toggle favorite"
                        >
                          <Heart size={14} weight={isFav ? 'fill' : 'regular'} color={isFav ? '#ef4444' : '#94a3b8'} />
                        </button>

                        {/* Large Visual Preview */}
                        <div className="clothing-card-image-wrap">
                          {item.thumbnail_url || item.image_url ? (
                            <img
                              src={item.thumbnail_url || item.image_url}
                              alt={item.name}
                              className="clothing-card-img"
                              loading="lazy"
                              decoding="async"
                            />
                          ) : (
                            <div className="clothing-card-placeholder">
                              <TShirt size={32} color={item.color || '#334155'} />
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                  {visibleWardrobeCount < filteredWardrobe.length && (
                    <div
                      ref={wardrobeSentinelRef}
                      className="wardrobe-scroll-sentinel"
                      style={{
                        gridColumn: '1 / -1',
                        height: '24px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        opacity: 0.6
                      }}
                    >
                      <span className="shimmer-block" style={{ width: '48px', height: '6px', borderRadius: '3px' }} />
                    </div>
                  )}
                </div>
              )}
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
                    <ArrowClockwise size={14} className={outfitLoading ? 'spin' : ''} />
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
                          <Sparkle size={14} />
                          <span>Drape Look on 3D Avatar</span>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ── TAB 3: 3D AVATAR CREATOR & MORPHS ── */}
            {activePrimaryTab === 'avatar' && (
              <div className="drawer-avatar-view" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                {renderAvatarCustomizer()}
              </div>
            )}
                </>
              )}
            </div>
          </>
        )}
      </section>
      </div>
    </div>
  );
};
