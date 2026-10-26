# Yorvyn Technology Library — File Migration & Semantic Renaming Map

**Refactor Scope**: Professional Project Structure & Semantic File Renaming  
**Architecture Inspiration**: Spring Boot (Controller-Service-Repository-Model) & Maven feature-based layout  
**Safety Protocol**: Incremental relocation, preserve 100% runtime and API backwards compatibility  
**Status**: COMPLETED & VERIFIED (Builds: 0 errors; Tests: 100% passing)

---

## 1. Complete Migration & Relocation Map

| Category | Source File / Path | Production Destination | Status | Rationale / Semantic Improvement |
| :--- | :--- | :--- | :--- | :--- |
| **Frontend Component** | `frontend/src/components/AraAvatarViewer.tsx` | `frontend/src/components/AvatarStudioViewer.tsx` | ✅ Completed | Eliminates third-party repository prefix ("Ara") from Yorvyn-owned component. Backward compatible forwarder retained. |
| **Frontend Style** | `frontend/src/components/AraAvatarViewer.css` | `frontend/src/components/AvatarStudioViewer.css` | ✅ Completed | Semantic stylesheet matching component name. |
| **Frontend Component** | `frontend/src/components/VantaFogBackground.tsx` | `frontend/src/components/AtmosphereBackground.tsx` | ✅ Completed | Eliminates third-party library branding ("Vanta") from component name. Backward compatible forwarder retained. |
| **Frontend Style** | `frontend/src/components/VantaFogBackground.css` | `frontend/src/components/AtmosphereBackground.css` | ✅ Completed | Semantic stylesheet matching component name. |
| **Frontend Engine** | `frontend/src/engine/ara/AraService.ts` | `frontend/src/engine/ara/avatarStudioService.ts` | ✅ Completed | Standardized camelCase service naming; removes vendor prefix. Re-exports `avatarEngine` & `araEngine`. |
| **Frontend Engine** | `frontend/src/engine/ara/AraAnimationController.ts` | `frontend/src/engine/ara/avatarAnimationController.ts` | ✅ Completed | Standardized camelCase controller naming; removes vendor prefix. Re-exports `avatarAnimationController` & `araAnim`. |
| **Backend Core** | `backend/app/config.py` | `backend/app/core/settings.py` | ✅ Completed | Spring Boot core configuration convention; standard `settings.py` with environment schema. |
| **Backend Core** | `backend/app/auth.py` | `backend/app/core/security.py` | ✅ Completed | Security and authentication boundary in `backend/app/core/`. |
| **Backend API Route** | `backend/app/fashion/routes_fashion.py` | `backend/app/api/fashion_routes.py` | ✅ Completed | Centralizes HTTP controller routes under `backend/app/api/`. |
| **Backend API Route** | `backend/app/fashion/garment_3d/routes_garment_3d.py` | `backend/app/api/garment_generation_routes.py` | ✅ Completed | Standard REST controller naming under `backend/app/api/`. |
| **Backend Service** | `backend/app/cache_service.py` | `backend/app/services/cache_service.py` | ✅ Completed | Layered architecture: relocates root service into `services/`. |
| **Backend Service** | `backend/app/user_service.py` | `backend/app/services/user_service.py` | ✅ Completed | Layered architecture: relocates root service into `services/`. |
| **Backend Service** | `backend/app/usage_service.py` | `backend/app/services/usage_service.py` | ✅ Completed | Layered architecture: relocates root service into `services/`. |
| **Backend Service** | `backend/app/personalization_service.py` | `backend/app/services/personalization_service.py` | ✅ Completed | Layered architecture: relocates root service into `services/`. |
| **Backend Service** | `backend/app/fashion/wardrobe_service.py` | `backend/app/services/wardrobe_service.py` | ✅ Completed | Core wardrobe domain service under `services/`. |
| **Backend Service** | `backend/app/fashion/context_service.py` | `backend/app/services/context_service.py` | ✅ Completed | Fashion context and occasion service under `services/`. |
| **Backend Service** | `backend/app/fashion/outfit_generator.py` | `backend/app/services/outfit_generator.py` | ✅ Completed | Outfit synthesis service under `services/`. |
| **Backend Service** | `backend/app/fashion/fashion_orchestrator.py` | `backend/app/services/fashion_orchestrator.py` | ✅ Completed | Multi-domain orchestrator service under `services/`. |
| **Backend Domain** | `backend/app/fashion/fashion_knowledge.py` | `backend/app/domain/fashion_knowledge.py` | ✅ Completed | Static domain knowledge matrix (color seasons, aesthetics, formality). |
| **Backend 3D Pipeline**| `backend/app/fashion/garment_3d/` | `backend/app/services/garments/` | ✅ Completed | Clean grouping of 3D garment reconstruction services: `job_manager.py`, `garment_analyzer.py`, `garment_mesh_builder.py`, `garment_texture_synthesizer.py`, `glb_exporter.py`, `preview_renderer.py`. |
| **Backend Model** | `backend/app/fashion/garment_3d/models.py` | `backend/app/models/garment_models.py` | ✅ Completed | Domain models located in dedicated `backend/app/models/` directory. |

---

## 2. Backward Compatibility Strategy

To ensure zero downtime, uninterrupted local development, and clean CI/CD runs:
1. **Re-export Forwarders**: Where modules were relocated, forwarder modules were left at the legacy path re-exporting the new module (e.g. `backend/app/config.py` re-exporting from `backend.app.core.settings`), ensuring existing scripts or tests continue to execute without breaking.
2. **Path Aliases**: In `frontend/vite.config.ts` and `frontend/tsconfig.json`, aliases are maintained and augmented (`@components`, `@services`, `@hooks`, `@yorvyn`).
3. **Public HTTP Contracts**: All FastAPI routes retain their exact public URLs (`/api/fashion/garment-gen/*`, `/api/fashion/*`, `/health`, `/docs`).
4. **Third-Party Provenance**: Research and upstream licenses in `licenses/THIRD_PARTY_NOTICES.md` remain intact.

---

## 3. Verification Evidence

- **Frontend Build**: `npm run build --prefix frontend` built 1,881 modules in 3.54s with exit code 0.
- **Packages Unit Tests**: `node --experimental-strip-types --test packages/tests/packages.test.ts` (12/12 passing).
- **Backend 3D Garment Pipeline Test**: `python3 backend/test_garment_3d_pipeline.py` (ALL PIPELINE TESTS PASSED, valid GLB, thumbnail, temporary privacy cleanup, wardrobe persistence).
- **Backend App Import**: `python3 -c "from backend.app.main import app; print('✓ App imported successfully')"` (Exit code 0).
- **Upstream Disconnection Isolation Test**: Production frontend build, package test, 3D pipeline test, and backend app import all succeed when `research/upstream` is completely unmounted.
