# YORVYN — PHASE 14.9 SECURITY AUDIT
## Cryptographic Provenance, HMAC Authentication, Replay Windows & Path Traversal Hardening
**Phase:** 14.9 | **Workstream:** K | **Standard:** Principal Security & ML Systems Engineer  
**Baseline Commit:** `7139fc7eea4e1f890e28da9140db2e8550081267`

---

## 1. Executive Summary

Phase 14.9 establishes comprehensive security auditing for the remote and local neural 3D reconstruction endpoints.
All API communications, asset storage, and inference pipelines are hardened against unauthorized execution, replay attacks, resource exhaustion, and path traversal vulnerabilities.

### Security Audit Scorecard
- **Cryptographic Request Authentication:** PASS (HMAC-SHA256 signature verification)
- **Replay Attack Mitigation:** PASS (Nonce cache with 300s sliding expiration window)
- **Payload Size Limiting:** PASS (25 MB strict enforcement, 413 Payload Too Large)
- **Arbitrary File Read / Path Traversal:** PASS (Regex sanitization + Path.is_relative_to boundary check)
- **Asset Provenance Tracking:** PASS (SHA-256 hash of input image, model checkpoint, and pipeline operations embedded in metadata)

---

## 2. Security Controls Implementation Audit

### 1. HMAC-SHA256 Request Signing
Every incoming job submission to `/v1/reconstruction/jobs` must present:
- `X-API-Key`: Staging API authentication token.
- `X-Timestamp`: Unix timestamp (verified within ±300s drift).
- `X-Nonce`: UUIDv4 unique identifier.
- `X-Signature`: Hex-encoded HMAC-SHA256 computed over `{timestamp}.{nonce}.{body_hash}` using `GARMENT_AI_REMOTE_SIGNING_SECRET`.

### 2. Replay Prevention Window
- Nonces are stored in a runtime lookup table (`SEEN_NONCES`).
- Any nonce repeated within the 300-second window is rejected with `401 Unauthorized (Replay detected)`.
- A periodic eviction routine purges nonces older than 300 seconds to prevent unbounded memory growth.

### 3. Path Traversal Hardening on Asset Delivery
The asset delivery endpoint `/v1/reconstruction/assets/{asset_name}` enforces:
```python
if not re.match(r"^[a-zA-Z0-9_\-\.]+$", asset_name):
    raise HTTPException(status_code=400, detail="Invalid asset name format")
target_file = (STORAGE_DIR / asset_name).resolve()
if not target_file.is_relative_to(STORAGE_DIR.resolve()):
    raise HTTPException(status_code=403, detail="Access denied: directory traversal detected")
```
Tested against `../../etc/passwd` and URL-encoded traversal payloads: all rejected with `400 Bad Request` or `403 Forbidden`.

### 4. Memory & Denial-of-Service Defense
- Payload bodies larger than 25,000,000 bytes trigger immediate streaming abort.
- Background worker jobs implement cooperative cancellation via `/v1/reconstruction/jobs/{id}/cancel`.
