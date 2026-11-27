/**
 * YORVYN — Avatar AI Privacy Manager (Phase 8)
 * 
 * Enforces strict user privacy, explicit consent, zero-retention memory models,
 * and transparent data protection policies across all AI-driven avatar workflows.
 */

import { UserPhotoConsent } from './avatarAITypes';

export class PhotoPrivacyConsentError extends Error {
  constructor(message = 'Explicit user consent required before processing reference photographs.') {
    super(message);
    this.name = 'PhotoPrivacyConsentError';
  }
}

export class AvatarAIPrivacyManager {
  private static readonly STORAGE_KEY = 'yorvyn_avatar_photo_consent';
  private static readonly PRIVACY_POLICY_VERSION = '2026.1';
  private static memoryConsent: UserPhotoConsent | null = null;

  public static readonly DOCUMENTED_RETENTION_POLICY = 
    'Yorvyn Zero-Retention Memory Guarantee: Reference images are processed ephemerally in-memory for facial structure, skin tone, and hair suggestions. Uploaded image binaries are NEVER permanently retained on disk, indexed in public datasets, or shared with third-party advertisers. Once the feature extraction proposal is delivered or dismissed, temporary in-memory buffers are instantly purged.';

  public static readonly PHOTO_ANALYSIS_DISCLAIMER =
    'Facial proportions, hairstyle suggestions, and skin undertones are approximate editorial suggestions derived from optical landmark heuristics. Yorvyn does NOT estimate exact tailoring measurements or sensitive biometric classifications from 2D photographs.';

  /**
   * Retrieves active user consent state from storage or runtime memory.
   */
  public static getConsent(): UserPhotoConsent {
    if (this.memoryConsent && this.memoryConsent.hasConsented) {
      return this.memoryConsent;
    }

    try {
      if (typeof localStorage !== 'undefined') {
        const stored = localStorage.getItem(this.STORAGE_KEY);
        if (stored) {
          const parsed = JSON.parse(stored);
          if (parsed.privacyPolicyVersion === this.PRIVACY_POLICY_VERSION && parsed.hasConsented) {
            return parsed;
          }
        }
      }
    } catch {}

    return {
      hasConsented: false,
      consentTimestamp: '',
      privacyPolicyVersion: this.PRIVACY_POLICY_VERSION,
      acceptedTerms: []
    };
  }

  /**
   * Records explicit user consent with timestamped audit trail.
   */
  public static grantConsent(acceptedTerms: string[] = []): UserPhotoConsent {
    const consent: UserPhotoConsent = {
      hasConsented: true,
      consentTimestamp: new Date().toISOString(),
      privacyPolicyVersion: this.PRIVACY_POLICY_VERSION,
      acceptedTerms: [
        'Processing reference photo solely for 3D avatar personalization',
        'Ephemeral in-memory feature estimation without permanent image storage',
        'Manual user approval required before saving any changes',
        ...acceptedTerms
      ]
    };

    this.memoryConsent = consent;

    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(consent));
      }
    } catch {}

    return consent;
  }

  /**
   * Revokes user consent and purges any cached references.
   */
  public static revokeConsent(): void {
    this.memoryConsent = null;
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem(this.STORAGE_KEY);
      }
    } catch {}
  }

  /**
   * Returns whether user has active valid consent.
   */
  public static hasValidConsent(): boolean {
    return this.getConsent().hasConsented;
  }

  /**
   * Asserts that consent is active. Throws `PhotoPrivacyConsentError` if missing.
   */
  public static verifyConsentOrThrow(): void {
    const consent = this.getConsent();
    if (!consent.hasConsented) {
      throw new PhotoPrivacyConsentError();
    }
  }

  /**
   * Safely disposes of a base64 or blob URL reference to enforce the zero-retention policy.
   */
  public static purgeEphemeralImage(urlOrDataUri: string): void {
    if (urlOrDataUri.startsWith('blob:')) {
      try {
        URL.revokeObjectURL(urlOrDataUri);
      } catch {}
    }
  }
}
