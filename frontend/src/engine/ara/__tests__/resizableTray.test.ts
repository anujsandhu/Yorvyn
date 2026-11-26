import { describe, it, expect, beforeEach } from 'vitest';
import { getPresetWidth, TrayPreset } from '../../../pages/AvatarStudio';

describe('Resizable Right-Side Interactive Tray — Presets & Dimension Calculations', () => {
  let mockStore: Record<string, string> = {};

  beforeEach(() => {
    mockStore = {};
    Object.defineProperty(globalThis, 'localStorage', {
      value: {
        getItem: (key: string) => mockStore[key] || null,
        setItem: (key: string, val: string) => { mockStore[key] = String(val); },
        removeItem: (key: string) => { delete mockStore[key]; },
        clear: () => { mockStore = {}; },
        key: (i: number) => Object.keys(mockStore)[i] || null,
        length: 0,
      },
      writable: true,
      configurable: true,
    });
  });

  it('should calculate compact width at controlled minimum of 340px', () => {
    // 1440px desktop
    const width1440 = getPresetWidth('compact', 1440);
    expect(width1440).toBe(340);

    // 1024px tablet/small laptop
    const width1024 = getPresetWidth('compact', 1024);
    expect(width1024).toBe(340);

    // 2560px ultra-wide
    const width2560 = getPresetWidth('compact', 2560);
    expect(width2560).toBe(340);
  });

  it('should calculate default width in the 380-420px range (400px on 1440px desktop)', () => {
    // 1440px desktop -> target 400px
    const width1440 = getPresetWidth('default', 1440);
    expect(width1440).toBe(400);
    expect(width1440).toBeGreaterThanOrEqual(380);
    expect(width1440).toBeLessThanOrEqual(420);

    // 1024px desktop -> 360px
    const width1024 = getPresetWidth('default', 1024);
    expect(width1024).toBe(360);

    // 1280px desktop -> 380px
    const width1280 = getPresetWidth('default', 1280);
    expect(width1280).toBe(380);
    expect(width1280).toBeGreaterThanOrEqual(380);

    // 1920px large monitor -> 420px
    const width1920 = getPresetWidth('default', 1920);
    expect(width1920).toBe(420);
  });

  it('should calculate expanded width at controlled maximum of 460px', () => {
    // 1440px desktop
    const width1440 = getPresetWidth('expanded', 1440);
    expect(width1440).toBe(460);

    // 1024px desktop
    const width1024 = getPresetWidth('expanded', 1024);
    expect(width1024).toBe(460);

    // 2560px ultra-wide
    const width2560 = getPresetWidth('expanded', 2560);
    expect(width2560).toBe(460);
  });

  it('guarantees the 3D avatar viewport always retains at least 50% of screen width across all presets', () => {
    const viewports = [1024, 1280, 1440, 1680, 1920, 2560];
    const presets: TrayPreset[] = ['compact', 'default', 'expanded'];

    for (const winW of viewports) {
      for (const preset of presets) {
        const trayW = getPresetWidth(preset, winW);
        const avatarViewportW = winW - trayW;
        const avatarStageRatio = avatarViewportW / winW;

        expect(avatarStageRatio).toBeGreaterThanOrEqual(0.50);
        expect(avatarViewportW).toBeGreaterThanOrEqual(500);
      }
    }
  });

  it('handles persistence round-trip in localStorage cleanly', () => {
    const userStoragePrefix = 'yorvyn_tray_user_123';

    // 1. Save preset & custom width
    localStorage.setItem(`${userStoragePrefix}_preset`, 'expanded');
    localStorage.setItem(`${userStoragePrefix}_width_px`, '460');

    // 2. Read back
    const loadedPreset = localStorage.getItem(`${userStoragePrefix}_preset`);
    const loadedWidth = parseInt(localStorage.getItem(`${userStoragePrefix}_width_px`) || '0', 10);

    expect(loadedPreset).toBe('expanded');
    expect(loadedWidth).toBe(460);

    // 3. Reset to default
    localStorage.setItem(`${userStoragePrefix}_preset`, 'default');
    localStorage.setItem(`${userStoragePrefix}_width_px`, getPresetWidth('default', 1440).toString());

    expect(localStorage.getItem(`${userStoragePrefix}_preset`)).toBe('default');
    expect(localStorage.getItem(`${userStoragePrefix}_width_px`)).toBe('400');
  });
});
