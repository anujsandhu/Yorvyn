"""Phase 16.3 Durable Garment Design Revisions & 2D/3D Synchronization Service."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class MaterialRevisionConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    preset: str = "cotton"
    base_color: str = "#ffffff"
    roughness: float = Field(default=0.75, ge=0.04, le=1.0)
    metalness: float = Field(default=0.0, ge=0.0, le=1.0)
    sheen: float = Field(default=0.0, ge=0.0, le=1.0)
    clearcoat: float = Field(default=0.0, ge=0.0, le=1.0)
    normal_intensity: float = Field(default=0.65, ge=0.0, le=2.0)
    repeat_x: float = Field(default=1.0, ge=0.25, le=8.0)
    repeat_y: float = Field(default=1.0, ge=0.25, le=8.0)
    rotation_deg: float = Field(default=0.0, ge=-180.0, le=180.0)
    offset_x: float = Field(default=0.0, ge=-1.0, le=1.0)
    offset_y: float = Field(default=0.0, ge=-1.0, le=1.0)
    stitch_visible: bool = False
    stitch_color: str = "#e2e8f0"
    print_scale: float = Field(default=1.0, ge=0.25, le=3.0)
    is_physically_verified: bool = False


class GeometryDesignParams(BaseModel):
    model_config = ConfigDict(extra="allow")
    torso_length_scale: float = Field(default=1.0, ge=0.65, le=1.40)
    torso_width_scale: float = Field(default=1.0, ge=0.70, le=1.45)
    sleeve_length_scale: float = Field(default=1.0, ge=0.50, le=1.35)
    sleeve_width_scale: float = Field(default=1.0, ge=0.70, le=1.45)
    collar_width_scale: float = Field(default=1.0, ge=0.70, le=1.35)
    hem_width_scale: float = Field(default=1.0, ge=0.75, le=1.40)
    chest_pocket_enabled: Optional[bool] = None


class DesignOperationRecord(BaseModel):
    operation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kind: str
    target_component: str = "garment"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    source: str = "studio"  # studio | pattern_2d | stylist_chat
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GarmentDesignRevision(BaseModel):
    revision_id: str = Field(default_factory=lambda: f"rev_{uuid.uuid4().hex[:12]}")
    garment_id: str
    user_id: str
    candidate_id: Optional[str] = None
    request_id: Optional[str] = None
    design_version: int = Field(default=1, ge=1)
    parent_version: Optional[int] = None
    geometry_version: int = Field(default=1, ge=1)
    pattern_version: int = Field(default=1, ge=1)
    material_version: int = Field(default=1, ge=1)
    texture_version: int = Field(default=1, ge=1)
    correspondence_version: str = "16.3.1"
    sync_status: str = "SYNCHRONIZED"
    geometry_hash: str
    pattern_hash: str
    mapping_hash: Optional[str] = None
    candidate_sha256: Optional[str] = None
    category: str = "jacket"
    subcategory: str = ""
    geometry_params: GeometryDesignParams = Field(default_factory=GeometryDesignParams)
    material_config: MaterialRevisionConfig = Field(default_factory=MaterialRevisionConfig)
    pattern_overrides: Dict[str, Any] = Field(default_factory=dict)
    measurements: Dict[str, float] = Field(default_factory=dict)
    scoped_measurements: Dict[str, Any] = Field(default_factory=dict)
    validation_summary: Dict[str, Any] = Field(default_factory=dict)
    operation_history: List[DesignOperationRecord] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SaveDesignRevisionRequest(BaseModel):
    candidate_id: Optional[str] = None
    request_id: Optional[str] = None
    expected_parent_version: Optional[int] = None
    geometry_version: int = Field(default=1, ge=1)
    pattern_version: int = Field(default=1, ge=1)
    material_version: int = Field(default=1, ge=1)
    texture_version: int = Field(default=1, ge=1)
    correspondence_version: str = "16.3.1"
    sync_status: str = "SYNCHRONIZED"
    candidate_sha256: Optional[str] = None
    category: str = "jacket"
    subcategory: str = ""
    geometry_params: GeometryDesignParams = Field(default_factory=GeometryDesignParams)
    material_config: MaterialRevisionConfig = Field(default_factory=MaterialRevisionConfig)
    pattern_overrides: Dict[str, Any] = Field(default_factory=dict)
    measurements: Dict[str, float] = Field(default_factory=dict)
    scoped_measurements: Dict[str, Any] = Field(default_factory=dict)
    validation_summary: Dict[str, Any] = Field(default_factory=dict)
    operation_history: List[DesignOperationRecord] = Field(default_factory=list)
    geometry_hash: Optional[str] = None
    pattern_hash: Optional[str] = None
    mapping_hash: Optional[str] = None


def compute_canonical_hash(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class DesignRevisionService:
    """Owner-scoped, version-checked persistence for garment design revisions."""

    def __init__(self) -> None:
        self._store: Dict[tuple[str, str], List[GarmentDesignRevision]] = {}

    def _pg_save(self, rev: GarmentDesignRevision) -> None:
        try:
            from backend.app.services.garments.job_manager import garment_job_manager
            adapter = getattr(garment_job_manager, "_postgres_adapter", None)
            if not adapter or not adapter.is_configured():
                return
            with adapter._connect() as conn:  # pragma: no cover - optional PG table when running cold DB
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS garment_design_revisions (
                            revision_id TEXT PRIMARY KEY,
                            garment_id TEXT NOT NULL,
                            user_id TEXT NOT NULL,
                            design_version INTEGER NOT NULL,
                            parent_version INTEGER,
                            payload_json JSONB NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                        """
                    )
                    cur.execute(
                        """
                        INSERT INTO garment_design_revisions (revision_id, garment_id, user_id, design_version, parent_version, payload_json)
                        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (revision_id) DO NOTHING
                        """,
                        (
                            rev.revision_id,
                            rev.garment_id,
                            rev.user_id,
                            rev.design_version,
                            rev.parent_version,
                            rev.model_dump_json(),
                        ),
                    )
        except Exception:
            # In-memory store stays authoritative in isolated/test mode if PostgreSQL is absent
            pass

    def _pg_list(self, user_id: str, garment_id: str) -> List[GarmentDesignRevision]:
        try:
            from backend.app.services.garments.job_manager import garment_job_manager
            adapter = getattr(garment_job_manager, "_postgres_adapter", None)
            if not adapter or not adapter.is_configured():
                return []
            with adapter._connect() as conn:  # pragma: no cover
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT payload_json FROM garment_design_revisions
                        WHERE garment_id = %s AND user_id = %s
                        ORDER BY design_version ASC
                        """,
                        (garment_id, user_id),
                    )
                    rows = cur.fetchall()
                    return [GarmentDesignRevision.model_validate(r[0]) for r in rows]
        except Exception:
            return []

    def list_revisions(self, user_id: str, garment_id: str) -> List[GarmentDesignRevision]:
        cached = self._store.get((user_id, garment_id), [])
        if cached:
            return list(cached)
        pg_rows = self._pg_list(user_id, garment_id)
        if pg_rows:
            self._store[(user_id, garment_id)] = list(pg_rows)
        return pg_rows

    def get_revision(self, user_id: str, garment_id: str, revision_id: str) -> Optional[GarmentDesignRevision]:
        for rev in self.list_revisions(user_id, garment_id):
            if rev.revision_id == revision_id:
                return rev
        return None

    def save_revision(self, user_id: str, garment_id: str, req: SaveDesignRevisionRequest) -> GarmentDesignRevision:
        history = self.list_revisions(user_id, garment_id)
        if req.request_id:
            for existing_rev in history:
                if existing_rev.request_id == req.request_id:
                    return existing_rev
        latest_version = history[-1].design_version if history else 0
        if req.expected_parent_version is not None and req.expected_parent_version != latest_version:
            raise ValueError(
                f"Version conflict: expected parent version {req.expected_parent_version}, "
                f"but current stored version is {latest_version}."
            )
        next_version = latest_version + 1
        geom_hash = req.geometry_hash or compute_canonical_hash(
            {"params": req.geometry_params.model_dump(), "measurements": req.measurements}
        )
        pat_hash = req.pattern_hash or compute_canonical_hash(req.pattern_overrides)
        rev = GarmentDesignRevision(
            garment_id=garment_id,
            user_id=user_id,
            candidate_id=req.candidate_id,
            request_id=req.request_id,
            design_version=next_version,
            parent_version=latest_version if latest_version > 0 else None,
            geometry_version=req.geometry_version,
            pattern_version=req.pattern_version,
            material_version=req.material_version,
            texture_version=req.texture_version,
            correspondence_version=req.correspondence_version,
            sync_status=req.sync_status,
            geometry_hash=geom_hash,
            pattern_hash=pat_hash,
            mapping_hash=req.mapping_hash,
            candidate_sha256=req.candidate_sha256,
            category=req.category,
            subcategory=req.subcategory,
            geometry_params=req.geometry_params,
            material_config=req.material_config,
            pattern_overrides=req.pattern_overrides,
            measurements=req.measurements,
            scoped_measurements=req.scoped_measurements,
            validation_summary=req.validation_summary,
            operation_history=req.operation_history,
        )
        self._store.setdefault((user_id, garment_id), []).append(rev)
        self._pg_save(rev)
        return rev


design_revision_service = DesignRevisionService()
