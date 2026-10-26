# Yorvyn Technology Library — File Migration & Semantic Renaming Map

**Refactor Scope**: Professional Project Structure & Semantic File Renaming  
**Architecture Inspiration**: Spring Boot (Controller-Service-Repository-Model) & Maven feature-based layout  
**Safety Protocol**: Incremental relocation, preserve 100% runtime and API backwards compatibility  

---

## 1. Migration Map Summary

| Category | Source File / Path | Proposed Destination | Rationale / Semantic Improvement |
| :--- | :--- | :--- | :--- |
| **Frontend Component** | `frontend/src/components/AraAvatarViewer.tsx` | `frontend/src/components/AvatarStudioViewer.tsx` | Eliminates third-party repository prefix ("Ara") from Yorvyn-owned component. |
| **Frontend Style** | `frontend/src/components/AraAvatarViewer.css` | `frontend/src/components/AvatarStudioViewer.css` | Semantic stylesheet matching component. |
| **Frontend Component** | `frontend/src/components/VantaFogBackground.tsx` | `frontend/src/components/AtmosphereBackground.tsx` | Eliminates third-party library branding ("Vanta") from component name. |
| **Frontend Style** | `frontend/src/components/VantaFogBackground.css` | `frontend/src/components/AtmosphereBackground.css` | Semantic stylesheet matching component. |
| **Frontend Engine** | `frontend/src/engine/ara/AraService.ts` | `frontend/src/engine/ara/avatarStudioService.ts` | Standardized camelCase service naming; removes vendor prefix. |
| **Frontend Engine** | `frontend/src/engine/ara/AraAnimationController.ts` | `frontend/src/engine/ara/avatarAnimationController.ts` | Standardized camelCase controller naming; removes vendor prefix. |
| **Backend Core** | `backend/app/config.py` | `backend/app/core/settings.py` | Spring Boot core configuration convention; standard `settings.py`. |
| **Backend Core** | `backend/app/auth.py` | `backend/app/core/security.py` | Security and authentication boundary in `core/`. |
| **Backend API Route** | `backend/app/fashion/routes_fashion.py` | `backend/app/api/fashion_routes.py` | Centralizes HTTP controller routes under `backend/app/api/`. |
| **Backend API Route** | `backend/app/fashion/garment_3d/routes_garment_3d.py` | `backend/app/api/garment_generation_routes.py` | Standard REST controller naming under `backend/app/api/`. |
| **Backend Service** | `backend/app/cache_service.py` | `backend/app/services/cache_service.py` | Layered architecture: relocates root service into `services/`. |
| **Backend Service** | `backend/app/user_service.py` | `backend/app/services/user_service.py` | Layered architecture: relocates root service into `services/`. |
| **Backend Service** | `backend/app/usage_service.py` | `backend/app/services/usage_service.py` | Layered architecture: relocates root service into `services/`. |
| **Backend Service** | `backend/app/personalization_service.py` | `backend/app/services/personalization_service.py` | Layered architecture: relocates root service into `services/`. |
| **Backend Service** | `backend/app/fashion/wardrobe_service.py` | `backend/app/services/wardrobe_service.py` | Core wardrobe domain service under `services/`. |
| **Backend Service** | `backend/app/fashion/context_service.py` | `backend/app/services/context_service.py` | Fashion context and occasion service under `services/`. |
| **Backend Service** | `backend/app/fashion/outfit_generator.py` | `backend/app/services/outfit_generator.py` | Outfit synthesis service under `services/`. |
| **Backend Service** | `backend/app/fashion/fashion_orchestrator.py` | `backend/app/services/fashion_orchestrator.py` | Multi-domain orchestrator service under `services/`. |
| **Backend Service** | `backend/app/fashion/fashion_knowledge.py` | `backend/app/domain/fashion_knowledge.py` | Static domain knowledge matrix (color seasons, aesthetics, formality). |
| **Backend 3D Pipeline**| `backend/app/fashion/garment_3d/` | `backend/app/services/garments/` | Clean grouping of 3D garment reconstruction services. |
| **Backend Model** | `backend/app/fashion/garment_3d/models.py` | `backend/app/models/garment_models.py` | Domain models located in dedicated `models/` directory. |
| **Backend NLP** | `backend/app/intent_classifier.py` | `backend/app/services/intelligence/intent_classifier.py` | Groups NLP intelligence submodules under services/intelligence/. |
| **Backend NLP** | `backend/app/tone_detector.py` | `backend/app/services/intelligence/tone_detector.py` | Groups NLP intelligence submodules under services/intelligence/. |
| **Backend NLP** | `backend/app/spell_corrector.py` | `backend/app/services/intelligence/spell_corrector.py` | Groups NLP intelligence submodules under services/intelligence/. |
| **Backend NLP** | `backend/app/prompt_builder.py` | `backend/app/services/intelligence/prompt_builder.py` | Groups NLP intelligence submodules under services/intelligence/. |
| **Backend NLP** | `backend/app/response_generator.py` | `backend/app/services/intelligence/response_generator.py` | Groups NLP intelligence submodules under services/intelligence/. |
| **Backend NLP** | `backend/app/strict_filter.py` | `backend/app/services/intelligence/strict_filter.py` | Groups NLP intelligence submodules under services/intelligence/. |
| **Backend NLP** | `backend/app/unified_scorer.py` | `backend/app/services/intelligence/unified_scorer.py` | Groups NLP intelligence submodules under services/intelligence/. |
| **Backend Tests** | `backend/test_*.py` | `backend/tests/integration/` | Organizes root test scripts into `tests/integration/` while maintaining entrypoint scripts. |

---

## 2. Backward Compatibility Strategy

To ensure zero downtime, uninterrupted local development, and clean CI/CD runs:
1. **Re-export Forwarders**: Where modules are relocated, forwarder modules will be left at the legacy path re-exporting the new module (e.g. `backend/app/config.py` importing from `backend.app.core.settings`), ensuring existing scripts or tests continue to execute without breaking.
2. **Path Aliases**: In `frontend/vite.config.ts` and `frontend/tsconfig.json`, aliases are maintained and augmented (`@components`, `@services`, `@hooks`, `@yorvyn`).
3. **Public HTTP Contracts**: All FastAPI routes retain their exact public URLs (`/api/fashion/garment-gen/*`, `/api/fashion/*`, `/health`, `/docs`).
4. **Third-Party Provenance**: Research and upstream licenses in `licenses/THIRD_PARTY_NOTICES.md` remain intact.
