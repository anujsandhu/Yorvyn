/**
 * YORVYN — Outfit State Manager (Phase 5)
 * Centralized, strongly-typed clothing state machine.
 * Manages dress, undress, atomic replacement, rollback, and cross-session persistence.
 */

export type GarmentCategory = 'underwear' | 'bottom' | 'top' | 'outfit' | 'outerwear' | 'shoes' | 'accessory';

export interface GarmentSlotState {
  id: string;
  name: string;
  category: GarmentCategory;
  layerOrder?: number;
  assetUrl?: string;
  color?: string;
  hidesSkin?: boolean;
  visibleBodyRegions?: string[];
  metadata?: Record<string, any>;
}

export interface PersistentOutfitState {
  version: number;
  userId?: string;
  underwear: GarmentSlotState | null;
  bottom: GarmentSlotState | null;
  top: GarmentSlotState | null;
  outfit: GarmentSlotState | null;
  outerwear: GarmentSlotState | null;
  shoes: GarmentSlotState | null;
  accessories: GarmentSlotState[];
  updatedAt: string;
}

export class OutfitStateManager {
  private current: PersistentOutfitState;
  private history: PersistentOutfitState[] = [];
  private maxHistory: number = 15;

  constructor(initialState?: Partial<PersistentOutfitState>) {
    this.current = {
      version: 1,
      userId: initialState?.userId,
      underwear: initialState?.underwear ?? {
        id: 'briefs',
        name: 'Neutral Modesty Briefs',
        category: 'underwear',
        hidesSkin: false
      },
      bottom: initialState?.bottom ?? null,
      top: initialState?.top ?? null,
      outfit: initialState?.outfit ?? null,
      outerwear: initialState?.outerwear ?? null,
      shoes: initialState?.shoes ?? null,
      accessories: initialState?.accessories ?? [],
      updatedAt: new Date().toISOString()
    };
  }

  private pushSnapshot() {
    this.history.push(JSON.parse(JSON.stringify(this.current)));
    if (this.history.length > this.maxHistory) {
      this.history.shift();
    }
  }

  public getState(): PersistentOutfitState {
    return JSON.parse(JSON.stringify(this.current));
  }

  public getGarment(category: GarmentCategory): GarmentSlotState | undefined {
    return (this.current as any)[category];
  }

  public hasActiveGarment(category: GarmentCategory): boolean {
    return !!this.getGarment(category);
  }

  /**
   * Dresses a garment onto the avatar with category-specific conflict resolution:
   * - Equipping an 'outfit' removes separate top, bottom, and outerwear.
   * - Equipping a 'top' or 'bottom' clears full 'outfit'.
   * - Atomic swap: updates state cleanly in one tick.
   */
  public dress(garment: GarmentSlotState): PersistentOutfitState {
    this.pushSnapshot();

    switch (garment.category) {
      case 'outfit':
        this.current.outfit = garment;
        this.current.top = null;
        this.current.bottom = null;
        this.current.outerwear = null;
        break;

      case 'top':
        this.current.top = garment;
        this.current.outfit = null;
        break;

      case 'bottom':
        this.current.bottom = garment;
        this.current.outfit = null;
        break;

      case 'outerwear':
        this.current.outerwear = garment;
        break;

      case 'shoes':
        this.current.shoes = garment;
        break;

      case 'underwear':
        // Form-fitting underwear NEVER hides skin
        this.current.underwear = { ...garment, hidesSkin: false };
        break;

      case 'accessory':
        this.current.accessories = this.current.accessories.filter(a => a.id !== garment.id);
        this.current.accessories.push(garment);
        break;
    }

    this.current.updatedAt = new Date().toISOString();
    return this.getState();
  }

  /**
   * Removes a garment from a specific category.
   * Restores the base body in that region without affecting compatible categories.
   */
  public undress(category: GarmentCategory, accessoryId?: string): PersistentOutfitState {
    this.pushSnapshot();

    switch (category) {
      case 'top':
        this.current.top = null;
        break;
      case 'bottom':
        this.current.bottom = null;
        break;
      case 'outfit':
        this.current.outfit = null;
        break;
      case 'outerwear':
        this.current.outerwear = null;
        break;
      case 'shoes':
        this.current.shoes = null;
        break;
      case 'underwear':
        this.current.underwear = null;
        break;
      case 'accessory':
        if (accessoryId) {
          this.current.accessories = this.current.accessories.filter(a => a.id !== accessoryId);
        } else {
          this.current.accessories = [];
        }
        break;
    }

    this.current.updatedAt = new Date().toISOString();
    return this.getState();
  }

  /**
   * Atomically replaces an existing garment with a new one in the same slot.
   */
  public replace(categoryOrGarment: GarmentCategory | GarmentSlotState, maybeGarment?: GarmentSlotState): PersistentOutfitState {
    const garment = maybeGarment || (categoryOrGarment as GarmentSlotState);
    return this.dress(garment);
  }

  /**
   * Undresses all removable garments, leaving the avatar in its pure base body state.
   */
  public undressAll(keepModestyUnderwear: boolean = true): PersistentOutfitState {
    this.pushSnapshot();

    this.current.top = null;
    this.current.bottom = null;
    this.current.outfit = null;
    this.current.outerwear = null;
    this.current.shoes = null;
    this.current.accessories = [];

    if (keepModestyUnderwear) {
      this.current.underwear = {
        id: 'briefs',
        name: 'Neutral Modesty Briefs',
        category: 'underwear',
        hidesSkin: false
      };
    } else {
      this.current.underwear = null;
    }

    this.current.updatedAt = new Date().toISOString();
    return this.getState();
  }

  /**
   * Restores a previously saved outfit state (from Supabase or localStorage).
   */
  public restore(savedState: PersistentOutfitState): PersistentOutfitState {
    this.pushSnapshot();
    this.current = JSON.parse(JSON.stringify(savedState));
    this.current.updatedAt = new Date().toISOString();
    return this.getState();
  }

  /**
   * Rolls back to the last valid outfit state if an asset loading or fitting failure occurs.
   */
  public rollback(): PersistentOutfitState | null {
    if (this.history.length === 0) return null;
    this.current = this.history.pop()!;
    return this.getState();
  }
}

