"""
YORVYN Intelligence Platform (YIP) — Phase 17.3 Tavily Web Intelligence Adapter & Security Firewall.

Integrates official Tavily REST API (`https://api.tavily.com` endpoints: `/search`,
`/extract`, `/research`, `/crawl`) using existing `httpx` client without extra SDK bloat.
Enforces:
- Strict URL / scheme / SSRF protection (blocks loopback, private, link-local, metadata IPs)
- HTML stripping, response byte caps, prompt-injection sanitization & zero tool/DB authority
- Per-user rate limiting, exponential backoff retries, TTL caching, circuit breaker & credit telemetry
- Strict separation between untrusted external web results and verified internal GarmentKnowledgeRAG
"""
from __future__ import annotations

import hashlib
import html
import ipaddress
import os
import random
import re
import socket
import threading
import time
from collections import OrderedDict, deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from pydantic import BaseModel, Field

from backend.app.core.settings import settings
from backend.app.services.intelligence.knowledge_rag import sanitize_retrieved_text

MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MB hard HTTP response limit
MAX_SNIPPET_CHARS = 3000
MAX_REDIRECT_HOPS = 0  # Disallow automatic external redirects unless explicitly validated
MAX_CONCURRENT_EXTERNAL_REQUESTS = 8
MAX_CACHE_ENTRIES = 256
PER_OWNER_DEFAULT_CREDIT_BUDGET = 200
_CGNAT_NET = ipaddress.ip_network("100.64.0.0/10")
_OBFUSCATED_IP_HOST_RE = re.compile(r"^(?:0x[0-9a-f]+|\d{7,}|(?:0[0-7]+|0x[0-9a-f]+|\d+)(?:\.(?:0[0-7]+|0x[0-9a-f]+|\d+)){1,3})$", re.I)

APPROVED_PUBLIC_FASHION_DOMAINS: Set[str] = {
    "vogue.com", "businessoffashion.com", "wwd.com", "fashionista.com",
    "cfda.com", "textileexchange.org", "fashionunited.com", "heddels.com",
    "wikimedia.org", "wikipedia.org",
}


class URLSecurityError(ValueError):
    """Raised when a URL fails SSRF, scheme, or approved-domain checks."""


class TavilyResultItem(BaseModel):
    provider_id: str = "tavily"
    request_id: Optional[str] = None
    source_url: str
    source_title: str = ""
    retrieved_content: str
    publication_date: Optional[str] = None  # Never fabricated if absent from API
    retrieval_timestamp: str
    domain: str
    relevance_score: Optional[float] = None
    content_hash: str
    extraction_status: str = "OK"
    injection_risk_detected: bool = False
    trust_classification: str = "UNTRUSTED_EXTERNAL_WEB"
    verification_status: str = "UNVERIFIED_EXTERNAL"
    executable_authority: bool = False
    auto_ingested_to_rag: bool = False


class TavilyOperationResponse(BaseModel):
    provider_id: str = "tavily"
    operation: str  # search | extract | research | crawl
    request_id: Optional[str] = None
    status: str  # OK | BLOCKED_NO_CREDENTIALS | CIRCUIT_OPEN | RATE_LIMITED | ERROR
    answer: Optional[str] = None
    results: List[TavilyResultItem] = Field(default_factory=list)
    failed_results: List[Dict[str, Any]] = Field(default_factory=list)
    cached: bool = False
    credits_used: int = 0
    error: Optional[str] = None
    verification_status: str = "UNVERIFIED_EXTERNAL"
    latency_ms: float = 0.0


class ExternalKnowledgeValidator:
    """SSRF-safe URL check, IPv4-mapped/obfuscated IP rejection, redirect guard, & injection firewall."""

    _TAG_RE = re.compile(r"<[^>]+>")
    _WS_RE = re.compile(r"\s+")

    @classmethod
    def _is_unsafe_ip(cls, ip_obj: Any) -> bool:
        if ip_obj is None:
            return False
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
        ):
            return True
        if isinstance(ip_obj, ipaddress.IPv4Address) and ip_obj in _CGNAT_NET:
            return True
        if isinstance(ip_obj, ipaddress.IPv6Address):
            if ip_obj.ipv4_mapped and cls._is_unsafe_ip(ip_obj.ipv4_mapped):
                return True
            if ip_obj.sixtofour and cls._is_unsafe_ip(ip_obj.sixtofour):
                return True
            if ip_obj.teredo and (
                cls._is_unsafe_ip(ip_obj.teredo[0]) or cls._is_unsafe_ip(ip_obj.teredo[1])
            ):
                return True
        return False

    @classmethod
    def validate_public_url(cls, url: str, *, resolve_dns: bool = True) -> Tuple[str, str]:
        if not url or not isinstance(url, str) or len(url) > 2048:
            raise URLSecurityError("URL missing or exceeds 2048 characters.")
        parsed = urlparse(url.strip())
        scheme = (parsed.scheme or "").lower()
        if scheme not in {"https", "http"}:
            raise URLSecurityError(f"Unsafe URL scheme '{scheme or 'empty'}' rejected.")
        if parsed.username or parsed.password or "@" in (parsed.netloc or ""):
            raise URLSecurityError("Embedded userinfo in URL is rejected by SSRF guard.")
        host = (parsed.hostname or "").strip().lower().rstrip(".")
        if not host:
            raise URLSecurityError("URL hostname is required.")
        if (
            host in {"localhost", "metadata.google.internal", "metadata", "ip6-localhost", "ip6-loopback"}
            or host.endswith((".local", ".internal", ".localhost", ".arpa"))
        ):
            raise URLSecurityError(f"Private/local hostname '{host}' rejected by SSRF guard.")

        # Direct IP literal check (covers IPv4, IPv6, IPv4-mapped IPv6 like ::ffff:127.0.0.1)
        try:
            ip_obj = ipaddress.ip_address(host)
        except ValueError:
            ip_obj = None
        if ip_obj is not None:
            if cls._is_unsafe_ip(ip_obj):
                raise URLSecurityError(f"Non-public/mapped IP target '{host}' rejected by SSRF guard.")
            return url.strip(), host

        # Reject decimal integer / hex / octal obfuscated IP forms (e.g. 2130706433, 0x7f000001, 0177.0.0.1)
        if _OBFUSCATED_IP_HOST_RE.match(host):
            raise URLSecurityError(f"Obfuscated numeric/octal/hex IP host '{host}' rejected by SSRF guard.")

        if resolve_dns:
            try:
                infos = socket.getaddrinfo(host, None)
                resolved_ips: List[str] = []
                for info in infos:
                    addr = info[4][0].split("%")[0]
                    r_ip = ipaddress.ip_address(addr)
                    if cls._is_unsafe_ip(r_ip):
                        raise URLSecurityError(f"Hostname '{host}' resolved to private/mapped IP '{addr}'; blocked by SSRF guard.")
                    resolved_ips.append(addr)
                # Detect trivial single-host DNS rebinding flip during validation window
                if resolved_ips:
                    infos_2 = socket.getaddrinfo(host, None)
                    for info2 in infos_2:
                        addr2 = info2[4][0].split("%")[0]
                        if cls._is_unsafe_ip(ipaddress.ip_address(addr2)):
                            raise URLSecurityError(f"Hostname '{host}' DNS rebound to unsafe IP '{addr2}'.")
            except URLSecurityError:
                raise
            except socket.gaierror:
                pass

        return url.strip(), host

    @classmethod
    def validate_redirect_target(
        cls,
        origin_url: str,
        location_header: str,
        *,
        allow_cross_origin: bool = False,
        resolve_dns: bool = True,
    ) -> Tuple[str, str]:
        """Validates an HTTP 3xx redirect destination against SSRF & cross-origin policy."""
        if not location_header:
            raise URLSecurityError("Redirect response missing Location header.")
        target_url = urljoin(origin_url, location_header.strip())
        clean_target, target_host = cls.validate_public_url(target_url, resolve_dns=resolve_dns)
        orig_p = urlparse(origin_url)
        targ_p = urlparse(clean_target)
        if not allow_cross_origin and (orig_p.scheme != targ_p.scheme or (orig_p.hostname or "").lower() != target_host):
            raise URLSecurityError(
                f"Cross-origin redirect from '{orig_p.hostname}' to '{target_host}' blocked by SSRF guard."
            )
        return clean_target, target_host

    @classmethod
    def sanitize_external_content(cls, raw_text: str) -> Tuple[str, bool, str]:
        unescaped = html.unescape(raw_text or "")
        # Scan BEFORE stripping HTML/XML comments so hidden directives inside tags/comments are flagged
        pre_sanitized, pre_flagged = sanitize_retrieved_text(unescaped)
        stripped_html = cls._TAG_RE.sub(" ", pre_sanitized)
        collapsed = cls._WS_RE.sub(" ", stripped_html).strip()[:MAX_SNIPPET_CHARS]
        sanitized, post_flagged = sanitize_retrieved_text(collapsed)
        flagged = bool(pre_flagged or post_flagged)
        chash = hashlib.sha256(sanitized.encode("utf-8")).hexdigest()
        return sanitized, flagged, chash

    @staticmethod
    def classify_trust(domain: str) -> str:
        dl = domain.lower().lstrip("www.")
        if any(dl == d or dl.endswith(f".{d}") for d in APPROVED_PUBLIC_FASHION_DOMAINS):
            return "APPROVED_PUBLIC_DOMAIN_EXTERNAL"
        return "UNTRUSTED_EXTERNAL_WEB"


class TavilyWebIntelligenceAdapter:
    """Governed HTTP client for Tavily REST API (`/search`, `/extract`, `/research`, `/crawl`)."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_s: Optional[float] = None,
        cache_ttl_s: float = 900.0,
        rate_limit_per_min: int = 20,
        per_owner_credit_budget: int = PER_OWNER_DEFAULT_CREDIT_BUDGET,
        global_credit_budget: Optional[int] = None,
        max_concurrent_requests: int = MAX_CONCURRENT_EXTERNAL_REQUESTS,
        max_retries: int = 2,
        failure_threshold: int = 3,
        circuit_recovery_s: float = 60.0,
        transport: Optional[httpx.BaseTransport] = None,
        resolve_dns: bool = True,
    ) -> None:
        self._explicit_key = api_key
        self.base_url = (base_url or settings.tavily_base_url or "https://api.tavily.com").rstrip("/")
        self.timeout_s = float(timeout_s if timeout_s is not None else settings.tavily_timeout_seconds)
        self.cache_ttl_s = float(cache_ttl_s)
        self.rate_limit_per_min = int(rate_limit_per_min)
        self.per_owner_credit_budget = int(per_owner_credit_budget)
        self.global_credit_budget = int(global_credit_budget if global_credit_budget is not None else settings.tavily_monthly_credit_budget)
        self.max_retries = max(0, min(int(max_retries), 3))
        self.failure_threshold = int(failure_threshold)
        self.circuit_recovery_s = float(circuit_recovery_s)
        self._transport = transport
        self._resolve_dns = resolve_dns

        self._lock = threading.Lock()
        self._inflight_lock = threading.Lock()
        self._inflight: Dict[str, threading.Event] = {}
        self._concurrency_sem = threading.BoundedSemaphore(max(1, int(max_concurrent_requests)))
        self._cache: "OrderedDict[str, Tuple[float, TavilyOperationResponse]]" = OrderedDict()
        self._user_windows: Dict[str, Deque[float]] = {}
        self._owner_credits: Dict[str, int] = {}
        self._usage_audit: List[Dict[str, Any]] = []
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0
        self._telemetry: Dict[str, Any] = {
            "requests_total": 0,
            "cache_hits": 0,
            "rate_limited": 0,
            "budget_rejected": 0,
            "redirect_blocked": 0,
            "coalesced_requests": 0,
            "failures": 0,
            "credits_used": 0,
            "live_verified_calls": 0,
            "mocked_calls": 0,
            "last_error": None,
        }

    def _get_api_key(self) -> str:
        return (self._explicit_key if self._explicit_key is not None else (settings.tavily_api_key or os.getenv("TAVILY_API_KEY", ""))).strip()

    @property
    def is_configured(self) -> bool:
        return bool(self._get_api_key())

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            return {
                "provider_id": "tavily",
                "configured": self.is_configured,
                "base_url": self.base_url,
                "circuit_open": now < self._circuit_open_until,
                "consecutive_failures": self._consecutive_failures,
                "telemetry": dict(self._telemetry),
                "cache_entries": len(self._cache),
                "monthly_credit_budget": self.global_credit_budget,
                "per_owner_credit_budget": self.per_owner_credit_budget,
                "usage_audit_count": len(self._usage_audit),
            }

    def get_owner_usage(self, owner_id: str) -> Dict[str, Any]:
        uid = str(owner_id)
        with self._lock:
            return {
                "owner_id": uid,
                "credits_used": self._owner_credits.get(uid, 0),
                "credit_budget": self.per_owner_credit_budget,
            }

    def _check_budget(self, owner_id: str, est_credits: int) -> Tuple[bool, Optional[str]]:
        uid = str(owner_id)
        with self._lock:
            global_used = int(self._telemetry.get("credits_used", 0))
            if global_used + est_credits > self.global_credit_budget:
                self._telemetry["budget_rejected"] += 1
                return False, "GLOBAL_BUDGET_EXCEEDED"
            owner_used = self._owner_credits.get(uid, 0)
            if owner_used + est_credits > self.per_owner_credit_budget:
                self._telemetry["budget_rejected"] += 1
                return False, "OWNER_BUDGET_EXCEEDED"
            return True, None

    def _record_usage_audit(self, owner_id: str, operation: str, credits: int, status: str) -> None:
        uid = str(owner_id)
        with self._lock:
            self._telemetry["credits_used"] += credits
            self._owner_credits[uid] = self._owner_credits.get(uid, 0) + credits
            self._usage_audit.append({
                "owner_hash": hashlib.sha256(uid.encode()).hexdigest()[:12],
                "operation": operation,
                "credits": credits,
                "status": status,
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            if len(self._usage_audit) > 500:
                self._usage_audit = self._usage_audit[-500:]

    def _check_rate_limit(self, owner_id: str) -> bool:
        now = time.monotonic()
        with self._lock:
            dq = self._user_windows.setdefault(str(owner_id), deque())
            while dq and now - dq[0] > 60.0:
                dq.popleft()
            if len(dq) >= self.rate_limit_per_min:
                self._telemetry["rate_limited"] += 1
                return False
            dq.append(now)
            return True

    def _post_with_retry(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        *,
        owner_id: str,
        session_id: Optional[str] = None,
        overall_deadline_s: Optional[float] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        api_key = self._get_api_key()
        if not api_key:
            return None, "NO_CREDENTIALS"

        now = time.monotonic()
        with self._lock:
            if now < self._circuit_open_until:
                return None, "CIRCUIT_OPEN"

        if not self._concurrency_sem.acquire(timeout=min(1.0, self.timeout_s)):
            return None, "CONCURRENCY_LIMIT_EXCEEDED"

        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-Project-ID": "yorvyn-yip-17.4",
            }
            if session_id:
                headers["X-Session-Id"] = str(session_id)[:128]

            url = f"{self.base_url}{endpoint}"
            ExternalKnowledgeValidator.validate_public_url(url, resolve_dns=self._resolve_dns)

            deadline_at = time.monotonic() + float(overall_deadline_s if overall_deadline_s is not None else max(self.timeout_s * 1.5, 2.0))
            last_err = "UNKNOWN_ERROR"
            max_attempts = self.max_retries + 1
            for attempt in range(max_attempts):
                remaining = deadline_at - time.monotonic()
                if remaining <= 0:
                    last_err = "DEADLINE_EXCEEDED"
                    break
                per_try_timeout = min(self.timeout_s, max(0.05, remaining))
                try:
                    client_kwargs: Dict[str, Any] = {
                        "timeout": httpx.Timeout(per_try_timeout, connect=min(5.0, per_try_timeout), read=per_try_timeout),
                        "follow_redirects": False,
                    }
                    if self._transport is not None:
                        client_kwargs["transport"] = self._transport
                    with httpx.Client(**client_kwargs) as client:
                        with client.stream("POST", url, json=payload, headers=headers) as resp:
                            if 300 <= resp.status_code < 400:
                                loc = resp.headers.get("location", "")
                                with self._lock:
                                    self._telemetry["redirect_blocked"] += 1
                                try:
                                    ExternalKnowledgeValidator.validate_redirect_target(
                                        url, loc, allow_cross_origin=False, resolve_dns=self._resolve_dns
                                    )
                                except URLSecurityError as exc:
                                    return None, f"REDIRECT_BLOCKED_SSRF:{exc}"
                                return None, "REDIRECT_DISALLOWED"

                            chunks: List[bytes] = []
                            total_bytes = 0
                            for chunk in resp.iter_bytes():
                                if time.monotonic() > deadline_at:
                                    last_err = "DEADLINE_EXCEEDED"
                                    raise httpx.ReadTimeout("Overall external request deadline exceeded")
                                total_bytes += len(chunk)
                                if total_bytes > MAX_RESPONSE_BYTES:
                                    return None, "RESPONSE_TOO_LARGE"
                                chunks.append(chunk)
                            body_bytes = b"".join(chunks)

                    if resp.status_code == 200:
                        import json as _json
                        data = _json.loads(body_bytes.decode("utf-8"))
                        if not isinstance(data, dict):
                            return None, "MALFORMED_RESPONSE"
                        with self._lock:
                            self._consecutive_failures = 0
                        return data, None
                    if resp.status_code in {401, 403}:
                        last_err = f"AUTH_ERROR_{resp.status_code}"
                        with self._lock:
                            self._telemetry["failures"] += 1
                            self._telemetry["last_error"] = last_err
                        return None, last_err
                    if resp.status_code == 429:
                        last_err = "PROVIDER_RATE_LIMITED"
                    elif resp.status_code >= 500:
                        last_err = f"PROVIDER_HTTP_{resp.status_code}"
                    else:
                        return None, f"PROVIDER_HTTP_{resp.status_code}"
                except URLSecurityError as exc:
                    return None, f"SSRF_BLOCKED:{exc}"
                except httpx.TimeoutException:
                    last_err = "TIMEOUT"
                except (httpx.HTTPError, ValueError, UnicodeDecodeError) as exc:
                    last_err = f"NETWORK_OR_PARSE_ERROR:{type(exc).__name__}"

                if attempt < max_attempts - 1:
                    rem_sleep = deadline_at - time.monotonic()
                    if rem_sleep <= 0.01:
                        break
                    jitter = random.uniform(0.0, 0.03)
                    time.sleep(min(rem_sleep, 0.05 * (2 ** attempt) + jitter))

            with self._lock:
                self._consecutive_failures += 1
                self._telemetry["failures"] += 1
                self._telemetry["last_error"] = last_err
                if self._consecutive_failures >= self.failure_threshold:
                    self._circuit_open_until = time.monotonic() + self.circuit_recovery_s
            return None, last_err
        finally:
            self._concurrency_sem.release()

    def _normalize_items(
        self,
        raw_results: List[Dict[str, Any]],
        *,
        request_id: Optional[str],
        verif_status: str,
        extraction_mode: str = "OK",
    ) -> List[TavilyResultItem]:
        now_iso = datetime.now(timezone.utc).isoformat()
        seen_hashes: Set[str] = set()
        out: List[TavilyResultItem] = []
        for item in raw_results or []:
            if not isinstance(item, dict):
                continue
            raw_url = str(item.get("url") or "")
            try:
                clean_url, host = ExternalKnowledgeValidator.validate_public_url(raw_url, resolve_dns=self._resolve_dns)
            except URLSecurityError:
                continue
            raw_text = str(item.get("raw_content") or item.get("content") or item.get("snippet") or "")
            sanitized, flagged, chash = ExternalKnowledgeValidator.sanitize_external_content(raw_text)
            if chash in seen_hashes:
                continue
            seen_hashes.add(chash)
            pub_date = item.get("published_date") or item.get("publication_date")
            rel = item.get("score")
            out.append(TavilyResultItem(
                request_id=request_id,
                source_url=clean_url,
                source_title=str(item.get("title") or "")[:300],
                retrieved_content=sanitized,
                publication_date=(str(pub_date) if pub_date else None),
                retrieval_timestamp=now_iso,
                domain=host,
                relevance_score=(round(float(rel), 4) if isinstance(rel, (int, float)) else None),
                content_hash=chash,
                extraction_status=extraction_mode,
                injection_risk_detected=flagged,
                trust_classification=ExternalKnowledgeValidator.classify_trust(host),
                verification_status=verif_status,
                executable_authority=False,
                auto_ingested_to_rag=False,
            ))
        return out

    def purge_expired_cache(self) -> int:
        now = time.monotonic()
        with self._lock:
            expired_keys = [k for k, (exp, _) in self._cache.items() if now >= exp]
            for k in expired_keys:
                self._cache.pop(k, None)
            return len(expired_keys)

    def _preflight_guard(self, operation: str, owner_id: str, est_credits: int, t0: float) -> Optional[TavilyOperationResponse]:
        if not self._check_rate_limit(owner_id):
            return TavilyOperationResponse(
                operation=operation,
                status="RATE_LIMITED",
                error="Owner rate limit exceeded.",
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
            )
        ok_b, b_err = self._check_budget(owner_id, est_credits)
        if not ok_b:
            return TavilyOperationResponse(
                operation=operation,
                status="BUDGET_EXCEEDED",
                error=b_err,
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
            )
        return None

    @staticmethod
    def _error_status_label(err: Optional[str]) -> str:
        if err == "NO_CREDENTIALS":
            return "BLOCKED_NO_CREDENTIALS"
        if err == "CIRCUIT_OPEN":
            return "CIRCUIT_OPEN"
        return "ERROR"

    def search_web(
        self,
        query: str,
        *,
        owner_id: str,
        search_depth: str = "basic",
        topic: str = "general",
        max_results: int = 5,
        days: Optional[int] = None,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        include_answer: bool = True,
        session_id: Optional[str] = None,
        overall_deadline_s: Optional[float] = None,
    ) -> TavilyOperationResponse:
        t0 = time.perf_counter()
        est_credits = 2 if search_depth == "advanced" else 1
        guard_err = self._preflight_guard("search", owner_id, est_credits, t0)
        if guard_err is not None:
            return guard_err

        q_clean = (query or "").strip()[:400]
        # Owner-isolated cache key prevents cross-tenant cache bleed across owner sessions
        cache_key = hashlib.sha256(
            f"search:{owner_id}:{q_clean}:{search_depth}:{topic}:{max_results}:{days}:{include_domains}:{exclude_domains}:{include_answer}".encode()
        ).hexdigest()

        inflight_ev: Optional[threading.Event] = None
        wait_ev: Optional[threading.Event] = None
        with self._lock:
            now = time.monotonic()
            cached = self._cache.get(cache_key)
            if cached and now < cached[0]:
                self._cache.move_to_end(cache_key)
                self._telemetry["cache_hits"] += 1
                res = cached[1].model_copy()
                res.cached = True
                res.latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
                return res
            elif cached:
                self._cache.pop(cache_key, None)

        with self._inflight_lock:
            if cache_key in self._inflight:
                wait_ev = self._inflight[cache_key]
            else:
                inflight_ev = threading.Event()
                self._inflight[cache_key] = inflight_ev

        if wait_ev is not None:
            wait_ev.wait(timeout=min(self.timeout_s, 10.0))
            with self._lock:
                cached = self._cache.get(cache_key)
                if cached and time.monotonic() < cached[0]:
                    self._telemetry["cache_hits"] += 1
                    self._telemetry["coalesced_requests"] += 1
                    res = cached[1].model_copy()
                    res.cached = True
                    res.latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
                    return res

        try:
            with self._lock:
                self._telemetry["requests_total"] += 1

            payload: Dict[str, Any] = {
                "query": q_clean,
                "search_depth": search_depth if search_depth in {"basic", "advanced"} else "basic",
                "topic": topic if topic in {"general", "news"} else "general",
                "max_results": max(1, min(int(max_results), 10)),
                "include_answer": include_answer,
                "include_raw_content": False,
            }
            if days is not None and topic == "news":
                payload["days"] = max(1, min(int(days), 365))
            if include_domains:
                payload["include_domains"] = list(include_domains)[:20]
            if exclude_domains:
                payload["exclude_domains"] = list(exclude_domains)[:20]

            data, err = self._post_with_retry(
                "/search", payload, owner_id=owner_id, session_id=session_id, overall_deadline_s=overall_deadline_s
            )
            if err is not None or data is None:
                return TavilyOperationResponse(
                    operation="search", status=self._error_status_label(err), error=err,
                    latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
                )

            verif = "MOCKED_TEST" if self._transport is not None else "VERIFIED_LIVE"
            req_id = data.get("request_id")
            items = self._normalize_items(data.get("results") or [], request_id=req_id, verif_status=verif)
            raw_ans = str(data.get("answer") or "")
            clean_ans, _, _ = ExternalKnowledgeValidator.sanitize_external_content(raw_ans) if raw_ans else ("", False, "")

            self._record_usage_audit(owner_id, "search", est_credits, "OK")
            with self._lock:
                if verif == "VERIFIED_LIVE":
                    self._telemetry["live_verified_calls"] += 1
                else:
                    self._telemetry["mocked_calls"] += 1
                out = TavilyOperationResponse(
                    operation="search",
                    request_id=req_id,
                    status="OK",
                    answer=clean_ans or None,
                    results=items,
                    credits_used=est_credits,
                    verification_status=verif,
                    latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
                )
                self._cache[cache_key] = (time.monotonic() + self.cache_ttl_s, out)
                while len(self._cache) > MAX_CACHE_ENTRIES:
                    self._cache.popitem(last=False)
                return out
        finally:
            if inflight_ev is not None:
                with self._inflight_lock:
                    self._inflight.pop(cache_key, None)
                inflight_ev.set()

    def extract_content(
        self,
        urls: List[str],
        *,
        owner_id: str,
        extract_depth: str = "basic",
        include_images: bool = False,
        session_id: Optional[str] = None,
        overall_deadline_s: Optional[float] = None,
    ) -> TavilyOperationResponse:
        t0 = time.perf_counter()
        validated_urls: List[str] = []
        rejected: List[Dict[str, Any]] = []
        for u in (urls or [])[:20]:
            try:
                cu, _ = ExternalKnowledgeValidator.validate_public_url(u, resolve_dns=self._resolve_dns)
                validated_urls.append(cu)
            except URLSecurityError as exc:
                rejected.append({"url": u, "error": str(exc)})

        if not validated_urls:
            return TavilyOperationResponse(
                operation="extract", status="ERROR",
                failed_results=rejected,
                error="All target URLs rejected by SSRF/URL security validation.",
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
            )

        est_credits = max(1, (len(validated_urls) + 4) // 5)
        guard_err = self._preflight_guard("extract", owner_id, est_credits, t0)
        if guard_err is not None:
            return guard_err

        with self._lock:
            self._telemetry["requests_total"] += 1
        data, err = self._post_with_retry(
            "/extract",
            {"urls": validated_urls, "extract_depth": extract_depth, "include_images": include_images},
            owner_id=owner_id,
            session_id=session_id,
            overall_deadline_s=overall_deadline_s,
        )
        if err is not None or data is None:
            return TavilyOperationResponse(
                operation="extract", status=self._error_status_label(err), failed_results=rejected, error=err,
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
            )

        verif = "MOCKED_TEST" if self._transport is not None else "VERIFIED_LIVE"
        items = self._normalize_items(
            data.get("results") or [], request_id=data.get("request_id"), verif_status=verif, extraction_mode="EXTRACTED"
        )
        self._record_usage_audit(owner_id, "extract", est_credits, "OK")
        return TavilyOperationResponse(
            operation="extract",
            request_id=data.get("request_id"),
            status="OK",
            results=items,
            failed_results=rejected + list(data.get("failed_results") or []),
            credits_used=est_credits,
            verification_status=verif,
            latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
        )

    def research_topic(
        self,
        topic_input: str,
        *,
        owner_id: str,
        session_id: Optional[str] = None,
        overall_deadline_s: Optional[float] = None,
    ) -> TavilyOperationResponse:
        t0 = time.perf_counter()
        guard_err = self._preflight_guard("research", owner_id, 4, t0)
        if guard_err is not None:
            return guard_err

        with self._lock:
            self._telemetry["requests_total"] += 1
        data, err = self._post_with_retry(
            "/research", {"input": (topic_input or "").strip()[:1000]}, owner_id=owner_id, session_id=session_id,
            overall_deadline_s=overall_deadline_s,
        )
        if err is not None or data is None:
            return TavilyOperationResponse(
                operation="research", status=self._error_status_label(err), error=err,
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
            )
        verif = "MOCKED_TEST" if self._transport is not None else "VERIFIED_LIVE"
        items = self._normalize_items(data.get("results") or data.get("sources") or [], request_id=data.get("request_id"), verif_status=verif)
        summary_raw = str(data.get("content") or data.get("report") or data.get("answer") or "")
        summary_clean, _, _ = ExternalKnowledgeValidator.sanitize_external_content(summary_raw) if summary_raw else ("", False, "")
        self._record_usage_audit(owner_id, "research", 4, "OK")
        return TavilyOperationResponse(
            operation="research",
            request_id=data.get("request_id"),
            status="OK",
            answer=summary_clean or None,
            results=items,
            credits_used=4,
            verification_status=verif,
            latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
        )

    def crawl_approved_source(
        self,
        url: str,
        *,
        owner_id: str,
        max_depth: int = 1,
        max_breadth: int = 5,
        limit: int = 5,
        instructions: Optional[str] = None,
        overall_deadline_s: Optional[float] = None,
    ) -> TavilyOperationResponse:
        t0 = time.perf_counter()
        try:
            clean_url, host = ExternalKnowledgeValidator.validate_public_url(url, resolve_dns=self._resolve_dns)
        except URLSecurityError as exc:
            return TavilyOperationResponse(operation="crawl", status="ERROR", error=str(exc))

        if ExternalKnowledgeValidator.classify_trust(host) != "APPROVED_PUBLIC_DOMAIN_EXTERNAL":
            return TavilyOperationResponse(
                operation="crawl",
                status="ERROR",
                error=f"Domain '{host}' is not in APPROVED_PUBLIC_FASHION_DOMAINS for crawling.",
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
            )
        guard_err = self._preflight_guard("crawl", owner_id, 2, t0)
        if guard_err is not None:
            return guard_err

        payload: Dict[str, Any] = {
            "url": clean_url,
            "max_depth": max(1, min(int(max_depth), 2)),
            "max_breadth": max(1, min(int(max_breadth), 10)),
            "limit": max(1, min(int(limit), 15)),
        }
        if instructions:
            payload["instructions"] = instructions[:300]
        data, err = self._post_with_retry("/crawl", payload, owner_id=owner_id, overall_deadline_s=overall_deadline_s)
        if err is not None or data is None:
            return TavilyOperationResponse(operation="crawl", status=self._error_status_label(err), error=err)

        verif = "MOCKED_TEST" if self._transport is not None else "VERIFIED_LIVE"
        items = self._normalize_items(data.get("results") or [], request_id=data.get("request_id"), verif_status=verif, extraction_mode="CRAWLED")
        self._record_usage_audit(owner_id, "crawl", 2, "OK")
        return TavilyOperationResponse(
            operation="crawl",
            request_id=data.get("request_id"),
            status="OK",
            results=items,
            credits_used=2,
            verification_status=verif,
            latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
        )


tavily_web_adapter = TavilyWebIntelligenceAdapter()
