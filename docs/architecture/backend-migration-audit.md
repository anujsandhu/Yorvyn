# Yorvyn Backend Migration Audit — Firebase to Supabase & Cloudinary

## 1. Executive Summary

This document audits the legacy backend architecture of Yorvyn (Firebase Auth, Firestore, and local asset storage) and establishes the target migration architecture to **Supabase Auth & PostgreSQL** paired with **Cloudinary Image Storage & CDN delivery**.

---

## 2. Current Architecture Inventory

| Layer / Component | Current Implementation | Files & Dependencies | Migration Action | Target Implementation |
| :--- | :--- | :--- | :--- | :--- |
| **Client Authentication** | Firebase Auth (`signInWithPopup`, GoogleAuthProvider) | `frontend/src/utils/firebase.ts`, `frontend/src/context/AuthContext.tsx`, `frontend/src/pages/Login.tsx` | Replace Firebase Auth with Supabase browser client | `@supabase/supabase-js` Auth (Email/Password registration, Login, Password Reset, Google OAuth) |
| **Server Auth Verification** | `firebase_admin.auth.verify_id_token` | `backend/app/core/security.py`, `backend/app/auth.py` | Replace Firebase Admin ID token verification with Supabase JWT validation | `python-jose` HS256/RS256 JWT validation using Supabase JWT Secret or JWKS endpoint |
| **User Data & Preferences** | Google Cloud Firestore collections (`users`, `user_preferences`) | `backend/app/firestore_client.py`, `backend/app/services/user_service.py` | Migrate collections to normalized relational tables with Row Level Security | Supabase PostgreSQL tables: `yorvyn_profiles`, `yorvyn_user_preferences` |
| **Digital Wardrobe Storage** | In-memory singleton with local file persistence | `backend/app/services/wardrobe_service.py` | Persist wardrobe items in PostgreSQL linked to `auth.uid()` | Supabase PostgreSQL table: `yorvyn_wardrobe_items` |
| **Garment Job State** | In-memory dictionary in `JobManager` | `backend/app/services/garments/job_manager.py` | Persist job lifecycle states (`queued`, `processing`, `completed`, `failed`) | Supabase PostgreSQL table: `yorvyn_garment_jobs` |
| **Garment Image Delivery** | Local disk storage under `data/wardrobe_assets/{job_id}/preview.png` | `backend/app/services/garments/job_manager.py`, `preview_renderer.py` | Upload rendered preview thumbnails and textures to Cloudinary | Cloudinary CDN (`yorvyn/users/{user_id}/garments/{asset_id}`) with signed delivery |
| **Conversation History** | Local in-memory session arrays | `backend/app/services/fashion_orchestrator.py` | Persist conversation threads and message logs | Supabase PostgreSQL tables: `yorvyn_conversations`, `yorvyn_messages` |
| **Static Web Hosting** | Firebase Hosting (`firebase.json`) | `firebase.json`, `.firebaserc` | PRESERVED | Firebase Hosting is decoupled from Auth and remains fully operational for static web deployments |

---

## 3. User Identity & Account Migration Strategy

Firebase UIDs (e.g. alphanumeric strings) and Supabase user IDs (UUIDv4) differ in format:
1. **`yorvyn_legacy_identity_map`**: A dedicated PostgreSQL mapping table stores `(firebase_uid, supabase_user_id, email, migrated_at)`.
2. **Account Relinking**:
   - When an existing Firebase user signs up or logs into Supabase with their verified email address, the migration adapter matches the email and relinks legacy wardrobe records, outfits, and styling preferences to their new Supabase UUID.
   - Password hashes are never transferred across unsupported channels; users set an initial password or use Google OAuth / magic-link recovery.
3. **Zero Data Loss Guarantee**: Legacy wardrobe item records retain foreign key compatibility through the mapping table.

---

## 4. Cloudinary Image Pipeline & Privacy Architecture

```text
User uploads garment photo ────► Backend validates & temporary buffer
                                         │
                                         ▼
                                Garment 3D Pipeline
                                (Silhouette, PBR, GLB, 3D Preview)
                                         │
                                         ▼
                            `CloudinaryStorageAdapter`
                     Uploads `preview.png` and PBR textures
                                         │
                                         ├────────► Cloudinary CDN
                                         │          Public ID: yorvyn/users/{user_id}/garments/{asset_id}
                                         │
                                         ▼
                            Supabase PostgreSQL
                     Inserts `yorvyn_garment_jobs` & `yorvyn_garment_assets`
                                         │
                                         ▼
                     STRICT PRIVACY CLEANUP: Original uploaded
                     photo is permanently purged from disk
```

---

## 5. Security & Isolation Safeguards

- **No Secrets in Frontend**: `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, and `CLOUDINARY_API_SECRET` reside exclusively in server-side environment variables.
- **Frontend Permissions**: The React application accesses Supabase strictly through `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`, governed by PostgreSQL **Row Level Security (RLS)** policies (`auth.uid() = user_id`).
- **Mock Fallback for CI/CD**: Both the Supabase and Cloudinary backend adapters include mock modes so local test suites and CI runners pass without requiring paid accounts or live network calls.
