/**
 * YORVYN — PHASE 7: Complete Snap-Style 3D Avatar Creator Engine Types
 * 
 * Strongly typed architecture for 13 customization categories,
 * visual preset cards, fine-adjustment sliders, color palettes,
 * undo/redo history, and 3D parameter mapping.
 */

import { AvatarProfile } from '../../types/avatarProfile';

export type AvatarCreatorCategory =
  | 'body'
  | 'face'
  | 'eyes'
  | 'eyebrows'
  | 'nose'
  | 'mouth'
  | 'ears'
  | 'hair'
  | 'facial_hair'
  | 'skin'
  | 'clothing'
  | 'accessories'
  | 'expressions';

export type CategorySubView = 'presets' | 'sliders' | 'colors' | 'styling';

export interface CategoryTabMeta {
  id: AvatarCreatorCategory;
  label: string;
  iconName: string;
  cameraFocus: 'head' | 'torso' | 'full' | 'feet';
  subViews: CategorySubView[];
  badge?: string;
}

export interface AvatarSliderDef {
  id: string;
  category: AvatarCreatorCategory;
  label: string;
  min: number;
  max: number;
  step: number;
  defaultValue: number;
  unit?: string;
  bipolar?: boolean; // -1 to 1 (vs 0 to 1)
  description?: string;
  /** Property path on AvatarProfile or direct modifier target key */
  modifierKey?: string;
  profilePath?: string;
}

export interface AvatarPresetDef {
  id: string;
  category: AvatarCreatorCategory;
  name: string;
  description?: string;
  badge?: string;
  previewColor?: string;
  iconSvg?: string;
  /** Parameters to apply to the AvatarProfile */
  apply: (current: AvatarProfile) => Partial<AvatarProfile>;
}

export interface AvatarColorSwatch {
  id: string;
  name: string;
  hex: string;
  group?: string;
  undertone?: 'cool' | 'warm' | 'neutral' | 'olive';
}

export interface AvatarActionSnapshot {
  timestamp: number;
  description: string;
  category: AvatarCreatorCategory;
  profile: AvatarProfile;
}

export interface AvatarCreatorHistory {
  canUndo: boolean;
  canRedo: boolean;
  historyLength: number;
  currentIndex: number;
}
