# Yorvyn Backend API

FastAPI-based recommendation engine with ML models and AI fallback.

## 🚀 Quick Start

### Local Development

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and add your API keys

# 4. Run server
python run.py
```

Server runs on Unix socket: `backend.sock` (proxied via Vite at http://localhost:5174)

### Production (Render)

See [DEPLOYMENT.md](../DEPLOYMENT.md) for full deployment guide.

## 📁 Project Structure

```
backend/
├── app/
│   ├── api/              # API route handlers
│   │   ├── recommendation_routes.py
│   │   ├── ai_routes.py
│   │   ├── chat_routes.py
│   │   └── recommend_routes.py
│   ├── core/             # Core business logic
│   ├── main.py           # FastAPI app
│   ├── config.py         # Configuration
│   ├── ml_model.py       # ML recommendation engine
│   ├── ai_fallback.py    # AI provider fallback
│   ├── auth.py           # Authentication (if needed)
│   ├── firestore_client.py
│   └── ...
├── tests/                # Test suite
├── .env                  # Environment variables (local)
├── .env.example          # Environment template
├── requirements.txt      # Python dependencies
├── run.py               # Development server
├── Procfile             # Render configuration
└── runtime.txt          # Python version
```

## 🔧 Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# AI Providers (at least one required)
GROQ_API_KEY=your-groq-api-key
GOOGLE_API_KEY=your-google-api-key
OPENROUTER_API_KEY=your-openrouter-api-key

# App Settings
DEBUG=true
APP_NAME=Yorvyn API

# AI Configuration
AI_FALLBACK_ENABLED=true
AI_FALLBACK_CONFIDENCE_THRESHOLD=0.24
AI_MAX_RESPONSE_TOKENS=150
AI_CACHE_TTL=3600
```

### AI Provider Priority

1. **Groq** (Primary) - 14,400 req/day free
2. **OpenRouter** (Secondary) - 200 req/day free
3. **Google Gemini** (Tertiary) - 1,500 req/day free
4. **HuggingFace** (Last Resort) - ~30 req/hr free

AI is only called when ML confidence < 0.24 (token conservation).

## 📡 API Endpoints

### Health & Status

```bash
GET /health
# Returns: { status, dataset_size, models_trained, ai_providers }

GET /
# Returns: API info and version
```

### Recommendations

```bash
POST /api/recommendations
# Body: { query, preferences, filters }
# Returns: Recommended perfumes

GET /api/perfumes/{id}
# Returns: Perfume details

GET /api/stats
# Returns: Dataset statistics
```

### AI Features

```bash
POST /api/ai/chat
# Body: { message, context }
# Returns: AI response

POST /api/ai/shopping-assistant
# Body: { query, preferences }
# Returns: Shopping recommendations
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_ml_model.py

# Run with coverage
pytest --cov=app tests/
```

## 🔍 Development

### Running Locally

```bash
# Standard mode (Unix socket)
python run.py

# HTTP mode (for testing)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### API Documentation

When running locally, visit:
- Swagger UI: http://localhost:5174/docs
- ReDoc: http://localhost:5174/redoc

### Logging

Logs are written to console with format:
```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

Set `DEBUG=true` in `.env` for verbose logging.

## 🚀 Deployment

### Render

1. Push code to GitHub/GitLab
2. Connect repository in Render
3. Render auto-detects `render.yaml`
4. Add environment variables in dashboard
5. Deploy!

Build command:
```bash
cd backend && pip install -r requirements.txt
```

Start command:
```bash
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Environment Variables (Production)

Set these in Render dashboard:
- `GROQ_API_KEY` or `GOOGLE_API_KEY`
- `ENVIRONMENT=production`
- `DEBUG=false`
- `FIREBASE_PROJECT_ID` (if using Firestore)
- `FIREBASE_PRIVATE_KEY` (if using Firestore)
- `FIREBASE_CLIENT_EMAIL` (if using Firestore)

## 📊 ML Model

### Dataset

- **Size**: ~73,000 perfumes
- **Features**: Notes, brand, gender, season, occasion
- **Vectorization**: TF-IDF on combined features

### Training

```bash
# Train model (from project root)
python train_model.py
```

Generates:
- `models/perfume_model.pkl` - Trained model
- `data/encoder.pkl` - Feature encoder

### Model Info

```python
from app.ml_model import recommender

info = recommender.get_model_info()
# Returns: { dataset_size, models_trained, features }
```

## 🔐 Security

### CORS

Production CORS is restricted to:
- `https://yorvyn-ai.web.app`
- `https://yorvyn-ai.firebaseapp.com`

Development allows all origins.

### API Keys

- Never commit `.env` files
- Use environment variables in production
- Rotate keys regularly

### Rate Limiting

Consider adding rate limiting for production:
```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)
```

## 🐛 Troubleshooting

### Import Errors

```bash
# Ensure you're in virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### ML Model Not Loading

```bash
# Check if model files exist
ls -la models/
ls -la data/

# Retrain if needed
python train_model.py
```

### AI Provider Errors

```bash
# Check API keys
python -c "from app.config import settings; settings.log_status()"

# Test specific provider
python -c "from app.ai_fallback import test_groq; test_groq()"
```

## 📚 Dependencies

Key packages:
- **FastAPI**: Web framework
- **Uvicorn**: ASGI server
- **scikit-learn**: ML models
- **pandas**: Data processing
- **google-generativeai**: Gemini AI
- **pydantic**: Data validation

See `requirements.txt` for full list.

## 🔄 Updates

### Adding Dependencies

```bash
# Install new package
pip install package-name

# Update requirements.txt
pip freeze > requirements.txt
```

### Database Migrations

If using SQLAlchemy:
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## 📞 Support

- **Issues**: Check logs in Render dashboard
- **Health**: Monitor `/health` endpoint
- **Docs**: See [DEPLOYMENT.md](../DEPLOYMENT.md)

## 📝 License

See project root for license information.
