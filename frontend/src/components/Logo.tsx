/**
 * Logo — single source of truth for the Yorvyn brand mark.
 *
 * Usage:
 *   <Logo />                    → md (navbar default) — full logo
 *   <Logo size="sm" />          → sidebar expanded header
 *   <Logo size="sm" collapsed /> → sidebar collapsed — small square icon
 *   <Logo size="lg" />          → login page / loader
 *   <Logo size="xl" />          → hero / splash
 *   <Logo size={32} />          → custom pixel height
 *
 * The component renders the PNG logo image.
 * collapsed=true shows a compact square crop of the logo.
 */

import logoSrc from '../assets/yorvyn-logo.png'

// ── Size map (height in px) ───────────────────────────────────────────
const SIZE: Record<string, number> = {
  xs:    24,
  sm:    32,
  md:    56,  // Increased for better navbar visibility
  lg:    72,
  xl:    96,
  '2xl': 128,
}

interface LogoProps {
  /** Named size token or explicit pixel height */
  size?: keyof typeof SIZE | number
  /** When true, renders the compact icon variant (sidebar collapsed) */
  collapsed?: boolean
  /** Extra CSS class */
  className?: string
  /** Alt text — defaults to "Yorvyn" */
  alt?: string
}

export function Logo({
  size = 'md',
  collapsed = false,
  className = '',
  alt = 'Yorvyn',
}: LogoProps) {
  const h = typeof size === 'number' ? size : SIZE[size] ?? SIZE.md

  // ── Collapsed: compact square icon ───────────────────────────────
  if (collapsed) {
    return (
      <img
        src={logoSrc}
        alt={alt}
        className={`logo-img logo-img-collapsed${className ? ` ${className}` : ''}`}
        style={{
          width: 32,
          height: 32,
          objectFit: 'cover',
          objectPosition: 'left center',
          borderRadius: 8,
          display: 'block',
          flexShrink: 0,
          transition: 'all 200ms ease',
        }}
        draggable={false}
      />
    )
  }

  // ── Expanded: full logo ───────────────────────────────────────────
  return (
    <img
      src={logoSrc}
      alt={alt}
      className={`logo-img${className ? ` ${className}` : ''}`}
      style={{
        height: h,
        width: 'auto',
        objectFit: 'contain',
        display: 'block',
        flexShrink: 0,
        transition: 'all 200ms ease',
      }}
      draggable={false}
    />
  )
}
