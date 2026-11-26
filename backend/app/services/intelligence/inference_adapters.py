"""
YORVYN Intelligence Platform (YIP) — Unified Inference Adapters & Performance Telemetry.

Coordinates:
- Hardware detection (Apple Silicon MPS / CUDA / CPU / ONNX Runtime) without external probes.
- Resident model lifecycle via existing SequentialModelManager (prevents loading all weights at once).
- Exact cold-start, warm inference, P50/P95/P99, and RSS memory telemetry.
- Task-specific hardware routing and bounded concurrency guarantees.
"""
from __future__ import annotations

import logging
import resource
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional

import torch

from backend.app.services.garments.intelligence.sequential_model_manager import model_manager

logger = logging.getLogger(__name__)


def _peak_rss_mb() -> float:
    try:
        raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round((raw / (1024.0 * 1024.0)) if sys.platform == "darwin" else (raw / 1024.0), 2)
    except (ImportError, OSError):
        return 0.0


class HardwareSelector:
    """Inspects real compute backends without fabricating unavailable GPU support."""

    @staticmethod
    def inspect() -> Dict[str, Any]:
        mps_avail = bool(torch.backends.mps.is_available())
        cuda_avail = bool(torch.cuda.is_available())
        ort_providers: List[str] = []
        ort_available = False
        try:
            import onnxruntime as ort
            ort_available = True
            ort_providers = list(ort.get_available_providers())
        except ImportError:
            pass

        preferred = "cuda" if cuda_avail else ("mps" if mps_avail else "cpu")
        return {
            "platform": sys.platform,
            "python_version": sys.version.split()[0],
            "torch_version": torch.__version__,
            "cuda_available": cuda_avail,
            "mps_available": mps_avail,
            "onnxruntime_available": ort_available,
            "onnxruntime_providers": ort_providers,
            "preferred_torch_device": preferred,
            "software_rendered_warning": False,
        }

    @staticmethod
    def select_device(preferred: Optional[str] = None, allow_mps: bool = True) -> str:
        if preferred in {"cpu", "mps", "cuda"}:
            if preferred == "cuda" and torch.cuda.is_available():
                return "cuda"
            if preferred == "mps" and allow_mps and torch.backends.mps.is_available():
                return "mps"
            return "cpu"
        if torch.cuda.is_available():
            return "cuda"
        if allow_mps and torch.backends.mps.is_available():
            return "mps"
        return "cpu"


@dataclass
class AdapterTelemetry:
    model_id: str
    cold_start_ms: Optional[float] = None
    failure_count: int = 0
    latencies_ms: Deque[float] = field(default_factory=lambda: deque(maxlen=200))
    peak_rss_mb: float = 0.0
    last_device: str = "cpu"
    last_backend: str = "uninitialized"

    def summary(self) -> Dict[str, Any]:
        vals = sorted(self.latencies_ms)
        count = len(vals)
        if count == 0:
            p50 = p95 = p99 = None
        else:
            p50 = round(vals[int(0.50 * (count - 1))], 3)
            p95 = round(vals[int(0.95 * (count - 1))], 3)
            p99 = round(vals[int(0.99 * (count - 1))], 3)
        return {
            "model_id": self.model_id,
            "sample_count": count,
            "cold_start_ms": round(self.cold_start_ms, 3) if self.cold_start_ms is not None else None,
            "p50_ms": p50,
            "p95_ms": p95,
            "p99_ms": p99,
            "failure_count": self.failure_count,
            "peak_rss_mb": self.peak_rss_mb,
            "last_device": self.last_device,
            "last_backend": self.last_backend,
        }


class InferenceTelemetryCollector:
    """Thread-safe collector for cold-start, percentile latency, failures, and RSS."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stats: Dict[str, AdapterTelemetry] = {}

    def record(
        self,
        model_id: str,
        latency_ms: float,
        *,
        is_cold_start: bool = False,
        device: str = "cpu",
        backend: str = "pytorch",
        success: bool = True,
    ) -> None:
        rss = _peak_rss_mb()
        with self._lock:
            entry = self._stats.get(model_id)
            if entry is None:
                entry = AdapterTelemetry(model_id=model_id)
                self._stats[model_id] = entry
            if is_cold_start and entry.cold_start_ms is None:
                entry.cold_start_ms = latency_ms
            if success:
                entry.latencies_ms.append(latency_ms)
            else:
                entry.failure_count += 1
            entry.peak_rss_mb = max(entry.peak_rss_mb, rss)
            entry.last_device = device
            entry.last_backend = backend

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {mid: item.summary() for mid, item in sorted(self._stats.items())}


class InferenceAdapter:
    """Common execution boundary for local PyTorch, ONNX Runtime, and deterministic engines."""

    def __init__(
        self,
        model_id: str,
        backend_name: str,
        runner: Callable[..., Any],
        *,
        allow_mps: bool = True,
        telemetry: Optional[InferenceTelemetryCollector] = None,
    ) -> None:
        self.model_id = model_id
        self.backend_name = backend_name
        self._runner = runner
        self.allow_mps = allow_mps
        self.telemetry = telemetry or inference_telemetry
        self._warmed_up = False
        self._lock = threading.Lock()

    def execute(self, *args: Any, timeout_fallback_cpu: bool = True, **kwargs: Any) -> Dict[str, Any]:
        device = HardwareSelector.select_device(allow_mps=self.allow_mps) if "pytorch" in self.backend_name else "cpu"
        with self._lock:
            is_cold = not self._warmed_up
            t0 = time.perf_counter()
            try:
                result = self._runner(*args, device=device, **kwargs)
                elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
                self._warmed_up = True
                self.telemetry.record(
                    self.model_id,
                    elapsed_ms,
                    is_cold_start=is_cold,
                    device=device,
                    backend=self.backend_name,
                    success=True,
                )
                return {
                    "ok": True,
                    "model_id": self.model_id,
                    "backend": self.backend_name,
                    "device": device,
                    "latency_ms": elapsed_ms,
                    "cold_start": is_cold,
                    "result": result,
                }
            except Exception as exc:
                if timeout_fallback_cpu and device == "mps":
                    model_manager.flush_memory()
                    try:
                        result = self._runner(*args, device="cpu", **kwargs)
                        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
                        self._warmed_up = True
                        self.telemetry.record(
                            self.model_id,
                            elapsed_ms,
                            is_cold_start=is_cold,
                            device="cpu",
                            backend=f"{self.backend_name}_cpu_fallback",
                            success=True,
                        )
                        return {
                            "ok": True,
                            "model_id": self.model_id,
                            "backend": f"{self.backend_name}_cpu_fallback",
                            "device": "cpu",
                            "latency_ms": elapsed_ms,
                            "cold_start": is_cold,
                            "fallback_reason": type(exc).__name__,
                            "result": result,
                        }
                    except Exception as cpu_exc:
                        exc = cpu_exc
                elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
                self.telemetry.record(
                    self.model_id,
                    elapsed_ms,
                    is_cold_start=is_cold,
                    device=device,
                    backend=self.backend_name,
                    success=False,
                )
                raise RuntimeError(f"InferenceAdapter[{self.model_id}] failed: {exc}") from exc


inference_telemetry = InferenceTelemetryCollector()
