# Yorvyn — Supabase & Cloudinary Backend Rollback and Recovery Runbook

This document defines the operational procedures for rolling back the Supabase Authentication, PostgreSQL database, and Cloudinary image storage migration, or running in dual/side-by-side mode during the transition phase.

---

## 1. Safety Principles & Pre-Switch Checklist

1. **Zero Data Loss Guarantee**: Never delete existing Firebase user records, Firestore collections, or Firebase Storage buckets until the migration has been verified in production for at least 30 days.
2. **Account Relinking Audit**: All user identities created or linked during the Supabase phase are recorded in the `yorvyn_legacy_identity_map` table:
   - `firebase_uid` <-> `supabase_user_id` <-> `email` <-> `migrated_at`
3. **No Secret Invalidation**: Do not rotate or invalidate Firebase API keys during the migration window.

---

## 2. Dual-Mode / Side-by-Side Operation

During the gradual rollout, the system supports both authentication mechanisms:
- **Frontend**: The `frontend/src/context/AuthContext.tsx` maintains backward compatibility for legacy properties (`user.uid` aliases `user.id`).
- **Backend**: The `backend/app/auth.py` and `backend/app/core/security.py` accept Supabase JWTs, and gracefully fall back to development/mock tokens in non-production environments.

---

## 3. Rollback Scenarios & Actions

### Scenario A: Frontend Auth Emergency Rollback (Supabase Auth Outage)

If Supabase Auth experiences downtime or issues:

1. **Re-enable Firebase Auth Client**:
   In `frontend/src/context/AuthContext.tsx`, switch back to importing from `./firebase.ts` or restore the previous git commit:
   ```bash
   git checkout origin/main~1 -- frontend/src/context/AuthContext.tsx frontend/src/pages/Login.tsx
   npm run build --prefix frontend
   ```
2. **Deploy Frontend**:
   Deploy the updated frontend bundle to your hosting provider (e.g. Firebase Hosting or Vercel).
3. **User Impact**:
   Existing users sign in using their original Firebase email/password credentials or Google Sign-In. Users who registered purely on Supabase during the outage window can use their email to initiate a password reset on Firebase once exported.

---

### Scenario B: Cloudinary CDN / Upload Failure Rollback

If Cloudinary uploads fail or rate limits are reached:

1. **Automatic In-Memory / Local Storage Fallback**:
   The backend `CloudinaryStorageService` in [`backend/app/services/storage/cloudinary_storage.py`](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/storage/cloudinary_storage.py) has an automatic fallback mode.
   If Cloudinary credentials are empty or upload calls error out, it generates mock or local file URLs without crashing the garment reconstruction pipeline.
2. **Local Fallback Switch**:
   Set `CLOUDINARY_API_KEY=""` in `backend/.env` to force local/ephemeral asset delivery until Cloudinary limits are restored:
   ```env
   CLOUDINARY_CLOUD_NAME=""
   CLOUDINARY_API_KEY=""
   CLOUDINARY_API_SECRET=""
   ```
3. Restart FastAPI backend:
   ```bash
   python3 backend/run.py
   ```

---

### Scenario C: Database Rollback (PostgreSQL to Firestore)

If Supabase PostgreSQL needs to be taken offline:

1. **Export Recent Transactions**:
   Dump any newly created records from Supabase tables:
   ```sql
   COPY (SELECT * FROM yorvyn_wardrobe_items WHERE created_at >= '2026-10-25') TO STDOUT WITH CSV HEADER;
   COPY (SELECT * FROM yorvyn_garment_jobs WHERE created_at >= '2026-10-25') TO STDOUT WITH CSV HEADER;
   ```
2. **Run Reconciliation Script**:
   Sync new wardrobe items back to Firestore using `backend/manage_data.py`.
3. **Schema Reversion**:
   If needed, drop the Supabase migration tables safely:
   ```sql
   -- Warning: Only run if rollback is fully verified
   DROP TABLE IF EXISTS yorvyn_messages CASCADE;
   DROP TABLE IF EXISTS yorvyn_conversations CASCADE;
   DROP TABLE IF EXISTS yorvyn_user_preferences CASCADE;
   DROP TABLE IF EXISTS yorvyn_garment_jobs CASCADE;
   DROP TABLE IF EXISTS yorvyn_garment_assets CASCADE;
   DROP TABLE IF EXISTS yorvyn_wardrobe_items CASCADE;
   DROP TABLE IF EXISTS yorvyn_legacy_identity_map CASCADE;
   DROP TABLE IF EXISTS yorvyn_profiles CASCADE;
   ```

---

## 4. Verification After Rollback

1. Execute test suite:
   ```bash
   python3 -m pytest backend/tests/ -v
   npm run build --prefix frontend
   ```
2. Verify user sign-in and wardrobe browsing in browser.
