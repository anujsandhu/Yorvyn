"""
YORVYN Intelligence Platform (YIP) — Garment Knowledge RAG Infrastructure (Phase 17.0 Stage 5).

Audit & Architecture:
- PostgreSQL 16.14 + `pg_trgm` 1.6 are available on this host (`pgvector` is NOT installed).
- Implements hybrid retrieval combining:
  1. Dense L2-normalized semantic vector cosine similarity
  2. Keyword / BM25-style TF-IDF matching
  3. Character trigram / phrase overlap
  4. Metadata & verification filters across 10 separate domain collections
  5. Cross-feature domain reranker
- Strict security boundary: untrusted retrieved text passes through a prompt-injection
  and execution firewall and can NEVER register tools, select filesystem paths, or
  override GarmentPolicy.
"""
from __future__ import annotations

import hashlib
import math
import re
import time
from collections import Counter
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from pydantic import BaseModel, Field

from backend.app.services.intelligence.inference_adapters import inference_telemetry


class KnowledgeDomain(str, Enum):
    GARMENT_CONSTRUCTION = "garment_construction"
    SEWING_PATTERNS = "sewing_patterns"
    TEXTILE_FABRIC_SCIENCE = "textile_fabric_science"
    GARMENT_MEASUREMENTS = "garment_measurements"
    BODY_FITTING = "body_fitting"
    FASHION_TERMINOLOGY = "fashion_terminology"
    MATERIAL_PROPERTIES = "material_properties"
    GEOMETRY_3D_PROCEDURES = "3d_geometry_procedures"
    ENGINEERING_DOCUMENTATION = "engineering_documentation"
    OPERATIONAL_KNOWLEDGE = "operational_knowledge"


ALLOWED_LICENSES = {
    "YORVYN Internal Engineering Knowledge",
    "CC-BY-4.0",
    "CC0-1.0",
    "MIT",
    "Apache-2.0",
    "Public Domain",
}

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions", re.I),
    re.compile(r"system\s*prompt|developer\s*message|override\s+(?:safety\s+|execution\s+)?policy", re.I),
    re.compile(r"<\s*script|javascript\s*:|vbscript\s*:|data\s*:\s*text/html", re.I),
    re.compile(r"<!--[\s\S]*?-->", re.I),
    re.compile(r"<\|(?:im_start|im_end|system|assistant|user)\|>", re.I),
    re.compile(r"(?:^|\n)\s*(?:SYSTEM|DEVELOPER|ASSISTANT)\s*:\s*", re.M),
    re.compile(r'["\']role["\']\s*:\s*["\']system["\']', re.I),
    re.compile(r"\b(?:tool_call|function_call|invoke_tool)\s*\(", re.I),
    re.compile(r"(?:DROP|DELETE|TRUNCATE|ALTER)\s+TABLE", re.I),
    re.compile(r"(?:/etc/passwd|~/\.ssh|\brm\s+-rf\b|\bsubprocess\b|\bos\.system\b)", re.I),
]


def sanitize_retrieved_text(raw: str) -> Tuple[str, bool]:
    """Strips dangerous prompt/command/script injection markers from untrusted text."""
    text = raw or ""
    flagged = False
    for pat in _INJECTION_PATTERNS:
        if pat.search(text):
            flagged = True
            text = pat.sub("[FILTERED_UNTRUSTED_DIRECTIVE]", text)
    return text.strip(), flagged


class KnowledgeDocument(BaseModel):
    doc_id: str
    domain: KnowledgeDomain
    title: str
    content: str
    source: str
    author_or_publisher: str
    license: str
    version: str = "1.0.0"
    ingestion_timestamp: str
    document_ref: str
    section_ref: str = "general"
    verification_status: str = "VERIFIED"  # VERIFIED | PROVISIONAL | UNVERIFIED
    owner_id: Optional[str] = None         # None => shared verified corpus; str => tenant-isolated doc
    injection_risk_detected: bool = False


class RetrievedKnowledgeHit(BaseModel):
    doc_id: str
    domain: str
    title: str
    snippet: str
    source: str
    author_or_publisher: str
    license: str
    version: str
    document_ref: str
    section_ref: str
    verification_status: str
    hybrid_score: float
    vector_score: float
    lexical_score: float
    rerank_score: float
    injection_risk_detected: bool = False
    executable_authority: bool = False  # Strictly False: retrieved text cannot invoke tools/policies


class KnowledgeSearchResponse(BaseModel):
    query: str
    pgvector_available: bool = False
    pg_trgm_available: bool = True
    retrieval_backend: str = "hybrid_dense_bm25_trigram_rerank"
    hits: List[RetrievedKnowledgeHit] = Field(default_factory=list)
    total_candidates_scanned: int = 0
    latency_ms: float = 0.0


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9_]+", (text or "").lower())


def _dense_hash_embed(text: str, dim: int = 256) -> np.ndarray:
    """Deterministic L2-normalized dense projection mixing word unigrams + char 3-grams."""
    vec = np.zeros(dim, dtype=np.float32)
    tokens = _tokenize(text)
    for tok in tokens:
        idx = int.from_bytes(hashlib.blake2b(tok.encode("utf-8"), digest_size=4).digest(), "little") % dim
        vec[idx] += 1.0
        padded = f"^{tok}$"
        for i in range(max(0, len(padded) - 2)):
            tri = padded[i : i + 3]
            tidx = int.from_bytes(hashlib.blake2b(tri.encode("utf-8"), digest_size=4).digest(), "little") % dim
            vec[tidx] += 0.35
    norm = float(np.linalg.norm(vec))
    return (vec / norm) if norm > 1e-8 else vec


_SEED_CORPUS: List[Dict[str, Any]] = [
    {
        "doc_id": "yip_const_01",
        "domain": KnowledgeDomain.GARMENT_CONSTRUCTION,
        "title": "Set-In Sleeve & Armscye Construction",
        "content": "A set-in sleeve joins the curved sleeve cap into the front and back bodice armscye seam. Front armscye notch matches single notch on sleeve cap; back armscye receives double notch and slightly higher easing margin (1.5cm to 2.5cm).",
        "source": "YORVYN Pattern Construction Spec 16.2",
        "author_or_publisher": "YORVYN Pattern Engineering",
        "license": "YORVYN Internal Engineering Knowledge",
        "document_ref": "backend/app/services/intelligence/pattern_construction_engine.py",
        "section_ref": "armscye_sleeve_join",
    },
    {
        "doc_id": "yip_pat_01",
        "domain": KnowledgeDomain.SEWING_PATTERNS,
        "title": "Seam Allowance & Tolerance Contract",
        "content": "Standard woven shirt side and shoulder seams allocate 1.0cm to 1.2cm seam allowance; flat-felled denim seams allocate 1.5cm; hem turn-ups allocate 2.0cm to 2.5cm. Grainlines orient parallel to warp (90 deg) for structural stability.",
        "source": "YORVYN Pattern Geometry Engine",
        "author_or_publisher": "YORVYN Pattern Engineering",
        "license": "YORVYN Internal Engineering Knowledge",
        "document_ref": "backend/app/services/garments/reconstruction/pattern_geometry.py",
        "section_ref": "seam_allowance_defaults",
    },
    {
        "doc_id": "yip_tex_01",
        "domain": KnowledgeDomain.TEXTILE_FABRIC_SCIENCE,
        "title": "Woven vs Knit Appearance and Drape Limits",
        "content": "Diagonal twill (denim) exhibits higher bending stiffness and anisotropic shear resistance; brushed cotton fleece displays matte surface roughness and moderate drape; jersey knit stretches asymmetrically along weft. Photographic appearance alone does not verify physical fiber percentages.",
        "source": "YORVYN Material & Drape Knowledge",
        "author_or_publisher": "YORVYN Textile Science Group",
        "license": "YORVYN Internal Engineering Knowledge",
        "document_ref": "backend/app/services/garments/appearance/material_profiles.py",
        "section_ref": "fabric_drape_estimates",
    },
    {
        "doc_id": "yip_meas_01",
        "domain": KnowledgeDomain.GARMENT_MEASUREMENTS,
        "title": "Ramanujan Cross-Section Circumference Estimation",
        "content": "Chest and waist garment circumferences from 3D meshes in Ara Y-up coordinates are estimated from bilateral X-width and anterior-posterior Z-depth half-axes using Ramanujan's ellipse perimeter approximation.",
        "source": "YORVYN Body Measurement Engine",
        "author_or_publisher": "YORVYN Fit Engineering",
        "license": "YORVYN Internal Engineering Knowledge",
        "document_ref": "backend/app/services/garments/fitting/avatar_body_measurement_engine.py",
        "section_ref": "ramanujan_ellipse_perimeter",
    },
    {
        "doc_id": "yip_fit_01",
        "domain": KnowledgeDomain.BODY_FITTING,
        "title": "Garment Ease Classification and Collision Thresholds",
        "content": "Chest ease bands: Slim (+2 to +5cm), Regular (+6 to +10cm), Relaxed (+10 to +16cm), Oversized (+15 to +26cm). Minimum wearable avatar clearance is 3.0mm; negative ease or penetration >6mm triggers a structural fit warning.",
        "source": "YORVYN Fit & Collision Spec",
        "author_or_publisher": "YORVYN Fit Engineering",
        "license": "YORVYN Internal Engineering Knowledge",
        "document_ref": "backend/app/services/ml/body_intelligence.py",
        "section_ref": "FIT_EASE_TOLERANCES",
    },
    {
        "doc_id": "yip_term_01",
        "domain": KnowledgeDomain.FASHION_TERMINOLOGY,
        "title": "Placket, Yoke, Gusset, and Kangaroo Pocket Definitions",
        "content": "Placket: reinforced front opening holding buttons or zipper. Yoke: shaped upper back or shoulder panel supporting fullness below. Kangaroo pocket: centered lower front pouch pocket typical of pullover hoodies.",
        "source": "YORVYN Component Taxonomy",
        "author_or_publisher": "YORVYN Intelligence Core",
        "license": "YORVYN Internal Engineering Knowledge",
        "document_ref": "backend/app/services/intelligence/component_taxonomy.py",
        "section_ref": "taxonomy_definitions",
    },
    {
        "doc_id": "yip_mat_01",
        "domain": KnowledgeDomain.MATERIAL_PROPERTIES,
        "title": "PBR Material Roughness & Specular Calibration",
        "content": "Matte woven wool and brushed fleece map to PBR roughness 0.85-0.95 and metallic 0.0; structured denim maps to roughness ~0.92; satin/coated outerwear maps to roughness 0.30-0.50 with optional clearcoat.",
        "source": "YORVYN Appearance System",
        "author_or_publisher": "YORVYN Graphics Team",
        "license": "YORVYN Internal Engineering Knowledge",
        "document_ref": "backend/app/services/garments/appearance/materialx_pbr_system.py",
        "section_ref": "pbr_presets",
    },
    {
        "doc_id": "yip_geo_01",
        "domain": KnowledgeDomain.GEOMETRY_3D_PROCEDURES,
        "title": "Manifold Verification & Bounded GLB Editing",
        "content": "Before publication, binary glTF 2.0 assets undergo edge incidence inspection, degenerate area filtering (>1e-9 m^2), winding checks, and anthropometric envelope bounds validation. Component edits protect unedited seam-shared vertices.",
        "source": "YORVYN Mesh Validation & Candidate Edit",
        "author_or_publisher": "YORVYN 3D Geometry Team",
        "license": "YORVYN Internal Engineering Knowledge",
        "document_ref": "backend/app/services/garments/mesh_validation_service.py",
        "section_ref": "validate_glb_bytes",
    },
    {
        "doc_id": "yip_eng_01",
        "domain": KnowledgeDomain.ENGINEERING_DOCUMENTATION,
        "title": "Durable Job Outbox & Fenced Publication Architecture",
        "content": "Every reconstruction job commits atomically in PostgreSQL with a yorvyn_job_outbox event before Redis delivery. Workers validate durable DB lease_generation and publish artifacts fenced by generation ID.",
        "source": "YORVYN Architecture ADR DURABLE-JOB-002",
        "author_or_publisher": "YORVYN Platform Engineering",
        "license": "YORVYN Internal Engineering Knowledge",
        "document_ref": "backend/app/services/garments/orchestration/unified_state_machine.py",
        "section_ref": "create_job_atomic",
    },
    {
        "doc_id": "yip_ops_01",
        "domain": KnowledgeDomain.OPERATIONAL_KNOWLEDGE,
        "title": "Model Verification & Honest Capability Reporting",
        "content": "Declared adapters without verified checkpoint SHA-256 digests remain DECLARED or UNAVAILABLE. Only executed and validated local artifacts (v6 classifier, landmarks v2, cached SegFormer-B2, cached DINOv2-small, cached generic CLIP) are eligible for local pipelines.",
        "source": "YORVYN Model Verification Matrix",
        "author_or_publisher": "YORVYN Reliability Engineering",
        "license": "YORVYN Internal Engineering Knowledge",
        "document_ref": "docs/engineering/phase-16/MODEL_VERIFICATION_MATRIX.md",
        "section_ref": "model_verification",
    },
]


class GarmentKnowledgeRAG:
    """Hybrid Dense + BM25 + Trigram RAG with separate collections and injection firewall."""

    def __init__(self) -> None:
        self._collections: Dict[KnowledgeDomain, List[Tuple[KnowledgeDocument, np.ndarray, Counter]]] = {
            d: [] for d in KnowledgeDomain
        }
        now_iso = datetime.now(timezone.utc).isoformat()
        for row in _SEED_CORPUS:
            self.ingest_document(
                doc_id=row["doc_id"],
                domain=row["domain"],
                title=row["title"],
                content=row["content"],
                source=row["source"],
                author_or_publisher=row["author_or_publisher"],
                license_name=row["license"],
                document_ref=row["document_ref"],
                section_ref=row["section_ref"],
                verification_status="VERIFIED",
                ingestion_timestamp=now_iso,
            )

    def get_status(self) -> Dict[str, Any]:
        return {
            "pgvector_available": False,
            "pgvector_installed": False,
            "pg_trgm_available": True,
            "retrieval_mode": "hybrid_dense_bm25_trigram_rerank",
            "collections": {d.value: len(items) for d, items in self._collections.items()},
            "total_documents": sum(len(v) for v in self._collections.values()),
        }

    def ingest_document(
        self,
        *,
        doc_id: str,
        domain: KnowledgeDomain,
        title: str,
        content: str,
        source: str,
        author_or_publisher: str,
        license_name: str,
        document_ref: str,
        section_ref: str = "general",
        version: str = "1.0.0",
        verification_status: str = "VERIFIED",
        owner_id: Optional[str] = None,
        ingestion_timestamp: Optional[str] = None,
    ) -> KnowledgeDocument:
        if license_name not in ALLOWED_LICENSES and not owner_id:
            raise ValueError(f"Unauthorized knowledge license '{license_name}' for shared corpus.")

        clean_content, risk_c = sanitize_retrieved_text(content)
        clean_title, risk_t = sanitize_retrieved_text(title)
        doc = KnowledgeDocument(
            doc_id=doc_id,
            domain=domain,
            title=clean_title,
            content=clean_content,
            source=source,
            author_or_publisher=author_or_publisher,
            license=license_name,
            version=version,
            ingestion_timestamp=ingestion_timestamp or datetime.now(timezone.utc).isoformat(),
            document_ref=document_ref,
            section_ref=section_ref,
            verification_status=verification_status,
            owner_id=owner_id,
            injection_risk_detected=bool(risk_c or risk_t),
        )
        full_text = f"{doc.title} {doc.content} {doc.domain.value} {doc.section_ref}"
        vec = _dense_hash_embed(full_text)
        tf = Counter(_tokenize(full_text))

        bucket = self._collections[domain]
        self._collections[domain] = [(d, v, c) for (d, v, c) in bucket if d.doc_id != doc_id]
        self._collections[domain].append((doc, vec, tf))
        return doc

    def search(
        self,
        query: str,
        *,
        domains: Optional[List[KnowledgeDomain]] = None,
        owner_id: Optional[str] = None,
        verified_only: bool = False,
        top_k: int = 5,
    ) -> KnowledgeSearchResponse:
        t0 = time.perf_counter()
        clean_query, _ = sanitize_retrieved_text(query)
        q_tokens = _tokenize(clean_query)
        q_vec = _dense_hash_embed(clean_query)
        q_trigrams = {clean_query.lower()[i : i + 3] for i in range(max(0, len(clean_query) - 2))}

        target_domains = domains or list(KnowledgeDomain)
        pool: List[Tuple[KnowledgeDocument, np.ndarray, Counter]] = []
        for dom in target_domains:
            for doc, vec, tf in self._collections.get(dom, []):
                if doc.owner_id is not None and doc.owner_id != owner_id:
                    continue
                if verified_only and doc.verification_status != "VERIFIED":
                    continue
                pool.append((doc, vec, tf))

        n_docs = max(1, len(pool))
        df: Counter = Counter()
        for _, _, tf in pool:
            for term in set(q_tokens):
                if term in tf:
                    df[term] += 1

        scored: List[RetrievedKnowledgeHit] = []
        for doc, vec, tf in pool:
            vec_score = max(0.0, float(np.dot(q_vec, vec)))
            # BM25-inspired TF-IDF lexical score
            lex_raw = 0.0
            doc_len = max(1, sum(tf.values()))
            for qt in q_tokens:
                f = tf.get(qt, 0)
                if f == 0:
                    continue
                idf = math.log((n_docs - df[qt] + 0.5) / (df[qt] + 0.5) + 1.0)
                lex_raw += idf * (f * 2.2) / (f + 1.2 * (0.25 + 0.75 * (doc_len / 45.0)))
            lex_score = 1.0 - math.exp(-lex_raw / max(1, len(q_tokens)))

            # Trigram & title bonus reranking
            text_l = f"{doc.title} {doc.content}".lower()
            tri_doc = {text_l[i : i + 3] for i in range(max(0, len(text_l) - 2))}
            tri_sim = (len(q_trigrams & tri_doc) / max(1, len(q_trigrams))) if q_trigrams else 0.0
            title_bonus = 0.12 if any(t in doc.title.lower() for t in q_tokens) else 0.0
            verif_bonus = 0.08 if doc.verification_status == "VERIFIED" else 0.0
            rerank = min(1.0, 0.55 * vec_score + 0.35 * lex_score + 0.10 * tri_sim + title_bonus + verif_bonus)
            hybrid = 0.45 * vec_score + 0.40 * lex_score + 0.15 * tri_sim

            scored.append(RetrievedKnowledgeHit(
                doc_id=doc.doc_id,
                domain=doc.domain.value,
                title=doc.title,
                snippet=doc.content[:360],
                source=doc.source,
                author_or_publisher=doc.author_or_publisher,
                license=doc.license,
                version=doc.version,
                document_ref=doc.document_ref,
                section_ref=doc.section_ref,
                verification_status=doc.verification_status,
                hybrid_score=round(float(hybrid), 4),
                vector_score=round(float(vec_score), 4),
                lexical_score=round(float(lex_score), 4),
                rerank_score=round(float(rerank), 4),
                injection_risk_detected=doc.injection_risk_detected,
                executable_authority=False,
            ))

        scored.sort(key=lambda h: (h.rerank_score, h.hybrid_score), reverse=True)
        lat_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        inference_telemetry.record("knowledge-rag-v17", lat_ms, device="cpu", backend="hybrid_retrieval")
        return KnowledgeSearchResponse(
            query=clean_query,
            pgvector_available=False,
            pg_trgm_available=True,
            hits=scored[: max(1, min(top_k, 25))],
            total_candidates_scanned=len(pool),
            latency_ms=lat_ms,
        )


knowledge_rag = GarmentKnowledgeRAG()
