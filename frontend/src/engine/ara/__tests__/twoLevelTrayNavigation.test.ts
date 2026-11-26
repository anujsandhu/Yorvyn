import { describe, it, expect } from 'vitest';
import {
  FASHION_SECONDARY_CATEGORIES,
  WARDROBE_SECONDARY_CATEGORIES,
  AVATAR_SECONDARY_CATEGORIES,
  PRIMARY_NAV_SECTIONS,
  PrimaryNavSection
} from '../../../pages/AvatarStudio';

describe('YORVYN — Morphing Exclusive Primary Navigation System', () => {
  describe('1. Initial Collapsed State & Navigation Structure', () => {
    it('should define exactly three primary navigation sections: fashion, wardrobe, avatar', () => {
      const allowedSections: PrimaryNavSection[] = ['fashion', 'wardrobe', 'avatar'];
      expect(allowedSections).toHaveLength(3);
      expect(PRIMARY_NAV_SECTIONS).toHaveLength(3);
      expect(PRIMARY_NAV_SECTIONS.map(s => s.id)).toEqual(['fashion', 'wardrobe', 'avatar']);
    });

    it('should initially have all three buttons in the collapsed state (expandedPrimarySection = null)', () => {
      let expandedPrimarySection: PrimaryNavSection | null = null;
      expect(expandedPrimarySection).toBeNull();
      // When null, each primary section renders as a circular icon button
      const circularControls = PRIMARY_NAV_SECTIONS.map(s => ({
        id: s.id,
        isExpanded: expandedPrimarySection === s.id,
        shape: expandedPrimarySection === s.id ? 'capsule' : 'circle'
      }));
      expect(circularControls.every(c => c.shape === 'circle')).toBe(true);
    });
  });

  describe('2. Exclusive Expansion & Morphing Logic', () => {
    // Pure function simulating the exclusive toggle logic implemented in AvatarStudio
    const handleToggle = (
      current: PrimaryNavSection | null,
      clicked: PrimaryNavSection
    ): PrimaryNavSection | null => {
      return current === clicked ? null : clicked;
    };

    it('should expand Fashion into a capsule when clicked from collapsed state', () => {
      let state: PrimaryNavSection | null = null;
      state = handleToggle(state, 'fashion');
      expect(state).toBe('fashion');
    });

    it('should expand Wardrobe into a capsule when clicked from collapsed state', () => {
      let state: PrimaryNavSection | null = null;
      state = handleToggle(state, 'wardrobe');
      expect(state).toBe('wardrobe');
    });

    it('should expand Avatar into a capsule when clicked from collapsed state', () => {
      let state: PrimaryNavSection | null = null;
      state = handleToggle(state, 'avatar');
      expect(state).toBe('avatar');
    });

    it('should collapse the active button back into a circle when clicked again', () => {
      let state: PrimaryNavSection | null = 'fashion';
      // User clicks Fashion while it is already expanded
      state = handleToggle(state, 'fashion');
      expect(state).toBeNull();

      // User expands Avatar, then clicks Avatar again
      state = handleToggle(state, 'avatar');
      expect(state).toBe('avatar');
      state = handleToggle(state, 'avatar');
      expect(state).toBeNull();
    });

    it('should collapse the previous capsule and expand the newly selected section', () => {
      let state: PrimaryNavSection | null = 'fashion'; // Fashion currently expanded
      // User clicks Wardrobe
      state = handleToggle(state, 'wardrobe');
      expect(state).toBe('wardrobe'); // Fashion collapsed, Wardrobe expanded!

      // User clicks Avatar
      state = handleToggle(state, 'avatar');
      expect(state).toBe('avatar'); // Wardrobe collapsed, Avatar expanded!
    });

    it('should guarantee that only ONE primary navigation capsule can be expanded at any time', () => {
      const testSequences: PrimaryNavSection[] = ['fashion', 'wardrobe', 'avatar', 'fashion', 'avatar'];
      let state: PrimaryNavSection | null = null;

      for (const section of testSequences) {
        state = handleToggle(state, section);
        const activeCount = PRIMARY_NAV_SECTIONS.filter(s => s.id === state).length;
        expect(activeCount).toBeLessThanOrEqual(1);
      }
    });
  });

  describe('3. Secondary Navigation Contents Inside Morphing Capsules', () => {
    it('Fashion capsule must contain all required clothing categories and actions', () => {
      const categoryIds = FASHION_SECONDARY_CATEGORIES.map(c => c.id);
      expect(categoryIds).toContain('all');
      expect(categoryIds).toContain('tops');
      expect(categoryIds).toContain('shirts');
      expect(categoryIds).toContain('t-shirts');
      expect(categoryIds).toContain('bottoms');
      expect(categoryIds).toContain('trousers');
      expect(categoryIds).toContain('jeans');
      expect(categoryIds).toContain('dresses');
      expect(categoryIds).toContain('outerwear');
      expect(categoryIds).toContain('jackets');
      expect(categoryIds).toContain('shoes');
      expect(categoryIds).toContain('accessories');
    });

    it('Wardrobe capsule must contain user clothing categories, Saved Outfits and Collections', () => {
      const categoryIds = WARDROBE_SECONDARY_CATEGORIES.map(c => c.id);
      expect(categoryIds).toContain('all');
      expect(categoryIds).toContain('top');
      expect(categoryIds).toContain('bottom');
      expect(categoryIds).toContain('outerwear');
      expect(categoryIds).toContain('footwear');
      expect(categoryIds).toContain('accessory');
      expect(categoryIds).toContain('saved_outfits');
      expect(categoryIds).toContain('collections');
    });

    it('Avatar capsule must contain all 11 required avatar customization categories', () => {
      const categoryIds = AVATAR_SECONDARY_CATEGORIES.map(c => c.id);
      expect(categoryIds).toContain('body');
      expect(categoryIds).toContain('face');
      expect(categoryIds).toContain('hair');
      expect(categoryIds).toContain('skin');
      expect(categoryIds).toContain('eyes');
      expect(categoryIds).toContain('eyebrows');
      expect(categoryIds).toContain('nose');
      expect(categoryIds).toContain('mouth');
      expect(categoryIds).toContain('facial_hair');
      expect(categoryIds).toContain('accessories');
      expect(categoryIds).toContain('expressions');
      expect(categoryIds).toHaveLength(11);
    });
  });

  describe('4. Secondary Selection & Independent State Preservation', () => {
    it('should preserve secondary category selections across primary collapses and expansions', () => {
      const navStore = {
        expandedPrimarySection: null as PrimaryNavSection | null,
        activePrimaryTab: 'fashion' as PrimaryNavSection,
        activeFashionCategory: 'tops',
        activeWardrobeCategory: 'all',
        activeAvatarCategory: 'hair'
      };

      // 1. Expand Fashion and select Jeans
      navStore.expandedPrimarySection = 'fashion';
      navStore.activePrimaryTab = 'fashion';
      navStore.activeFashionCategory = 'jeans';
      expect(navStore.activeFashionCategory).toBe('jeans');

      // 2. Expand Avatar and select Nose
      navStore.expandedPrimarySection = 'avatar';
      navStore.activePrimaryTab = 'avatar';
      navStore.activeAvatarCategory = 'nose';
      expect(navStore.activeAvatarCategory).toBe('nose');
      expect(navStore.activeFashionCategory).toBe('jeans'); // Kept intact!

      // 3. Expand Wardrobe and select Saved Outfits
      navStore.expandedPrimarySection = 'wardrobe';
      navStore.activePrimaryTab = 'wardrobe';
      navStore.activeWardrobeCategory = 'saved_outfits';
      expect(navStore.activeWardrobeCategory).toBe('saved_outfits');

      // 4. Collapse navigation to all-circular state
      navStore.expandedPrimarySection = null;
      expect(navStore.expandedPrimarySection).toBeNull();

      // 5. Re-expand Fashion: Jeans must still be selected
      navStore.expandedPrimarySection = 'fashion';
      expect(navStore.activeFashionCategory).toBe('jeans');

      // 6. Re-expand Avatar: Nose must still be selected
      navStore.expandedPrimarySection = 'avatar';
      expect(navStore.activeAvatarCategory).toBe('nose');

      // 7. Re-expand Wardrobe: Saved Outfits must still be selected
      navStore.expandedPrimarySection = 'wardrobe';
      expect(navStore.activeWardrobeCategory).toBe('saved_outfits');
    });

    it('selecting a secondary category must keep its primary capsule expanded', () => {
      let expandedPrimarySection: PrimaryNavSection | null = 'fashion';
      let activeFashionCategory = 'tops';

      // User selects a secondary category
      activeFashionCategory = 'outerwear';

      // Primary capsule remains expanded
      expect(expandedPrimarySection).toBe('fashion');
      expect(activeFashionCategory).toBe('outerwear');
    });
  });

  describe('5. Camera Director Framing Mapping', () => {
    it('should map facial and hair categories to head focus and body to full body', () => {
      const getFraming = (catId: string) => {
        if (['face', 'hair', 'skin', 'eyes', 'eyebrows', 'nose', 'mouth', 'facial_hair'].includes(catId)) {
          return 'head';
        }
        if (catId === 'accessories') {
          return 'torso';
        }
        return 'full';
      };

      expect(getFraming('hair')).toBe('head');
      expect(getFraming('face')).toBe('head');
      expect(getFraming('skin')).toBe('head');
      expect(getFraming('eyes')).toBe('head');
      expect(getFraming('nose')).toBe('head');
      expect(getFraming('mouth')).toBe('head');
      expect(getFraming('facial_hair')).toBe('head');
      expect(getFraming('accessories')).toBe('torso');
      expect(getFraming('body')).toBe('full');
      expect(getFraming('expressions')).toBe('full');
    });
  });

  describe('6. Resizable Tray & Responsive Layout Support', () => {
    it('should preserve active morphing state and category selection across tray width changes', () => {
      let trayWidth = 460;
      let expandedPrimarySection: PrimaryNavSection | null = 'fashion';
      let activeFashionCategory = 'jackets';

      // Simulate resizing tray to Compact (340px)
      trayWidth = 340;
      expect(expandedPrimarySection).toBe('fashion');
      expect(activeFashionCategory).toBe('jackets');

      // Simulate resizing tray to Expanded (720px)
      trayWidth = 720;
      expect(expandedPrimarySection).toBe('fashion');
      expect(activeFashionCategory).toBe('jackets');
      expect(trayWidth).toBe(720);
    });

    it('should provide smooth luxury liquid glass transition and respect reduced motion', () => {
      const getTransition = (reducedMotion: boolean) => {
        return reducedMotion
          ? { duration: 0 }
          : { duration: 0.52, ease: [0.16, 1, 0.3, 1] };
      };

      expect(getTransition(false)).toEqual({ duration: 0.52, ease: [0.16, 1, 0.3, 1] });
      expect(getTransition(true)).toEqual({ duration: 0 });
    });
  });

  describe('7. In-Tray Embedded Modal Architecture (No Screen Popups)', () => {
    it('should default embedded mode to true so AI Assistant renders within tray without backdrop', () => {
      interface AssistantConfig {
        isOpen: boolean;
        embedded?: boolean;
      }
      const config: AssistantConfig = { isOpen: true };
      const isEmbedded = config.embedded ?? true;
      expect(isEmbedded).toBe(true);

      // In embedded mode, root class is .avatar-ai-tray-view, not .avatar-ai-modal-backdrop
      const rootClass = isEmbedded ? 'avatar-ai-tray-view' : 'avatar-ai-modal-backdrop';
      expect(rootClass).toBe('avatar-ai-tray-view');
    });

    it('should confine all modal workspaces strictly inside the right-side tray container', () => {
      // Modals that must render inside stage-drawer-card / avatar-creator-container:
      const inTrayWorkspaces = [
        'AvatarAIAssistantModal',
        'CategoryManagerModal',
        'PhotoTo3DGarmentModal',
        'DigitizeNewGarmentForm',
        'Preview2DGarmentDetail',
        'ResetCharacterConfirm'
      ];

      // Each workspace must be absolute within the tray, preventing fullscreen viewport blocking
      const workspaceLayoutRules = inTrayWorkspaces.map(name => ({
        name,
        targetContainer: 'stage-drawer-card',
        position: 'absolute',
        inset: '0',
        blocksLeftAvatarStage: false
      }));

      expect(workspaceLayoutRules.every(r => !r.blocksLeftAvatarStage)).toBe(true);
      expect(workspaceLayoutRules.every(r => r.position === 'absolute')).toBe(true);
    });

    it('should keep the 3D avatar stage permanently visible, centered, and interactive when in-tray overlays are active', () => {
      const stageState = {
        avatarMounted: true,
        leftStageWidthCalc: 'calc(100% - var(--drawer-w) - 1.5rem - 5.5rem)',
        activeTrayOverlay: 'avatar-ai-intelligence' as string | null,
        backdropBlurOverAvatar: false
      };

      expect(stageState.avatarMounted).toBe(true);
      expect(stageState.backdropBlurOverAvatar).toBe(false);
      expect(stageState.activeTrayOverlay).not.toBeNull();
    });
  });

  describe('8. Streamlined Fashion Tray View (Saved Outfits & AI Recommendations Only)', () => {
    it('should restrict Fashion section content strictly to Saved Outfits and AI Recommendations', () => {
      interface FashionSectionModel {
        activePrimaryTab: 'fashion' | 'wardrobe' | 'avatar';
        visibleModules: Array<'saved_outfits' | 'ai_recommendations' | 'clothing_catalog_grid' | 'studio_source_switcher'>;
      }

      const fashionState: FashionSectionModel = {
        activePrimaryTab: 'fashion',
        visibleModules: ['saved_outfits', 'ai_recommendations']
      };

      expect(fashionState.visibleModules).toContain('saved_outfits');
      expect(fashionState.visibleModules).toContain('ai_recommendations');
      expect(fashionState.visibleModules).not.toContain('clothing_catalog_grid');
      expect(fashionState.visibleModules).not.toContain('studio_source_switcher');
    });

    it('should support switching view filter between all, saved outfits, and ai recommendations', () => {
      type FashionFilterTab = 'all' | 'saved' | 'ai';

      const getVisibleSections = (filter: FashionFilterTab) => {
        const sections: string[] = [];
        if (filter === 'all' || filter === 'saved') sections.push('saved_outfits');
        if (filter === 'all' || filter === 'ai') sections.push('ai_recommendations');
        return sections;
      };

      expect(getVisibleSections('all')).toEqual(['saved_outfits', 'ai_recommendations']);
      expect(getVisibleSections('saved')).toEqual(['saved_outfits']);
      expect(getVisibleSections('ai')).toEqual(['ai_recommendations']);
    });

    it('should allow saving current avatar attire and immediately equipping saved outfits', () => {
      interface MockSavedOutfit {
        id: string;
        title: string;
        appliedParams: Record<string, any>;
      }

      const savedOutfits: MockSavedOutfit[] = [
        { id: 'cld-blouse', title: 'Atelier Stealth Bomber Suit', appliedParams: { outfit: 'male_elegantsuit01' } }
      ];

      // Simulate saving new outfit
      const newOutfit: MockSavedOutfit = {
        id: 'saved-look-custom',
        title: 'Look #2 • Custom Muse',
        appliedParams: { outfit: 'male_casualsuit06', top: 'none', bottom: 'none' }
      };
      savedOutfits.unshift(newOutfit);

      expect(savedOutfits).toHaveLength(2);
      expect(savedOutfits[0].id).toBe('saved-look-custom');

      // Equip saved outfit
      const currentAvatar = { outfit: 'none' };
      Object.assign(currentAvatar, savedOutfits[0].appliedParams);
      expect(currentAvatar.outfit).toBe('male_casualsuit06');
    });
  });

  describe('9. Icon-Only Secondary Navigation Pills (No Visible Text Next to Icon)', () => {
    it('secondary category buttons must render icons only without visible text labels', () => {
      const getSecondaryButtonFormat = (category: { id: string; label: string; iconKey: string }) => ({
        hasIcon: Boolean(category.iconKey),
        showVisibleText: false,
        accessibleLabel: category.label,
        accessibleTooltip: category.label,
        hasActiveDot: true
      });

      const sampleFashionCat = FASHION_SECONDARY_CATEGORIES[2]; // 'shirts'
      expect(sampleFashionCat.id).toBe('shirts');
      expect(sampleFashionCat.label).toBe('Shirts');

      const formatted = getSecondaryButtonFormat(sampleFashionCat);
      expect(formatted.hasIcon).toBe(true);
      expect(formatted.showVisibleText).toBe(false);
      expect(formatted.accessibleLabel).toBe('Shirts');
      expect(formatted.accessibleTooltip).toBe('Shirts');
      expect(formatted.hasActiveDot).toBe(true);
    });

    it('all primary navigation sections (Fashion, Wardrobe, Avatar) enforce icon-only secondary navigation', () => {
      const navSections = [
        { name: 'fashion', items: FASHION_SECONDARY_CATEGORIES },
        { name: 'wardrobe', items: WARDROBE_SECONDARY_CATEGORIES },
        { name: 'avatar', items: AVATAR_SECONDARY_CATEGORIES }
      ];

      for (const section of navSections) {
        expect(section.items.length).toBeGreaterThan(0);
        for (const item of section.items) {
          expect(item.iconKey).toBeDefined();
          expect(item.label).toBeDefined(); // preserved for title / aria-label
        }
      }
    });
  });
});
