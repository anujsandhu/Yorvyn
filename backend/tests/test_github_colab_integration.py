"""Tests for GitHub backup safety rules and Colab reproducibility runner."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ops.colab_experiment_runner import (  # noqa: E402
    build_experiment_manifest,
    compute_sha256,
    redact_sensitive_params,
    write_manifest,
)


def test_gitattributes_tracks_large_binary_patterns() -> None:
    gitattributes = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    for ext in ("*.pt", "*.pth", "*.safetensors", "*.onnx", "*.glb"):
        assert f"{ext} filter=lfs" in gitattributes


def test_gitignore_excludes_secrets_and_runtime_binaries() -> None:
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in (".env", "models/generated_3d/", "models/checkpoints/*.pt", "dump.rdb", "backend.sock"):
        assert pattern in gitignore


def test_colab_notebook_valid_and_token_free() -> None:
    nb_path = REPO_ROOT / "notebooks" / "yorvyn_colab_gpu_worker.ipynb"
    raw = nb_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert data["nbformat"] == 4
    assert len(data["cells"]) >= 5
    for forbidden in ("ghp_", "github_pat_", "AIza", "sk_live_"):
        assert forbidden not in raw


def test_redact_sensitive_params_hides_tokens() -> None:
    redacted = redact_sensitive_params(
        {
            "target_branch": "release/stabilize-17.4",
            "github_token": "ghp_secret_value",
            "worker_api_key": "key_123",
            "batch_size": 4,
        }
    )
    assert redacted["target_branch"] == "release/stabilize-17.4"
    assert redacted["batch_size"] == 4
    assert redacted["github_token"] == "[REDACTED]"
    assert redacted["worker_api_key"] == "[REDACTED]"


def test_build_and_write_experiment_manifest(tmp_path: Path) -> None:
    ckpt = tmp_path / "dummy.pt"
    ckpt.write_bytes(b"yorvyn-checkpoint-bytes")
    artifact = tmp_path / "output.glb"
    artifact.write_bytes(b"glTF-binary-payload")

    manifest = build_experiment_manifest(
        repo_root=REPO_ROOT,
        experiment_id="test_exp_001",
        dataset_version="yorvyn_golden_v1",
        execution_parameters={"lr": 1e-4, "api_key": "must-not-leak"},
        checkpoint_path=ckpt,
        output_artifact_paths=[artifact],
        execution_status="SUCCEEDED",
    )

    out_path = write_manifest(manifest, tmp_path / "manifest.json")
    loaded = json.loads(out_path.read_text(encoding="utf-8"))

    assert loaded["experiment_id"] == "test_exp_001"
    assert loaded["git_commit_sha"] != "unknown"
    assert loaded["checkpoint_sha256"] == compute_sha256(ckpt)
    assert loaded["execution_parameters"]["api_key"] == "[REDACTED]"
    assert loaded["output_artifacts"][0]["sha256"] == compute_sha256(artifact)
    assert loaded["execution_status"] == "SUCCEEDED"
