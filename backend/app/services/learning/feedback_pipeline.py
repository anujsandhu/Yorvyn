"""
Feedback Pipeline & Quality Validation Engine (Layer B — Global Model Improvement)
Implements:
1. Consent Verification (global, image, conversation)
2. Sensitive Data & Token Scrubbing
3. Poisoning & Spam Protection (rate limiting, contradiction detection, label syntax validation)
4. Duplicate Detection (hashing)
5. Dataset Example Packaging & Provenance Tracking
"""

from __future__ import annotations

import re
import json
import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from backend.app.services.database.supabase_repository import SupabaseRepository, supabase_repo

logger = logging.getLogger(__name__)

# Sensitive data sanitization regexes
TOKEN_REGEX = re.compile(r'(?:Bearer\s+[A-Za-z0-9\-._~+/]+=*|eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+|ak-[A-Za-z0-9]{20,})', re.IGNORECASE)
EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')
PHONE_REGEX = re.compile(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
PROFANITY_OR_SPAM_PATTERNS = [r'spam', r'bot_attack', r'asdfgh', r'qwertyuiop', r'<script', r'DROP\s+TABLE']


class FeedbackPipeline:
    """Orchestrates intake, sanitation, poisoning defense, and dataset example creation."""

    def __init__(self, repo: Optional[SupabaseRepository] = None):
        self.repo = repo or supabase_repo
        self._recent_submissions: Dict[str, List[datetime]] = {}  # user_id -> [submission_timestamps]
        self._seen_example_hashes: set = set()

    def sanitize_payload(self, data: Any) -> Any:
        """Deeply removes auth tokens, passwords, emails, phone numbers and secrets."""
        if isinstance(data, str):
            clean = TOKEN_REGEX.sub("[REDACTED_TOKEN]", data)
            clean = EMAIL_REGEX.sub("[REDACTED_EMAIL]", clean)
            clean = PHONE_REGEX.sub("[REDACTED_PHONE]", clean)
            return clean
        elif isinstance(data, dict):
            sanitized = {}
            for k, v in data.items():
                if any(sec in k.lower() for sec in ("token", "password", "secret", "authorization", "cookie", "api_key")):
                    continue
                sanitized[k] = self.sanitize_payload(v)
            return sanitized
        elif isinstance(data, list):
            return [self.sanitize_payload(item) for item in data]
        return data

    def detect_spam_or_abuse(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """Rate limiting & high-velocity feedback spam detection."""
        now = datetime.utcnow()
        one_minute_ago = now - timedelta(seconds=60)
        history = self._recent_submissions.get(user_id, [])
        valid_history = [t for t in history if t > one_minute_ago]
        self._recent_submissions[user_id] = valid_history

        if len(valid_history) >= 10:
            return True, "Rate limit exceeded: suspicious high-velocity feedback burst"

        valid_history.append(now)
        self._recent_submissions[user_id] = valid_history
        return False, None

    def validate_correction_integrity(
        self,
        original_output: Dict[str, Any],
        corrected_output: Dict[str, Any],
        feedback_text: Optional[str] = None
    ) -> Tuple[bool, float, Optional[str]]:
        """
        Guards against poisoning, contradictory corrections, and malformed labels.
        Returns: (is_valid, quality_score, reason_if_invalid)
        """
        if not corrected_output and not feedback_text:
            return False, 0.0, "Empty correction payload"

        # Check for spam/injection characters
        text_to_check = f"{feedback_text or ''} {json.dumps(corrected_output)}"
        for pat in PROFANITY_OR_SPAM_PATTERNS:
            if re.search(pat, text_to_check, re.IGNORECASE):
                return False, 0.0, f"Poisoning detected: contains suspicious pattern or injection ({pat})"

        # Label syntax validation
        for k, v in corrected_output.items():
            if len(k) > 64 or len(str(v)) > 256:
                return False, 0.0, "Malformed label: key or value exceeds permitted length"
            if re.search(r'[<>{}\[\]\\]', str(k)):
                return False, 0.0, "Malformed label: contains invalid syntax characters"

        # Contradiction check: correction should not be identical to original prediction
        if original_output and corrected_output:
            if original_output == corrected_output:
                return False, 0.1, "Contradictory feedback: correction is identical to original prediction"

        # Calculate preliminary quality score
        quality_score = 0.85
        if feedback_text and len(feedback_text.split()) > 3:
            quality_score = min(1.0, quality_score + 0.10)

        return True, quality_score, None

    def process_and_route_feedback(
        self,
        feedback_id: str,
        target_dataset_version: str = "v1.2_continuous"
    ) -> Dict[str, Any]:
        """
        Executes full ingestion pipeline for an existing or newly submitted feedback:
        1. Fetch feedback record.
        2. Verify user consent.
        3. Scrub sensitive information.
        4. Detect spam / abuse.
        5. Validate correction integrity.
        6. Compute content hash to prevent duplicate training examples.
        7. If eligible, write to yorvyn_learning_examples.
        """
        feedback = self.repo.get_feedback_by_id(feedback_id)
        if not feedback:
            return {"success": False, "error": f"Feedback {feedback_id} not found"}

        user_id = feedback["user_id"]
        fb_type = feedback["feedback_type"]
        original_output = feedback.get("original_output") or {}
        corrected_output = feedback.get("corrected_output") or {}
        feedback_text = feedback.get("feedback_text")
        metadata = feedback.get("metadata") or {}

        # 1. Consent Verification
        consent = self.repo.get_learning_consent(user_id)
        if not consent.get("global_model_training_enabled", False):
            return {
                "success": False,
                "status": "excluded",
                "reason": "Global model training consent not enabled by user",
                "example_id": None
            }

        # Determine task type
        task_type = metadata.get("task_type") or "classification"
        is_image_task = task_type in ("segmentation", "human_parsing", "reconstruction", "avatar_fitting", "component_detection", "fabric_estimation")
        is_conversation_task = task_type in ("response_quality", "preference_prediction")

        if is_image_task and not consent.get("image_training_enabled", False):
            return {
                "success": False,
                "status": "excluded",
                "reason": "Image training consent not enabled by user",
                "example_id": None
            }

        if is_conversation_task and not consent.get("conversation_training_enabled", False):
            return {
                "success": False,
                "status": "excluded",
                "reason": "Conversation training consent not enabled by user",
                "example_id": None
            }

        # 2. Abuse / Velocity Check
        is_spam, spam_reason = self.detect_spam_or_abuse(user_id)
        if is_spam:
            return {
                "success": False,
                "status": "rejected",
                "reason": spam_reason,
                "example_id": None
            }

        # 3. Correction Integrity & Poisoning Check
        is_valid, quality_score, invalid_reason = self.validate_correction_integrity(
            original_output=original_output,
            corrected_output=corrected_output,
            feedback_text=feedback_text
        )
        if not is_valid:
            # Record quarantined / rejected example for inspection
            ex = self.repo.create_learning_example(
                source_feedback_id=feedback_id,
                task_type=task_type,
                input_reference=self.sanitize_payload(original_output),
                target_output=self.sanitize_payload(corrected_output),
                consent_scope="global_model_training",
                quality_score=0.0,
                validation_status="quarantined",
                dataset_version=target_dataset_version,
                exclusion_reason=invalid_reason
            )
            return {
                "success": False,
                "status": "quarantined",
                "reason": invalid_reason,
                "example_id": ex["id"]
            }

        # 4. Duplicate Detection (Content Hash)
        canonical_input = json.dumps(self.sanitize_payload(original_output), sort_keys=True)
        canonical_target = json.dumps(self.sanitize_payload(corrected_output), sort_keys=True)
        content_hash = hashlib.sha256(f"{task_type}:{canonical_input}:{canonical_target}".encode()).hexdigest()

        if content_hash in self._seen_example_hashes:
            return {
                "success": False,
                "status": "duplicate",
                "reason": "Identical training example already exists in pipeline",
                "example_id": None
            }
        self._seen_example_hashes.add(content_hash)

        # 5. Create Validated Learning Example
        learning_example = self.repo.create_learning_example(
            source_feedback_id=feedback_id,
            task_type=task_type,
            input_reference=self.sanitize_payload(original_output),
            target_output=self.sanitize_payload(corrected_output),
            consent_scope="global_model_training",
            quality_score=quality_score,
            validation_status="validated",
            dataset_version=target_dataset_version,
            exclusion_reason=None
        )

        logger.info(f"[FeedbackPipeline] Enrolled validated example {learning_example['id']} for task '{task_type}' (quality={quality_score:.2f})")
        return {
            "success": True,
            "status": "validated",
            "example_id": learning_example["id"],
            "quality_score": quality_score,
            "dataset_version": target_dataset_version
        }


# Global singleton
feedback_pipeline = FeedbackPipeline()

