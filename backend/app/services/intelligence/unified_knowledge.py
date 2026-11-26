"""
YORVYN Intelligence Platform (YIP) — Phase 17.3 Unified Internal + External Knowledge Coordinator.

Strictly separates:
- Internal Verified Knowledge (`GarmentKnowledgeRAG`)
- Untrusted External Web Evidence (`TavilyWebIntelligenceAdapter`)

Never auto-ingests unverified web results into permanent internal RAG storage.
Promotions require explicit trusted ingestion policy verification (no injection flags + approved license).
"""
from __future__ import annotations

import hashlib
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.app.services.intelligence.knowledge_rag import (
    ALLOWED_LICENSES,
    KnowledgeDocument,
    KnowledgeDomain,
    RetrievedKnowledgeHit,
    knowledge_rag,
)
from backend.app.services.intelligence.tavily_web_adapter import (
    APPROVED_PUBLIC_FASHION_DOMAINS,
    ExternalKnowledgeValidator,
    TavilyResultItem,
    TavilyWebIntelligenceAdapter,
    tavily_web_adapter,
)


class PromotionAuditEntry(BaseModel):
    doc_id: str
    version: str
    domain: str
    source_url: str
    content_hash: str
    license_name: str
    approved_by: str
    rights_verified: bool
    promoted_at: str


class UnifiedKnowledgeResponse(BaseModel):
    query: str
    owner_id: str
    internal_hits: List[RetrievedKnowledgeHit] = Field(default_factory=list)
    external_evidence: List[TavilyResultItem] = Field(default_factory=list)
    external_answer_summary: Optional[str] = None
    external_status: str = "SKIPPED"  # SKIPPED | OK | BLOCKED_NO_CREDENTIALS | CIRCUIT_OPEN | ERROR
    internal_rag_remained_isolated: bool = True
    warnings: List[str] = Field(default_factory=list)
    latency_ms: float = 0.0


class UnifiedKnowledgeCoordinator:
    """Queries GarmentKnowledgeRAG and optionally Tavily without cross-contaminating trust tiers."""

    def __init__(
        self,
        *,
        web_adapter: Optional[TavilyWebIntelligenceAdapter] = None,
    ) -> None:
        self.web_adapter = web_adapter or tavily_web_adapter

    _promotion_lock = threading.Lock()
    _promoted_hashes: Dict[str, str] = {}
    _promotion_versions: Dict[str, int] = {}
    _promotion_audit: List[PromotionAuditEntry] = []

    def retrieve(
        self,
        query: str,
        *,
        owner_id: str,
        domains: Optional[List[KnowledgeDomain]] = None,
        verified_internal_only: bool = True,
        include_external: bool = False,
        external_max_results: int = 4,
        session_id: Optional[str] = None,
    ) -> UnifiedKnowledgeResponse:
        t0 = time.perf_counter()
        internal_res = knowledge_rag.search(
            query,
            domains=domains,
            owner_id=owner_id,
            verified_only=verified_internal_only,
            top_k=5,
        )

        ext_items: List[TavilyResultItem] = []
        ext_ans: Optional[str] = None
        ext_status = "SKIPPED"
        warnings: List[str] = []

        if include_external:
            web_res = self.web_adapter.search_web(
                query,
                owner_id=owner_id,
                max_results=external_max_results,
                session_id=session_id,
            )
            ext_status = web_res.status
            ext_items = web_res.results
            ext_ans = web_res.answer
            if web_res.status != "OK":
                warnings.append(f"External search unavailable ({web_res.status}); using verified internal RAG.")
            if any(it.injection_risk_detected for it in ext_items):
                warnings.append("Prompt-injection patterns stripped from external web snippets.")

        return UnifiedKnowledgeResponse(
            query=query,
            owner_id=str(owner_id),
            internal_hits=internal_res.hits,
            external_evidence=ext_items,
            external_answer_summary=ext_ans,
            external_status=ext_status,
            internal_rag_remained_isolated=True,
            warnings=warnings,
            latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
        )

    @classmethod
    def get_promotion_audit_log(cls) -> List[PromotionAuditEntry]:
        with cls._promotion_lock:
            return list(cls._promotion_audit)

    @classmethod
    def promote_validated_external_item(
        cls,
        item: TavilyResultItem,
        *,
        doc_id: str,
        domain: KnowledgeDomain,
        title: Optional[str] = None,
        license_name: str = "CC-BY-4.0",
        explicit_approval: bool = False,
        approved_by: str = "",
        rights_verified: bool = False,
        allow_duplicate: bool = False,
    ) -> KnowledgeDocument:
        """
        Explicit trusted ingestion gate: requires explicit human/admin approval, zero prompt-injection
        flags, intact content SHA-256 provenance, verified rights/license, and duplicate suppression.
        """
        if not explicit_approval:
            raise ValueError("External evidence promotion requires explicit_approval=True.")
        if item.injection_risk_detected:
            raise ValueError("Cannot promote external content flagged for prompt-injection risk.")
        if not item.source_url or not item.retrieval_timestamp or not item.content_hash:
            raise ValueError("Missing provenance metadata (source_url, retrieval_timestamp, or content_hash).")
        if item.verification_status in {"REJECTED", "FAILED"}:
            raise ValueError(f"Cannot promote item with verification_status='{item.verification_status}'.")
        ExternalKnowledgeValidator.validate_public_url(item.source_url, resolve_dns=False)

        expected_hash = hashlib.sha256((item.retrieved_content or "").encode("utf-8")).hexdigest()
        if expected_hash != item.content_hash:
            raise ValueError("External evidence content_hash integrity mismatch.")
        if license_name not in ALLOWED_LICENSES:
            raise ValueError(f"License '{license_name}' is not in ALLOWED_LICENSES.")

        is_approved_domain = any(
            item.domain.lower().lstrip("www.") == d or item.domain.lower().lstrip("www.").endswith(f".{d}")
            for d in APPROVED_PUBLIC_FASHION_DOMAINS
        )
        if not (rights_verified or is_approved_domain):
            raise ValueError(
                f"Domain '{item.domain}' is not an approved public reference source and rights_verified=False."
            )

        with cls._promotion_lock:
            if not allow_duplicate and item.content_hash in cls._promoted_hashes:
                existing_id = cls._promoted_hashes[item.content_hash]
                raise ValueError(f"Duplicate external content_hash already promoted under doc_id='{existing_id}'.")
            ver_num = cls._promotion_versions.get(doc_id, 0) + 1
            cls._promotion_versions[doc_id] = ver_num
            version_str = f"1.0.{ver_num - 1}" if ver_num == 1 else f"1.{ver_num}.0"

            doc = knowledge_rag.ingest_document(
                doc_id=doc_id,
                domain=domain,
                title=title or item.source_title or "Validated External Reference",
                content=item.retrieved_content,
                source=item.domain,
                author_or_publisher=item.domain,
                license_name=license_name,
                version=version_str,
                document_ref=item.source_url,
                verification_status="PROVISIONAL",
                owner_id=None,
            )
            if doc.injection_risk_detected:
                raise ValueError("Promoted content failed secondary RAG injection scan.")
            cls._promoted_hashes[item.content_hash] = doc_id
            cls._promotion_audit.append(PromotionAuditEntry(
                doc_id=doc_id,
                version=version_str,
                domain=domain.value,
                source_url=item.source_url,
                content_hash=item.content_hash,
                license_name=license_name,
                approved_by=approved_by or "system_reviewer",
                rights_verified=bool(rights_verified or is_approved_domain),
                promoted_at=datetime.now(timezone.utc).isoformat(),
            ))
            return doc


unified_knowledge = UnifiedKnowledgeCoordinator()
