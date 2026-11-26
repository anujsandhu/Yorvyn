/**
 * YORVYN PREMIUM ICON SYSTEM
 * Powered by Phosphor Icons for React (@phosphor-icons/react)
 *
 * Sizing Hierarchy:
 * - xs (14px): Micro badges, inline tags, status indicators
 * - sm (16px): Compact buttons, chip icons, secondary toolbar controls
 * - md (20px): Standard interface icons, input field icons, modal actions
 * - lg (24px): Primary navigation items, hero drawer triggers
 * - xl (28px): Stage viewport controls, prominent visual buttons
 * - 2xl (32px): Empty state illustrations, hero headers
 *
 * Weight Hierarchy:
 * - 'regular': Default for all interface controls (refined luxury feel)
 * - 'light' / 'thin': Subtle secondary/decorative indicators
 * - 'bold': Emphasized interactive states, active filters
 * - 'fill': Active navigation tabs, equipped items, toggled-on states
 * - 'duotone': Restrained visual highlights (AI features)
 */

export const ICON_SIZES = {
  xs: 14,
  sm: 16,
  md: 20,
  lg: 24,
  xl: 28,
  '2xl': 32
} as const;

export type IconSize = keyof typeof ICON_SIZES;

export const ICON_WEIGHTS = {
  subtle: 'light' as const,
  regular: 'regular' as const,
  emphasis: 'bold' as const,
  active: 'fill' as const,
  accent: 'duotone' as const
} as const;

export type IconWeight = 'thin' | 'light' | 'regular' | 'bold' | 'fill' | 'duotone';

// ── Phosphor Icon Exports ──
export {
  // Navigation & Core Hubs
  Storefront,
  Sparkle,
  UserGear,
  House,
  MagnifyingGlass,

  // Wardrobe & Fashion Categories
  TShirt,
  Pants,
  CoatHanger,
  Dress,
  Sneaker,
  Sunglasses,
  BagSimple,
  ShoppingBag,
  Suitcase,
  Stack,
  GridFour,
  Cube,
  SquaresFour,
  Watch,
  Diamond,
  Handbag,
  Backpack,
  BaseballCap,
  Drop,
  DeviceMobile,
  Crown,
  Tag,
  Package,
  Sliders,
  BookmarkSimple,
  Bell,
  DotsSixVertical,
  PencilSimple,
  PushPin,

  // 3D Avatar Studio & Controls
  ArrowCounterClockwise,
  ArrowClockwise,
  ArrowsOut,
  ArrowsIn,
  MagnifyingGlassPlus,
  MagnifyingGlassMinus,
  Smiley,
  SmileyWink,
  HandWaving,
  UserFocus,
  UserCheck,
  User,
  UserSwitch,
  Scissors,
  Palette,
  PersonSimpleRun,
  Dog,
  Camera,
  ShareNetwork,
  GenderMale,
  GenderFemale,

  // Outfits & Garment Actions
  Check,
  CheckCircle,
  Plus,
  Minus,
  Trash,
  Heart,
  Star,
  Eye,
  EyeSlash,
  UploadSimple,
  WarningCircle,
  FloppyDisk,
  SignOut,
  ThermometerSimple,
  Headphones,
  Bug,
  Lightbulb,
  ArrowSquareOut,
  GithubLogo,
  LinkedinLogo,
  InstagramLogo,
  DotsThree,
  Question,
  BookOpen,
  List,
  Lightning,
  X,
  Clock,
  Archive,
  SidebarSimple,

  // AI Stylist & Audio / Voice Controls
  PaperPlaneTilt,
  Microphone,
  MicrophoneSlash,
  SpeakerHigh,
  SpeakerSimpleSlash,
  Stop,
  ChatCircleText,
  Robot,
  ThumbsUp,
  ThumbsDown,

  // Settings & System Controls
  SlidersHorizontal,
  LockKey,
  EnvelopeSimple,
  SunHorizon,
  ShieldCheck,
  CaretRight,
  CaretLeft,
  CaretDown,
  CaretUp,
  ArrowRight,
  ArrowLeft,
  ArrowUp,
  ArrowDown,
  Gear,
  Info,

  // Device & Platform Controls
  AppleLogo,
  WindowsLogo,
  Command,
  Keyboard,
  Devices
} from '@phosphor-icons/react';
