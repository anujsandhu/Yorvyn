import React from 'react';
import {
  SquaresFour,
  CoatHanger,
  Pants,
  Sneaker,
  Watch,
  Diamond,
  Handbag,
  Backpack,
  BaseballCap,
  Drop,
  Sparkle,
  DeviceMobile,
  Crown,
  Dress,
  Sunglasses,
  TShirt,
  Tag,
  ShoppingBag,
  Heart,
  GridFour,
  User,
  Package,
  Sliders,
  Scissors,
  Smiley,
  Eye,
  Palette,
  ArrowsOut,
  BookmarkSimple,
  SlidersHorizontal
} from '../icons';
import { WardrobeCategory } from '../../types/fashion';

interface CategoryIconProps {
  category?: WardrobeCategory;
  iconKey?: string;
  size?: number;
  weight?: 'regular' | 'bold' | 'fill' | 'light' | 'thin';
  className?: string;
  color?: string;
}

export const PRESET_ICON_MAP: Record<string, React.FC<any>> = {
  SquaresFour,
  CoatHanger,
  Pants,
  Sneaker,
  Watch,
  Diamond,
  Handbag,
  Backpack,
  BaseballCap,
  Drop,
  Sparkle,
  DeviceMobile,
  Crown,
  Dress,
  Sunglasses,
  TShirt,
  Tag,
  ShoppingBag,
  Heart,
  GridFour,
  User,
  Package,
  Sliders,
  Scissors,
  Smiley,
  Eye,
  Palette,
  ArrowsOut,
  BookmarkSimple,
  SlidersHorizontal,
  Beard: User,
  Eyebrows: Eye,
  Nose: SlidersHorizontal,
  Mouth: Smiley
};

export const CategoryIcon: React.FC<CategoryIconProps> = ({
  category,
  iconKey,
  size = 20,
  weight = 'regular',
  className = '',
  color
}) => {
  // 1. Custom SVG uploaded by user
  if (category?.iconType === 'custom_svg' && category.customSvg) {
    return (
      <span
        className={`category-icon-svg ${className}`}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: size,
          height: size,
          color: color || 'currentColor'
        }}
        dangerouslySetInnerHTML={{ __html: category.customSvg }}
      />
    );
  }

  // 2. Custom Image Thumbnail URL
  if (category?.iconType === 'custom_image' && category.customImageUrl) {
    return (
      <img
        src={category.customImageUrl}
        alt={category.label}
        className={`category-icon-img ${className}`}
        style={{
          width: size,
          height: size,
          objectFit: 'contain',
          borderRadius: 4
        }}
      />
    );
  }

  // 3. Preset Phosphor Icon
  const targetKey = category?.iconKey || iconKey || 'Tag';
  const IconComponent = PRESET_ICON_MAP[targetKey] || Tag;

  return (
    <IconComponent
      size={size}
      weight={weight}
      className={className}
      color={color}
    />
  );
};

