# YORVYN — GitHub Backup & Google Colab Remote Execution Integration Report

**Date:** 2026-11-26  
**Branch:** `release/stabilize-17.4`  
**Remote:** `https://github.com/anujsandhu/Yorvyn.git` (`origin`)

---

## 1. GitHub Repository Configuration

- **Remote:** `origin` -> `https://github.com/anujsandhu/Yorvyn.git` (private repository).
- **Branches:**
  - `main` — stable production baseline (`7139fc7`).
  - `release/stabilize-17.4` — active integration/stabilization branch containing Phase 0 + GitHub/Colab workflow integration.
  - Feature branches (`feat/<scope>`, `fix/<scope>`, `chore/<scope>`) — branched from the active integration branch or `main`.
- **Commit Conventions:** Conventional Commits (`feat(...)`, `fix(...)`, `chore(...)`, `docs(...)`, `test(...)`).
- **Version Tags:** Annotated semantic tags (`v17.4.0`, `v17.5.0`, etc.) created on verified `main` commits (`git tag -a vX.Y.Z -m "Release vX.Y.Z"`).
- **Recommended GitHub Branch Protection (`main`):**
  - Require pull request reviews before merging.
  - Require status checks to pass (`.github/workflows/ci.yml`: `backend-test`, `frontend-test-and-build`, `security-and-lint`).
  - Disallow force pushes (`--force`) and branch deletions.

---

## 2. Automated Backup Workflow

Implemented in [scripts/ops/github_backup.sh](file:///Users/anujsandhu/Projects/yorvyn/scripts/ops/github_backup.sh):

1. **Inspect Git status & active branch** (`git status --short`).
2. **Guard against forbidden/large runtime files** (blocks `.env`, `.env.*`, `dump.rdb`, `backend.sock`, `*.pt`, `*.pth`, `*.safetensors`, `generated_3d/`, `wardrobe_assets/`, `temp_processing/`).
3. **Secret scan on `git diff HEAD`** (blocks GitHub PATs, AWS keys, Stripe live keys, Google API keys, and PEM private keys).
4. **Verify `.gitignore` invariants** (ensures core ignore patterns remain present).
5. **Run verification checks** (`cd frontend && npm test && npm run build`; skippable only when explicitly requested with `SKIP_TESTS=1`).
6. **Explicit commit gate** — refuses to auto-commit unreviewed changes without an explicit commit message.
7. **Non-destructive push** (`git push origin <branch>`, never `--force`, never resets history or deletes remote branches).
8. **Remote SHA verification** — compares `git rev-parse HEAD` against `git ls-remote origin refs/heads/<branch>`.

---

## 3. Branch Strategy

- `main`: Protected baseline; updated via reviewed PRs or verified fast-forward merges after CI passes.
- `release/*` / `develop`: Integration branch for multi-step stabilization and feature batching.
- `feat/*` / `fix/*`: Short-lived branches for isolated work, merged after tests pass.

---

## 4. Large-File, Model & Dataset Storage

- **Git LFS rules:** Added [.gitattributes](file:///Users/anujsandhu/Projects/yorvyn/.gitattributes) tracking `*.pt`, `*.pth`, `*.safetensors`, `*.onnx`, `*.glb`, `*.bin`, `*.pkl`, `*.tar.gz`, and `*.zip` via LFS when explicitly versioned.
- **Git exclusions:** [.gitignore](file:///Users/anujsandhu/Projects/yorvyn/.gitignore) excludes `models/generated_3d/`, `models/checkpoints/*.pt`, `data/datasets/`, `backend/data/wardrobe_assets/`, `backend/data/temp_processing/`, `dump.rdb`, `backend.sock`, `scratch/`, and `.env`.
- **Metadata & provenance in Git:** Lightweight manifests (`models/registry.json`, `models/checkpoints/checkpoint_manifest.json`) remain in Git so model SHA-256s are auditable without bloating Git history.
- **Persistent artifact storage:** Colab exports artifacts and execution logs to Google Drive (`/content/drive/MyDrive/yorvyn_artifacts/<experiment_id>/`) or configured object storage, never Git history. Private user images are never committed to GitHub.

---

## 5. Google Colab Execution Workflow & Reproducibility

Implemented across [notebooks/yorvyn_colab_gpu_worker.ipynb](file:///Users/anujsandhu/Projects/yorvyn/notebooks/yorvyn_colab_gpu_worker.ipynb) and [scripts/ops/colab_experiment_runner.py](file:///Users/anujsandhu/Projects/yorvyn/scripts/ops/colab_experiment_runner.py):

1. **Explicit code version selection:** User specifies `TARGET_BRANCH` and optional `TARGET_COMMIT_SHA` (pinned via `git checkout --detach <sha>`), never assuming `main` is the active experiment version.
2. **Pinned dependency installation:** Installs from `backend/requirements.txt`.
3. **Hardware detection:** Logs CUDA GPU model, VRAM, and `nvidia-smi` output (or MPS/CPU fallback).
4. **Checkpoint verification:** Loads `models/checkpoints/checkpoint_manifest.json` and computes SHA-256 of loaded checkpoints via `compute_sha256()`.
5. **Module execution & provenance manifest:** `build_experiment_manifest()` writes `reproducibility_manifest.json` containing:
   - `git_repository`, `git_branch`, `git_commit_sha`
   - `python_version`, `dependency_versions`
   - `gpu_model`, `gpu_device`, `vram_mb`
   - `checkpoint_path`, `checkpoint_sha256`
   - `dataset_version`, `execution_parameters` (with secret keys redacted)
   - `output_artifacts` (path, SHA-256, byte size)
   - `execution_status`, `timestamp_utc`

---

## 6. Authentication & Security

- **Zero embedded tokens:** Colab retrieves `GITHUB_TOKEN` ephemerally via `google.colab.userdata` or `getpass.getpass()`, passes it through a temporary `GIT_ASKPASS` helper (`0o700`, immediately unlinked after `git clone`), and deletes the Python variable (`del _gh_token`).
- **Log redaction:** `redact_sensitive_params()` replaces any parameter key containing `token`, `secret`, `password`, `api_key`, `pat`, or `credential` with `[REDACTED]`.
- **URL sanitization:** `collect_git_metadata()` strips any embedded `@` credentials from remote URLs before writing manifests.
- **No unauthenticated public tunnels:** Colab execution does not expose unauthenticated public endpoints.

---

## 7. Recovery Procedure

See [GITHUB_BACKUP_AND_RESTORE.md](file:///Users/anujsandhu/Projects/yorvyn/docs/operations/GITHUB_BACKUP_AND_RESTORE.md) for full runbooks:
- Clean clone + `npm ci` + `pip install -r backend/requirements.txt`.
- Non-destructive rollback via `git revert <sha>`.
- Single-file recovery via `git checkout <sha> -- <path>`.
- Safe stash recovery using `git stash apply` before `drop`.

---

## 8. Verification Results & Known Environment Gaps

| Check | Result | Details |
|---|---|---|
| `bash -n scripts/ops/github_backup.sh` | **PASS** | Exit code `0`. |
| `cd backend && ./venv/bin/pytest -q tests/test_github_colab_integration.py` | **PASS** | `5 passed in 1.28s` (`.gitattributes`, `.gitignore`, notebook JSON/token scan, secret redaction, manifest SHA-256 generation). |
| `git lfs version` (local Mac environment) | **NOT INSTALLED** | `git: 'lfs' is not a git command`. Install `brew install git-lfs && git lfs install` locally before committing LFS-tracked binaries. |
| `git ls-remote --heads --tags origin` (from this sandbox) | **BLOCKED (SSL)** | `fatal: unable to access 'https://github.com/anujsandhu/Yorvyn.git/': SSL certificate problem: self signed certificate in certificate chain`. Run `scripts/ops/github_backup.sh` from your authenticated local terminal to push `release/stabilize-17.4` and verify the remote SHA. |
