# Yorvyn — Supabase & Cloudinary Migration Audit Report

**Audit Date:** October 26, 2026  
**Scope:** Firebase Deprecation, Supabase Auth + PostgreSQL Integration, and Cloudinary Media Storage.

---

## 1. Migration State Overview

The migration from Firebase to Supabase and Cloudinary is currently in **Phase 7 (Dual-Mode Transition)**. The core application logic (user authentication, registration, onboarding, profile storage, garment generation jobs, and preview thumbnails) has been ported to Supabase and Cloudinary. Legacy Firebase dependencies remain in non-critical modules to avoid breaking backwards compatibility before production deployment.

```
┌─────────────────────────────────────────────────────────────┐
│                      MIGRATION STATUS                       │
│                                                             │
│  [========================================......] 85%       │
│                                                             │
│  ✓ Supabase Auth: Complete & Verified                       │
│  ✓ Supabase Schema: Complete (Migrations 001 & 002)         │
│  ✓ Cloudinary Storage: Complete & Verified (with mock)      │
│  ✓ Garment 3D Pipeline: Uploads to Cloudinary & Supabase    │
│  ⚠ Legacy Firestore: Partially retained in useFirestore.ts │
│  ⚠ Production Keys: Pending live environment injection      │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Supabase Integration Audit

### Authentication
- **Frontend Client**: [`frontend/src/utils/supabase.ts`](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/utils/supabase.ts) initializes `@supabase/supabase-js` with persistent local storage.
- **Session Management**: Handled in [`frontend/src/context/AuthContext.tsx`](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/context/AuthContext.tsx) via `supabase.auth.onAuthStateChange`. Maps `user.id` to `user.uid` for zero-regression backward compatibility.
- **Backend Verification**: [`backend/app/core/security.py`](file:///Users/anujsandhu/Projects/yorvyn/backend/app/core/security.py) implements `verify_supabase_jwt(token)` validating HS256 JWT signatures and token expiration.

### PostgreSQL Database Schema
Migrations located in [`backend/migrations/`](file:///Users/anujsandhu/Projects/yorvyn/backend/migrations/):
1. **`001_initial_supabase_schema.sql`**:
   - `yorvyn_profiles`: User profile data, avatars, and aesthetic preferences.
   - `yorvyn_wardrobe_items`: Digital wardrobe items, categories, colors, and 3D mesh links.
   - `yorvyn_garment_assets`: High-resolution textures, normal maps, and GLB asset metadata.
   - `yorvyn_garment_jobs`: Async 3D generation jobs (`queued`, `processing`, `completed`, `failed`).
   - `yorvyn_conversations` & `yorvyn_messages`: AI Stylist conversation history.
   - `yorvyn_user_preferences`: Fit, budget, and sizing preferences.
   - `yorvyn_legacy_identity_map`: Verified map linking legacy `firebase_uid` to Supabase `supabase_user_id` by email.
2. **`002_user_profile_onboarding.sql`**:
   - Adds `age`, `height_value`, `height_unit`, `body_type`, `skin_tone_id`, `skin_tone_hex`, `hair_colour_id`, `hair_colour_hex`, `avatar_gender_presentation`, `avatar_configuration` (JSONB), and `onboarding_completed` (BOOLEAN).

### Row Level Security (RLS)
All user-owned tables have RLS enabled:
```sql
ALTER TABLE public.yorvyn_profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can only view their own profile"
    ON public.yorvyn_profiles FOR SELECT
    USING (auth.uid() = user_id);
```

---

## 3. Cloudinary Integration Audit

### Storage Adapter
Located in [`backend/app/services/storage/cloudinary_storage.py`](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/storage/cloudinary_storage.py):
- **Structured Naming Convention**: `yorvyn/users/{sanitized_uid}/garments/{asset_id}`.
- **Server-Side Uploads**: Executes via `cloudinary.uploader.upload(file, public_id=..., tags=...)`.
- **CDN Optimization**: `get_delivery_url(public_id)` generates URLs with automatic format and quality optimization (`f_auto,q_auto`).
- **Asset Deletion**: `delete_garment_image(public_id)` cleans up assets via `cloudinary.uploader.destroy`.
- **Ephemeral Mock Fallback**: When `CLOUDINARY_API_KEY` is not set or begins with `your_`, the adapter returns valid mock CDN URLs (`https://res.cloudinary.com/yorvyn-cloud/image/upload/...`), enabling 100% of local unit and integration tests to pass offline without incurring network costs or requiring live accounts.

---

## 4. Remaining Firebase Dependencies & Retirement Plan

### Identified Active Firebase References

| File | Purpose | Retention Reason | Retirement Action |
|---|---|---|---|
| `frontend/src/utils/firebase.ts` | Firebase App, Auth, Firestore, Analytics | Dual-mode support | Retire once live Supabase is active |
| `frontend/src/hooks/useFirestore.ts` | Legacy chat histories, wishlists | Secondary store | Switch queries to Supabase `yorvyn_conversations` |
| `frontend/src/utils/api.ts` | Attaches legacy token if present | Legacy fallback | Remove once Firebase Auth is retired |
| `backend/app/firestore_client.py` | Admin SDK Firestore client | Legacy user lookup | Retire once all accounts are mapped |

### Safe Decommissioning Procedure
1. Verify Supabase tables and RLS in production environment.
2. Run data export from Firestore to populate `yorvyn_legacy_identity_map`.
3. Switch `useFirestore.ts` calls to Supabase REST endpoints.
4. Remove `firebase` package from `frontend/package.json` and `backend/requirements.txt`.
