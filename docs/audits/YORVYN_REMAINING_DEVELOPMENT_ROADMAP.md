# Yorvyn — Prioritized Development Roadmap & Backlog

**Audit Date:** October 26, 2026  
**Standard:** P0 (Blockers) -> P1 (Core Functionality) -> P2 (Advanced Intelligence) -> P3 (Polish).

---

## 1. Prioritized Development Backlog

### P0 — Critical Blockers & Staging Deployment

| ID | Task | Affected Files | Dependencies | Acceptance Criteria | Complexity |
|---|---|---|---|---|---|
| **P0-1** | Execute Supabase SQL Migrations | `backend/migrations/001_initial_supabase_schema.sql`<br>`backend/migrations/002_user_profile_onboarding.sql` | Live Supabase Project | All 8 tables and RLS policies created in Supabase PostgreSQL | **Low** |
| **P0-2** | Configure Staging Environment Variables | `backend/.env`<br>`frontend/.env` | Supabase & Cloudinary Dashboards | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`, `CLOUDINARY_*` set with live values | **Low** |
| **P0-3** | Deprecate Outdated Perfume Test Regressions | `backend/tests/test_spell_corrector.py`<br>`backend/tests/test_response_generator.py` | None | Deprecate or retire old perfume spell corrector tests so CI passes with 100% green | **Low** |

---

### P1 — Core Product Functionality & Decommissioning

| ID | Task | Affected Files | Dependencies | Acceptance Criteria | Complexity |
|---|---|---|---|---|---|
| **P1-1** | Switch Chat History to Supabase | `frontend/src/hooks/useFirestore.ts`<br>`backend/app/services/database/supabase_repository.py` | P0-1 | AI Stylist conversation messages persist in `yorvyn_conversations` / `yorvyn_messages` | **Medium** |
| **P1-2** | Complete Firebase Package Removal | `frontend/package.json`<br>`frontend/src/utils/firebase.ts` | P1-1 | Remove `firebase` and `@firebase/analytics` packages; zero bundle overhead | **Medium** |
| **P1-3** | Google OAuth Configuration | `frontend/src/context/AuthContext.tsx` | Google Cloud Console | Users can log in with one click using their verified Google identity | **Low** |
| **P1-4** | User Account Deletion Flow | `frontend/src/pages/PersonalProfile.tsx`<br>`backend/app/api/fashion_routes.py` | P0-1 | Users can request complete GDPR-compliant deletion of profile, wardrobe, and Cloudinary assets | **Medium** |

---

### P2 — Advanced Intelligence & 3D Garment Enhancements

| ID | Task | Affected Files | Dependencies | Acceptance Criteria | Complexity |
|---|---|---|---|---|---|
| **P2-1** | Neural Background Removal | `backend/app/services/garments/garment_analyzer.py` | ONNX Runtime | Integrate lightweight ONNX segmentation (RMBG-1.4) for complex patterned clothing | **High** |
| **P2-2** | Avatar-Garment Collision Fitting | `packages/garment-fitting/index.ts`<br>`frontend/src/components/AvatarStudioViewer.tsx` | Three.js | Real-time vertex projection ensuring garments conform to avatar body shape without clipping | **High** |
| **P2-3** | Multi-Garment Layered Try-On | `frontend/src/pages/OutfitStudio.tsx` | P2-2 | Display complete outfit (top + bottom + outerwear + shoes) on avatar simultaneously | **Medium** |
| **P2-4** | Voice Conversation Interruption | `frontend/src/pages/StylistChat.tsx` | Web Speech API | When user speaks, ongoing TTS speech synthesis automatically cancels immediately | **Low** |

---

### P3 — Production Polish & Observability

| ID | Task | Affected Files | Dependencies | Acceptance Criteria | Complexity |
|---|---|---|---|---|---|
| **P3-1** | Sentry Error Monitoring | `frontend/src/main.tsx`<br>`backend/app/main.py` | Sentry DSN | Automatic capture of unhandled client and server exceptions | **Low** |
| **P3-2** | Mobile WebGL Optimization | `frontend/src/components/AvatarStudioViewer.tsx` | Three.js | Reduced shadow resolution and texture mipmaps on low-power mobile devices | **Medium** |
| **P3-3** | End-to-End Playwright Smoke Tests | `tests/e2e/` | Playwright | Automated headless browser test for registration -> onboarding -> wardrobe upload | **Medium** |

---

## 2. Recommended Next Milestone

**Milestone: Staging Activation & Firebase Decommissioning**
1. Run migrations `001` and `002` in the live Supabase SQL Console.
2. Inject live credentials into `backend/.env` and `frontend/.env`.
3. Verify live registration, onboarding, and garment photo upload through Cloudinary in staging.
4. Remove `firebase` package from `frontend/package.json` to complete Phase 10 of backend migration.
