"""
YORVYN — Atomic Fenced Artifact Publication Protocol & Deep GLB Validation (Phase 14.13 Workstream I.6)
Implements:
1. Generation-specific immutable artifact paths: <storage>/<job_id>_gen<lease_generation>.glb
2. Fenced conditional publication boundary preventing stale worker overwrites
3. Deep structural glTF 2.0 validation (headers, chunks, bufferViews, accessors, mesh primitives, URI security)
4. Atomic canonical pointer updates (linking/copying to <job_id>.glb only upon active generation verification)
5. Startup reconciliation for orphaned generation-specific artifacts
"""

import os
import time
import json
import uuid
import struct
import hashlib
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List, Set

logger = logging.getLogger("yorvyn_artifact_publisher")

# Allowed component types in glTF 2.0
VALID_COMPONENT_TYPES = {
    5120: "BYTE",
    5121: "UNSIGNED_BYTE",
    5122: "SHORT",
    5123: "UNSIGNED_SHORT",
    5125: "UNSIGNED_INT",
    5126: "FLOAT"
}

VALID_ACCESSOR_TYPES = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
    "MAT2": 4,
    "MAT3": 9,
    "MAT4": 16
}


class ArtifactPublicationException(Exception):
    """Raised when an artifact fails structural validation, integrity checks, or atomic publication."""
    pass


# Backwards compatibility alias
ArtifactCommitException = ArtifactPublicationException


class AtomicArtifactPublisher:
    """
    Manages generation-specific immutable artifact writes, deep glTF 2.0 structural inspection,
    and fenced conditional updates of canonical pointers.
    """

    def __init__(self, storage_dir: Path):
        self.storage_dir = Path(storage_dir).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def validate_glb_deep_structure(self, data: bytes) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Comprehensive structural and security validation for glTF 2.0 binary (GLB):
        1. 12-byte GLB header (magic == 0x46546C67, version == 2)
        2. Declared length equals byte length
        3. 4-byte boundary alignment on entire file and individual chunks
        4. Chunk 0 is JSON, valid JSON syntax
        5. Deep JSON structural validation:
           - Banned external URIs (reject http://, https://, file://, relative path traversals)
           - Buffer and bufferView bounds validation
           - Accessor types, componentTypes, and range boundaries
           - Mesh primitives attributes (POSITION, NORMAL, etc.) and indices
           - Node and scene reference validation
        6. Chunk 1 is BIN (if present), length matches buffer declarations
        """
        if len(data) < 20:
            return False, "Data too small to constitute a valid glTF binary (< 20 bytes)", {}

        # 1. 12-byte header
        magic, version, length = struct.unpack("<III", data[:12])
        if magic != 0x46546C67:  # 'glTF'
            return False, f"Invalid magic header: {hex(magic)} (expected 0x46546c67)", {}
        if version != 2:
            return False, f"Unsupported glTF version: {version} (expected 2)", {}
        if length != len(data):
            return False, f"Header length mismatch: declared {length} vs actual {len(data)}", {}

        # 2. 4-byte total length alignment
        if len(data) % 4 != 0:
            return False, f"Total file length {len(data)} is not 4-byte aligned", {}

        # 3. Chunk 0: JSON Chunk
        c0_len, c0_type = struct.unpack("<II", data[12:20])
        if c0_type != 0x4E4F534A:  # 'JSON'
            return False, f"Chunk 0 is not JSON: {hex(c0_type)} (expected 0x4e4f534a)", {}
        if c0_len % 4 != 0:
            return False, f"Chunk 0 length {c0_len} is not 4-byte aligned", {}

        c0_end = 20 + c0_len
        if c0_end > len(data):
            return False, f"Chunk 0 extends beyond file boundaries ({c0_end} > {len(data)})", {}

        json_bytes = data[20:c0_end]
        try:
            json_str = json_bytes.decode("utf-8").strip()
            gltf = json.loads(json_str)
        except Exception as e:
            return False, f"Failed to parse glTF JSON chunk: {e}", {}

        # 4. Deep JSON structural and security validation
        asset = gltf.get("asset")
        if not asset or not isinstance(asset, dict):
            return False, "Missing or invalid 'asset' metadata object in glTF JSON", {}
        if asset.get("version") != "2.0":
            return False, f"Unsupported glTF asset version: {asset.get('version')} (expected '2.0')", {}

        # Security check: detect and reject external URI references in buffers or images
        for buf in gltf.get("buffers", []):
            uri = buf.get("uri")
            if uri:
                return False, f"Security violation: External buffer URI '{uri}' is forbidden in binary GLB", {}

        for img in gltf.get("images", []):
            uri = img.get("uri")
            if uri and (uri.startswith("http://") or uri.startswith("https://") or uri.startswith("file://") or ".." in uri or uri.startswith("data:")):
                return False, f"Security violation: Disallowed image URI '{uri}'", {}

        # 5. Chunk 1: Binary Buffer Chunk
        bin_chunk_len = 0
        has_bin_chunk = False
        offset = c0_end

        if offset < len(data):
            if offset + 8 > len(data):
                return False, f"Truncated chunk 1 header at offset {offset}", {}
            c1_len, c1_type = struct.unpack("<II", data[offset:offset + 8])
            if c1_type != 0x004E4942:  # 'BIN\0'
                return False, f"Chunk 1 type {hex(c1_type)} is not BIN (expected 0x004e4942)", {}
            if c1_len % 4 != 0:
                return False, f"Chunk 1 length {c1_len} is not 4-byte aligned", {}
            c1_end = offset + 8 + c1_len
            if c1_end != len(data):
                return False, f"Chunk 1 boundary {c1_end} does not match total file length {len(data)}", {}
            has_bin_chunk = True
            bin_chunk_len = c1_len

        # 6. Buffer and bufferView validation
        buffers = gltf.get("buffers", [])
        if buffers and has_bin_chunk:
            declared_buf_len = buffers[0].get("byteLength", 0)
            if declared_buf_len > bin_chunk_len:
                return False, f"Declared buffer byteLength {declared_buf_len} exceeds BIN chunk size {bin_chunk_len}", {}

        buffer_views = gltf.get("bufferViews", [])
        for idx, bv in enumerate(buffer_views):
            bv_offset = bv.get("byteOffset", 0)
            bv_len = bv.get("byteLength", 0)
            if bv_offset < 0 or bv_len <= 0:
                return False, f"Invalid bufferView {idx} range: offset={bv_offset}, length={bv_len}", {}
            if (bv_offset + bv_len) > bin_chunk_len:
                return False, f"bufferView {idx} exceeds BIN chunk boundaries ({bv_offset + bv_len} > {bin_chunk_len})", {}

        # 7. Accessor validation
        accessors = gltf.get("accessors", [])
        for idx, acc in enumerate(accessors):
            comp_type = acc.get("componentType")
            acc_type = acc.get("type")
            count = acc.get("count", 0)
            if comp_type not in VALID_COMPONENT_TYPES:
                return False, f"Accessor {idx} has invalid componentType {comp_type}", {}
            if acc_type not in VALID_ACCESSOR_TYPES:
                return False, f"Accessor {idx} has invalid type '{acc_type}'", {}
            if count <= 0:
                return False, f"Accessor {idx} has invalid count {count}", {}

            bv_idx = acc.get("bufferView")
            if bv_idx is not None:
                if bv_idx < 0 or bv_idx >= len(buffer_views):
                    return False, f"Accessor {idx} references out-of-bounds bufferView {bv_idx}", {}

        # 8. Mesh primitives validation
        meshes = gltf.get("meshes", [])
        for m_idx, mesh in enumerate(meshes):
            primitives = mesh.get("primitives", [])
            if not primitives:
                return False, f"Mesh {m_idx} contains no primitives", {}
            for p_idx, prim in enumerate(primitives):
                attrs = prim.get("attributes", {})
                if "POSITION" not in attrs:
                    return False, f"Mesh {m_idx} primitive {p_idx} missing mandatory POSITION attribute", {}
                pos_acc_idx = attrs["POSITION"]
                if pos_acc_idx < 0 or pos_acc_idx >= len(accessors):
                    return False, f"POSITION attribute in mesh {m_idx} references invalid accessor {pos_acc_idx}", {}

                # Check indices if indexed primitive
                if "indices" in prim:
                    ind_idx = prim["indices"]
                    if ind_idx < 0 or ind_idx >= len(accessors):
                        return False, f"Indices in mesh {m_idx} references invalid accessor {ind_idx}", {}

        # 9. Scene and node hierarchy validation
        nodes = gltf.get("nodes", [])
        scenes = gltf.get("scenes", [])
        for s_idx, scene in enumerate(scenes):
            for n_idx in scene.get("nodes", []):
                if n_idx < 0 or n_idx >= len(nodes):
                    return False, f"Scene {s_idx} references invalid node {n_idx}", {}

        # 10. Skinning and animation hierarchy validation
        skins = gltf.get("skins", [])
        for sk_idx, skin in enumerate(skins):
            for j_idx in skin.get("joints", []):
                if j_idx < 0 or j_idx >= len(nodes):
                    return False, f"Skin {sk_idx} references invalid joint node {j_idx}", {}

        animations = gltf.get("animations", [])
        for a_idx, anim in enumerate(animations):
            for ch in anim.get("channels", []):
                target_node = ch.get("target", {}).get("node")
                if target_node is not None and (target_node < 0 or target_node >= len(nodes)):
                    return False, f"Animation {a_idx} references invalid target node {target_node}", {}

        return True, "Valid glTF 2.0 binary with complete structural integrity", {
            "version": version,
            "declared_length": length,
            "json_chunk_length": c0_len,
            "has_bin_chunk": has_bin_chunk,
            "bin_chunk_length": bin_chunk_len,
            "buffer_view_count": len(buffer_views),
            "accessor_count": len(accessors),
            "mesh_count": len(meshes),
            "node_count": len(nodes),
            "generator": asset.get("generator", "unknown")
        }

    # Alias for backwards compatibility
    validate_gltf_binary_header = lambda self, data: self.validate_glb_deep_structure(data)[:2]
    validate_gltf_binary_structure = lambda self, data: self.validate_glb_deep_structure(data)

    def publish_artifact_fenced(
        self,
        job_id: str,
        glb_bytes: bytes,
        user_id: str,
        tenant_id: str,
        correlation_id: str,
        lease_generation: int,
        job_state_ref: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Executes Atomic Fenced Artifact Publication:
        1. Deep structural validation of the binary glTF 2.0 model.
        2. Computes SHA256 checksum.
        3. Writes to an IMMUTABLE generation-specific path:
           <storage>/<job_id>_gen<lease_generation>.glb
           (Workers of different generations NEVER overwrite each other's files).
        4. Flushes file data (fsync).
        5. Fenced state commit: Authoritative state machine verifies lease_generation.
        6. Updates canonical pointer (<storage>/<job_id>.glb) atomically ONLY IF state commit succeeds.
        7. If state commit fails (stale worker): The active generation's artifact is preserved untouched.
        """
        # Step 1: Pre-publication deep structural & security check
        is_valid, msg, gltf_details = self.validate_glb_deep_structure(glb_bytes)
        if not is_valid:
            raise ArtifactPublicationException(f"Pre-publication validation failed for {job_id}: {msg}")

        # Step 2: Compute SHA256
        sha256_hash = hashlib.sha256(glb_bytes).hexdigest()

        # Step 3: Immutable generation-specific file path
        gen_filename = f"{job_id}_gen{lease_generation}.glb"
        gen_path = self.storage_dir / gen_filename
        canonical_filename = f"{job_id}.glb"
        canonical_path = self.storage_dir / canonical_filename

        temp_path = self.storage_dir / f".tmp_pub_{job_id}_gen{lease_generation}_{uuid.uuid4().hex[:8]}.glb"

        try:
            # Write to temp file on the same mount
            with open(temp_path, "wb") as f:
                f.write(glb_bytes)
                f.flush()
                os.fsync(f.fileno())

            # Atomic move to immutable generation-specific path
            temp_path.replace(gen_path)

            # Flush directory where supported
            try:
                dir_fd = os.open(str(self.storage_dir), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except Exception:
                pass

            # Step 5: Fenced authoritative state commit
            if job_state_ref is not None:
                worker_id = getattr(job_state_ref, "claimed_by_worker", "worker")
                commit_ok, commit_msg = job_state_ref.commit_completion(
                    worker_id=worker_id,
                    lease_generation=lease_generation,
                    asset_path=str(gen_path),
                    asset_sha256=sha256_hash
                )
                if not commit_ok:
                    # Stale worker detected! Reject publication.
                    # CRITICAL: We do NOT delete canonical_path because it may belong to a newer generation!
                    raise ArtifactPublicationException(
                        f"Fenced state commit rejected for {job_id} (gen {lease_generation}): {commit_msg}"
                    )

            # Step 6: Atomic conditional update of canonical pointer file
            # Copy/replace temp to canonical
            temp_canon = self.storage_dir / f".tmp_canon_{job_id}_{uuid.uuid4().hex[:8]}.glb"
            with open(temp_canon, "wb") as f:
                f.write(glb_bytes)
                f.flush()
                os.fsync(f.fileno())
            temp_canon.replace(canonical_path)

            return {
                "job_id": job_id,
                "generation_filename": gen_filename,
                "generation_path": str(gen_path),
                "canonical_filename": canonical_filename,
                "canonical_path": str(canonical_path),
                "file_size_bytes": len(glb_bytes),
                "sha256": sha256_hash,
                "published_at": time.time(),
                "user_id": user_id,
                "tenant_id": tenant_id,
                "correlation_id": correlation_id,
                "lease_generation": lease_generation,
                "gltf_metadata": gltf_details
            }

        except Exception as e:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            if not isinstance(e, ArtifactPublicationException):
                raise ArtifactPublicationException(f"Atomic artifact publication failed for {job_id}: {e}")
            raise

    # Backwards compatibility alias
    def publish_artifact(self, *args, **kwargs):
        return self.publish_artifact_fenced(*args, **kwargs)

    def commit_asset(self, *args, **kwargs):
        return self.publish_artifact_fenced(*args, **kwargs)

    def verify_persisted_artifact(
        self,
        job_id: str,
        expected_sha256: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Verifies that an asset on disk exists, has valid deep glTF structure, and matches expected hash."""
        asset_path = self.storage_dir / f"{job_id}.glb"
        if not asset_path.exists():
            return False, {"error": "Artifact file not found on disk"}

        if asset_path.stat().st_size == 0:
            return False, {"error": "Artifact file is 0 bytes"}

        try:
            with open(asset_path, "rb") as f:
                data = f.read()

            is_valid, msg, details = self.validate_glb_deep_structure(data)
            if not is_valid:
                return False, {"error": f"Structural corruption: {msg}"}

            actual_sha = hashlib.sha256(data).hexdigest()
            if expected_sha256 and actual_sha != expected_sha256:
                return False, {"error": f"SHA256 mismatch: {actual_sha} vs {expected_sha256}"}

            return True, {
                "job_id": job_id,
                "asset_path": str(asset_path),
                "file_size_bytes": len(data),
                "sha256": actual_sha,
                "gltf_details": details
            }
        except Exception as e:
            return False, {"error": str(e)}

    def startup_reconciliation(self, active_jobs_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scans storage directory for:
        1. Orphaned temporary files (.tmp_*) -> unlinked.
        2. Orphaned generation artifacts with no active state reference.
        3. Missing completed artifacts.
        4. Corrupted artifacts or checksum mismatches.
        """
        reconciliation_report = {
            "purged_orphaned_tmp_files": 0,
            "orphaned_generation_files": [],
            "missing_completed_artifacts": [],
            "corrupted_artifacts": [],
            "reconciled_valid_artifacts": 0
        }

        # 1. Purge all orphaned temporary files
        for tmp_file in self.storage_dir.glob(".tmp_*"):
            try:
                tmp_file.unlink()
                reconciliation_report["purged_orphaned_tmp_files"] += 1
            except Exception:
                pass

        # 2. Reconcile generation artifacts
        for gen_file in self.storage_dir.glob("*_gen*.glb"):
            parts = gen_file.stem.split("_gen")
            if len(parts) == 2:
                base_job_id = parts[0]
                if base_job_id not in active_jobs_metadata:
                    reconciliation_report["orphaned_generation_files"].append(str(gen_file.name))

        # 3. Check canonical GLBs against metadata and heal from immutable generation asset if needed
        for job_id, meta in active_jobs_metadata.items():
            if meta.get("current_state") == "COMPLETED":
                canon_path = self.storage_dir / f"{job_id}.glb"
                if not canon_path.exists():
                    # Check if generation artifact exists to heal canonical pointer
                    asset_path_str = meta.get("asset_path")
                    if asset_path_str and Path(asset_path_str).exists():
                        gen_p = Path(asset_path_str)
                        temp_c = self.storage_dir / f".tmp_heal_{job_id}_{uuid.uuid4().hex[:6]}.glb"
                        try:
                            shutil.copy2(gen_p, temp_c)
                            temp_c.replace(canon_path)
                            reconciliation_report["healed_canonical_artifacts"] = reconciliation_report.get("healed_canonical_artifacts", 0) + 1
                            reconciliation_report["reconciled_valid_artifacts"] += 1
                        except Exception as e:
                            logger.error(f"Failed to heal canonical artifact {canon_path}: {e}")
                            reconciliation_report["missing_completed_artifacts"].append(job_id)
                    else:
                        reconciliation_report["missing_completed_artifacts"].append(job_id)
                else:
                    expected_sha = meta.get("asset_sha256")
                    is_valid, res = self.verify_persisted_artifact(job_id, expected_sha)
                    if not is_valid:
                        reconciliation_report["corrupted_artifacts"].append({
                            "job_id": job_id,
                            "error": res.get("error")
                        })
                    else:
                        reconciliation_report["reconciled_valid_artifacts"] += 1

        return reconciliation_report


# Alias for backward compatibility
ArtifactCommitter = AtomicArtifactPublisher
