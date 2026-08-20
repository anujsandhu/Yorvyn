# 🌸 Yorvyn - AI-Powered Perfume Recommendation System

**Advanced Machine Learning & AI-Powered Fragrance Recommendations**

[![Deploy Backend](https://img.shields.io/badge/Deploy-Render-46E3B7?logo=render)](https://render.com)
[![Deploy Frontend](https://img.shields.io/badge/Deploy-Firebase-FFCA28?logo=firebase)](https://firebase.google.com)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)](https://python.org)
[![React](https://img.shields.io/badge/React-18.2-61DAFB?logo=react)](https://react.dev)

---

## 🚀 Live Demo

- **Frontend**: [https://yorvyn-ai.web.app](https://yorvyn-ai.web.app)
- **Backend API**: [https://yorvyn-backend.onrender.com](https://yorvyn-backend.onrender.com)
- **API Docs**: [https://yorvyn-backend.onrender.com/docs](https://yorvyn-backend.onrender.com/docs)

---

## ✨ Features

### 🤖 Machine Learning Engine
- **73,000+ perfumes** in dataset
- **TF-IDF vectorization** for semantic matching
- **Real-time recommendations** based on preferences
- **Hybrid scoring system**: ML + ratings + popularity

### 🧠 AI-Powered Intelligence
- **Multi-provider fallback**: Groq → OpenRouter → Gemini → HuggingFace
- **Natural language understanding** for user queries
- **Smart shopping assistant** with personalized suggestions
- **Token conservation**: AI only called when ML confidence < 0.24

### 💬 Interactive Chat
- **Conversational interface** for perfume discovery
- **Context-aware responses** using chat history
- **Personalized recommendations** based on conversation

### 🎨 Modern UI/UX
- **React + TypeScript** frontend
- **Responsive design** for all devices
- **Smooth animations** with Framer Motion
- **Real-time updates** with Zustand state management

### 🔐 Firebase Integration
- **Authentication** (optional)
- **Firestore** for user preferences
- **Hosting** on Firebase CDN

---

## 📊 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User Browser                             │
│              https://yorvyn-ai.web.app                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ HTTPS
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Firebase Hosting (Frontend)                     │
│         React + Vite + TypeScript + Zustand                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ REST API
                     ▼
┌─────────────────────────────────────────────────────────────┐
│           Render (Backend API)                               │
│    FastAPI + Python + scikit-learn + AI Providers            │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  ML Engine   │  │ AI Fallback  │  │  Firestore   │     │
│  │  (73K data)  │  │ (4 providers)│  │   Client     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** for backend
- **Node.js 18+** for frontend
- **Firebase CLI** for deployment
- **Git** for version control

### Local Development

#### 1. Clone Repository
```bash
git clone <your-repo-url>
cd yorvyn
```

#### 2. Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your API keys

# Run backend
python run.py
```

Backend runs on Unix socket (proxied via Vite).

#### 3. Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

Frontend runs at: **http://localhost:5174**

#### 4. Quick Start Script
```bash
# From project root
./start.sh  # macOS/Linux
start.bat   # Windows
```

---

## 📁 Project Structure

```
yorvyn/
├── backend/                    # Python FastAPI Backend
│   ├── app/                   # Application code
│   │   ├── api/              # API routes
│   │   ├── main.py           # FastAPI app
│   │   ├── ml_model.py       # ML engine
│   │   └── config.py         # Configuration
│   ├── requirements.txt      # Python dependencies
│   ├── Procfile             # Render config
│   └── runtime.txt          # Python version
│
├── frontend/                  # React Frontend
│   ├── src/                  # Source code
│   │   ├── components/      # React components
│   │   ├── pages/           # Page components
│   │   ├── context/         # Context providers
│   │   └── App.tsx          # Main app
│   ├── package.json         # Node dependencies
│   └── vite.config.ts       # Vite config
│
├── data/                     # ML training data
├── models/                   # Trained models
├── docs/                     # Documentation
│
├── render.yaml              # Render deployment
├── firebase.json            # Firebase hosting
├── DEPLOYMENT.md            # Deployment guide
└── README.md                # This file
```

See [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) for detailed structure.

---

## 🚀 Deployment

### Backend → Render

1. **Push to GitHub**
2. **Connect to Render**
3. **Add environment variables**
4. **Deploy automatically**

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed instructions.

### Frontend → Firebase

```bash
cd frontend
npm run build:prod
firebase deploy --only hosting
```

See [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md) for step-by-step guide.

---

## 🔧 Configuration

### Backend Environment Variables

```bash
# AI Providers (at least one required)
GROQ_API_KEY=your-groq-api-key
GOOGLE_API_KEY=your-google-api-key
OPENROUTER_API_KEY=your-openrouter-api-key

# App Settings
DEBUG=false
ENVIRONMENT=production

# AI Configuration
AI_FALLBACK_ENABLED=true
AI_FALLBACK_CONFIDENCE_THRESHOLD=0.24
AI_MAX_RESPONSE_TOKENS=150
```

### Frontend Environment Variables

```bash
# Development
VITE_API_URL=/api

# Production
VITE_API_URL=https://yorvyn-backend.onrender.com
```

---

## 📡 API Endpoints

### Health & Status
```bash
GET /health
GET /
```

### Recommendations
```bash
POST /api/recommendations
GET /api/perfumes/{id}
GET /api/stats
```

### AI Features
```bash
POST /api/ai/chat
POST /api/ai/shopping-assistant
POST /api/recommend
```

See API documentation at: `/docs` (Swagger UI)

---

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest
```

### Frontend Tests
```bash
cd frontend
npm test
```

---

## 📊 Dataset Statistics

| Metric | Value |
|--------|-------|
| **Total Perfumes** | 73,000+ |
| **Unique Brands** | 600+ |
| **Features** | TF-IDF vectorized |
| **ML Model** | scikit-learn |

---

## 🎯 How It Works

1. **User Input**: Select preferences or chat naturally
2. **ML Processing**: TF-IDF vectorization + similarity matching
3. **AI Fallback**: If confidence < 0.24, AI providers enhance results
4. **Hybrid Scoring**: Combine ML + ratings + popularity
5. **Results**: Top recommendations with explanations

---

## 🌟 Key Technologies

### Backend
- **FastAPI**: Modern Python web framework
- **scikit-learn**: ML models
- **pandas/numpy**: Data processing
- **Uvicorn**: ASGI server
- **Google Gemini**: AI provider

### Frontend
- **React 18**: UI framework
- **TypeScript**: Type safety
- **Vite**: Build tool
- **Zustand**: State management
- **React Router**: Navigation
- **Framer Motion**: Animations
- **Firebase**: Hosting & auth

---

## 📚 Documentation

- **[DEPLOYMENT.md](./DEPLOYMENT.md)** - Complete deployment guide
- **[DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md)** - Step-by-step checklist
- **[PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md)** - Project organization
- **[backend/README.md](./backend/README.md)** - Backend documentation

---

## 🐛 Troubleshooting

### Backend Issues
- Check Render logs
- Verify environment variables
- Test health endpoint: `/health`

### Frontend Issues
- Check browser console
- Verify API URL in `.env.production`
- Test API connectivity

### Common Issues
- **502 Bad Gateway**: Backend is starting (wait 1-2 min)
- **CORS errors**: Check backend CORS configuration
- **Slow first request**: Render free tier cold start

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed troubleshooting.

---

## 🤝 Contributing

Contributions welcome! Areas for enhancement:

- [ ] Additional AI providers
- [ ] User authentication
- [ ] Wishlist functionality
- [ ] Review system
- [ ] Mobile app
- [ ] Real-time price tracking
- [ ] Multi-language support

---

## 📄 License

**MIT License** - Feel free to use for personal or commercial projects

---

## 👨‍💻 Author

**Your Name**
- GitHub: [@yourusername](https://github.com/yourusername)
- Repository: [yorvyn](https://github.com/yourusername/yorvyn)

---

## 🙏 Acknowledgments

- Google Generative AI for Gemini API
- Groq for fast inference
- OpenRouter for model access
- Firebase for hosting
- Render for backend hosting
- scikit-learn for ML tools
- React community

---

## 📞 Support

- **Documentation**: See `/docs` folder
- **Issues**: Create GitHub issue
- **Deployment Help**: See [DEPLOYMENT.md](./DEPLOYMENT.md)
- **API Docs**: Visit `/docs` endpoint

---

## 🔄 Version History

- **v2.0** - React frontend + FastAPI backend
- **v1.0** - Initial Streamlit version

---

**🎉 Discover your perfect fragrance with AI! 🌸**

---

*Last Updated: May 1, 2026 | Version 2.0 - Production Ready*
