"""Tests & benchmarks for Phase 17.6 Multi-Layer Caching, HTTP Headers, AI Reuse & Performance."""

from __future__ import annotations

import concurrent.futures
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from backend.app.core.cache_service import AppCacheService, app_cache
from backend.app.core.settings import settings
from backend.app.main import app
from backend.app.services.ai.ai_computation_cache import AIComputationCache


client = TestClient(app)


def _auth_header(user_id: str = "usr_cache_a") -> dict[str, str]:
    now = int(time.time())
    tok = jwt.encode(
        {"sub": user_id, "role": "authenticated", "aud": "authenticated", "iat": now, "exp": now + 3600},
        settings.supabase_jwt_secret or settings.secret_key,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {tok}"}


def test_cache_hit_miss_ttl_and_lru_eviction() -> None:
    cache = AppCacheService(max_l1_entries=32, enable_redis=False)
    assert cache.get("taxonomy", "tops", is_public=True) is None

    cache.set("taxonomy", "tops", {"cat": "top"}, ttl_seconds=1, is_public=True)
    assert cache.get("taxonomy", "tops", is_public=True) == {"cat": "top"}

    # Bounded LRU eviction check
    for i in range(40):
        cache.set("catalog", f"k_{i}", {"idx": i}, ttl_seconds=60, is_public=True)
    assert cache.get_stats()["l1_entries"] <= 32

    # Wait for 1s TTL expiration on tops
    time.sleep(1.05)
    assert cache.get("taxonomy", "tops", is_public=True) is None


def test_concurrent_cache_stampede_protection() -> None:
    cache = AppCacheService(enable_redis=False)
    calls = 0

    def expensive_compute():
        nonlocal calls
        calls += 1
        time.sleep(0.03)
        return {"computed": 42}

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futures = [
            pool.submit(
                cache.get_or_set,
                "heavy_op",
                "same_key",
                expensive_compute,
                ttl_seconds=60,
                is_public=True,
            )
            for _ in range(12)
        ]
        results = [f.result() for f in futures]

    assert calls == 1
    assert all(val == {"computed": 42} for val, _ in results)


def test_redis_outage_falls_back_gracefully_without_error() -> None:
    class BrokenRedis:
        def get(self, _k):
            raise ConnectionError("redis down")

        def setex(self, _k, _ttl, _v):
            raise ConnectionError("redis down")

    cache = AppCacheService(enable_redis=False)
    cache._redis_client = BrokenRedis()

    cache.set("taxonomy", "dresses", {"ok": True}, ttl_seconds=30, is_public=True)
    assert cache.get("taxonomy", "dresses", is_public=True) == {"ok": True}
    assert cache.get_stats()["redis_errors"] >= 1


def test_private_owner_isolation_and_selective_invalidation() -> None:
    cache = AppCacheService(enable_redis=False)
    with pytest.raises(ValueError, match="owner_id"):
        cache.set("wardrobe", "items", [{"id": "1"}])

    cache.set("wardrobe", "items", [{"id": "a1"}], owner_id="usr_A", is_public=False)
    cache.set("wardrobe", "items", [{"id": "b1"}], owner_id="usr_B", is_public=False)

    assert cache.get("wardrobe", "items", owner_id="usr_A") == [{"id": "a1"}]
    assert cache.get("wardrobe", "items", owner_id="usr_B") == [{"id": "b1"}]

    cache.invalidate_owner("usr_A")
    assert cache.get("wardrobe", "items", owner_id="usr_A") is None
    assert cache.get("wardrobe", "items", owner_id="usr_B") == [{"id": "b1"}]

    # Namespace version bump invalidates cleanly across keys
    cache.set("taxonomy", "v_check", {"v": 1}, is_public=True)
    cache.bump_namespace_version("taxonomy")
    assert cache.get("taxonomy", "v_check", is_public=True) is None


def test_ai_computation_cache_invalidates_on_checkpoint_change_and_isolates_users() -> None:
    cache = AppCacheService(enable_redis=False)
    ai_cache = AIComputationCache(cache=cache)
    img_bytes = b"sample-garment-image-payload"

    calls = 0

    def run_model():
        nonlocal calls
        calls += 1
        return {"category": "tops", "confidence": 0.94}

    res1, hit1 = ai_cache.get_or_compute(
        owner_id="usr_A",
        operation="classify",
        input_bytes=img_bytes,
        model_id="mobilenetv3",
        checkpoint_sha256="sha_v6_aaa111",
        compute_fn=run_model,
    )
    res2, hit2 = ai_cache.get_or_compute(
        owner_id="usr_A",
        operation="classify",
        input_bytes=img_bytes,
        model_id="mobilenetv3",
        checkpoint_sha256="sha_v6_aaa111",
        compute_fn=run_model,
    )
    # Cross-user must miss & recompute inside usr_B scope
    res3, hit3 = ai_cache.get_or_compute(
        owner_id="usr_B",
        operation="classify",
        input_bytes=img_bytes,
        model_id="mobilenetv3",
        checkpoint_sha256="sha_v6_aaa111",
        compute_fn=run_model,
    )
    # Checkpoint update must miss & recompute for usr_A
    res4, hit4 = ai_cache.get_or_compute(
        owner_id="usr_A",
        operation="classify",
        input_bytes=img_bytes,
        model_id="mobilenetv3",
        checkpoint_sha256="sha_v7_bbb222",
        compute_fn=run_model,
    )

    assert hit1 is False and hit2 is True and hit3 is False and hit4 is False
    assert calls == 3
    assert res1 == res2 == res3 == res4


def test_http_etag_gzip_and_private_glb_cache_headers(tmp_path: Path) -> None:
    # 1. Public plans endpoint: ETag + 304 + public Cache-Control + GZip support
    r1 = client.get("/api/billing/plans", headers={"Accept-Encoding": "gzip"})
    assert r1.status_code == 200
    assert "max-age=300" in (r1.headers.get("cache-control") or "")
    etag = r1.headers.get("etag")
    assert etag

    r2 = client.get("/api/billing/plans", headers={"If-None-Match": etag})
    assert r2.status_code == 304

    # 2. Performance telemetry endpoint (no PII)
    perf = client.get("/api/ops/performance")
    assert perf.status_code == 200
    pbody = perf.json()
    assert "cache" in pbody and "ai_cache" in pbody

    # 3. Private GLB asset cache headers + Vary: Authorization
    fake_job_dir = tmp_path / "job_cache_1"
    fake_job_dir.mkdir()
    glb_file = fake_job_dir / "garment.glb"
    glb_file.write_bytes(b"glTF" + b"\x02\x00\x00\x00" + b"\x20\x00\x00\x00" + b"\x00" * 20)

    class _Job:
        user_id = "usr_cache_a"

    with patch("backend.app.api.garment_generation_routes.PERMANENT_ASSET_DIR", str(tmp_path)), patch(
        "backend.app.api.garment_generation_routes.garment_job_manager.get_job", return_value=_Job()
    ):
        headers = _auth_header("usr_cache_a")
        asset_r1 = client.get("/api/fashion/garment-gen/assets/job_cache_1/garment.glb", headers=headers)
        assert asset_r1.status_code == 200
        cc = asset_r1.headers.get("cache-control") or ""
        assert "private" in cc and "max-age=3600" in cc
        assert "Authorization" in (asset_r1.headers.get("vary") or "")
        asset_etag = asset_r1.headers.get("etag")
        assert asset_etag

        asset_r2 = client.get(
            "/api/fashion/garment-gen/assets/job_cache_1/garment.glb",
            headers={**headers, "If-None-Match": asset_etag},
        )
        assert asset_r2.status_code == 304


def test_reproducible_cache_latency_benchmark() -> None:
    app_cache.clear_all()
    t0 = time.perf_counter()
    for _ in range(50):
        # Simulated uncached JSON/dict lookup cost
        _ = app_cache.build_key("bench", "item_001", is_public=True)
        time.sleep(0.0005)
    uncached_ms = (time.perf_counter() - t0) * 1000.0

    app_cache.set("bench", "item_001", {"data": [1, 2, 3]}, ttl_seconds=60, is_public=True)
    t1 = time.perf_counter()
    for _ in range(50):
        val = app_cache.get("bench", "item_001", is_public=True)
        assert val == {"data": [1, 2, 3]}
    cached_ms = (time.perf_counter() - t1) * 1000.0

    assert cached_ms < uncached_ms
