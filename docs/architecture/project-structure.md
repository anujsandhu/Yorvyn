# Yorvyn Architecture & Project Structure Guide

## 1. Overview & Architectural Philosophy

Yorvyn adopts a clean, layered software architecture inspired by **Spring Boot** and **Maven** feature-driven principles, adapted for a modern TypeScript/React frontend, a FastAPI Python backend, and an independent 12-package modular technology library.

The architecture emphasizes:
- **Separation of Concerns**: Controllers (API endpoints), business logic (services), domain rules, data models, and infrastructure/storage are strictly separated.
- **Independence from Upstream Clones**: Yorvyn's production application and runtime execute completely independently of research clones (`research/upstream/`), using Yorvyn's private packages and internal services.
- **Human-Readable Semantic Naming**: Components and services describe their actual domain function rather than implementation quirks or third-party company branding.
- **Zero-Downtime Backward Compatibility**: Seamless re-export forwarders ensure existing scripts, legacy tests, and tooling continue to function without interruption.

---

## 2. Repository Layout

```text
yorvyn/
├── frontend/                     # React 18 + Vite + Three.js + Framer Motion
│   ├── public/                   # Static web assets & icons
│   └── src/
│       ├── app/                  # Application root & routes
│       ├── assets/               # Branding, local 3D models, textures
│       ├── components/           # UI components organized semantically
│       │   ├── layout/           # AppSideNav, AppHeader, navigation shells
│       │   ├── feedback/         # Modals, toasts, loading spinners
│       │   ├── common/           # Buttons, cards, form inputs
│       │   ├── AvatarStudioViewer.tsx  # Production 3D avatar & garment viewport
│       │   └── AtmosphereBackground.tsx # Studio atmospheric environment & fog
│       ├── features/             # Feature-specific components, hooks & services
│       │   ├── avatar-studio/    # Avatar inspection & garment dressing
│       │   ├── wardrobe/         # Digital wardrobe collection & curation
│       │   ├── garment-gen/      # Photo-to-3D garment reconstruction
│       │   └── outfit-studio/    # Stylist chat & outfit lookbooks
│       ├── engine/               # 3D engine interfaces & controllers
│       │   └── ara/              # Parametric avatar & animation bindings
│       │       ├── avatarStudioService.ts       # Avatar engine service
│       │       └── avatarAnimationController.ts # Animation state machine
│       ├── services/             # API client services & network layer
│       ├── hooks/                # Custom React hooks
│       ├── styles/               # Global CSS design system & typography
│       └── types/                # Frontend contracts & TypeScript definitions
│
├── backend/                      # Python 3 / FastAPI Layered Backend
│   ├── app/
│   │   ├── main.py               # Application bootstrap & middleware
│   │   ├── api/                  # Controllers / HTTP route handlers
│   │   │   ├── fashion_routes.py            # Wardrobe, stylist & outfits API
│   │   │   └── garment_generation_routes.py # Photo-to-3D garment pipeline API
│   │   ├── core/                 # Core cross-cutting configuration
│   │   │   ├── settings.py       # Pydantic environment & app settings
│   │   │   └── security.py       # Authentication & security handlers
│   │   ├── domain/               # Pure business domain rules & heuristics
│   │   │   └── fashion_knowledge.py # Color harmony, occasion matrices, thermal rules
│   │   ├── models/               # Domain data transfer & entity models
│   │   │   └── garment_models.py # Pydantic schemas for 3D garments & jobs
│   │   └── services/             # Domain business services (Spring Service layer)
│   │       ├── wardrobe_service.py       # Digital wardrobe & asset persistence
│   │       ├── context_service.py        # Weather, occasion & intent parsing
│   │       ├── outfit_generator.py       # Algorithmic outfit generation
│   │       ├── fashion_orchestrator.py   # Multi-service styling coordinator
│   │       ├── cache_service.py          # Fast caching layer
│   │       ├── user_service.py           # User state management
│   │       ├── usage_service.py          # Quotas & telemetry
│   │       ├── personalization_service.py# Preference tracking
│   │       └── garments/                 # 3D Garment Pipeline Services
│   │           ├── job_manager.py                 # Async job state machine
│   │           ├── garment_analyzer.py            # Computer vision & color analyzer
│   │           ├── garment_mesh_builder.py        # 3D mesh synthesis & seaming
│   │           ├── garment_texture_synthesizer.py  # PBR map synthesizer
│   │           ├── glb_exporter.py                # Binary GLB packaging
│   │           └── preview_renderer.py            # Offscreen 3D thumbnail renderer
│   ├── tests/                    # Backend automated tests
│   │   ├── test_fashion.py       # Fashion intelligence unit tests
│   │   ├── test_garment_3d_pipeline.py # End-to-end 3D reconstruction tests
│   │   └── ...
│   └── requirements.txt
│
├── packages/                     # Yorvyn Modular Technology Library (12 Packages)
│   ├── shared-types/             # Core math, bounding boxes & contracts
│   ├── avatar-core/              # Anthropometry & body measurement solvers
│   ├── avatar-generation/        # Parametric avatar synthesis & GLB export
│   ├── avatar-rigging/           # 65-bone humanoid skeleton & skinning weights
│   ├── avatar-animation/         # BVH/glTF clip registry & animation controller
│   ├── garment-core/             # Garment boundary loops & mesh validation
│   ├── garment-reconstruction/   # Photograph analysis & separable garment geometry
│   ├── garment-fitting/          # Body-to-garment collision & deformation
│   ├── materials-textures/       # PBR normal/roughness synthesis & texture baking
│   ├── three-renderer/           # Studio lighting presets & camera choreography
│   ├── asset-pipeline/           # GLB asset bundling & storage adapters
│   ├── ai-adapters/              # PyTorch/ONNX inference runners & GPU fallbacks
│   └── tests/                    # Automated package test suite (12/12 passing)
│
├── research/                     # Isolated Research & Clones (Never imported in prod)
│   └── upstream/                 # Upstream reference repositories (read-only)
│
├── docs/                         # Project Documentation
│   ├── architecture/             # Architecture, migration maps, technology plans
│   ├── development/              # Conventions, guidelines & contributor docs
│   ├── audits/                   # Verification reports & compliance audits
│   └── operations/               # Runbooks, deployment & backup procedures
│
└── licenses/                     # Third-party notices, SPDX licenses & attribution
```

---

## 3. Placement Rules for New Code

1. **New UI Components**:
   - Generic/shared UI controls (e.g. `Modal.tsx`, `Slider.tsx`) belong in `frontend/src/components/common/` or `frontend/src/components/feedback/`.
   - Complex 3D or scene viewers belong in `frontend/src/components/` or under the respective feature in `frontend/src/features/`.
   - Always avoid third-party branding in file names (e.g. use `AvatarStudioViewer.tsx`, never vendor-branded prefixes).

2. **New Backend Services**:
   - New business logic belongs in `backend/app/services/`.
   - New HTTP endpoints belong in `backend/app/api/` as `*_routes.py`.
   - New data models or Pydantic schemas belong in `backend/app/models/`.
   - Pure domain heuristics (e.g. style formulas, rules) belong in `backend/app/domain/`.
   - Cross-cutting concerns (authentication, config) belong in `backend/app/core/`.

3. **New Shared 3D/AI Algorithms**:
   - Generic 3D mathematics, meshes, and AI adapters belong in `packages/<package-name>/`.
   - Each package must maintain its own `index.ts` with explicit exports and test coverage in `packages/tests/`.

4. **Upstream Research & Experiments**:
   - Place experimental prototypes, external research papers, and reference clones exclusively under `research/`.
   - Never import files from `research/` into `frontend/`, `backend/`, or `packages/`.
