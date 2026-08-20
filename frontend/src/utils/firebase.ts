/**
 * Firebase Configuration and Initialization
 * 
 * Initializes Firebase with Firestore, Authentication (Google Sign-In),
 * and Analytics for the Yorvyn perfume recommendation app.
 */

import { initializeApp } from "firebase/app"
import { getAuth, GoogleAuthProvider, setPersistence, browserLocalPersistence } from "firebase/auth"
import { initializeFirestore } from "firebase/firestore"

// ============================================================================
// Firebase Configuration for Yorvyn Project
// ============================================================================

const firebaseConfig = {
  apiKey: "AIzaSyBitRg-Tv35P6qEyyob-VJB7Fi_ZpVK4Us",
  authDomain: "yorvyn-ai.firebaseapp.com",
  projectId: "yorvyn-ai",
  storageBucket: "yorvyn-ai.firebasestorage.app",
  messagingSenderId: "708830902447",
  appId: "1:708830902447:web:91e8ad687532afd5967c5a",
  measurementId: "G-RR8J9L77RN",
}

// ============================================================================
// Initialize Firebase App, Auth, and Firestore
// ============================================================================

export const firebaseApp = initializeApp(firebaseConfig)
export const auth = getAuth(firebaseApp)
export let firestoreUnavailable = false

// Set auth persistence to survive page refresh
setPersistence(auth, browserLocalPersistence).catch(err => {
  console.warn('Could not set auth persistence:', err)
})

// Use long-polling transport to avoid WebSocket/gRPC-web CORS issues
// This bypasses browser restrictions on persistent connections to Firebase servers
export const db = initializeFirestore(firebaseApp, {
  experimentalForceLongPolling: true,
})

export function markFirestoreUnavailable() {
  firestoreUnavailable = true
}

export function isFirestoreConnectionIssue(error: unknown): boolean {
  const message = String((error as { message?: unknown })?.message || '').toLowerCase()
  return message.includes('firestore') || message.includes('offline') || message.includes('unavailable') || message.includes('network')
}

// ============================================================================
// Google Sign-In Provider Configuration
// ============================================================================

export const googleProvider = new GoogleAuthProvider()

// Configure Google provider for better UX
googleProvider.addScope('profile')
googleProvider.addScope('email')
googleProvider.setCustomParameters({
  prompt: 'select_account', // Always show account selection
})

// ============================================================================
// Auth Persistence (keep user logged in after refresh)
// ============================================================================

// Set persistence to LOCAL so user stays logged in
setPersistence(auth, browserLocalPersistence)
  .catch((error) => console.warn('Auth persistence error:', error))

// ============================================================================
// Analytics Setup (Lazy-loaded to avoid ad blocker issues)
// ============================================================================

/**
 * Initialize Google Analytics for Yorvyn app.
 * 
 * Loads analytics only if supported and not blocked by ad blockers.
 * Safe to call multiple times.
 */
export const initAnalytics = async () => {
  try {
    const { getAnalytics, isSupported } = await import("firebase/analytics")
    
    if (await isSupported()) {
      const analytics = getAnalytics(firebaseApp)
      return analytics
    }
  } catch (error) {
    // Silently ignore if blocked by ad blockers or not supported
  }
}
