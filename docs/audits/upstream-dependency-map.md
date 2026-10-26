# Yorvyn Technology Library — Upstream Dependency Map

**Document Version**: 1.0  
**Audit Date**: October 26, 2026  
**Auditor**: Senior Systems & Dependency Architect (Antigravity)  
**Subject**: Exhaustive Dependency Tracing and Upstream Repository Isolation Verification  

---

## 1. Scope and Objective

This audit maps every external codebase, cloned repository, runtime path, dynamic loader, and build script to guarantee that Yorvyn operates with **zero runtime dependency on external cloned repositories in [research/upstream](file:///Users/anujsandhu/Projects/yorvyn/research/upstream)**.

Production code must be self-contained within project directories, managed by standard package managers (`npm`, `pip`), or loaded from versioned local assets.

---

## 2. Exhaustive Search for Upstream References

An automated scan across the entire project source tree was executed to find any string or import references to `research/upstream`, `upstream`, or external paths.

### 2.1 Frontend Source Tree (`frontend/src/`)
- **Query**: `grep -rn "research/upstream" frontend/src/`
- **Result**: `0 matches found`.
- **Finding**: No frontend TypeScript/JavaScript/CSS files import or reference `research/upstream/`.

### 2.2 Backend Source Tree (`backend/app/`)
- **Query**: `grep -rn "research/upstream" backend/app/`
- **Result**: `0 matches found`.
- **Finding**: No backend Python modules modify `sys.path` to include `research/` or import from cloned checkouts.

### 2.3 Modular Technology Packages (`packages/`)
- **Query**: `grep -rn "research/upstream" packages/`
- **Result**: `0 matches found`.
- **Finding**: All 12 packages in `packages/` are 100% self-contained TypeScript libraries.

### 2.4 Build and Bundler Configurations
- [frontend/vite.config.ts](file:///Users/anujsandhu/Projects/yorvyn/frontend/vite.config.ts):
  - Aliases defined: `@`, `@components`, `@pages`, `@hooks`, `@utils`, `@T`, `@yorvyn`.
  - All aliases resolve strictly within `frontend/src` or `packages/`.
  - No build alias resolves to `research/`.
- [frontend/tsconfig.json](file:///Users/anujsandhu/Projects/yorvyn/frontend/tsconfig.json):
  - Paths defined: `@/* -> src/*`, `@yorvyn -> ../packages/index.ts`, `@yorvyn/* -> ../packages/*`.
  - No path references any research repository.

### 2.5 Runtime Shell & Automation Scripts
- [scripts/acquire_repositories.sh](file:///Users/anujsandhu/Projects/yorvyn/scripts/acquire_repositories.sh):
  - Purpose: Developer utility script to clone candidate research repositories into `research/upstream/` for offline algorithmic study.
  - Runtime impact: Zero. This script is never called by Vite, Node, Uvicorn, or any application entrypoint.

---

## 3. Cloned Upstream Repository Status

Four upstream repositories exist in `research/upstream/` for reference and benchmarking only:

| Repository | Cloned Path | Commit SHA | Declared License | Production Status |
| :--- | :--- | :--- | :--- | :--- |
| **Ara 3D Gen** | `research/upstream/3d-gen` | `6114eb3` | MIT License | **INDEPENDENT** — Clean-room engine integrated in `frontend/src/engine/ara` |
| **Clothware** | `research/upstream/Clothware` | `0507ef4` | MIT (code) / Academic dataset | **OFFLINE REFERENCE ONLY** — No code imported |
| **Garment3DGen** | `research/upstream/Garment3DGen` | `61d3032` | CC-BY-NC 4.0 | **OFFLINE REFERENCE ONLY** — Non-commercial; strictly excluded from SaaS bundle |
| **ReMu** | `research/upstream/ReMu` | `a3bd095` | Non-Commercial / SMPL-X terms | **OFFLINE REFERENCE ONLY** — Excluded from production |

---

## 4. Symlink and Git Submodule Verification

A verification of Git metadata and filesystem symlinks was conducted:

1. **Git Submodules**:
   - Check: `git submodule status`
   - Result: No Git submodules configured.
2. **Filesystem Symlinks**:
   - Check: `find . -maxdepth 4 -type l`
   - Result: No symlinks pointing into `research/upstream/` or outside the workspace.
3. **Hardcoded Absolute Paths**:
   - Check: Search for `/Users/` or absolute system paths in runtime code.
   - Result: All paths in frontend and backend are relative to project root or configured via environment variables (`VITE_BACKEND_TARGET`, `PORT`).

---

## 5. Architectural Isolation Boundary Diagram

```mermaid
graph TD
    subgraph BrowserClient["Yorvyn Client (Browser)"]
        UI["React 18 MainView / Studio"]
        Viewer["AraAvatarViewer (Three.js)"]
        Engine["Ara 3D Character Engine (Local)"]
        YorvynPackages["@yorvyn Technology Packages (In-Tree)"]
    end

    subgraph BackendService["Yorvyn Backend (FastAPI / Uvicorn)"]
        API["/api/fashion/garment-gen"]
        Reconstruct["Photo-to-3D Pipeline (Local CPU / In-Process)"]
        Storage["Digital Wardrobe Storage (Local Static Assets)"]
    end

    subgraph IsolatedResearch["Isolated Research (Strictly Offline)"]
        ResearchDir["research/upstream/* (Clothware, Garment3DGen, ReMu)"]
    end

    UI --> Viewer
    Viewer --> Engine
    Viewer --> YorvynPackages
    UI --> API
    API --> Reconstruct
    Reconstruct --> Storage
    Storage --> Viewer

    IsolatedResearch -.->|NO RUNTIME CALLS / NO IMPORTS / NO SYMLINKS| BackendService
    IsolatedResearch -.->|NO BUNDLE IMPORTS / NO VITE PATHS| BrowserClient
```

---

## 6. Conclusion

Yorvyn satisfies **100% upstream independence**. No production workflow, build task, or test suite requires access to `research/upstream/`. The application is completely maintainable within its own source repository.
