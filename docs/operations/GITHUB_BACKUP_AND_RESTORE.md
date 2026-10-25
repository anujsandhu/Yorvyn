# Yorvyn — GitHub Backup, Safe Stash, Push & Disaster Recovery Manual

This operational manual documents how the Yorvyn application is backed up to GitHub, how to restore the project onto a clean development environment, how to safely inspect and apply Git stashes, and how to recover from broken or accidental changes without destructive actions.

---

## 1. Verified Upstream Repository Details

- **Official Remote URL**: `https://github.com/anujsandhu/Yorvyn.git`
- **Default Production Branch**: `main`
- **Authenticated Push Target**: `origin/main`

---

## 2. Fresh Machine Setup & Clean Clone Procedure

To clone and set up the repository on a new development machine:

```bash
# 1. Clone the repository
git clone https://github.com/anujsandhu/Yorvyn.git
cd Yorvyn

# 2. Verify git branch and commit SHA
git status
git log -1 --oneline

# 3. Restore frontend dependencies using the exact lockfile
cd frontend
npm ci
cd ..

# 4. Set up python virtual environment and backend dependencies
python3 -m venv backend/venv
source backend/venv/bin/activate
pip install -r backend/requirements.txt
```

---

## 3. Environment Variables & Secret Configuration

Git intentionally does **not** track `.env` files to prevent security leaks. After cloning, configure local environment files:

### Backend Configuration (`backend/.env`)
```bash
cp backend/.env.example backend/.env 2>/dev/null || cat << 'EOF' > backend/.env
# Yorvyn Fashion Intelligence Server Configuration
ENVIRONMENT=development
PORT=8002
HOST=0.0.0.0
CORS_ORIGINS=http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174
SECRET_KEY=yorvyn_development_secret_key_replace_in_production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
TEMP_PROCESSING_DIR=data/temp_processing
WARDROBE_DATA_FILE=data/wardrobe_items.json
EOF
```

### Frontend Configuration (`frontend/.env`)
```bash
cat << 'EOF' > frontend/.env
VITE_API_URL=/api
VITE_ENGINE_ENV=development
EOF
```

---

## 4. Reversible Recovery Procedures

### A. Reverting to a Known Working Commit
If a newly pushed commit introduces bugs, **never force-push or reset remote history**. Instead, create a safe, reversible revert commit:

```bash
# 1. Inspect recent commit history
git log -5 --oneline

# 2. Revert the problematic commit (creates a new commit that undoes the changes)
git revert <problematic-commit-sha>

# 3. Verify and push the revert
npm run build --prefix frontend
git push origin main
```

### B. Checking Out an Older Commit (Read-Only Inspection)
To inspect the codebase at a historical commit without altering the `main` branch:

```bash
# Checkout the historical commit (produces a detached HEAD state)
git checkout <commit-sha>

# When inspection is finished, cleanly return to main
git checkout main
```

### C. Restoring a Single Deleted or Corrupted File
To recover a specific tracked file without affecting the rest of your working tree:

```bash
# Restore file from HEAD (most recent commit)
git checkout HEAD -- path/to/file.tsx

# Or restore file from a specific historical commit
git checkout <commit-sha> -- path/to/file.tsx
```

---

## 5. Git Stash Management & Safety Rules

Stashing is temporary local storage, not a permanent GitHub backup. Follow these rules to prevent accidental work loss:

### Creating a Safe Stash
Always provide a descriptive, timestamped message and include untracked files:
```bash
git stash push --include-untracked -m "yorvyn-safety-checkpoint-$(date +%Y-%m-%d-%H%M)"
```

### Inspecting Existing Stashes
Before applying or altering stashes, inspect what each stash contains:
```bash
# List all stashes
git stash list

# Inspect modified files in a specific stash
git stash show stash@{0}

# Inspect full unified diff of a specific stash
git stash show -p stash@{0}
```

### Safely Restoring a Stash
Always use `apply` rather than `pop`. `apply` leaves the stash in your stash list so your work remains recoverable even if a conflict occurs during application:
```bash
# 1. Apply the stash
git stash apply stash@{0}

# 2. Verify all files and compile
npm run build --prefix frontend

# 3. Only after the work is verified and committed, remove the stash:
git stash drop stash@{0}
```

---

## 6. What Git Does NOT Back Up

The following assets are excluded from Git by design and must be managed via local backups or external storage:

1. **Environment Secrets & API Credentials**: `.env`, private keys, and service account tokens.
2. **Temporary User Uploads**: Photos uploaded for 3D reconstruction are temporarily stored in `backend/data/temp_processing/` and deleted immediately upon job completion under Yorvyn's zero-retention privacy policy.
3. **Heavy Third-Party Research Repositories**: Cloned research checkouts in `research/upstream/` (Clothware, Garment3DGen, ReMu). These can be re-acquired at any time using `scripts/acquire_repositories.sh`.
4. **Active Runtime State**: `node_modules/`, `venv/`, runtime build caches (`dist/`, `.pytest_cache/`), and active uvicorn logs.

---

## 7. Restoration Verification & Health Checks

After restoring or syncing the project, run these health checks to ensure the system is operational:

```bash
# 1. Verify frontend TypeScript types and Vite bundle
cd frontend && npm run build && cd ..

# 2. Run backend 3D garment pipeline integration test
python3 backend/test_garment_3d_pipeline.py

# 3. Start local development servers
./start.sh
```
All tests must exit with code `0`.
