"""Resolve category evidence from the existing, strictly loaded v6 singleton."""
import io
import time
from PIL import Image

from backend.app.services.ai.base import AIProviderResponse, ModelMetadata
from .capability_registry import State, garment_capabilities
from .garment_execution import current_execution

# Operational abstention threshold, not a calibrated guarantee of accuracy.
CATEGORY_THRESHOLD = 0.65


class EvidenceRequired(ValueError):
    """Local identity evidence does not support a reconstruction decision."""


def classifier_prediction(image_bytes):
    import torch
    from backend.app.services.garments.intelligence.universal_garment_classifier import (
        NEURAL_CATEGORIES, NEURAL_SUBCATEGORIES, universal_garment_classifier as model)
    receipt = model.checkpoint_receipt
    if garment_capabilities.classifier_status(model) != State.VERIFIED:
        return None
    start = time.monotonic()
    with Image.open(io.BytesIO(image_bytes)) as image, torch.inference_mode():
        category, sub = model._neural_model(model._transform(image.convert("RGB")).unsqueeze(0).to(model.device))
        for vector, size in ((category, len(NEURAL_CATEGORIES)), (sub, len(NEURAL_SUBCATEGORIES))):
            if (tuple(vector.shape) != (1, size) or not torch.isfinite(vector).all()
                    or vector.min().item() < 0 or abs(vector.sum().item() - 1) > 1e-5):
                return None
        return {"model_id": "universal-garment-classifier", "sha256": receipt["actual_sha"],
                "device": str(model.device), "category": NEURAL_CATEGORIES[category.argmax().item()],
                "subcategory": NEURAL_SUBCATEGORIES[sub.argmax().item()], "confidence": category.max().item(),
                "duration_ms": round((time.monotonic() - start) * 1000, 3),
                "calibration": "no deployment holdout calibration established"}


def local_vision(request, local_cv, predict=classifier_prediction):
    start = time.monotonic()
    fallback_reason = None
    try:
        prediction = predict(request.image_bytes)
    except (RuntimeError, OSError) as exc:
        prediction = None
        fallback_reason = type(exc).__name__
    confident = prediction is not None and prediction["confidence"] >= CATEGORY_THRESHOLD
    context = current_execution.get()
    details = context is None or context.requires_details
    extra = None
    if (details or not confident) and local_cv.is_available():
        extra = local_cv.execute(request)
    if extra is not None and extra.success:
        data = extra.structured_data
        local = data.get("garment", {})
        agreement = None if prediction is None else prediction["category"] == local.get("category")
        routing = dict(
            classifier=prediction, same_category=agreement,
            classifier_fallback=None if confident else (fallback_reason or "artifact_unavailable_or_uncertain"))
        if confident and agreement:
            data["garment"] = {**local, "category": prediction["category"], "confidence": prediction["confidence"]}
        routing["identity_conflict"] = bool(confident and agreement is False)
        data.setdefault("model_execution_provenance", {})["category_routing"] = routing
        return extra
    if not confident:
        raise EvidenceRequired("Insufficient local category evidence. Supply another clear view.")
    garment = {k: prediction[k] for k in ("category", "subcategory", "confidence")}
    return AIProviderResponse(request_id=request.request_id, provider_name="yorvyn_classifier",
                              model_metadata=ModelMetadata(provider_name="yorvyn_classifier",
                                                           model_name=prediction["model_id"], model_version="6.0.0",
                                                           is_local=True, device=prediction["device"]),
                              task_type=request.task_type, success=True,
                              structured_data={"garment": garment, "components": {}, "appearance": {
                                  "primary_color": "unknown", "pattern": "unknown", "fabric_appearance": "unknown"},
                                  "model_execution_provenance": {"category_routing": {"classifier": prediction,
                                      "component_evidence": "unavailable" if details else "not_requested"}},
                                  "unknown_properties": ["construction", "fabric composition", "hidden surfaces"]},
                              latency_ms=(time.monotonic() - start) * 1000)
