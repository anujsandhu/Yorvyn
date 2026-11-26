import { useState, useEffect } from 'react';

export type DeviceOS = 'mac' | 'windows' | 'linux' | 'chromebook' | 'ios' | 'android';

export interface ShortcutItem {
  id: string;
  name: string;
  keys: string[];
  display: string;
  label: string; // Full tooltip or button label, e.g. "Undo (⌘Z)" or "Undo"
  description: string;
}

export interface GestureItem {
  id: string;
  name: string;
  action: string;
  iconName: string;
  description: string;
}

export interface DeviceCommandsState {
  os: DeviceOS;
  osName: string;
  isMac: boolean;
  isWindows: boolean;
  isLinux: boolean;
  isChromebook: boolean;
  isMobileOrTouch: boolean;
  isSmallScreen: boolean;
  modKey: string;
  modKeyName: string;
  shortcuts: {
    undo: ShortcutItem;
    redo: ShortcutItem;
    center: ShortcutItem;
    zoomIn: ShortcutItem;
    zoomOut: ShortcutItem;
  };
  gestures: GestureItem[];
}

/**
 * Detect current platform / operating system reliably across all modern browsers.
 */
export function detectDeviceOS(): DeviceOS {
  if (typeof window === 'undefined' || !navigator) return 'mac';

  const nav = navigator as any;
  const platform = (nav.userAgentData?.platform || nav.platform || '').toLowerCase();
  const ua = (nav.userAgent || '').toLowerCase();

  // Chromebook / ChromeOS check
  if (/cros/i.test(ua) || /chromebook/i.test(ua)) {
    return 'chromebook';
  }

  // iOS / iPadOS check (including iPad Pro reporting as MacIntel with touch points)
  if (/iphone|ipad|ipod/i.test(ua) || (platform === 'macintel' && nav.maxTouchPoints > 1)) {
    return 'ios';
  }

  // Android check
  if (/android/i.test(ua)) {
    return 'android';
  }

  // macOS check
  if (/mac/i.test(platform) || /macintosh|mac os x/i.test(ua)) {
    return 'mac';
  }

  // Windows check
  if (/win/i.test(platform) || /windows/i.test(ua)) {
    return 'windows';
  }

  // Linux check
  if (/linux/i.test(platform) || /linux/i.test(ua)) {
    return 'linux';
  }

  return 'windows';
}

/**
 * Build device-specific commands, shortcut key combos, and gesture hints.
 */
export function buildDeviceCommands(os: DeviceOS, isSmallScreen: boolean): DeviceCommandsState {
  const isMac = os === 'mac' || os === 'ios';
  const isWindows = os === 'windows';
  const isChromebook = os === 'chromebook';
  const isLinux = os === 'linux';
  const isMobileOrTouch = os === 'ios' || os === 'android';

  let osName = 'macOS';
  let modKey = '⌘';
  let modKeyName = 'Command';

  if (isWindows) {
    osName = 'Windows';
    modKey = 'Ctrl';
    modKeyName = 'Control';
  } else if (isChromebook) {
    osName = 'ChromeOS';
    modKey = 'Ctrl';
    modKeyName = 'Control';
  } else if (isLinux) {
    osName = 'Linux';
    modKey = 'Ctrl';
    modKeyName = 'Control';
  } else if (isMobileOrTouch) {
    osName = 'Mobile';
    modKey = '';
    modKeyName = 'Touch';
  }

  // Undo / Redo key combos by OS
  const undoKeys = isMac ? ['⌘', 'Z'] : ['Ctrl', 'Z'];
  const undoDisplay = isMac ? '⌘Z' : 'Ctrl+Z';

  let redoKeys = isMac ? ['⇧', '⌘', 'Z'] : ['Ctrl', 'Y'];
  let redoDisplay = isMac ? '⇧⌘Z' : 'Ctrl+Y';
  if (isLinux || isChromebook) {
    redoKeys = ['Ctrl', 'Shift', 'Z'];
    redoDisplay = 'Ctrl+⇧+Z';
  }

  const centerKeys = ['Space'];
  const centerDisplay = 'Space';

  const zoomInKeys = ['+'];
  const zoomInDisplay = '+';

  const zoomOutKeys = ['-'];
  const zoomOutDisplay = '-';

  // Format labels: on small screen, skip keyboard combo text
  const undoLabel = isSmallScreen ? 'Undo' : `Undo · ${undoDisplay}`;
  const redoLabel = isSmallScreen ? 'Redo' : `Redo · ${redoDisplay}`;
  const centerLabel = isSmallScreen ? 'Fit Frame' : `Fit Frame · ${centerDisplay}`;
  const zoomInLabel = isSmallScreen ? 'Zoom In' : `Zoom In · ${zoomInDisplay}`;
  const zoomOutLabel = isSmallScreen ? 'Zoom Out' : `Zoom Out · ${zoomOutDisplay}`;

  // Gesture hints adapted to platform
  const gestures: GestureItem[] = isMobileOrTouch
    ? [
        {
          id: 'orbit',
          name: 'Rotate',
          action: '1-Finger Drag',
          iconName: 'rotate',
          description: 'Swipe horizontally or vertically to orbit around avatar'
        },
        {
          id: 'zoom',
          name: 'Zoom',
          action: 'Pinch Fingers',
          iconName: 'zoom',
          description: 'Pinch with two fingers to zoom in or out'
        },
        {
          id: 'fit',
          name: 'Center',
          action: 'Double Tap',
          iconName: 'center',
          description: 'Double tap anywhere on the canvas to center avatar'
        }
      ]
    : [
        {
          id: 'trackpad-orbit',
          name: 'Orbit View',
          action: isMac || isChromebook ? 'Two-Finger Swipe' : 'Left Drag / Two-Finger',
          iconName: 'rotate',
          description: 'Smoothly rotate around avatar with momentum glide'
        },
        {
          id: 'trackpad-zoom',
          name: 'Pinch Zoom',
          action: isMac || isChromebook ? 'Pinch Trackpad' : 'Pinch or Scroll Wheel',
          iconName: 'zoom',
          description: 'Fluid exponential zoom with viscous Apple damping'
        },
        {
          id: 'center-frame',
          name: 'Fit Frame',
          action: 'Space / F',
          iconName: 'center',
          description: 'Cinematically snap camera to center avatar'
        }
      ];

  return {
    os,
    osName,
    isMac,
    isWindows,
    isLinux,
    isChromebook,
    isMobileOrTouch,
    isSmallScreen,
    modKey,
    modKeyName,
    shortcuts: {
      undo: {
        id: 'undo',
        name: 'Undo',
        keys: undoKeys,
        display: undoDisplay,
        label: undoLabel,
        description: 'Revert last outfit or avatar modification'
      },
      redo: {
        id: 'redo',
        name: 'Redo',
        keys: redoKeys,
        display: redoDisplay,
        label: redoLabel,
        description: 'Re-apply reverted modification'
      },
      center: {
        id: 'center',
        name: 'Fit Frame',
        keys: centerKeys,
        display: centerDisplay,
        label: centerLabel,
        description: 'Smoothly center and frame avatar on stage'
      },
      zoomIn: {
        id: 'zoomIn',
        name: 'Zoom In',
        keys: zoomInKeys,
        display: zoomInDisplay,
        label: zoomInLabel,
        description: 'Inspect avatar tailoring, fabrics and details'
      },
      zoomOut: {
        id: 'zoomOut',
        name: 'Zoom Out',
        keys: zoomOutKeys,
        display: zoomOutDisplay,
        label: zoomOutLabel,
        description: 'Full silhouette view and runway context'
      }
    },
    gestures
  };
}

/**
 * React hook to listen to OS, viewport resize, and small-screen state.
 */
export function useDeviceCommands() {
  const [os] = useState<DeviceOS>(() => detectDeviceOS());
  const [isSmallScreen, setIsSmallScreen] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return window.innerWidth < 900;
  });

  useEffect(() => {
    const handleResize = () => {
      setIsSmallScreen(window.innerWidth < 900);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return buildDeviceCommands(os, isSmallScreen);
}

