"""
YORVYN — Unified Model Registry Service (Phase 13.2 Remediated)
Maintains client/server model mapping, SHA256 integrity verification,
path traversal security, model load validation, and registry health reporting.
"""

import hashlib
import io
import json
import os
import re
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class CanonicalModelRecord(BaseModel):
    """Normalized Phase 17.0 Unified Model Registry contract."""
    model_config = ConfigDict(extra="ignore")
    model_id: str
    name: str
    version: str
    family: str
    domain: str
    task: str
    input_contract: str
    output_contract: str
    checkpoint_reference: Optional[str] = None
    sha256: Optional[str] = None
    license: str = "Not independently verified"
    source: str = "internal"
    hardware_requirements: str = "CPU"
    memory_mb: Optional[float] = None
    inference_backend: str = "pytorch"
    availability: str = "DECLARED_ONLY"
    verification_state: str = "DECLARED"
    performance_ms: Optional[float] = None
    limitations: str = ""
    failure_conditions: str = ""
    fallback_model_id: Optional[str] = None


class UnifiedModelRegistry:
    def __init__(self, registry_file: Optional[str] = None):
        self.repo_root = Path(__file__).resolve().parents[4]
        reports = self.repo_root / "docs/reports"
        self.registry_file = registry_file or str(reports / "YORVYN_PHASE_13_MODEL_REGISTRY.json")
        self._active_release = None if registry_file else reports / "YORVYN_PHASE_14_1_MODEL_PROVENANCE.json"
        self._models: Dict[str, Any] = {}
        self._aliases: Dict[str, str] = {}
        self._load_registry()

    @staticmethod
    def _unique_keys(pairs):
        values = {}
        for key, value in pairs:
            if key in values:
                raise ValueError(f"Duplicate registry field: {key}")
            values[key] = value
        return values

    def _register(self, alias, spec):
        mid = spec["model_id"]
        for key in {alias, mid}:
            if not key or key in self._aliases:
                raise ValueError(f"Duplicate or empty model identity: {key}")
        self._aliases.update({alias: mid, mid: mid})
        self._models[mid] = spec

    def _load_registry(self) -> None:
        with open(self.registry_file, encoding="utf-8") as source:
            data = json.load(source, object_pairs_hook=self._unique_keys)
        self._taxonomy_version = data.get("taxonomy_version", "v3.2")
        for alias, spec in data["models"].items():
            self._register(alias, spec)

        if self._active_release:
            release = json.loads(self._active_release.read_text(), object_pairs_hook=self._unique_keys)
            artifacts = release["active_models"]
            model = self._models["universal-garment-classifier"]
            server = artifacts["pytorch_v6_checkpoint"]
            edge = artifacts["edge_onnx_classifier"]
            model["release_provenance"] = str(self._active_release.relative_to(self.repo_root))
            model["server"].update(checkpoint_path=server["relative_path"], model_version="6.0.0",
                                   sha256_checksum=server["sha256_checksum"], file_size_bytes=server["file_size_bytes"])
            model["client"].update(sha256_checksum=edge["sha256_checksum"], file_size_bytes=edge["file_size_bytes"])

        # Ensure Phase 14.22 Advanced Technology Models are registered
        phase_14_22_specs = {
            "dinov2_small": {
                "model_id": "dinov2_small",
                "name": "DINOv2 ViT-S/14 Visual Feature Extractor",
                "version": "1.0",
                "server": {"runtime": "pytorch_mps", "file_size_bytes": 88200000, "input_shape": [1, 3, 224, 224]},
                "compatibility": {"license": "Apache 2.0", "hardware": "Apple Silicon MPS / CPU", "output_classes": 384}
            },
            "depth_anything_v2": {
                "model_id": "depth_anything_v2",
                "name": "Depth Anything V2 Monocular Disparity Adapter",
                "version": "2.0",
                "server": {"runtime": "pytorch_mps", "file_size_bytes": 95000000, "input_shape": [1, 3, 518, 518]},
                "compatibility": {"license": "Apache 2.0", "hardware": "Apple Silicon MPS / CPU", "output_classes": 1}
            },
            "grounded_sam2": {
                "model_id": "grounded_sam2",
                "name": "Grounded-SAM 2 Garment Component Perception",
                "version": "2.1",
                "server": {"runtime": "pytorch_mps", "file_size_bytes": 140000000, "input_shape": [1, 3, 1024, 1024]},
                "compatibility": {"license": "Apache 2.0", "hardware": "Apple Silicon MPS / CPU", "output_classes": 10}
            },
            "xatlas_unwrapper": {
                "model_id": "xatlas_unwrapper",
                "name": "xatlas Automated UV Parameterization Engine",
                "version": "0.0.11",
                "server": {"runtime": "native_cpu_arm64", "file_size_bytes": 199000},
                "compatibility": {"license": "MIT", "hardware": "Apple Silicon arm64 CPU", "output_classes": 2}
            }
        }
        for mid, spec in phase_14_22_specs.items():
            self._register(mid, spec)

        contracts = {
            "universal-garment-classifier": ("hierarchical classification", "RGB image", "10 category and 55 subcategory probabilities"),
            "human-pose-and-landmarks": ("landmark localization", "64-dimensional embedding", "12 normalized x/y pairs"),
            "garment-silhouette-segmenter": ("foreground segmentation", "RGB image", "foreground alpha mask"),
            "feature-embedder": ("feature extraction", "RGB image", "64-dimensional embedding"),
            "dinov2_small": ("visual feature extraction", "RGB image", "384-dimensional features"),
            "depth_anything_v2": ("relative depth estimation", "RGB image", "relative depth map"),
            "grounded_sam2": ("prompted segmentation", "image and text prompts", "component masks"),
            "xatlas_unwrapper": ("UV parameterization", "triangle mesh", "UV coordinates and remapped indices"),
        }
        for mid, model in self._models.items():
            server = model.get("server") or {}
            client = model.get("client") or {}
            capability, inputs, outputs = contracts.get(mid, (None, None, None))
            artifact = server.get("checkpoint_path")
            path, _ = self.resolve_safe_path(artifact) if artifact else (None, None)
            model.setdefault("execution_type", "local")
            model.setdefault("version", server.get("model_version") or client.get("model_version"))
            model.setdefault("artifact_identity", {"path": artifact, "sha256": server.get("sha256_checksum")})
            model.setdefault("capabilities", [capability] if capability else [])
            model.setdefault("input_schema", {"type": inputs, "shape": server.get("input_shape")})
            model.setdefault("output_schema", {"type": outputs})
            availability = "DECLARED_ONLY"
            if artifact:
                availability = "PRESENT_UNVERIFIED" if path and path.is_file() else "MISSING"
            model.setdefault("availability_status", availability)
            model.setdefault("confidence_limitations", "Release identity alone does not establish predictive accuracy.")
            model.setdefault("hardware_requirements", server.get("device_target") or model.get("compatibility", {}).get("hardware"))
            model.setdefault("execution_cost", {"provider_charge_usd": 0, "compute_cost_usd": None})

    def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        return self._models.get(self._aliases.get(model_id))

    def list_models(self) -> List[Dict[str, Any]]:
        return [self._models[mid] for mid in sorted(self._models)]

    def get_model_spec(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Returns the execution spec (server or client) for a given model ID."""
        model = self.get_model(model_id)
        if not model:
            return None
        server = model.get("server") or {}
        client = model.get("client") or {}
        return {
            **model,
            "name": model.get("name"),
            "target_backend": server.get("runtime") or client.get("runtime", "pytorch"),
            "input_tensor": server.get("input_shape") or client.get("input_shape"),
            "output_tensor": {
                "universal-garment-classifier": [1, 10],
                "human-pose-and-landmarks": [1, 12, 2],
                "feature-embedder": [1, 64],
            }.get(model["model_id"]),
            "vram_basis": "legacy estimate from artifact size",
            "vram_required_mb": max(10, (server.get("file_size_bytes", 5000000) // (1024 * 1024)) * 4),
            "server": server,
            "client": client,
            "compatibility": model.get("compatibility")
        }

    @staticmethod
    def verify_checksum(data: bytes, expected_hash: str) -> bool:
        """Computes SHA256 of data bytes and compares with expected hex string."""
        calc_hash = hashlib.sha256(data).hexdigest()
        return calc_hash.lower() == expected_hash.lower()

    def resolve_safe_path(self, relative_path: str) -> Tuple[Optional[Path], Optional[str]]:
        """
        Safely resolves a relative model path against repo root, strictly preventing path traversal.
        """
        if not relative_path:
            return None, "Empty path provided"

        # Prevent URI fragments (#) in filesystem path resolution
        clean_path = relative_path.split("#")[0].strip()

        try:
            target_path = (self.repo_root / clean_path).resolve()
            # Ensure target_path is within repo_root
            if self.repo_root not in target_path.parents and target_path != self.repo_root:
                return None, f"Path traversal attempt detected: {relative_path}"
            return target_path, None
        except (OSError, RuntimeError, ValueError) as e:
            return None, f"Path resolution failed: {e}"

    def verify_server_checkpoint(self, model_id: str) -> Dict[str, Any]:
        info, _ = self.read_server_checkpoint(model_id)
        return info

    def read_server_checkpoint(self, model_id: str):
        """
        Validates whether the local server checkpoint file exists and matches recorded checksum,
        with strict path traversal guards and load verification.
        """
        model = self.get_model(model_id)
        server = (model or {}).get("server") or {}
        path, error = self.resolve_safe_path(server.get("checkpoint_path") or "")
        if error or not path or not path.is_file():
            return {"valid": False, "reason": error or "Checkpoint missing"}, None
        expected = server.get("sha256_checksum") or ""
        if not isinstance(expected, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", expected):
            return {"valid": False, "reason": "Missing or invalid release digest"}, None
        try:
            payload = path.read_bytes()
        except OSError as exc:
            return {"valid": False, "reason": type(exc).__name__}, None
        actual = hashlib.sha256(payload).hexdigest()
        info = {"resolved_path": str(path), "actual_sha": actual, "expected_sha": expected,
                "version": server.get("model_version"), "file_size": len(payload),
                "deployment_status": server.get("deployment_status")}
        if actual != expected.lower():
            return dict(info, valid=False, reason="SHA256 mismatch"), None
        state = None
        if path.suffix == ".pt":
            import pickle
            try:
                import torch
            except ImportError:
                return dict(info, valid=False, reason="PyTorch runtime unavailable"), None
            import numpy as np
            from numpy.lib import NumpyVersion
            if NumpyVersion(np.__version__) >= "2.0.0":
                from numpy._core.multiarray import _reconstruct
            else:
                from numpy.core.multiarray import _reconstruct
            # The v6 training payload includes a float32 NumPy hierarchy mask.
            try:
                with torch.serialization.safe_globals([np.dtype, np.ndarray, type(np.dtype(np.float32)),
                                                       _reconstruct]):
                    state = torch.load(io.BytesIO(payload), map_location="cpu", weights_only=True)
            except (pickle.UnpicklingError, RuntimeError, ValueError, EOFError) as exc:
                return dict(info, valid=False, reason=type(exc).__name__), None
        return dict(info, valid=True), state

    def get_registry_health_report(self) -> Dict[str, Any]:
        """
        Generates a comprehensive diagnostic health report for all registered models.
        """
        report: Dict[str, Any] = {
            "registry_version": "15.5",
            "taxonomy_version": self._taxonomy_version,
            "models_evaluated": 0,
            "models_healthy": 0,
            "models_unhealthy": 0,
            "results": {}
        }

        for model in self.list_models():
            mid = model["model_id"]
            report["models_evaluated"] += 1
            server_res = self.verify_server_checkpoint(mid)

            client_info = model.get("client", {})
            client_url = client_info.get("artifact_url", "")
            client_status = "UNKNOWN"

            if client_url.startswith("/"):
                client_path, _ = self.resolve_safe_path(f"frontend/public{client_url}")
                if client_path and client_path.exists():
                    client_status = ("VALID_ON_DISK" if self.verify_checksum(client_path.read_bytes(),
                                    client_info.get("sha256_checksum") or "") else "CHECKSUM_MISMATCH")
                else:
                    client_status = "MISSING_FROM_DISK"
            elif client_url.startswith("http"):
                client_status = "REMOTE_CDN"
            elif client_url == "inlined_web_worker":
                client_status = "WORKER_INLINED"

            is_healthy = server_res.get("valid", False)
            if is_healthy:
                report["models_healthy"] += 1
            else:
                report["models_unhealthy"] += 1

            report["results"][mid] = {
                "name": model.get("name"),
                "server_verification": server_res,
                "client_status": client_status
            }

        return report

    def validate_client_compatibility(self, model_id: str, client_version: str) -> Dict[str, Any]:
        """
        Validates client version compatibility against the authoritative server taxonomy.
        """
        model = self.get_model(model_id)
        if not model:
            return {"compatible": False, "reason": f"Model {model_id} unknown"}

        client_spec = model.get("client")
        if not client_spec:
            return {"compatible": False, "reason": "No client deployment defined"}

        expected_client_ver = client_spec.get("model_version", "1.0.0")
        major_client = client_version.split(".")[0]
        major_expected = expected_client_ver.split(".")[0]

        if major_client != major_expected:
            return {
                "compatible": False,
                "reason": f"Major version mismatch: client is {client_version}, expected ~{major_expected}.x.x",
                "recommended_action": "FORCE_CLOUD_INFERENCE"
            }

        return {
            "compatible": True,
            "authoritative_taxonomy": self._taxonomy_version,
            "min_device_tier": client_spec.get("min_device_tier", "MID")
        }

    # ------------------------------------------------------------------
    # Phase 17.0 YIP Extensions: Cache Verification, Typed Records & Selection
    # ------------------------------------------------------------------
    @staticmethod
    def probe_hf_local_cache(repo_id: str) -> Dict[str, Any]:
        """Inspects local HF hub cache without network access, hashing weight files if present."""
        hf_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
        repo_dir = hf_home / "hub" / ("models--" + repo_id.replace("/", "--"))
        snapshots = repo_dir / "snapshots"
        if not snapshots.is_dir():
            return {"cached": False, "snapshot": None, "weight_file": None, "sha256": None, "bytes": 0}
        for snap in sorted(snapshots.iterdir()):
            if not snap.is_dir() or not (snap / "config.json").is_file():
                continue
            for wname in ("model.safetensors", "pytorch_model.bin"):
                wpath = snap / wname
                if wpath.is_file():
                    h = hashlib.sha256()
                    total = 0
                    with open(wpath, "rb") as fh:
                        while True:
                            chunk = fh.read(1024 * 1024)
                            if not chunk:
                                break
                            h.update(chunk)
                            total += len(chunk)
                    return {
                        "cached": True,
                        "snapshot": snap.name,
                        "weight_file": str(wpath),
                        "sha256": h.hexdigest(),
                        "bytes": total,
                    }
        return {"cached": False, "snapshot": None, "weight_file": None, "sha256": None, "bytes": 0}

    def get_hardware_profile(self) -> Dict[str, Any]:
        from backend.app.services.intelligence.inference_adapters import HardwareSelector
        return HardwareSelector.inspect()

    def get_yip_model_catalog(self) -> List[CanonicalModelRecord]:
        """Returns complete Phase 17.0 normalized model records with real disk/cache verification."""
        from backend.app.services.intelligence.inference_adapters import inference_telemetry

        telemetry_map = inference_telemetry.snapshot()
        records: List[CanonicalModelRecord] = []

        # 1. Existing file-backed & declared Phase 13-16 models
        meta_overrides: Dict[str, Dict[str, Any]] = {
            "universal-garment-classifier": {
                "family": "yorvyn-resnet-hierarchical",
                "domain": "fashion_classification",
                "task": "category_subcategory_classification",
                "license": "Proprietary / Internal YORVYN Checkpoint",
                "source": "models/checkpoints/garment_classifier_v6.pt",
                "memory_mb": 48.0,
                "inference_backend": "pytorch_mps_or_cpu",
                "verification_state": "VERIFIED",
                "limitations": "10 categories / 55 subcategories; no independent holdout certification on arbitrary domain shift.",
                "failure_conditions": "Corrupted digest, unsupported device, or missing RGB frame.",
            },
            "human-pose-and-landmarks": {
                "family": "yorvyn-landmark-mlp",
                "domain": "fit_and_alignment",
                "task": "garment_landmark_regression",
                "license": "Proprietary / Internal YORVYN Checkpoint",
                "source": "models/checkpoints/garment_landmarks_v2.pt",
                "memory_mb": 12.0,
                "inference_backend": "pytorch_cpu_or_mps",
                "verification_state": "AVAILABLE",
                "limitations": "Takes 64-dim embedding; browser MediaPipe pose uses separate CDN weights.",
                "failure_conditions": "Malformed embedding dimension or empty foreground.",
            },
            "dinov2_small": {
                "family": "vision-transformer-ssl",
                "domain": "multimodal_vision",
                "task": "visual_embedding_and_patch_features",
                "license": "Apache-2.0",
                "source": "facebook/dinov2-small",
                "memory_mb": 180.0,
                "inference_backend": "pytorch_mps_or_cpu",
                "limitations": "Self-supervised representations require cosine ranking or probe head; no direct text alignment.",
                "failure_conditions": "If local HF cache absent, falls back to explicitly untrained shape-only ViT.",
                "fallback_model_id": "feature-embedder",
            },
            "depth_anything_v2": {
                "family": "monocular-depth",
                "domain": "3d_geometry",
                "task": "relative_disparity_estimation",
                "license": "Apache-2.0",
                "source": "analytic_heuristic (no Depth Anything V2 weights)",
                "memory_mb": 16.0,
                "inference_backend": "opencv_heuristic",
                "verification_state": "DECLARED",
                "limitations": "Current adapter computes analytic disparity heuristics without Depth Anything V2 weights or metric scale.",
                "failure_conditions": "Uniform or unlit background contaminates Otsu foreground disparity.",
            },
            "grounded_sam2": {
                "family": "prompted-segmentation",
                "domain": "component_perception",
                "task": "instance_component_masking",
                "license": "Apache-2.0",
                "source": "opencv_heuristic (no Grounded-SAM2 weights)",
                "memory_mb": 20.0,
                "inference_backend": "opencv_heuristic",
                "verification_state": "DECLARED",
                "limitations": "Proportional OpenCV bounding-box heuristic; not GroundingDINO/SAM2 neural weights.",
                "failure_conditions": "Non-standard poses or cropped images break proportional priors.",
                "fallback_model_id": "human_parsing_segformer_b2",
            },
            "garment-silhouette-segmenter": {
                "family": "birefnet-onnx",
                "domain": "vision_segmentation",
                "task": "foreground_silhouette_alpha",
                "license": "MIT",
                "source": "onnxruntime_absent",
                "memory_mb": 150.0,
                "inference_backend": "onnxruntime",
                "verification_state": "UNAVAILABLE",
                "limitations": "Server ONNX artifact absent; OpenCV/SegFormer fallback handles foreground.",
                "failure_conditions": "Missing ONNX checkpoint on server.",
                "fallback_model_id": "human_parsing_segformer_b2",
            },
            "feature-embedder": {
                "family": "mobilenet-feature-embedder",
                "domain": "multimodal_vision",
                "task": "compact_visual_embedding",
                "license": "Proprietary / Declared",
                "source": "server_weights_absent",
                "memory_mb": 32.0,
                "inference_backend": "worker_inlined",
                "verification_state": "UNAVAILABLE",
                "limitations": "Server checkpoint absent; browser client worker or DINOv2 provides embeddings.",
                "failure_conditions": "Missing server weights.",
                "fallback_model_id": "dinov2_small",
            },
            "xatlas_unwrapper": {
                "family": "uv-parameterization",
                "domain": "3d_geometry",
                "task": "uv_atlas_packing",
                "license": "MIT",
                "source": "native_package",
                "memory_mb": 24.0,
                "inference_backend": "native_cpu",
                "verification_state": "DECLARED",
                "limitations": "UV parameterization requires triangle mesh cleanliness; deterministic grid unwrap serves as fallback.",
                "failure_conditions": "Degenerate zero-area triangles or non-manifold seams.",
            },
        }

        hf_map = {
            "dinov2_small": "facebook/dinov2-small",
        }

        for model in self.list_models():
            mid = model["model_id"]
            ovr = meta_overrides.get(mid, {})
            server = model.get("server") or {}
            tstats = telemetry_map.get(mid, {})
            ckpt_res = self.verify_server_checkpoint(mid) if server.get("checkpoint_path") else {"valid": False}
            hf_info = self.probe_hf_local_cache(hf_map[mid]) if mid in hf_map else None

            if ckpt_res.get("valid"):
                availability = "AVAILABLE"
                vstate = ovr.get("verification_state", "AVAILABLE")
                sha = ckpt_res.get("actual_sha")
                ref = server.get("checkpoint_path")
            elif hf_info and hf_info["cached"]:
                availability = "AVAILABLE"
                vstate = "AVAILABLE"
                sha = hf_info["sha256"]
                ref = hf_info["weight_file"]
            elif mid in ("depth_anything_v2", "grounded_sam2"):
                availability = "DECLARED_HEURISTIC"
                vstate = "DECLARED"
                sha = None
                ref = None
            elif mid == "xatlas_unwrapper":
                try:
                    import xatlas  # noqa: F401
                    availability = "AVAILABLE"
                    vstate = "EXECUTABLE"
                except ImportError:
                    availability = "UNAVAILABLE"
                    vstate = "UNAVAILABLE"
                sha = None
                ref = "python_package:xatlas"
            else:
                availability = "UNAVAILABLE"
                vstate = "UNAVAILABLE"
                sha = None
                ref = server.get("checkpoint_path")

            records.append(CanonicalModelRecord(
                model_id=mid,
                name=model.get("name", mid),
                version=str(model.get("version") or server.get("model_version") or "unverified"),
                family=ovr.get("family", "yorvyn-core"),
                domain=ovr.get("domain", "general"),
                task=ovr.get("task", "inference"),
                input_contract=str((model.get("input_schema") or {}).get("type") or "tensor"),
                output_contract=str((model.get("output_schema") or {}).get("type") or "structured"),
                checkpoint_reference=ref,
                sha256=sha,
                license=ovr.get("license", model.get("compatibility", {}).get("license", "Not independently verified")),
                source=ovr.get("source", "registry"),
                hardware_requirements=str(model.get("hardware_requirements") or "CPU"),
                memory_mb=ovr.get("memory_mb"),
                inference_backend=ovr.get("inference_backend", "pytorch"),
                availability=availability,
                verification_state=vstate,
                performance_ms=tstats.get("p50_ms"),
                limitations=ovr.get("limitations", model.get("confidence_limitations", "")),
                failure_conditions=ovr.get("failure_conditions", ""),
                fallback_model_id=ovr.get("fallback_model_id"),
            ))

        # 2. Additional Hugging Face cached & unavailable Phase 17.0 models
        hf_catalog = [
            {
                "model_id": "human_parsing_segformer_b2",
                "name": "SegFormer-B2 Human & Apparel Parsing",
                "repo": "mattmdjaga/segformer_b2_clothes",
                "version": "b2-clothes",
                "family": "segformer",
                "domain": "vision_segmentation",
                "task": "semantic_garment_parsing",
                "input_contract": "RGB photograph",
                "output_contract": "18-class pixel parsing map + occlusion mask",
                "license": "MIT / Non-commercial dataset terms apply; inspect upstream before commercial release",
                "hardware_requirements": "Apple Silicon MPS / CPU",
                "memory_mb": 220.0,
                "inference_backend": "pytorch_mps_or_cpu",
                "limitations": "Evaluated on local benchmark samples; pixel IoU against external benchmark remains uncertified.",
                "failure_conditions": "Heavy motion blur or extreme crop.",
                "fallback_model_id": "opencv_contour_segmenter",
            },
            {
                "model_id": "clip_vit_b32_local",
                "name": "OpenAI CLIP ViT-B/32 Local Cache",
                "repo": "openai/clip-vit-base-patch32",
                "version": "vit-b-32",
                "family": "clip",
                "domain": "multimodal_vision",
                "task": "visual_text_matching_and_crop_scoring",
                "input_contract": "RGB crop + text prompts",
                "output_contract": "512-dim L2 embedding + cosine logits",
                "license": "MIT",
                "hardware_requirements": "Apple Silicon MPS / CPU",
                "memory_mb": 610.0,
                "inference_backend": "pytorch_mps_or_cpu",
                "limitations": "Generic OpenAI CLIP (not FashionCLIP/SigLIP weights); zero-shot similarity is not semantic ground truth.",
                "failure_conditions": "Ambiguous text prompts or small crop resolution.",
                "fallback_model_id": "universal-garment-classifier",
            },
            {
                "model_id": "fashion_clip_native",
                "name": "FashionCLIP Native",
                "repo": "patrickjohncyh/fashion-clip",
                "version": "uninstalled",
                "family": "fashion-clip",
                "domain": "multimodal_vision",
                "task": "fashion_domain_zero_shot_matching",
                "license": "MIT",
                "input_contract": "RGB garment image + fashion prompt",
                "output_contract": "512-dim fashion embedding",
                "hardware_requirements": "Apple Silicon MPS / CPU",
                "memory_mb": 610.0,
                "inference_backend": "unavailable",
                "limitations": "Native FashionCLIP checkpoint is NOT cached locally; current adapter substitutes clip_vit_b32_local.",
                "failure_conditions": "Offline mode blocks remote weight download.",
                "fallback_model_id": "clip_vit_b32_local",
            },
            {
                "model_id": "siglip_native",
                "name": "Google SigLIP Native",
                "repo": "google/siglip-base-patch16-224",
                "version": "uninstalled",
                "family": "siglip",
                "domain": "multimodal_vision",
                "task": "sigmoid_multilabel_attribute_scoring",
                "license": "Apache-2.0",
                "input_contract": "RGB garment image + attribute prompt",
                "output_contract": "Sigmoid attribute probabilities",
                "hardware_requirements": "Apple Silicon MPS / CPU",
                "memory_mb": 820.0,
                "inference_backend": "unavailable",
                "limitations": "Native SigLIP weights are NOT cached locally; SigLIPAdapter falls back to clip_vit_b32_local.",
                "failure_conditions": "Offline mode blocks remote weight download.",
                "fallback_model_id": "clip_vit_b32_local",
            },
        ]
        for spec in hf_catalog:
            hf_info = self.probe_hf_local_cache(spec["repo"])
            cached = bool(hf_info["cached"])
            tstats = telemetry_map.get(spec["model_id"], {})
            records.append(CanonicalModelRecord(
                model_id=spec["model_id"],
                name=spec["name"],
                version=spec["version"],
                family=spec["family"],
                domain=spec["domain"],
                task=spec["task"],
                input_contract=spec["input_contract"],
                output_contract=spec["output_contract"],
                checkpoint_reference=hf_info["weight_file"] if cached else None,
                sha256=hf_info["sha256"],
                license=spec["license"],
                source=spec["repo"],
                hardware_requirements=spec["hardware_requirements"],
                memory_mb=spec["memory_mb"],
                inference_backend=spec["inference_backend"] if cached else "unavailable",
                availability="AVAILABLE" if cached else "UNAVAILABLE",
                verification_state="EXECUTED" if tstats.get("sample_count", 0) > 0 else ("AVAILABLE" if cached else "UNAVAILABLE"),
                performance_ms=tstats.get("p50_ms"),
                limitations=spec["limitations"],
                failure_conditions=spec["failure_conditions"],
                fallback_model_id=spec.get("fallback_model_id"),
            ))

        # 3. Registered Local Hybrid Recommendation Adapter
        rec_tstats = telemetry_map.get("fashion-recommendation-engine", {})
        records.append(CanonicalModelRecord(
            model_id="fashion-recommendation-engine",
            name="YORVYN Hybrid Fashion Recommendation Engine",
            version="17.0-rec-v1",
            family="hybrid-multi-signal-ranker",
            domain="recommendation",
            task="personalized_and_outfit_ranking",
            input_contract="owner_id + preference_profile + candidates + session_context",
            output_contract="RankedRecommendationItem[] + explainable reasons",
            checkpoint_reference="backend/app/services/intelligence/recommendation_engine.py",
            sha256=None,
            license="Proprietary / Internal YORVYN Engine",
            source="intelligence/recommendation_engine",
            hardware_requirements="CPU (plus optional MPS via dinov2_small embeddings)",
            memory_mb=24.0,
            inference_backend="hybrid_ranking",
            availability="AVAILABLE",
            verification_state="EXECUTED" if rec_tstats.get("sample_count", 0) > 0 else "EXECUTABLE",
            performance_ms=rec_tstats.get("p50_ms"),
            limitations="Collaborative filtering remains gated until >=5 users meet minimum positive interaction counts; visual similarity delegates to DINOv2/CLIP.",
            failure_conditions="Disabled consent or empty candidate catalog.",
            fallback_model_id="dinov2_small",
        ))

        # 4. Phase 17.2 Neural Fashion Recommendation Models (honest disk + SHA-256 verification)
        neural_rec_specs = [
            {
                "model_id": "two_tower_recommender",
                "name": "Two-Tower Fashion Retrieval Network (BPR)",
                "family": "pytorch-two-tower",
                "task": "user_item_embedding_retrieval",
                "input_contract": "explicit_user_features + inferred_user_features + item_features",
                "output_contract": "32-dim L2 user/item embeddings + similarity logits",
                "filename": "two_tower_recommender_17.2.0.pt",
                "limitations": "Evaluated via chronological holdout against algorithmic baselines; never auto-promoted on small datasets.",
            },
            {
                "model_id": "neural_ranking_network",
                "name": "Hybrid Neural Candidate Ranking Network",
                "family": "pytorch-neural-ranker",
                "task": "masked_multi_signal_reranking",
                "input_contract": "user_emb + item_emb + masked_verified_scalars",
                "output_contract": "calibrated relevance probability + verified attributions",
                "filename": "neural_ranking_network_17.2.0.pt",
                "limitations": "Unverified signals stay masked to 0.0; falls back cleanly to hybrid_balanced preset if absent.",
            },
            {
                "model_id": "sequential_transformer_recommender",
                "name": "Causal Time-Aware Sequential Transformer Recommender",
                "family": "pytorch-causal-transformer",
                "task": "chronological_next_item_prediction",
                "input_contract": "chronological_non_view_sequence + delta_days + causal_mask",
                "output_contract": "32-dim L2 sequential state embedding",
                "filename": "sequential_transformer_recommender_17.2.0.pt",
                "limitations": "Causal attention prevents future leakage; cold-start sequences fall back to Two-Tower/algorithmic scoring.",
            },
            {
                "model_id": "graph_recommendation_model",
                "name": "Provenance-Aware Fashion Graph Propagation Model",
                "family": "pytorch-lightgcn-hybrid",
                "task": "bipartite_taxonomy_graph_propagation",
                "input_contract": "consented_user_item_category_style_graph",
                "output_contract": "32-dim normalized graph embeddings",
                "filename": "graph_recommendation_model_17.2.0.pt",
                "limitations": "Pure PyTorch propagation (torch_geometric not installed); excludes private cross-owner edges.",
            },
            {
                "model_id": "neural_outfit_compatibility",
                "name": "Symmetric Multi-Item Neural Outfit Compatibility Model",
                "family": "pytorch-deepsets-pairwise",
                "task": "outfit_compatibility_prediction",
                "input_contract": "2..4 garment feature vectors + slot coherence stats",
                "output_contract": "probabilistic calibrated outfit compatibility logit",
                "filename": "neural_outfit_compatibility_17.2.0.pt",
                "limitations": "Evaluated on curated catalog outfits; probabilistic prediction, not deterministic fashion rule.",
            },
        ]
        rec_ckpt_dir = self.repo_root / "models" / "checkpoints" / "recommendation_v17_2"
        for nspec in neural_rec_specs:
            ckpt_p = rec_ckpt_dir / nspec["filename"]
            ntstats = telemetry_map.get(nspec["model_id"], {})
            ckpt_sha = None
            has_file = ckpt_p.is_file()
            if has_file:
                try:
                    ckpt_sha = hashlib.sha256(ckpt_p.read_bytes()).hexdigest()
                except OSError:
                    has_file = False
            records.append(CanonicalModelRecord(
                model_id=nspec["model_id"],
                name=nspec["name"],
                version="17.2.0" if has_file else "untrained",
                family=nspec["family"],
                domain="recommendation",
                task=nspec["task"],
                input_contract=nspec["input_contract"],
                output_contract=nspec["output_contract"],
                checkpoint_reference=str(ckpt_p.relative_to(self.repo_root)) if has_file else None,
                sha256=ckpt_sha,
                license="Proprietary / Internal YORVYN Checkpoint",
                source="intelligence/neural_recommendation_models",
                hardware_requirements="CPU or Apple Silicon MPS",
                memory_mb=16.0,
                inference_backend="pytorch_cpu_or_mps" if has_file else "unavailable",
                availability="AVAILABLE" if has_file else "DECLARED_ONLY",
                verification_state=(
                    "EXECUTED" if (has_file and ntstats.get("sample_count", 0) > 0)
                    else ("AVAILABLE" if has_file else "DECLARED")
                ),
                performance_ms=ntstats.get("p50_ms"),
                limitations=nspec["limitations"],
                failure_conditions="Missing/corrupted checkpoint or disabled user consent.",
                fallback_model_id="fashion-recommendation-engine",
            ))
        return records

    def select_model(
        self,
        domain: str,
        task: Optional[str] = None,
        *,
        require_available: bool = True,
        max_memory_mb: Optional[float] = None,
    ) -> Optional[CanonicalModelRecord]:
        """Selects an eligible model based on task, verification state, availability, memory, and latency."""
        rank = {"VERIFIED": 4, "EXECUTED": 3, "AVAILABLE": 2, "DECLARED": 1, "UNAVAILABLE": 0}
        candidates = []
        for rec in self.get_yip_model_catalog():
            if rec.domain != domain:
                continue
            if task and rec.task != task:
                continue
            if require_available and rec.availability in {"UNAVAILABLE"}:
                continue
            if max_memory_mb is not None and rec.memory_mb is not None and rec.memory_mb > max_memory_mb:
                continue
            score = (
                rank.get(rec.verification_state, 0),
                1 if rec.availability == "AVAILABLE" else 0,
                -(rec.performance_ms or 9999.0),
            )
            candidates.append((score, rec))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def get_external_providers_and_frameworks(self) -> List[Dict[str, Any]]:
        """
        Lists external web providers and workflow orchestration frameworks cleanly
        without misrepresenting them as trained neural models (Section 10).
        Never includes raw API keys or credentials.
        """
        from backend.app.services.intelligence.langgraph_workflows import langgraph_workflow_adapter
        from backend.app.services.intelligence.tavily_web_adapter import tavily_web_adapter

        t_status = tavily_web_adapter.get_status()
        has_live = int(t_status.get("telemetry", {}).get("live_verified_calls", 0)) > 0
        return [
            {
                "integration_id": "tavily",
                "kind": "external_web_provider",
                "name": "Tavily Web Intelligence Provider",
                "endpoint_base": t_status["base_url"],
                "configured": t_status["configured"],
                "verification_state": "VERIFIED" if has_live else ("BLOCKED" if not t_status["configured"] else "DECLARED"),
                "capabilities": ["knowledge.external.search", "knowledge.external.extract", "knowledge.external.research"],
                "telemetry": t_status["telemetry"],
                "circuit_open": t_status["circuit_open"],
                "limitations": "External results are untrusted web evidence isolated from GarmentKnowledgeRAG.",
            },
            {
                "integration_id": "langgraph",
                "kind": "workflow_framework",
                "name": "LangGraph Bounded Workflow Adapter",
                "version": "0.6.9",
                "license": "MIT",
                "configured": True,
                "verification_state": "EXECUTABLE",
                "workflows": [w["workflow_name"] for w in langgraph_workflow_adapter.list_workflows()],
                "capabilities": ["workflow.garment.research", "workflow.fashion.discovery", "workflow.design.assistance"],
                "limitations": "Subordinate to YIPOrchestrator and GarmentCapabilities; max 8 steps and strict timeout enforced.",
            },
        ]


# Global Singleton
unified_model_registry = UnifiedModelRegistry()
