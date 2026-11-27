"""
YORVYN — Unified Application Cache Service (Phase 17.6)

Provides multi-tier caching (in-process bounded LRU L1 + Redis L2) with:
- Namespaced & versioned keys (`yorvyn:cache:v{ver}:{namespace}:{owner}:{key}`)
- Strict owner isolation (public vs owner_id scoping)
- Single-flight stampede protection (`get_or_set`)
- Graceful Redis outage fallback
- Instant namespace version bump invalidation & prefix cleanup
- Cache hit/miss/error telemetry
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class AppCacheService:
    """Thread-safe L1 LRU + optional Redis L2 cache with stampede protection."""

    def __init__(
        self,
        *,
        redis_host: Optional[str] = None,
        redis_port: Optional[int] = None,
        max_l1_entries: int = 1024,
        enable_redis: bool = True,
    ) -> None:
        self._lock = threading.RLock()
        self._key_locks: Dict[str, threading.Lock] = {}
        self._l1: "OrderedDict[str, Tuple[float, str]]" = OrderedDict()
        self._max_l1_entries = max(32, max_l1_entries)
        self._namespace_versions: Dict[str, int] = {}
        self._redis_client: Any = None
        self._enable_redis = enable_redis
        self._redis_host = redis_host or os.getenv("REDIS_HOST", "localhost")
        self._redis_port = int(redis_port or os.getenv("REDIS_PORT", "6379"))
        self._stats: Dict[str, int] = {
            "hits": 0,
            "l1_hits": 0,
            "redis_hits": 0,
            "misses": 0,
            "sets": 0,
            "invalidations": 0,
            "redis_errors": 0,
            "stampede_waiters": 0,
        }
        if self._enable_redis:
            self._init_redis()

    def _init_redis(self) -> None:
        try:
            import redis

            client = redis.Redis(
                host=self._redis_host,
                port=self._redis_port,
                socket_connect_timeout=0.4,
                socket_timeout=0.4,
                decode_responses=True,
            )
            client.ping()
            self._redis_client = client
        except Exception as exc:
            logger.debug(f"[AppCacheService] Redis unavailable, using bounded L1 cache fallback: {exc}")
            self._redis_client = None

    def _get_key_lock(self, full_key: str) -> threading.Lock:
        with self._lock:
            lock = self._key_locks.get(full_key)
            if lock is None:
                lock = threading.Lock()
                if len(self._key_locks) > 4096:
                    self._key_locks.clear()
                self._key_locks[full_key] = lock
            return lock

    def get_namespace_version(self, namespace: str) -> int:
        with self._lock:
            return self._namespace_versions.get(namespace, 1)

    def bump_namespace_version(self, namespace: str) -> int:
        with self._lock:
            new_ver = self._namespace_versions.get(namespace, 1) + 1
            self._namespace_versions[namespace] = new_ver
            self._stats["invalidations"] += 1
            return new_ver

    def build_key(
        self,
        namespace: str,
        key: str,
        *,
        owner_id: Optional[str] = None,
        is_public: bool = False,
    ) -> str:
        if not is_public and not owner_id:
            raise ValueError("Non-public cache keys must specify owner_id to preserve tenant isolation.")
        owner_scope = "public" if is_public else f"owner:{owner_id}"
        ns_ver = self.get_namespace_version(namespace)
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24] if len(key) > 64 else key
        return f"yorvyn:cache:v{ns_ver}:{namespace}:{owner_scope}:{digest}"

    def get(
        self,
        namespace: str,
        key: str,
        *,
        owner_id: Optional[str] = None,
        is_public: bool = False,
    ) -> Optional[Any]:
        full_key = self.build_key(namespace, key, owner_id=owner_id, is_public=is_public)
        now = time.time()

        with self._lock:
            entry = self._l1.get(full_key)
            if entry is not None:
                expires_at, raw = entry
                if expires_at > now:
                    self._l1.move_to_end(full_key)
                    self._stats["hits"] += 1
                    self._stats["l1_hits"] += 1
                    try:
                        return json.loads(raw)
                    except Exception:
                        self._l1.pop(full_key, None)
                else:
                    self._l1.pop(full_key, None)

        if self._redis_client is not None:
            try:
                raw_redis = self._redis_client.get(full_key)
                if raw_redis is not None:
                    parsed = json.loads(raw_redis)
                    with self._lock:
                        self._stats["hits"] += 1
                        self._stats["redis_hits"] += 1
                        self._set_l1(full_key, raw_redis, ttl_seconds=60)
                    return parsed
            except Exception as exc:
                with self._lock:
                    self._stats["redis_errors"] += 1
                logger.debug(f"[AppCacheService] Redis get fallback for {namespace}: {exc}")

        with self._lock:
            self._stats["misses"] += 1
        return None

    def _set_l1(self, full_key: str, serialized: str, ttl_seconds: int) -> None:
        self._l1[full_key] = (time.time() + max(1, ttl_seconds), serialized)
        self._l1.move_to_end(full_key)
        while len(self._l1) > self._max_l1_entries:
            self._l1.popitem(last=False)

    def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        *,
        ttl_seconds: int = 300,
        owner_id: Optional[str] = None,
        is_public: bool = False,
    ) -> bool:
        full_key = self.build_key(namespace, key, owner_id=owner_id, is_public=is_public)
        serialized = json.dumps(value, separators=(",", ":"), sort_keys=True)

        with self._lock:
            self._set_l1(full_key, serialized, ttl_seconds)
            self._stats["sets"] += 1

        if self._redis_client is not None:
            try:
                self._redis_client.setex(full_key, max(1, int(ttl_seconds)), serialized)
            except Exception as exc:
                with self._lock:
                    self._stats["redis_errors"] += 1
                logger.debug(f"[AppCacheService] Redis setex skipped cleanly: {exc}")
        return True

    def get_or_set(
        self,
        namespace: str,
        key: str,
        factory: Callable[[], Any],
        *,
        ttl_seconds: int = 300,
        owner_id: Optional[str] = None,
        is_public: bool = False,
    ) -> Tuple[Any, bool]:
        """Single-flight stampede-protected lookup. Returns (value, cache_hit)."""
        cached = self.get(namespace, key, owner_id=owner_id, is_public=is_public)
        if cached is not None:
            return cached, True

        full_key = self.build_key(namespace, key, owner_id=owner_id, is_public=is_public)
        key_lock = self._get_key_lock(full_key)
        with key_lock:
            # Double-check after acquiring per-key lock (coalesces stampeding callers)
            cached_again = self.get(namespace, key, owner_id=owner_id, is_public=is_public)
            if cached_again is not None:
                with self._lock:
                    self._stats["stampede_waiters"] += 1
                return cached_again, True
            fresh = factory()
            if fresh is not None:
                self.set(
                    namespace,
                    key,
                    fresh,
                    ttl_seconds=ttl_seconds,
                    owner_id=owner_id,
                    is_public=is_public,
                )
            return fresh, False

    def invalidate(
        self,
        namespace: str,
        key: str,
        *,
        owner_id: Optional[str] = None,
        is_public: bool = False,
    ) -> None:
        full_key = self.build_key(namespace, key, owner_id=owner_id, is_public=is_public)
        with self._lock:
            self._l1.pop(full_key, None)
            self._stats["invalidations"] += 1
        if self._redis_client is not None:
            try:
                self._redis_client.delete(full_key)
            except Exception:
                with self._lock:
                    self._stats["redis_errors"] += 1

    def invalidate_owner(self, owner_id: str) -> int:
        marker = f":owner:{owner_id}:"
        removed = 0
        with self._lock:
            victims = [k for k in self._l1.keys() if marker in k]
            for k in victims:
                self._l1.pop(k, None)
                removed += 1
            self._stats["invalidations"] += removed
        if self._redis_client is not None:
            try:
                for k in self._redis_client.scan_iter(match=f"yorvyn:cache:*{marker}*"):
                    self._redis_client.delete(k)
            except Exception:
                with self._lock:
                    self._stats["redis_errors"] += 1
        return removed

    def clear_all(self) -> None:
        with self._lock:
            self._l1.clear()
            self._stats["invalidations"] += 1

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_ratio = round(self._stats["hits"] / total, 4) if total > 0 else 0.0
            return {
                **self._stats,
                "l1_entries": len(self._l1),
                "max_l1_entries": self._max_l1_entries,
                "hit_ratio": hit_ratio,
                "redis_connected": self._redis_client is not None,
            }


app_cache = AppCacheService()
