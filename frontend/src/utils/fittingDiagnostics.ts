/**
 * Yorvyn Try-On Diagnostic Logger
 * Non-sensitive structured logging for garment selection, 3D mesh resolution,
 * layer compatibility validation, and the avatar fitting lifecycle.
 */

export interface FittingLifecycleLog {
  timestamp: string;
  garmentId: string;
  garmentName: string;
  category: string;
  assetType: '2d_image' | '3d_mesh' | 'fitted_garment' | 'processing' | 'unavailable';
  targetSlot: 'full_outfit' | 'top' | 'bottom' | 'shoes' | 'outerwear' | 'custom_3d';
  previousOutfitState: {
    slotType: string;
    outfitId?: string | null;
    topId?: string | null;
    bottomId?: string | null;
    shoesId?: string | null;
  };
  replacementAction: {
    removedGarments: string[];
    appliedGarment: string;
    preservedSlots: string[];
  };
  meshValidation: {
    status: 'passed' | 'failed' | 'not_applicable';
    reason?: string;
  };
  fittingStatus: 'success' | 'failed' | 'rejected_2d_only';
  errorMessage?: string;
}

class FittingDiagnosticsLogger {
  private logHistory: FittingLifecycleLog[] = [];

  public logSelection(log: Omit<FittingLifecycleLog, 'timestamp'>): void {
    const entry: FittingLifecycleLog = {
      ...log,
      timestamp: new Date().toISOString()
    };
    this.logHistory.push(entry);

    if (entry.fittingStatus === 'success') {
      console.info(
        `%c[Yorvyn Try-On Success] Slot: ${entry.targetSlot.toUpperCase()} | Applied: "${entry.garmentName}" (${entry.assetType}) | Replaced: [${entry.replacementAction.removedGarments.join(', ') || 'none'}]`,
        'color: #0284c7; font-weight: bold;',
        entry
      );
    } else if (entry.fittingStatus === 'rejected_2d_only') {
      console.warn(
        `%c[Yorvyn Try-On Honest 2D] Garment "${entry.garmentName}" is photographic 2D. 3D mesh fitting skipped; 2D detail preview opened.`,
        'color: #eab308; font-weight: bold;',
        entry
      );
    } else {
      console.error(
        `%c[Yorvyn Try-On Error] Failed fitting "${entry.garmentName}": ${entry.errorMessage || 'Unknown error'}`,
        'color: #ef4444; font-weight: bold;',
        entry
      );
    }
  }

  public getHistory(): FittingLifecycleLog[] {
    return [...this.logHistory];
  }

  public getLatest(): FittingLifecycleLog | null {
    return this.logHistory.length > 0 ? this.logHistory[this.logHistory.length - 1] : null;
  }
}

export const fittingDiagnostics = new FittingDiagnosticsLogger();

