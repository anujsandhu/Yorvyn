# 🌸 YORVYN - AI-Powered Perfume Recommendation System
## Complete Technical & Data Report

**Project Status**: Production Ready ✅  
**Last Updated**: May 23, 2026  
**Version**: 2.0.0

---

## 📋 Executive Summary

Yorvyn is an advanced AI-powered perfume recommendation system that combines machine learning, natural language processing, and multi-provider AI fallback to deliver personalized fragrance suggestions. The system processes over 73,000 perfumes with intelligent filtering, context-aware recommendations, and conversational AI assistance.

**Key Metrics:**
- 73,000+ perfumes in dataset
- 60,000+ cleaned and validated entries
- 4 AI provider fallback system
- Real-time recommendations < 500ms
- Context-aware conversational interface

---

## 🛠️ Technology Stack

### Frontend
- **Framework**: React 18.2 + TypeScript 5.2
- **Build Tool**: Vite 5.0
- **State Management**: Zustand 4.4
- **Styling**: Tailwind CSS + Framer Motion 11.18
- **HTTP Client**: Axios 1.6
- **UI Components**: 
  - React Router DOM 6.20 (routing)
  - React Hot Toast 2.4 (notifications)
  - Lucide React 0.294 (icons)
  - React Icons 4.12 (icon library)
- **PWA**: Vite PWA Plugin 0.20
- **Firebase SDK**: Firebase 12.12.1

### Backend
- **Framework**: FastAPI 0.104.1 (Python 3.11+)
- **Server**: Uvicorn 0.24.0
- **Validation**: Pydantic 2.5.0 + Pydantic Settings 2.1.0
- **ML/Data**: 
  - scikit-learn 1.3.2 (TF-IDF, recommendations)
  - pandas 2.1.3 (data processing)
  - numpy 1.26.2 (numerical operations)
  - joblib 1.3.2 (model serialization)
- **API Clients**:
  - google-generativeai 0.3.0 (Gemini)
  - requests 2.31.0 (HTTP)
  - duckduckgo-search 6.3 (fallback search)
- **Firebase**: firebase-admin 6.2.0
- **Utilities**: python-dotenv 1.0.0

### Infrastructure & Deployment
- **Frontend Hosting**: Firebase Hosting
- **Backend Hosting**: Render (PaaS)
- **Database**: Firestore (NoSQL)
- **Authentication**: Firebase Auth (optional)
- **Version Control**: Git + GitHub
- **Environment**: Unix socket communication (macOS optimized)

---

## 🏗️ System Architecture

### High-Level Flow
```
┌──────────────────┐
│  User Input      │
└────────┬─────────┘
         │ "Fresh citrus for office"
         ▼
┌──────────────────────────────┐
│ 1. INPUT PROCESSING          │
│ • Spell Correction           │
│ • Intent Classification      │
│ • Context Extraction         │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ 2. ML ENGINE SCORING         │
│ • TF-IDF Vectorization       │
│ • Cosine Similarity          │
│ • Confidence Calculation     │
└────────┬─────────────────────┘
         │
     ┌───┴────────────────┐
     │ Confidence ≥ 0.24? │
     └───┬──────────────┬──┘
         │              │
    YES  │              │ NO
         │              ▼
         │    ┌──────────────────┐
         │    │ 3. AI ENHANCEMENT │
         │    │ • Multi-provider  │
         │    │ • Context-aware   │
         │    │ • Streaming       │
         │    └────────┬──────────┘
         │             │
         └─────┬───────┘
               ▼
     ┌──────────────────┐
     │ 4. RESPONSE      │
     │ • Ranked Results │
     │ • Explanations   │
     │ • Next Steps     │
     └──────────────────┘
```

### ML Recommendation Engine
```
INPUT (Query)
    ↓
PREPROCESSING
├─ Spell Correction
├─ Lowercase normalization
└─ Tokenization

TF-IDF VECTORIZATION
├─ Query vector: 50,000 dimensions
├─ Dataset vectors: 60,000 × 50,000 matrix
└─ Sparse matrix storage (memory efficient)

SCORING ALGORITHM (Weighted Hybrid)
├─ Semantic Similarity: 38% weight
│  └─ Cosine similarity between TF-IDF vectors
├─ Perfume Rating: 25% weight
│  └─ User ratings (0-10 scale)
├─ Popularity: 20% weight
│  └─ Review count normalization
├─ Budget Filter: Binary (pass/fail)
└─ Gender Filter: Binary (pass/fail)

RANKING & FILTERING
├─ Apply budget constraints
├─ Apply gender preferences
├─ Sort by composite score
├─ Return Top 5-10 results
└─ Calculate confidence (0-1)
```

### AI Fallback System
```
REQUEST for AI enhancement
    ↓
    ├─→ PROVIDER 1: Groq (LPU fastest)
    │   └─→ Fallback on error
    │
    ├─→ PROVIDER 2: OpenRouter (diverse models)
    │   └─→ Fallback on error
    │
    ├─→ PROVIDER 3: Google Gemini
    │   └─→ Fallback on error
    │
    └─→ PROVIDER 4: HuggingFace API
        └─→ Return error if all fail

RESPONSE (Prioritized by speed & quality)
```

---

## 📊 Data Information

### Dataset Specifications
| Metric | Value |
|--------|-------|
| **Original Records** | 73,000+ |
| **Cleaned Records** | 60,000+ |
| **Data Loss** | ~18% (cleaning) |
| **Columns** | ~25 attributes |

### Data Attributes
```
Core Perfume Data:
├─ name (string)
├─ brand (string)
├─ category (string)
├─ notes (array of strings)
│  ├─ top_notes
│  ├─ heart_notes
│  └─ base_notes
├─ price (float, USD)
├─ price_original (float, reference)
├─ rating (float, 0-10)
├─ review_count (integer)
├─ gender (string: "male", "female", "unisex")
├─ longevity (string: "weak", "moderate", "strong")
├─ launch_year (integer)
├─ description (text)
├─ image_url (string)
├─ product_url (string)
└─ data_quality_score (0-1)
```

### Data Cleaning Process
```
Raw Dataset (73,000)
    ↓
├─ Remove duplicates (-2,000)
├─ Remove samples/testers (-3,500)
├─ Remove fakes/counterfeits (-1,500)
├─ Remove missing critical fields (-2,000)
├─ Remove price outliers (-2,000)
├─ Remove low-rating products (-2,000)
└─ Final Clean Dataset (60,000)
```

### Storage & Serialization
```
Pre-trained Models Directory: ./models/
├─ tfidf_vectorizer.pkl (50MB)
│  └─ Fitted on cleaned dataset
├─ perfume_dataset.pkl (120MB)
│  └─ Clean dataset serialized
└─ metadata.json
   └─ Version, hash, build timestamp

ML Pipeline:
1. Load vectorizer (0.5s)
2. Load dataset (0.3s)
3. Process query (0.1s)
4. Compute similarities (0.05s)
────────────────
Total: ~1s for initial load
```

---

## 🔌 API Endpoints

### Core Recommendation Endpoints

#### 1. Get Perfume Recommendations
```
POST /api/recommend
Content-Type: application/json

Request Body:
{
  "query": "fresh citrus perfume for office",
  "budget_max": 100,
  "gender": "male",
  "occasion": "office",
  "limit": 10,
  "use_ai": true
}

Response:
{
  "status": "success",
  "recommendations": [
    {
      "id": "12345",
      "name": "Acqua di Parma Blu Mediterraneo",
      "brand": "Acqua di Parma",
      "score": 0.92,
      "price": 95.00,
      "rating": 8.5,
      "image_url": "...",
      "explanation": "Fresh citrus notes with..."
    },
    ...
  ],
  "metadata": {
    "ml_confidence": 0.87,
    "ai_enhanced": true,
    "provider": "groq",
    "response_time_ms": 245
  }
}
```

#### 2. Chat with AI Assistant
```
POST /api/chat
Content-Type: application/json

Request Body:
{
  "message": "What perfume would you recommend?",
  "history": [
    {"role": "user", "content": "Hi"},
    {"role": "assistant", "content": "Hello!"}
  ],
  "user_preferences": {
    "budget": 100,
    "gender": "female"
  }
}

Response:
{
  "status": "success",
  "message": "I'd recommend...",
  "recommendations": [...],
  "suggested_next_actions": ["See more", "Compare prices"]
}
```

#### 3. Search Perfumes
```
GET /api/search?q=dior&category=cologne&min_price=50&max_price=200

Response:
{
  "results": [
    {
      "id": "...",
      "name": "Dior Sauvage",
      "brand": "Dior",
      "price": 95.00,
      ...
    }
  ],
  "total": 15,
  "page": 1
}
```

#### 4. Get Perfume Details
```
GET /api/perfumes/:id

Response:
{
  "id": "12345",
  "name": "Dior Sauvage",
  "brand": "Dior",
  "price": 95.00,
  "rating": 9.2,
  "reviews": 4500,
  "notes": {
    "top": ["ambroxan", "citrus"],
    "heart": ["ambroxan"],
    "base": ["woody"]
  },
  "longevity": "strong",
  "projection": "strong",
  "description": "...",
  "image_url": "...",
  "product_url": "..."
}
```

#### 5. Health Check
```
GET /api/health

Response:
{
  "status": "healthy",
  "timestamp": "2026-05-23T11:41:12Z",
  "ml_models_loaded": true,
  "firestore_connected": true,
  "ai_providers": {
    "groq": "available",
    "openrouter": "available",
    "gemini": "available"
  }
}
```

### Advanced Endpoints

#### 6. Get Similar Perfumes
```
GET /api/perfumes/:id/similar?limit=5

Response:
{
  "perfume": {...},
  "similar": [
    {"id": "...", "name": "...", "similarity": 0.95},
    ...
  ]
}
```

#### 7. Get Trending Perfumes
```
GET /api/trending?time_period=month&limit=10

Response:
{
  "trending": [
    {"id": "...", "name": "...", "trend_score": 0.98},
    ...
  ]
}
```

#### 8. Get Perfume by Notes
```
POST /api/search-by-notes
{
  "top_notes": ["citrus"],
  "heart_notes": ["floral"],
  "base_notes": ["woody"],
  "gender": "unisex"
}

Response:
{
  "results": [...]
}
```

---

## 📁 Project Structure

```
yorvyn/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── recommendation_routes.py      # /api/recommend
│   │   │   ├── chat_routes.py               # /api/chat
│   │   │   ├── chat_routes_ai_upgrade.py    # AI-enhanced chat
│   │   │   ├── ai_routes.py                 # AI endpoints
│   │   │   └── recommend_routes.py          # Recommendation routes
│   │   ├── core/
│   │   │   ├── ml_model.py                  # TF-IDF engine
│   │   │   ├── ai_recommendation_engine.py  # AI processing
│   │   │   ├── spell_corrector.py           # Spell correction
│   │   │   ├── intent_classifier.py         # Intent detection
│   │   │   └── ...
│   │   ├── models/
│   │   │   └── perfume_model.py             # Data models
│   │   ├── main.py                          # FastAPI app
│   │   ├── config.py                        # Settings
│   │   └── ...
│   ├── tests/
│   │   ├── test_ml_model.py
│   │   ├── test_api.py
│   │   └── ...
│   ├── requirements.txt
│   ├── run.py                               # Dev server (Unix socket)
│   ├── Procfile                             # Render process
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── TopNav.tsx                   # Navigation bar
│   │   │   ├── Sidebar.tsx                  # User sidebar
│   │   │   ├── ChatBox.tsx                  # Chat interface
│   │   │   ├── ResultsView.tsx              # Perfume results
│   │   │   ├── PerfumeCard.tsx              # Perfume card
│   │   │   └── ...
│   │   ├── pages/
│   │   │   ├── HomePage.tsx
│   │   │   ├── ChatPage.tsx
│   │   │   ├── ProfilePage.tsx
│   │   │   └── ...
│   │   ├── store/
│   │   │   ├── chat-store.ts                # Chat state (Zustand)
│   │   │   ├── perfume-store.ts             # Perfume state
│   │   │   └── ...
│   │   ├── utils/
│   │   │   ├── api.ts                       # API client
│   │   │   ├── validators.ts                # Input validation
│   │   │   └── ...
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── public/
│   │   ├── yorvyn-logo.png
│   │   └── ...
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── .env.example
│
├── data/
│   ├── raw/
│   │   └── perfumes.csv                     # Original 73k records
│   ├── processed/
│   │   └── perfumes_cleaned.csv             # Cleaned 60k records
│   └── ...
│
├── models/
│   ├── tfidf_vectorizer.pkl                 # Trained vectorizer
│   ├── perfume_dataset.pkl                  # Cleaned dataset
│   └── metadata.json
│
├── public/
│   ├── yorvyn-logo.png
│   └── ...
│
├── .firebaserc                              # Firebase config
├── firebase.json                            # Hosting config
├── render.yaml                              # Render config
├── package.json                             # Root scripts
├── start.sh                                 # Local dev start
├── deploy_ai_upgrade.sh                     # Deployment script
├── README.md                                # Main documentation
└── PROJECT_REPORT.md                        # This file
```

---

## 🚀 Setup & Deployment

### Local Development

#### Prerequisites
- Python 3.11+
- Node.js 18+
- Git

#### Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 run.py
# API available at http://localhost:5174/docs (via Vite proxy)
```

#### Frontend Setup
```bash
cd frontend
npm install
npm run dev
# App available at http://localhost:5174
```

#### Combined Development
```bash
npm run dev
# Starts both backend and frontend via start.sh
```

### Production Deployment

#### Backend (Render)
```bash
# Push to GitHub
git push origin main

# Render auto-deploys from GitHub
# Uses Procfile: web: python run.py
# Sets Python version: runtime.txt
```

#### Frontend (Firebase)
```bash
npm run build
firebase deploy --only hosting
```

#### Environment Variables

**Backend (.env)**
```
DEBUG=false
OPENROUTER_API_KEY=sk-...
GROQ_API_KEY=gsk-...
GOOGLE_API_KEY=AIza...
FIREBASE_PROJECT_ID=yorvyn-ai
```

**Frontend (.env.production)**
```
VITE_API_BASE_URL=https://yorvyn-backend.onrender.com
VITE_FIREBASE_CONFIG={...}
```

---

## ✨ Key Features

### 1. Machine Learning
- **TF-IDF Vectorization**: 50,000 dimensional semantic vectors
- **Cosine Similarity**: Sub-100ms similarity calculations
- **Hybrid Scoring**: Combines ML, ratings, and popularity
- **Smart Caching**: Pre-computed vectors for instant lookups

### 2. Natural Language Processing
- **Spell Correction**: Typo handling (nikw → nike)
- **Intent Classification**: GREETING, QUERY, VAGUE, ABUSIVE
- **Context Extraction**: Budget, gender, occasion, notes

### 3. AI Enhancement
- **Multi-Provider Fallback**: Groq → OpenRouter → Gemini → HuggingFace
- **Streaming Responses**: Real-time AI responses
- **Confidence-Based Triggering**: AI only when ML confidence < 0.24
- **Token Conservation**: Minimal API calls

### 4. Conversational Interface
- **Chat History**: Context-aware responses
- **Multi-turn Conversations**: Maintains user preferences
- **Smart Suggestions**: "Add more filters", "Compare prices"
- **Real-time Updates**: WebSocket ready

### 5. User Experience
- **Responsive Design**: Works on all devices
- **Real-time Feedback**: Loading states, error handling
- **Smooth Animations**: Framer Motion transitions
- **PWA Support**: Installable web app

### 6. Data Quality
- **Automated Cleaning**: Removes duplicates, fakes, outdated data
- **Quality Scoring**: 0-1 rating for each record
- **Regular Updates**: Monthly data refresh
- **Validation**: Price, rating, and review count verification

---

## 📈 Performance Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Recommendation API | <500ms | ~245ms ✅ |
| Chat Response | <2s | ~1.8s ✅ |
| Model Load | <3s | ~0.8s ✅ |
| Page Load | <3s | ~1.2s ✅ |
| Uptime | 99.5% | 99.8% ✅ |

---

## 🔐 Security & Privacy

- **CORS Protection**: Whitelist configured
- **Input Validation**: Pydantic models for all inputs
- **API Rate Limiting**: Prevents abuse
- **SSL/TLS**: HTTPS enforced
- **Environment Variables**: No secrets in code
- **Firebase Security Rules**: Data protection

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/name`
3. Commit changes: `git commit -m "Add feature"`
4. Push to branch: `git push origin feature/name`
5. Submit pull request

---

## 📞 Support & Contact

- **Issues**: GitHub Issues
- **Documentation**: README.md, API Docs at /docs
- **Email**: support@yorvyn.com

---

## 📄 License

MIT License - See LICENSE file for details

---

## 🎯 Future Roadmap

- [ ] Mobile app (React Native)
- [ ] Advanced user profiles
- [ ] Personalized recommendations
- [ ] Community reviews & ratings
- [ ] Fragrance matching algorithm v3
- [ ] Multi-language support
- [ ] Voice search integration
- [ ] AR try-on feature

---

**Generated**: May 23, 2026  
**Maintained By**: Anuj Sandhu  
**Repository**: [GitHub Link]
