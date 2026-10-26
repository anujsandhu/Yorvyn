# Yorvyn File Naming & Code Conventions

This document defines the official naming conventions and development standards across all Yorvyn codebases (Frontend, Backend, Packages, and Documentation).

---

## 1. Core Principles

1. **Responsibility-Driven Naming**: Name files after what they do or represent in the Yorvyn domain, not who originally created the algorithm or where an initial idea originated.
2. **No Third-Party Company or Brand Prefixes in Yorvyn Modules**:
   - ❌ Bad: `AraAvatarViewer.tsx`, `VantaFogBackground.tsx`, `SmplxRigAdapter.ts`
   - ✅ Good: `AvatarStudioViewer.tsx`, `AtmosphereBackground.tsx`, `HumanoidRigAdapter.ts`
3. **No Ambiguous or Incremental Suffixes**:
   - ❌ Bad: `helper.ts`, `common2.ts`, `new.ts`, `temp.py`, `final_mesh.py`
   - ✅ Good: `meshValidation.ts`, `garmentSeamBuilder.ts`, `clothingAnalyzer.py`
4. **Consistency**: Follow the standard idioms of the language and ecosystem.

---

## 2. Frontend Conventions (TypeScript / React)

### React Components
- **File Name**: `PascalCase.tsx`
- **Component Identifier**: `PascalCase`
- **Stylesheet**: `PascalCase.css` alongside the component or in `styles/`
- **Examples**:
  - `AvatarStudioViewer.tsx` + `AvatarStudioViewer.css`
  - `AtmosphereBackground.tsx` + `AtmosphereBackground.css`
  - `GarmentUploadModal.tsx`
  - `WardrobeItemCard.tsx`

### Custom React Hooks
- **File Name**: `useCamelCase.ts`
- **Export**: `function useCamelCase(...)`
- **Examples**:
  - `useAvatarAnimation.ts`
  - `useWardrobeSync.ts`
  - `useGarmentJobStatus.ts`

### Services & Controllers
- **File Name**: `camelCaseService.ts` or `camelCaseController.ts`
- **Examples**:
  - `avatarStudioService.ts`
  - `avatarAnimationController.ts`
  - `garmentGenerationClient.ts`

### Utilities & Helpers
- **File Name**: `camelCase.ts`
- **Examples**:
  - `meshValidation.ts`
  - `colorPaletteUtils.ts`
  - `formatCurrency.ts`

### Types & Contracts
- **File Name**: `camelCase.ts` or `camelCaseTypes.ts`
- **Examples**:
  - `garmentTypes.ts`
  - `avatarContracts.ts`

---

## 3. Backend Conventions (Python / FastAPI)

### Modules & Source Files
- **File Name**: `snake_case.py`
- **Examples**:
  - `wardrobe_service.py`
  - `garment_analyzer.py`
  - `fashion_orchestrator.py`
  - `glb_exporter.py`

### API Route Modules (Controllers)
- **File Name**: `*_routes.py` located under `backend/app/api/`
- **Examples**:
  - `fashion_routes.py`
  - `garment_generation_routes.py`
  - `auth_routes.py`

### Services (Spring-Style Service Layer)
- **File Name**: `*_service.py` or domain-specific noun (`outfit_generator.py`) located under `backend/app/services/`
- **Class Name**: `PascalCase`
- **Singleton Export**: `snake_case` instance
- **Examples**:
  - `WardrobeService` in `wardrobe_service.py` -> exported as `wardrobe_service`
  - `GarmentJobManager` in `job_manager.py` -> exported as `garment_job_manager`

### Models & Schemas
- **File Name**: `*_models.py` or `*_schemas.py` under `backend/app/models/` or `backend/app/schemas/`
- **Class Names**: Pydantic models in `PascalCase`
- **Examples**:
  - `garment_models.py` (`GarmentGenJob`, `GarmentGenResult`, `DetectedGarmentFeatures`)

### Domain Knowledge
- **File Name**: `*_knowledge.py` or `*_rules.py` under `backend/app/domain/`
- **Examples**:
  - `fashion_knowledge.py` (contains color matrices, style aesthetic dictionaries, weather thresholds)

### Core Cross-Cutting Configuration
- **File Name**: `settings.py`, `security.py`, `logging_config.py` under `backend/app/core/`

---

## 4. Shared Packages (`packages/`)

- **Directory Name**: `kebab-case` under `packages/` (e.g. `garment-reconstruction`, `avatar-generation`)
- **Package Manifest**: `@yorvyn/<kebab-case>`
- **Entrypoint**: `index.ts` exporting explicit named symbols
- **Unit Tests**: Co-located or in `packages/tests/` named `*.test.ts`

---

## 5. Upstream Reference Isolation (`research/upstream/`)

- Cloned research repositories live under `research/upstream/<original-repo-name>/`.
- Their original file names, commit histories, Git metadata, and license files are preserved intact.
- **Strict Prohibition**: No production code in `frontend/`, `backend/`, or `packages/` may import directly from `research/upstream/`.
