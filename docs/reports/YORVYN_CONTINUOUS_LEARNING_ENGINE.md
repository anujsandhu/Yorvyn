# YORVYN — CONTINUOUS AI LEARNING & PERSONALIZATION ENGINE
## Architectural Specification, Engineering Implementation & Production Validation Report

**Date:** 2026-11-07  
**Role:** Principal AI/ML Architect, Machine Learning Engineer, Data Engineer, Supabase Security Engineer, Full-Stack Engineer  
**Status:** **COMPLETE & VALIDATED (20/20 Automated Tests Passing, 100% Frontend Build Verification)**  

---

## 1. Executive Summary

The Yorvyn Continuous AI Learning & Personalization Engine has been implemented to systematically improve fashion intelligence, garment reconstruction, and virtual try-on recommendations without resorting to naive online model retraining. The architecture strictly enforces data privacy, multi-tenant isolation, dataset sanitation, and rigorous model evaluation gates.

### Core Architectural Principles
1. **No Naive Online Retraining:** Production neural model weights are never updated directly from raw user messages or single feedback clicks.
2. **Three-Tier Learning Decoupling:**
   - **Layer A (User Personalization Memory):** User-specific preference memory that adapts to fit, style, color, fabric, brand, and occasion preferences with confidence scores and evidence counts.
   - **Layer B (Global Model Improvement):** Offline, asynchronous dataset compilation from permissioned, sanitized, and poisoning-guarded interactions to fine-tune shared AI models on remote GPU infrastructure.
   - **Layer C (Session Context Learning):** Isolated multi-turn conversational context retained per persistent AI session without cross-session or cross-tenant leakage.
3. **Granular Server-Side Consent:** Global model training, image training, and conversation training each require independent opt-in consent. Disabling global training never disables ordinary styling features or user-requested personalization.
4. **Poisoning & Abuse Resistance:** Submissions with contradictory labels, injection payloads, or high-velocity bursts are automatically isolated into quarantine. Original predictions and proposed corrections are persisted separately.
5. **Quality Gates & Rollback:** Candidate models are benchmarked against baseline production models on held-out test splits. Regressions are automatically rejected, and one-click rollback ensures zero-downtime recovery.

---

## 2. Multi-Layer Learning Architecture

```mermaid
flowchart TD
    subgraph UserInteraction["User Interaction & Experience Tier"]
        UI["Yorvyn Web & Studio UI / StylistChat"]
        FB["Feedback Controls (Thumbs, Corrections, Outfit Actions)"]
        UI --> FB
    end

    subgraph LayerA["Layer A: User Personalization Memory"]
        UP["yorvyn_user_preferences (RLS auth.uid() = user_id)"]
        CONF["Confidence Accumulator & Evidence Counter"]
        CTX["Dynamic Context Builder (Injected into Stylist Prompts)"]
        FB -->|Explicit / Behavioral| UP
        UP --> CONF --> CTX
    end

    subgraph LayerB["Layer B: Global Model Improvement (Sanitized Offline)"]
        CONSENT{"Consent Check\n(global_model_training_enabled?)"}
        SCRUB["PII & Token Scrubber\n(Bearer, Email, Secret Redaction)"]
        POISON{"Poisoning & Spam Defense\n(Contradictions, Syntax, Velocity)"}
        EX["yorvyn_learning_examples\n(Validated & Versioned Dataset)"]
        REMOTE["Remote GPU Worker Queue\n(NVIDIA A100 Training Jobs)"]
        EVAL{"Held-Out Benchmark Gate\n(Accuracy, Chamfer, NDCG)"}
        REG["yorvyn_model_registry\n(Versioned Artifacts & Rollback)"]

        FB --> CONSENT
        CONSENT -->|Opt-In Granted| SCRUB
        CONSENT -->|Consent Disabled| EXCLUDE["Excluded from Global Pool\n(Personalization Only)"]
        SCRUB --> POISON
        POISON -->|Valid| EX
        POISON -->|Suspicious| QUAR["Quarantined / Rejected"]
        EX --> REMOTE --> EVAL
        EVAL -->|Meets Threshold| REG
        EVAL -->|Regression Detected| REJ["Candidate Rejected"]
    end

    subgraph LayerC["Layer C: Session Context Learning"]
        SESS["Persistent AI Session (010 Schema)"]
        SUMM["Automatic Context Window Summarizer"]
        SESS --> SUMM --> CTX
    end
```

---

## 3. Database Schema Implementation

The continuous learning infrastructure is defined in `backend/migrations/011_continuous_learning_and_personalization.sql`:

### 1. `yorvyn_user_preferences`
- **Columns:** `id`, `user_id`, `preference_category`, `preference_key`, `preference_value`, `source`, `confidence`, `evidence_count`, `status`, `last_confirmed_at`, `created_at`, `updated_at`.
- **Constraint:** Unique index on `(user_id, preference_category, preference_key)`.
- **Row-Level Security:** Strict isolation ensuring `auth.uid() = user_id` for SELECT, INSERT, UPDATE, and DELETE.

### 2. `yorvyn_ai_feedback`
- **Columns:** `id`, `user_id`, `session_id`, `message_id`, `search_id`, `feedback_type`, `rating`, `original_output`, `corrected_output`, `feedback_text`, `metadata`, `consent_snapshot`, `created_at`.
- **Feedback Types Supported:** `positive`, `negative`, `correction`, `preference`, `accepted_recommendation`, `rejected_recommendation`, `edited_result`, `confirmed_result`, `reported_error`.

### 3. `yorvyn_learning_examples`
- **Columns:** `id`, `source_feedback_id`, `task_type`, `input_reference`, `target_output`, `quality_score`, `validation_status`, `consent_scope`, `dataset_version`, `exclusion_reason`, `created_at`, `validated_at`.
- **Validation Statuses:** `pending`, `validated`, `rejected`, `quarantined`.

### 4. `yorvyn_model_registry`
- **Columns:** `id`, `model_name`, `model_version`, `task_type`, `artifact_uri`, `artifact_checksum`, `base_model`, `training_dataset_version`, `evaluation_metrics`, `status`, `deployed_at`, `created_at`.
- **Statuses Supported:** `candidate`, `training`, `evaluation`, `approved`, `deployed`, `rejected`, `archived`.

### 5. `yorvyn_training_jobs`
- **Columns:** `id`, `model_name`, `task_type`, `dataset_version`, `status`, `training_config`, `evaluation_results`, `resource_usage`, `failure_reason`, `started_at`, `completed_at`, `created_at`.
- **Statuses Supported:** `queued`, `running`, `validating`, `completed`, `failed`, `cancelled`.

### 6. `yorvyn_learning_consent`
- **Columns:** `id`, `user_id`, `personalization_enabled`, `global_model_training_enabled`, `image_training_enabled`, `conversation_training_enabled`, `consent_version`, `consent_updated_at`.
- **Privacy Defaults:** `personalization_enabled = true`, `global_model_training_enabled = false`, `image_training_enabled = false`, `conversation_training_enabled = false`.

---

## 4. Software Service Architecture

### 1. `PersonalizationService` (`backend/app/services/learning/personalization_service.py`)
- Provides Layer A preference memory and bayesian-style confidence accumulation.
- Distinguishes explicit user inputs (`confidence = 0.90+`), behavioral selections (`confidence = 0.60+`), and corrections (`confidence = 0.95+`).
- Implements `build_personalized_context(user_id, session_id)`:
  - Dynamically synthesizes validated preferences into structured prompt context.
  - Automatically respects user consent: if `personalization_enabled = false`, returns zero personalization context.
  - Injects into `PersistentSessionService.assemble_session_prompt_context`.

### 2. `FeedbackPipeline` (`backend/app/services/learning/feedback_pipeline.py`)
- Orchestrates intake, sanitation, and defense:
  1. Verifies server-side consent.
  2. Scrubs Bearer tokens, JWTs, secrets, emails, and phone numbers.
  3. Detects high-velocity spam bursts (>10 requests/min).
  4. Detects contradictory corrections (e.g. proposed correction identical to original prediction).
  5. Validates label syntax and guards against XSS and injection patterns.
  6. Filters duplicate training examples using SHA-256 content hashing.
  7. Tags eligible examples with dataset versions (e.g., `v1.2_continuous`).

### 3. `ModelTrainingService` (`backend/app/services/learning/model_training_service.py`)
- Manages offline training job scheduling, held-out benchmark evaluations, and regression gates:
  - Verifies minimum example thresholds before triggering runs.
  - Evaluates candidate models against held-out test splits.
  - Enforces automatic quality gates (e.g. accuracy drop or Chamfer distance degradation blocks deployment).
  - Provides atomic, zero-downtime rollback controls (`rollback_model`).

---

## 5. API Endpoints Reference

The FastAPI router is mounted at `/api/learning`:

| Endpoint | Method | Authorization | Description |
| :--- | :---: | :---: | :--- |
| `/api/learning/preferences` | `GET` | Authenticated User | Retrieves active personalized style preferences |
| `/api/learning/preferences` | `POST` | Authenticated User | Explicitly creates/reinforces a preference |
| `/api/learning/preferences/{id}` | `PATCH` | Authenticated User | Edits/updates a specific preference record |
| `/api/learning/preferences/{id}` | `DELETE` | Authenticated User | Deletes an individual preference record |
| `/api/learning/preferences/reset` | `POST` | Authenticated User | Resets all or categorical preferences |
| `/api/learning/preferences/export`| `GET` | Authenticated User | GDPR/CCPA machine-readable data export |
| `/api/learning/consent` | `GET` | Authenticated User | Retrieves current user learning consent toggles |
| `/api/learning/consent` | `PUT` | Authenticated User | Updates user learning & training consent toggles |
| `/api/learning/feedback` | `POST` | Authenticated User | Submits feedback; updates Layer A & Layer B |
| `/api/learning/user-data` | `DELETE`| Authenticated User | Complete data erasure and deletion propagation |
| `/api/learning/admin/dashboard` | `GET` | Admin / Internal | Aggregated telemetry & dataset quality stats |
| `/api/learning/admin/models` | `GET` | Admin / Internal | Lists registered candidate & deployed models |
| `/api/learning/admin/training-jobs` | `POST` | Admin / Internal | Enqueues background remote training job |
| `/api/learning/admin/training-jobs/{id}/execute` | `POST` | Admin / Internal | Executes training run & registers candidate |
| `/api/learning/admin/evaluate-model` | `POST` | Admin / Internal | Evaluates candidate against held-out benchmark |
| `/api/learning/admin/deploy-model` | `POST` | Admin / Internal | Promotes approved candidate to production |
| `/api/learning/admin/rollback-model` | `POST` | Admin / Internal | Reverts production model to target version |

---

## 6. Frontend Integration

1. **`learningService.ts` (`frontend/src/services/learningService.ts`):** Complete TypeScript client with Axios interceptors attaching verified Supabase JWT Bearer tokens and handling automatic refresh on 401.
2. **`StylistChat.tsx` (`frontend/src/pages/StylistChat.tsx`):**
   - Added lightweight, non-intrusive Thumbs Up and Thumbs Down feedback buttons next to audio playback controls on assistant messages.
   - Connected outfit wear and like actions directly to `learningService.submitFeedback` with `accepted_recommendation` feedback types.
   - Verified clean production compilation with `tsc && vite build` (zero errors, built in 4.72s).

---

## 7. Automated Test Suite Verification

The test suite in `backend/tests/test_continuous_learning.py` executes 20 comprehensive end-to-end test scenarios:

| # | Test Name | Target Behavior | Result |
| :---: | :--- | :--- | :---: |
| 1 | `test_01_personalization_from_explicit_preferences` | Explicit preference stored and reflected in context builder | **PASS** |
| 2 | `test_02_preference_confidence_updates` | Repeated confirmations increment evidence and confidence | **PASS** |
| 3 | `test_03_feedback_persistence` | Structured feedback stored with consent snapshot | **PASS** |
| 4 | `test_04_consent_disabled` | Global training consent False blocks global dataset entry | **PASS** |
| 5 | `test_05_consent_enabled` | Global training consent True allows validated example entry | **PASS** |
| 6 | `test_06_image_training_consent_independently_disabled`| Missing image consent blocks image-based training data | **PASS** |
| 7 | `test_07_global_training_eligibility` | Validated high-quality example enrolled in dataset | **PASS** |
| 8 | `test_08_invalid_feedback_rejection` | Malformed/XSS injection labels rejected by pipeline | **PASS** |
| 9 | `test_09_duplicate_feedback_detection` | Content hash deduplication blocks duplicate training samples | **PASS** |
| 10 | `test_10_poisoning_protection` | Contradictory corrections detected and quarantined | **PASS** |
| 11 | `test_11_training_dataset_generation` | Dataset version tagging and versioned partition retrieval | **PASS** |
| 12 | `test_12_dataset_provenance` | Complete audit trail linking example to source feedback | **PASS** |
| 13 | `test_13_model_evaluation` | Benchmark evaluation computes accuracy, F1, and metrics | **PASS** |
| 14 | `test_14_candidate_model_rejection` | Regression below baseline marks candidate as rejected | **PASS** |
| 15 | `test_15_safe_model_deployment` | Approved candidate promoted; previous model archived | **PASS** |
| 16 | `test_16_rollback` | Atomic registry rollback restores previous production version | **PASS** |
| 17 | `test_17_user_data_deletion` | User erasure purges preferences and derived examples | **PASS** |
| 18 | `test_18_cross_user_isolation` | Zero data leakage between distinct user accounts | **PASS** |
| 19 | `test_19_user_preference_export` | GDPR/CCPA machine-readable data export validated | **PASS** |
| 20 | `test_20_session_context_separation` | Session context isolated; model weights unchanged | **PASS** |

**Test Execution Summary:** `20 passed in 30.06s` (100% pass rate).

---

## 8. Definition of Done Checklist

- [x] **1. User interactions produce structured feedback:** Standardized feedback types supported.
- [x] **2. Individual preferences persist independently:** Layer A memory stored with confidence and evidence counts.
- [x] **3. Session context remains isolated:** In-session summaries isolated to individual sessions.
- [x] **4. Training consent enforced server-side:** Defaults to disabled; verified cryptographically.
- [x] **5. Eligible examples enter validated datasets:** Filtered, scrubbed, and versioned.
- [x] **6. Dataset provenance is traceable:** Source feedback IDs and validation timestamps preserved.
- [x] **7. Training jobs run independently of live user requests:** Background execution targeting remote GPUs.
- [x] **8. Candidate models evaluated against existing models:** Held-out test set benchmark comparisons.
- [x] **9. Poor candidate models are rejected:** Automatic quality regression gate prevents deployment.
- [x] **10. Production models can be rolled back:** Zero-downtime rollback controls implemented.
- [x] **11. Users can control and delete personalization data:** Inspect, edit, reset, export, and purge APIs verified.
- [x] **12. Existing Yorvyn AI functionality continues working:** All 19 Phase 10 persistent session tests continue to pass.

