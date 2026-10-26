# Yorvyn AI Stylist, Voice, Text, and Dataset Integration Plan

## 1. Baseline Audit & Current State Analysis

| Component | Current State | Target State | Implementation Strategy |
| :--- | :--- | :--- | :--- |
| **Stylist Chat UI** | Text input with static submit button; synchronous response rendering; no audio controls. | Full dual-mode (Text & Voice) interface with live mic waveform, streaming tokens, stop button, and photo understanding. | Extend `StylistChat.tsx` with Web Speech API + backend audio fallback, audio player, photo upload, and SSE streaming. |
| **Stylist LLM Engine** | Hardcoded text generation (`self._synthesize_editorial_rationale`) with rule strings. | Multi-provider AI stylist engine (Groq, OpenRouter, Gemini, OpenAI) with structured Pydantic schemas and deterministic fallback for offline/CI. | Implement `backend/app/services/ai_stylist_engine.py` integrated into `fashion_orchestrator.py`. |
| **Voice & Speech** | None. No audio endpoints or speech recognition in app. | Speech-to-Text (STT) and Text-to-Speech (TTS) pipeline with browser native speech integration and backend API endpoints. | Add `backend/app/api/speech_routes.py` with `/transcribe` and `/synthesize`. |
| **Dataset Integration** | Static JSON taxonomy only (`data/taxonomy/fashion_taxonomy.json`). No real dataset files or ML evaluation. | Acquired real fashion dataset (Fashion-MNIST, 70,000 real Zalando product items) with SHA-256 verification, dataset registry, and license audit. | Script `scripts/acquire_fashion_dataset.py`, create `research/datasets/manifest.json` and `registry.md`. |
| **Fashion ML Pipeline** | No functional training or evaluation script. | Functional ML pipeline: dataset loader, feature extraction, multiclass classification, metrics reporting (Accuracy, Precision, Recall, F1), and saved model checkpoint. | Implement `backend/app/services/ml/fashion_classifier.py`. |
| **3D Avatar & Try-On Link** | Outfit cards have "Wear Today" and "Save", but no direct link to try on garments on 3D avatar. | "Try on 3D Avatar" action button on outfit cards that routes to `AvatarStudio` with recommended garments pre-selected. | Connect outfit items to wardrobe IDs and avatar dressing state. |

---

## 2. Dataset Licensing & Legal Compliance Matrix

| Dataset | Official Source & Custodian | Access Method | License / Restrictions | Yorvyn Status |
| :--- | :--- | :--- | :--- | :--- |
| **Fashion-MNIST** | Zalando Research (`zalandoresearch/fashion-mnist`) | Official GitHub & Hugging Face mirror | **MIT License** (Permissive commercial & non-commercial use). 70,000 images, 10 categories. | **APPROVED & ACQUIRED**: Integrated into active ML evaluation pipeline. |
| **DeepFashion** | CUHK Multimedia Lab (MMLab) | Google Drive / Baidu Wangpan form | **Non-Commercial Research Only**: Requires signed form sent to CUHK; commercial use strictly prohibited. | **BLOCKED BY ACCESS/LICENSE**: Registered in catalog; gated until commercial authorization. |
| **DeepFashion2** | switchablenorms / DeepFashion2 | Google Drive / Baidu Wangpan form | **Non-Commercial Research Only**: Requires agreement form. | **BLOCKED BY ACCESS/LICENSE**: Registered in catalog; gated until commercial authorization. |
| **Fashionpedia** | Fashionpedia consortium | Official AWS / Google Cloud repository | **Annotations: CC BY 4.0**; Images: Fair research use. | **ANNOTATED**: Registered in catalog for future segmentation fine-tuning. |

---

## 3. Implementation Milestones

1. **Backend AI Stylist & Multi-Provider Engine**:
   - `backend/app/services/ai_stylist_engine.py`
   - `backend/app/api/fashion_routes.py` (Streaming SSE `/chat/stream`)
2. **Backend Speech Services**:
   - `backend/app/api/speech_routes.py` (Audio transcription & speech synthesis)
3. **Frontend Voice & Text Chat Experience**:
   - `frontend/src/pages/StylistChat.tsx` + `StylistChat.css`
   - `frontend/src/services/fashionApi.ts`
4. **Real Dataset Acquisition**:
   - `scripts/acquire_fashion_dataset.py`
   - `research/datasets/registry.md` & `research/datasets/manifest.json`
   - `docs/architecture/dataset-pipeline.md` & `docs/architecture/model-licensing.md`
5. **Real Fashion ML Classification & Evaluation**:
   - `backend/app/services/ml/fashion_classifier.py`
6. **Automated Test Suite & Verification**:
   - `backend/tests/test_ai_stylist.py`
   - `backend/tests/test_speech.py`
   - `backend/tests/test_fashion_ml.py`
   - End-to-end frontend build, packages tests, and backend 3D pipeline tests.
