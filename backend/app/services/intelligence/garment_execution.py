"""Request-scoped, server-bound execution. Only small references cross into durable history."""
import asyncio
from contextvars import ContextVar
from dataclasses import dataclass
import inspect
import logging
import time
from typing import Callable, Literal, Optional, Tuple
from uuid import uuid4
from weakref import WeakKeyDictionary

from pydantic import BaseModel, ConfigDict, Field

from .capability_registry import State, garment_capabilities

logger = logging.getLogger(__name__)
current_execution = ContextVar("garment_execution", default=None)


class Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    action: Optional[Literal["widen", "shorten", "widen_sleeves", "denim", "undo", "inspect",
                             "reconstruct", "identify", "cancel", "retry", "clarify"]] = None
    category: Optional[str] = Field(None, max_length=128)
    subcategory: Optional[str] = Field(None, max_length=128)
    view_count: int = Field(0, ge=0, le=10)


class Operation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["16.0"] = "16.0"
    operation_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    capability_id: str
    algorithm_id: str
    input_refs: Tuple[str, ...]
    parameters: Parameters
    timeout_s: float = Field(gt=0, le=600)
    max_retries: Literal[0] = 0
    validation: str
    result_ref: str


@dataclass(frozen=True)
class Binding:
    handler: Callable
    validate: Callable
    algorithm: str
    validation: str
    timeout: float
    owned: bool = False


class ExecutionContext:
    def __init__(self, owner, session, task):
        self.owner, self.session, self.task = str(owner), str(session), str(task)
        self.requires_details = True
        self.operations = []
        self.requests = []
        self.start = time.monotonic()

    def report(self, garment, decision):
        report = garment.get("mesh_report") or {}
        receipts = garment.get("recognition", {}).get("model_execution_provenance", {})
        # Charge perception only on the turn which actually processed new photos.
        views = [v.get("category_routing", {}) for v in receipts.values() if isinstance(v, dict)] if any(
            op["capability_id"] == "views.identify" and op["status"] == "COMPLETED" for op in self.operations) else []
        classification = [v["classifier"] for v in views if v.get("classifier")]
        missing_identity = sum(bool(v.get("classifier_fallback")) for v in views)
        failed_mesh = any(op["capability_id"] in {"candidate.inspect", "candidate.edit"} and
                          op.get("error_type") == "HTTPException" and op.get("http_status") == 422 for op in self.operations)
        return {
            "schema_version": "16.0", "user_id": self.owner, "conversation_id": self.session,
            "task_id": self.task, "input_sha256": garment.get("source_sha256", []),
            "garment_id": garment.get("garment_id"), "job_id": garment.get("job_id"),
            "candidate_sha256": garment.get("candidate_sha256"), "parent_turn_id": garment.get("parent_turn_id"),
            "decision": decision, "classifiers": classification, "operations": self.operations, "provider_requests": list(self.requests),
            "accounting": {
                "turn_ms": round((time.monotonic() - self.start) * 1000, 3),
                "provider_request_count": len(self.requests),
                "classifier_inference_ms": sum(v["duration_ms"] for v in classification) if classification else None,
                "turn_thread_cpu_ms": sum(r["thread_cpu_ms"] for r in self.operations if "thread_cpu_ms" in r),
                "job_report_ref": garment.get("job_id"),
                "provider_retry_count": sum(r["retry"] for r in self.requests),
                "fallback_count": missing_identity + sum(1 for r in self.operations if r.get("fallback_reason")),
                "external_input_tokens": self._usage("input_tokens"),
                "external_output_tokens": self._usage("output_tokens"),
                "provider_billed_usd": self._usage("billed_usd"),
                "process_peak_rss_bytes": peak_rss(), "gpu_utilization": None,
            },
            "quality": {"operation": "FAILED" if garment.get("last_error") else "COMPLETED",
                        "asset_integrity": "VERIFIED" if garment.get("candidate_sha256") and report.get("is_valid") else "NOT_EVALUATED",
                        "mesh_structure": "FAILED" if failed_mesh else "PASSED" if report.get("is_valid") else "NOT_EVALUATED",
                        **{k: "NOT_EVALUATED" for k in ("geometry_accuracy", "visual_accuracy", "material_accuracy", "fit_accuracy")}}
        }

    def _usage(self, key):
        values = [r.get(key) for r in self.requests]
        return sum(values) if all(type(v) in (float, int) and v >= 0 for v in values) else None


def peak_rss():
    import sys
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return usage if sys.platform == "darwin" else usage * 1024
    except (ImportError, OSError):
        return None


class GarmentRouter:
    def __init__(self, bindings, registry=garment_capabilities, concurrency=2):
        if concurrency < 1:
            raise ValueError("Concurrency must be positive")
        self.registry = registry
        self.bindings = dict(bindings)
        self.concurrency = concurrency
        self._limits = WeakKeyDictionary()
        for key in bindings:
            self.registry.get(key)

    async def execute(self, context, capability, *args, refs=(), parameters=None):
        spec = self.registry.get(capability)
        if capability not in self.bindings or spec.availability not in (State.EXECUTABLE, State.VERIFIED):
            raise ValueError(f"No executable binding for {capability}")
        binding = self.bindings[capability]
        if binding.owned and (not args or getattr(args[-1], "user_id", None) != context.owner):
            raise PermissionError("Garment operation owner mismatch")
        operation = Operation(task_id=context.task, capability_id=capability, algorithm_id=binding.algorithm,
                              input_refs=tuple(refs), parameters=Parameters.model_validate(parameters or {}),
                              timeout_s=binding.timeout, validation=binding.validation,
                              result_ref=f"turn:{context.task}/operations/{len(context.operations)}")
        rec = operation.model_dump(mode="json")
        context.operations.append(rec)
        start = time.monotonic()
        loop = asyncio.get_running_loop()
        if loop not in self._limits:
            self._limits[loop] = asyncio.Semaphore(self.concurrency)
        slots = self._limits[loop]
        work = None

        def sync_call():
            begin = time.thread_time()
            try:
                return binding.handler(*args)
            finally:
                rec["thread_cpu_ms"] = round((time.thread_time() - begin) * 1000, 3)

        def release(future):
            slots.release()
            if not future.cancelled():
                future.exception()  # Consume a late failure after timeout/disconnect.

        try:
            await asyncio.wait_for(slots.acquire(), binding.timeout)
            token = current_execution.set(context)
            try:
                call = binding.handler(*args) if inspect.iscoroutinefunction(binding.handler) else asyncio.to_thread(sync_call)
                work = asyncio.create_task(call)
                work.add_done_callback(release)
            finally:
                current_execution.reset(token)
            remaining = max(0, binding.timeout - (time.monotonic() - start))
            value = await asyncio.wait_for(asyncio.shield(work), remaining)
            if not binding.validate(value):
                raise ValueError(f"Invalid result for {capability}")
            rec["status"] = "COMPLETED"
            return value
        except asyncio.TimeoutError:
            rec["status"] = "TIMED_OUT"
            raise
        except asyncio.CancelledError:
            rec["status"] = "CANCELLED"
            raise
        except Exception as exc:
            rec.update(status="FAILED", error_type=type(exc).__name__)
            if hasattr(exc, "status_code"):
                rec["http_status"] = exc.status_code
            raise
        finally:
            rec["duration_ms"] = round((time.monotonic() - start) * 1000, 3)
            logger.info("Garment operation %s %s %s", operation.operation_id, capability, rec.get("status"))
