import React from 'react';
import toast, { ToastOptions } from 'react-hot-toast';
import { 
  Check, 
  ArrowsOut, 
  ArrowCounterClockwise, 
  ArrowClockwise, 
  BookmarkSimple, 
  Trash, 
  Sparkle,
  CoatHanger,
  FloppyDisk,
  WarningCircle,
  Info
} from '../components/icons';

/**
 * Premium circular icon badge for capsule toasts.
 * Strictly vector-based — zero emojis, luxury Apple-grade styling.
 */
interface IconBadgeProps {
  children: React.ReactNode;
  variant?: 'dark' | 'subtle' | 'danger';
}

const IconBadge: React.FC<IconBadgeProps> = ({ 
  children, 
  variant = 'dark' 
}) => {
  const bg = variant === 'danger' ? '#ef4444' : variant === 'subtle' ? 'rgba(15, 23, 42, 0.08)' : '#0f172a';
  const color = variant === 'subtle' ? '#0f172a' : '#ffffff';
  return (
    <span 
      className={`luxury-toast-icon-badge ${variant}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 22,
        height: 22,
        borderRadius: '50%',
        backgroundColor: bg,
        color: color,
        flexShrink: 0,
        boxShadow: variant === 'subtle' ? 'none' : '0 2px 6px rgba(15, 23, 42, 0.18)',
      }}
    >
      {children}
    </span>
  );
};

export const luxuryToast = {
  /** Standard success with dark obsidian checkmark */
  success: (msg: string, opts?: ToastOptions) => 
    toast.success(msg, {
      icon: <IconBadge><Check size={13} weight="bold" /></IconBadge>,
      ...opts
    }),

  /** Subtle info with sparkle or info icon */
  info: (msg: string, opts?: ToastOptions) => 
    toast(msg, {
      icon: <IconBadge variant="subtle"><Info size={13} weight="bold" /></IconBadge>,
      ...opts
    }),

  /** Centered camera viewport fit on avatar */
  centerFrame: (msg = 'Centered avatar on stage', opts?: ToastOptions) =>
    toast(msg, {
      icon: <IconBadge><ArrowsOut size={13} weight="bold" /></IconBadge>,
      duration: 1100,
      ...opts
    }),

  /** Undo action */
  undo: (msg = 'Undo', opts?: ToastOptions) =>
    toast(msg, {
      icon: <IconBadge variant="subtle"><ArrowCounterClockwise size={13} weight="bold" /></IconBadge>,
      duration: 850,
      ...opts
    }),

  /** Redo action */
  redo: (msg = 'Redo', opts?: ToastOptions) =>
    toast(msg, {
      icon: <IconBadge variant="subtle"><ArrowClockwise size={13} weight="bold" /></IconBadge>,
      duration: 850,
      ...opts
    }),

  /** Favorite saved or removed */
  favorite: (msg: string, _isFav?: boolean, opts?: ToastOptions) =>
    toast(msg, {
      icon: <IconBadge><BookmarkSimple size={13} weight="fill" /></IconBadge>,
      duration: 1500,
      ...opts
    }),

  /** Remove or delete item */
  delete: (msg: string, opts?: ToastOptions) =>
    toast(msg, {
      icon: <IconBadge variant="danger"><Trash size={13} weight="bold" /></IconBadge>,
      duration: 1500,
      ...opts
    }),

  /** Error with red circular badge */
  error: (msg: string, opts?: ToastOptions) => 
    toast.error(msg, {
      icon: <IconBadge variant="danger"><WarningCircle size={13} weight="bold" /></IconBadge>,
      duration: 3200,
      ...opts
    }),

  /** Saved look or avatar configuration */
  saved: (msg: string, opts?: ToastOptions) => 
    toast.success(msg, {
      icon: <IconBadge><FloppyDisk size={13} weight="fill" /></IconBadge>,
      duration: 1800,
      ...opts
    }),

  /** Garment draped / equipped onto avatar */
  draped: (msg: string, opts?: ToastOptions) => 
    toast.success(msg, {
      icon: <IconBadge><CoatHanger size={13} weight="bold" /></IconBadge>,
      duration: 1600,
      ...opts
    }),

  /** AI Stylist insight */
  stylist: (msg: string, opts?: ToastOptions) =>
    toast(msg, {
      icon: <IconBadge><Sparkle size={13} weight="fill" /></IconBadge>,
      duration: 2000,
      ...opts
    }),

  /** Generic toast with custom vector icon */
  custom: (msg: string, icon: React.ReactNode, opts?: ToastOptions) =>
    toast(msg, {
      icon: <IconBadge>{icon}</IconBadge>,
      ...opts
    })
};

export default luxuryToast;

