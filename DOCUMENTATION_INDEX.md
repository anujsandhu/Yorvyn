# 📚 Project Documentation Index

## Main Documentation Files

### 🔴 **[PROJECT_REPORT.md](PROJECT_REPORT.md)** - YOUR COMPREHENSIVE PROJECT REPORT
**All-in-one complete documentation including:**
- 🛠️ Technology Stack (Frontend, Backend, AI Providers)
- 🏗️ System Architecture & Data Flow
- 📊 Dataset Information (73,000+ perfumes, 60,000+ cleaned)
- 🔌 Complete API Endpoint Documentation
- 📁 Full Project Structure
- 🚀 Setup & Deployment Instructions
- ✨ Key Features & Performance Metrics
- 🔐 Security & Privacy
- 🎯 Future Roadmap

### 📖 [README.md](README.md)
Quick start guide and project overview

### 🏛️ [Yorvyn Documentation Portal](docs/README.md)
Comprehensive technical architecture, technology library packages, and development standards:
- [Project Structure & Layered Architecture](docs/architecture/project-structure.md)
- [File Migration & Semantic Renaming Map](docs/architecture/file-migration-map.md)
- [File Naming & Code Conventions](docs/development/file-naming-conventions.md)
- [Technology Library Map](docs/architecture/technology-library-map.md)
- [Independent Technology Library Integration Audit](docs/audits/library-integration-audit.md)
- [Third-Party Notices & Attribution](licenses/THIRD_PARTY_NOTICES.md)

---

## Configuration Files

| File | Purpose |
|------|---------|
| `firebase.json` | Firebase Hosting configuration |
| `firestore.rules` | Firestore security rules |
| `render.yaml` | Render deployment config |
| `.firebaserc` | Firebase project settings |
| `runtime.txt` | Python version specification |
| `package.json` | Root npm scripts |

---

## Startup Scripts

| Script | Purpose |
|--------|---------|
| `start.sh` | ✅ Start both frontend & backend (Unix socket) |
| `deploy_ai_upgrade.sh` | Deploy to production |
| `restart_backend.sh` | Restart backend service |

---

## Project Directories

| Directory | Contents |
|-----------|----------|
| `backend/` | FastAPI server with ML engine |
| `frontend/` | React/Vite app |
| `data/` | Raw and processed datasets |
| `models/` | Pre-trained ML models |
| `public/` | Static assets |

---

## 🎯 Quick Start

```bash
# Start development server
npm run dev

# API will be available at http://localhost:5174/docs
# Frontend at http://localhost:5174
```

---

## 📋 What Was Removed

✅ **Deleted 79+ temporary files:**
- Status reports (AI_UPGRADE_*.md, TASK_*.md, etc.)
- Task completion markers
- Intermediate documentation
- Test scripts for development
- Temporary Python files

✅ **Result:** Clean project root with only essential files

---

Generated: May 23, 2026
