"""
YORVYN Reproducible Colab & Remote GPU Experiment Runner.

Records full execution provenance (Git repo/branch/SHA, Python & package versions,
GPU hardware, model checkpoint SHA-256, dataset version, parameters, output artifacts,
and status) while strictly excluding credentials and user secrets from logs.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


SENSITIVE_KEY_MARKERS = ("token", "secret", "password", "api_key", "pat", "credential")


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hex digest of a file in 1 MB chunks."""
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def redact_sensitive_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of params with any credential-like keys redacted."""
    cleaned: Dict[str, Any] = {}
    for key, value in params.items():
        lowered = key.lower()
        if any(marker in lowered for marker in SENSITIVE_KEY_MARKERS):
            cleaned[key] = "[REDACTED]"
        else:
            cleaned[key] = value
    return cleaned


def collect_git_metadata(repo_root: Path) -> Dict[str, str]:
    """Read current Git remote URL (without embedded tokens), branch, and commit SHA."""
    def _run_git(args: List[str]) -> str:
        try:
            out = subprocess.check_output(
                ["git", *args],
                cwd=str(repo_root),
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            return out
        except Exception:
            return "unknown"

    remote_url = _run_git(["remote", "get-url", "origin"])
    # Strip any embedded credentials if present in a local URL
    if "@" in remote_url and "://" in remote_url:
        scheme, rest = remote_url.split("://", 1)
        if "@" in rest:
            remote_url = f"{scheme}://{rest.split('@', 1)[1]}"

    return {
        "repository": remote_url,
        "branch": _run_git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "commit_sha": _run_git(["rev-parse", "HEAD"]),
    }


def collect_dependency_versions(packages: Optional[List[str]] = None) -> Dict[str, str]:
    """Collect installed versions for key ML and runtime packages."""
    targets = packages or [
        "torch",
        "torchvision",
        "transformers",
        "opencv-python-headless",
        "numpy",
        "scipy",
        "trimesh",
        "fastapi",
        "pydantic",
        "langgraph",
    ]
    versions: Dict[str, str] = {}
    for pkg in targets:
        try:
            versions[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            versions[pkg] = "not-installed"
    return versions


def detect_gpu_info() -> Dict[str, Any]:
    """Detect CUDA/MPS/CPU hardware safely without failing when torch is absent."""
    try:
        import torch

        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            return {
                "device": "cuda",
                "gpu_model": torch.cuda.get_device_name(0),
                "vram_mb": int(props.total_memory // (1024 * 1024)),
            }
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return {"device": "mps", "gpu_model": "Apple Silicon MPS", "vram_mb": None}
    except Exception:
        pass
    return {"device": "cpu", "gpu_model": "CPU", "vram_mb": 0}


@dataclass
class ExperimentManifest:
    experiment_id: str
    timestamp_utc: str
    git_repository: str
    git_branch: str
    git_commit_sha: str
    python_version: str
    dependency_versions: Dict[str, str]
    gpu_model: str
    gpu_device: str
    vram_mb: Optional[int]
    checkpoint_path: Optional[str]
    checkpoint_sha256: Optional[str]
    dataset_version: str
    execution_parameters: Dict[str, Any] = field(default_factory=dict)
    output_artifacts: List[Dict[str, str]] = field(default_factory=list)
    execution_status: str = "PENDING"
    notes: Optional[str] = None


def build_experiment_manifest(
    repo_root: Path,
    experiment_id: str,
    dataset_version: str,
    execution_parameters: Dict[str, Any],
    checkpoint_path: Optional[Path] = None,
    output_artifact_paths: Optional[List[Path]] = None,
    execution_status: str = "SUCCEEDED",
    notes: Optional[str] = None,
) -> ExperimentManifest:
    """Build a complete, credential-free reproducibility manifest."""
    git_meta = collect_git_metadata(repo_root)
    gpu = detect_gpu_info()

    ckpt_sha: Optional[str] = None
    ckpt_str: Optional[str] = None
    if checkpoint_path is not None and checkpoint_path.exists():
        ckpt_str = str(checkpoint_path)
        ckpt_sha = compute_sha256(checkpoint_path)

    artifacts: List[Dict[str, str]] = []
    for art_path in output_artifact_paths or []:
        if art_path.exists():
            artifacts.append(
                {
                    "path": str(art_path),
                    "sha256": compute_sha256(art_path),
                    "size_bytes": str(art_path.stat().st_size),
                }
            )

    return ExperimentManifest(
        experiment_id=experiment_id,
        timestamp_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        git_repository=git_meta["repository"],
        git_branch=git_meta["branch"],
        git_commit_sha=git_meta["commit_sha"],
        python_version=platform.python_version(),
        dependency_versions=collect_dependency_versions(),
        gpu_model=str(gpu["gpu_model"]),
        gpu_device=str(gpu["device"]),
        vram_mb=gpu["vram_mb"],
        checkpoint_path=ckpt_str,
        checkpoint_sha256=ckpt_sha,
        dataset_version=dataset_version,
        execution_parameters=redact_sensitive_params(execution_parameters),
        output_artifacts=artifacts,
        execution_status=execution_status,
        notes=notes,
    )


def write_manifest(manifest: ExperimentManifest, output_path: Path) -> Path:
    """Persist manifest JSON to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(manifest), indent=2) + "\n", encoding="utf-8")
    return output_path


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    exp_id = os.environ.get("YORVYN_EXPERIMENT_ID", f"exp_{int(time.time())}")
    dataset_ver = os.environ.get("YORVYN_DATASET_VERSION", "untracked")
    ckpt_env = os.environ.get("YORVYN_CHECKPOINT_PATH", "").strip()
    ckpt = Path(ckpt_env) if ckpt_env else None
    out_file = root / "models" / "experiment_logs" / f"{exp_id}_manifest.json"
    manifest = build_experiment_manifest(
        repo_root=root,
        experiment_id=exp_id,
        dataset_version=dataset_ver,
        execution_parameters={"cli_entrypoint": True},
        checkpoint_path=ckpt,
        execution_status="SUCCEEDED",
    )
    write_manifest(manifest, out_file)
    print(f"Wrote reproducibility manifest: {out_file}")
