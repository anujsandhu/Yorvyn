"""
Structured Output Validation and Schema Enforcement for Yorvyn LLM Architecture.
Ensures responses adhere strictly to typed Pydantic models before returning to client.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional, Tuple, Type, TypeVar
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class StructuredOutputValidator:
    """Validates raw LLM text against Pydantic schemas."""

    @staticmethod
    def extract_json_block(text: str) -> Optional[str]:
        """Extracts JSON substring from markdown fenced code blocks or raw text."""
        # 1. Search for ```json ... ``` or ``` ... ```
        pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            return matches[0].strip()

        # 2. Search for first { ... } or [ ... ]
        curly_start = text.find("{")
        curly_end = text.rfind("}")
        if curly_start != -1 and curly_end != -1 and curly_end > curly_start:
            return text[curly_start:curly_end + 1].strip()

        return None

    @classmethod
    def validate_model(cls, text: str, model_cls: Type[T]) -> Tuple[Optional[T], Optional[str]]:
        """
        Parses text into JSON and validates against target Pydantic model.
        Returns (model_instance, error_message).
        """
        json_str = cls.extract_json_block(text) or text.strip()

        try:
            parsed_dict = json.loads(json_str)
            instance = model_cls(**parsed_dict)
            return instance, None
        except json.JSONDecodeError as jde:
            msg = f"JSON decode failed: {jde}"
            logger.warning(msg)
            return None, msg
        except ValidationError as ve:
            msg = f"Pydantic validation failed: {ve}"
            logger.warning(msg)
            return None, msg
        except Exception as e:
            msg = f"Unexpected validation error: {e}"
            logger.warning(msg)
            return None, msg
