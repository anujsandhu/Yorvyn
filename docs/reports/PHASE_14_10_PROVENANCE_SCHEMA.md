# YORVYN — PHASE 14.10 PROVENANCE SCHEMA & TAMPER-EVIDENT SPECIFICATION
## Cryptographic Model Fingerprinting, Procedural Null Enforcing & HMAC-SHA256 Verification
**Phase:** 14.10 | **Workstream:** A | **Standard:** Principal ML Infrastructure & Security Engineer  
**Baseline Commit:** `7139fc7eea4e1f890e28da9140db2e8550081267`

---

## 1. Forensic Audit & Hash Invalidation

In Phase 14.9, the reported checkpoint hash:
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
was forensically identified as the SHA-256 digest of an empty string (`b""`).

### Phase 14.10 Invalidation Rule:
1. `e3b0c442...` is permanently **blacklisted** across YORVYN. Any asset bearing this hash is automatically rejected as invalid.
2. Procedural and hybrid 3D engines must set `checkpoint_sha256 = null`. Calling a model "neural" when using procedural geometry is strictly prohibited.
3. Neural 2D parsing components declare `segmentation_checkpoint_sha256 = "8f86fd90c567afd4370b3cc3a7e81ed767a632b2832a738331af660acc0c4c68"`, computed from the exact 109,265,144 bytes of SegFormer's `model.safetensors`.
4. Neural 3D models compute `checkpoint_sha256` directly from disk bytes and verify the hash prior to loading.

---

## 2. 16-Field Authoritative Provenance Schema

| Field Name | Type | Description | Hybrid Mode Value | Parametric Mode Value |
| :--- | :--- | :--- | :--- | :--- |
| `engine_identity` | `string` | Unique engine service identifier | `"yorvyn_hybrid_reconstruction_engine"` | `"yorvyn_parametric_reconstruction_engine"` |
| `engine_mode` | `string` | Explicit execution modality | `"hybrid_reconstruction"` | `"parametric_reconstruction"` |
| `engine_version` | `string` | Engine release version | `"14.10.0"` | `"14.10.0"` |
| `model_id` | `string?` | Machine learning model ID | `"mattmdjaga/segformer_b2_clothes"` | `null` |
| `model_version` | `string?` | Machine learning model version | `"14.10.0"` | `null` |
| `checkpoint_sha256` | `string?` | Genuine byte-level SHA-256 of 3D checkpoint | `null` (Procedural 3D) | `null` (Procedural 3D) |
| `segmentation_checkpoint_sha256` | `string?` | Genuine byte-level SHA-256 of 2D segmenter | `"8f86fd90c567afd4370b3cc3a7e81ed767a632b2832a738331af660acc0c4c68"` | `null` |
| `source_code_revision` | `string` | Git commit HEAD hash | `"7139fc7eea4e1f890e28da9140db2e8550081267"` | `"7139fc7eea4e1f890e28da9140db2e8550081267"` |
| `configuration_sha256` | `string` | SHA-256 of pipeline configuration dict | `sha256(json(config))` | `sha256(json(config))` |
| `input_image_sha256` | `string` | SHA-256 of input PNG/JPEG photograph bytes | `sha256(image_bytes)` | `sha256(image_bytes)` |
| `output_glb_sha256` | `string` | SHA-256 of generated binary GLB asset | `sha256(glb_bytes)` | `sha256(glb_bytes)` |
| `inference_device` | `string` | Hardware accelerator used | `"mps"` (Apple Silicon) | `"mps"` |
| `inference_endpoint` | `string` | Worker API endpoint | `"local_mps_in_process"` | `"local_mps_in_process"` |
| `reconstruction_timestamp` | `string` | ISO 8601 UTC execution timestamp | e.g. `"2026-11-19T18:00:00Z"` | e.g. `"2026-11-19T18:00:00Z"` |
| `post_processing_operations` | `list[str]`| List of applied geometry/skinning filters | `["segformer_b2_parsing", ...]` | `["parametric_contour_profiling", ...]` |
| `provenance_signature` | `string` | HMAC-SHA256 signature preventing tampering | `hmac_sha256(signing_key, payload)` | `hmac_sha256(signing_key, payload)` |

---

## 3. Tamper-Evident Signature Construction

To guarantee that provenance cannot be altered post-hoc:
```python
sig_payload = f"{engine_identity}:{engine_mode}:{engine_version}:{input_image_sha256}:{output_glb_sha256}:{checkpoint_sha256}:{segmentation_checkpoint_sha256}:{reconstruction_timestamp}"
provenance_signature = hmac.new(SIGNING_KEY, sig_payload.encode(), hashlib.sha256).hexdigest()
```
If an adversary attempts to modify `output_glb_sha256`, swap `checkpoint_sha256`, or tamper with the timestamp, signature verification fails instantly.
