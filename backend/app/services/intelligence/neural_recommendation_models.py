"""
YORVYN Intelligence Platform (YIP) — Phase 17.2 Neural Recommendation Models & Feature Encoders.

Implements PyTorch trainable recommendation architectures with strict separation of
explicit vs. inferred user signals, privacy-safe non-sensitive feature encoding,
SHA-256 verified checkpoint serialization, and deterministic fallback behavior:
1. User & Item Feature Encoders (non-sensitive, schema-versioned `17.2.0`)
2. TwoTowerRecommendationModel (independent User & Item Towers with L2 embeddings + BPR loss)
3. NeuralRankingModel (cross-interaction + verified scalar signals with explainable attributions)
4. SequentialTransformerRecommender (causal time-aware Transformer preventing future leakage)
5. GraphRecommendationModel (provenance-aware LightGCN-style normalized message passing)
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from backend.app.services.intelligence.recommendation_profile import (
    SENSITIVE_ATTRIBUTE_BLOCKLIST,
    UserPreferenceProfile,
)
from backend.app.services.intelligence.recommendation_taxonomy import (
    CANONICAL_CATEGORIES,
    RecommendationGarmentAttributes,
    normalize_item,
)

NEURAL_REC_SCHEMA_VERSION = "17.2.0"

CATEGORY_VOCAB: Tuple[str, ...] = tuple(sorted(CANONICAL_CATEGORIES.keys()))
STYLE_VOCAB: Tuple[str, ...] = (
    "quiet_luxury", "minimalist", "minimalist_scandi", "streetwear", "sportswear",
    "formalwear", "traditional", "casual", "smart_casual", "parisian_chic", "vintage",
)
SILHOUETTE_VOCAB: Tuple[str, ...] = ("regular", "slim", "tailored", "relaxed", "oversized", "boxy", "fitted", "a_line", "other")
FIT_VOCAB: Tuple[str, ...] = ("regular", "slim", "tailored", "relaxed", "oversized", "tight", "other")
COLOR_VOCAB: Tuple[str, ...] = (
    "black", "white", "grey", "charcoal", "navy", "sky blue", "blue", "cream", "beige",
    "camel", "brown", "dark brown", "olive", "green", "burgundy", "red", "neutral", "other",
)
PATTERN_VOCAB: Tuple[str, ...] = ("solid", "striped", "checked", "floral", "print", "textured", "other")
MATERIAL_VOCAB: Tuple[str, ...] = (
    "cotton", "wool", "merino wool", "virgin wool", "denim", "leather", "silk",
    "linen", "fleece", "nylon", "ripstop", "polyester", "other",
)
OCCASION_VOCAB: Tuple[str, ...] = ("casual", "everyday", "work", "business", "formal", "wedding", "smart_casual", "athletic")
SEASON_VOCAB: Tuple[str, ...] = ("all_season", "spring", "summer", "autumn", "winter")

VISUAL_PROJ_DIM = 16
EMBEDDING_DIM = 32

ITEM_FEAT_DIM: int = (
    len(CATEGORY_VOCAB)
    + len(STYLE_VOCAB)
    + len(SILHOUETTE_VOCAB)
    + len(FIT_VOCAB)
    + len(COLOR_VOCAB)
    + len(PATTERN_VOCAB)
    + len(MATERIAL_VOCAB)
    + len(OCCASION_VOCAB)
    + len(SEASON_VOCAB)
    + 5  # normalized formality, warmth, available, freshness, has_visual_embedding
    + VISUAL_PROJ_DIM
)

# Explicit branch kept strictly distinct from inferred interaction branch
USER_EXPLICIT_DIM: int = len(CATEGORY_VOCAB) + len(STYLE_VOCAB) + len(COLOR_VOCAB) + len(FIT_VOCAB)
USER_INFERRED_DIM: int = len(CATEGORY_VOCAB) + len(STYLE_VOCAB) + len(COLOR_VOCAB) + 3 + VISUAL_PROJ_DIM  # +3 = pos_density, is_cold_start, decayed_strength
USER_FEAT_DIM: int = USER_EXPLICIT_DIM + USER_INFERRED_DIM


def _project_visual_embedding(vec: Optional[Sequence[float]], target_dim: int = VISUAL_PROJ_DIM) -> Tuple[np.ndarray, float]:
    """Deterministically pools/projects any verified visual embedding into fixed dims with a presence flag."""
    out = np.zeros(target_dim, dtype=np.float32)
    if not vec:
        return out, 0.0
    arr = np.asarray(vec, dtype=np.float32)
    if arr.ndim != 1 or arr.size == 0 or not np.all(np.isfinite(arr)):
        return out, 0.0
    norm = float(np.linalg.norm(arr))
    if norm <= 1e-8:
        return out, 0.0
    arr = arr / norm
    if arr.size >= target_dim:
        # Bucket mean pooling preserves L2 structure stably across arbitrary dims (e.g. 4, 384, 512)
        splits = np.array_split(arr, target_dim)
        out = np.asarray([float(np.mean(s)) for s in splits], dtype=np.float32)
    else:
        out[: arr.size] = arr
    o_norm = float(np.linalg.norm(out))
    if o_norm > 1e-8:
        out = out / o_norm
    return out, 1.0


def _one_hot(vocab: Tuple[str, ...], value: str) -> np.ndarray:
    vec = np.zeros(len(vocab), dtype=np.float32)
    vl = (value or "").strip().lower()
    if vl in vocab:
        vec[vocab.index(vl)] = 1.0
    elif "other" in vocab:
        vec[vocab.index("other")] = 1.0
    return vec


def _multi_hot(vocab: Tuple[str, ...], values: Sequence[str]) -> np.ndarray:
    vec = np.zeros(len(vocab), dtype=np.float32)
    for val in values or ():
        vl = str(val).strip().lower()
        if vl in vocab:
            vec[vocab.index(vl)] = 1.0
    return vec


def encode_item_features(item: RecommendationGarmentAttributes | Dict[str, Any]) -> np.ndarray:
    """Encodes non-sensitive garment metadata + optional verified visual embedding."""
    norm = item if isinstance(item, RecommendationGarmentAttributes) else normalize_item(item)
    vis_vec, has_vis = _project_visual_embedding(norm.visual_embedding)
    scalars = np.asarray([
        max(0.0, min(1.0, float(norm.formality) / 10.0)),
        max(0.0, min(1.0, float(norm.warmth) / 10.0)),
        1.0 if norm.available else 0.0,
        math.exp(-max(0.0, float(norm.freshness_days)) / 60.0),
        has_vis,
    ], dtype=np.float32)
    return np.concatenate([
        _one_hot(CATEGORY_VOCAB, norm.category),
        _multi_hot(STYLE_VOCAB, norm.style),
        _one_hot(SILHOUETTE_VOCAB, norm.silhouette),
        _one_hot(FIT_VOCAB, norm.fit),
        _one_hot(COLOR_VOCAB, norm.color),
        _one_hot(PATTERN_VOCAB, norm.pattern),
        _one_hot(MATERIAL_VOCAB, norm.material),
        _multi_hot(OCCASION_VOCAB, norm.occasion),
        _multi_hot(SEASON_VOCAB, norm.season),
        scalars,
        vis_vec,
    ]).astype(np.float32)


def encode_user_features(
    profile: UserPreferenceProfile,
    *,
    positive_items: Optional[List[RecommendationGarmentAttributes]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Returns `(explicit_vector, inferred_vector)` strictly separated so the neural
    UserTower preserves explicit vs. inferred provenance without sensitive traits.
    """
    exp = profile.explicit_preferences or {}
    for k in exp:
        if k.lower() in SENSITIVE_ATTRIBUTE_BLOCKLIST:
            raise ValueError(f"Sensitive attribute '{k}' rejected by neural encoder.")

    explicit_vec = np.concatenate([
        _multi_hot(CATEGORY_VOCAB, exp.get("category", [])),
        _multi_hot(STYLE_VOCAB, exp.get("style", [])),
        _multi_hot(COLOR_VOCAB, exp.get("color", [])),
        _multi_hot(FIT_VOCAB, exp.get("fit", [])),
    ]).astype(np.float32)

    inf = profile.inferred_preferences or {}
    cat_aff_vec = np.asarray(
        [max(0.0, float(profile.category_affinity.get(c, 0.0))) for c in CATEGORY_VOCAB],
        dtype=np.float32,
    )
    style_inf = inf.get("style", {}) or {}
    max_s = max([abs(v) for v in style_inf.values()] or [1.0]) or 1.0
    style_inf_vec = np.asarray(
        [max(0.0, min(1.0, float(style_inf.get(s, 0.0)) / max_s)) for s in STYLE_VOCAB],
        dtype=np.float32,
    )
    color_inf = inf.get("color", {}) or {}
    max_c = max([abs(v) for v in color_inf.values()] or [1.0]) or 1.0
    color_inf_vec = np.asarray(
        [max(0.0, min(1.0, float(color_inf.get(c, 0.0)) / max_c)) for c in COLOR_VOCAB],
        dtype=np.float32,
    )

    # Pool positive garment visual embeddings if verified visuals exist
    vis_vecs = []
    for p_it in positive_items or ():
        pv, has_pv = _project_visual_embedding(p_it.visual_embedding)
        if has_pv > 0.5:
            vis_vecs.append(pv)
    if vis_vecs:
        vis_centroid = np.mean(np.stack(vis_vecs, axis=0), axis=0).astype(np.float32)
        vn = float(np.linalg.norm(vis_centroid))
        if vn > 1e-8:
            vis_centroid = vis_centroid / vn
    else:
        vis_centroid = np.zeros(VISUAL_PROJ_DIM, dtype=np.float32)

    inferred_scalars = np.asarray([
        min(1.0, float(profile.positive_interaction_count) / 10.0),
        1.0 if profile.is_cold_start else 0.0,
        min(1.0, float(sum(max(0.0, v) for v in profile.category_affinity.values())) / 3.0),
    ], dtype=np.float32)

    inferred_vec = np.concatenate([
        cat_aff_vec,
        style_inf_vec,
        color_inf_vec,
        inferred_scalars,
        vis_centroid,
    ]).astype(np.float32)

    return explicit_vec, inferred_vec


class TwoTowerRecommendationModel(nn.Module):
    """Independent PyTorch User & Item Towers producing L2-normalized embeddings."""

    def __init__(
        self,
        explicit_dim: int = USER_EXPLICIT_DIM,
        inferred_dim: int = USER_INFERRED_DIM,
        item_dim: int = ITEM_FEAT_DIM,
        embed_dim: int = EMBEDDING_DIM,
    ) -> None:
        super().__init__()
        self.explicit_dim = explicit_dim
        self.inferred_dim = inferred_dim
        self.item_dim = item_dim
        self.embed_dim = embed_dim

        # Separate explicit vs inferred branches inside User Tower
        self.explicit_branch = nn.Sequential(nn.Linear(explicit_dim, embed_dim), nn.ReLU())
        self.inferred_branch = nn.Sequential(nn.Linear(inferred_dim, embed_dim), nn.ReLU())
        self.user_fusion = nn.Sequential(
            nn.Linear(embed_dim * 2, embed_dim),
            nn.LayerNorm(embed_dim),
            nn.ReLU(),
            nn.Linear(embed_dim, embed_dim),
        )
        self.item_tower = nn.Sequential(
            nn.Linear(item_dim, embed_dim * 2),
            nn.LayerNorm(embed_dim * 2),
            nn.ReLU(),
            nn.Linear(embed_dim * 2, embed_dim),
        )
        self.logit_scale = nn.Parameter(torch.tensor(math.log(6.0), dtype=torch.float32))

    def encode_user(self, explicit_x: torch.Tensor, inferred_x: torch.Tensor) -> torch.Tensor:
        e_h = self.explicit_branch(explicit_x)
        i_h = self.inferred_branch(inferred_x)
        u = self.user_fusion(torch.cat([e_h, i_h], dim=-1))
        return F.normalize(u, p=2, dim=-1)

    def encode_item(self, item_x: torch.Tensor) -> torch.Tensor:
        v = self.item_tower(item_x)
        return F.normalize(v, p=2, dim=-1)

    def forward(
        self,
        explicit_x: torch.Tensor,
        inferred_x: torch.Tensor,
        item_x: torch.Tensor,
    ) -> torch.Tensor:
        u = self.encode_user(explicit_x, inferred_x)
        v = self.encode_item(item_x)
        scale = torch.clamp(self.logit_scale.exp(), min=1.0, max=25.0)
        return (u * v).sum(dim=-1) * scale


# Scalar signal order verified for NeuralRankingModel
NEURAL_RANK_SIGNAL_NAMES: Tuple[str, ...] = (
    "category_affinity",
    "visual_similarity",
    "contextual_relevance",
    "diversity_signal",
    "item_availability",
)


class NeuralRankingModel(nn.Module):
    """
    Hybrid Neural Candidate Ranker combining Two-Tower embeddings + verified algorithmic signals.
    Unverified signals are explicitly zero-masked via `signal_mask` so they never affect scores or attributions.
    """

    def __init__(self, embed_dim: int = EMBEDDING_DIM, scalar_dim: int = len(NEURAL_RANK_SIGNAL_NAMES)) -> None:
        super().__init__()
        self.embed_dim = embed_dim
        self.scalar_dim = scalar_dim
        in_dim = (embed_dim * 3) + 1 + scalar_dim  # [u, v, u*v, dot, masked_scalars]
        self.scorer = nn.Sequential(
            nn.Linear(in_dim, 48),
            nn.LayerNorm(48),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(48, 24),
            nn.ReLU(),
            nn.Linear(24, 1),
        )
        # Learnable interpretable linear skip weights initialized evenly
        self.scalar_skip = nn.Linear(scalar_dim, 1, bias=False)
        with torch.no_grad():
            self.scalar_skip.weight.fill_(0.25)

    def forward(
        self,
        user_emb: torch.Tensor,
        item_emb: torch.Tensor,
        scalar_signals: torch.Tensor,
        signal_mask: torch.Tensor,
    ) -> torch.Tensor:
        masked_scalars = scalar_signals * signal_mask
        dot = (user_emb * item_emb).sum(dim=-1, keepdim=True)
        hadamard = user_emb * item_emb
        x = torch.cat([user_emb, item_emb, hadamard, dot, masked_scalars], dim=-1)
        mlp_out = self.scorer(x).squeeze(-1)
        skip_out = self.scalar_skip(masked_scalars).squeeze(-1)
        return mlp_out + skip_out

    def explain_verified_attributions(
        self,
        scalar_signals: torch.Tensor,
        signal_mask: torch.Tensor,
        user_emb: torch.Tensor,
        item_emb: torch.Tensor,
    ) -> Dict[str, float]:
        """Returns attribution magnitudes strictly over verified non-masked factors."""
        with torch.no_grad():
            dot_val = float((user_emb * item_emb).sum().item())
            weights = self.scalar_skip.weight.squeeze(0)
            out: Dict[str, float] = {"embedding_similarity": round(max(0.0, (dot_val + 1.0) * 0.5), 4)}
            for idx, name in enumerate(NEURAL_RANK_SIGNAL_NAMES):
                if float(signal_mask[idx].item()) > 0.5:
                    contrib = float((scalar_signals[idx] * weights[idx]).item())
                    out[name] = round(contrib, 4)
            return out


MIN_SEQ_LEN_FOR_TRANSFORMER = 3


class SequentialTransformerRecommender(nn.Module):
    """
    Time-aware causal Transformer sequential model over chronological non-view positive interactions.
    Uses upper-triangular causal masks, positional embeddings, sinusoidal time-delta encodings,
    and a residual skip from the last observed item so short sequences degrade smoothly.
    """

    def __init__(self, item_dim: int = ITEM_FEAT_DIM, d_model: int = EMBEDDING_DIM, nhead: int = 4, num_layers: int = 2, max_seq_len: int = 64) -> None:
        super().__init__()
        self.d_model = d_model
        self.item_proj = nn.Linear(item_dim, d_model)
        self.type_emb = nn.Embedding(8, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.time_proj = nn.Linear(4, d_model)  # sinusoidal log-delta-days encoding
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=d_model * 2, dropout=0.1, batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.out_proj = nn.Linear(d_model, d_model)

    @staticmethod
    def encode_time_deltas(delta_days: torch.Tensor) -> torch.Tensor:
        d = torch.log1p(torch.clamp(delta_days, min=0.0)).unsqueeze(-1)
        freqs = torch.tensor([0.5, 1.0, 2.0, 4.0], dtype=d.dtype, device=d.device)
        return torch.sin(d * freqs)

    def encode_sequence(
        self,
        item_feats: torch.Tensor,      # (B, T, item_dim)
        action_types: torch.Tensor,    # (B, T)
        delta_days: torch.Tensor,      # (B, T)
        padding_mask: Optional[torch.Tensor] = None,  # (B, T) True where padded
    ) -> torch.Tensor:
        t_len = item_feats.size(1)
        item_h = self.item_proj(item_feats)
        pos_ids = torch.arange(t_len, device=item_h.device).clamp(max=self.pos_emb.num_embeddings - 1).unsqueeze(0)
        h = (
            item_h
            + self.type_emb(torch.clamp(action_types, 0, 7))
            + self.pos_emb(pos_ids)
            + self.time_proj(self.encode_time_deltas(delta_days))
        )
        causal_mask = torch.triu(torch.ones((t_len, t_len), device=h.device, dtype=torch.bool), diagonal=1)
        out = self.transformer(h, mask=causal_mask, src_key_padding_mask=padding_mask)
        if padding_mask is not None:
            valid_lens = (~padding_mask).sum(dim=1).clamp(min=1) - 1
            batch_idx = torch.arange(out.size(0), device=out.device)
            last_h = out[batch_idx, valid_lens]
            last_raw = item_h[batch_idx, valid_lens]
        else:
            last_h = out[:, -1]
            last_raw = item_h[:, -1]
        # Residual blend stabilizes ultra-short sequences while letting Transformer shape longer sequences
        return F.normalize(self.out_proj(last_h) + 0.35 * last_raw, p=2, dim=-1)


class NeuralOutfitCompatibilityModel(nn.Module):
    """
    Stage 7 Set-Pooling & Pairwise Outfit Compatibility Predictor.
    Predicts calibrated compatibility logits (prediction, NOT a deterministic rule) across
    2-to-4 garment ensembles using normalized item representations, pairwise Hadamard & diff terms,
    and explicit category/slot diversity features.
    """

    def __init__(self, item_dim: int = ITEM_FEAT_DIM, embed_dim: int = EMBEDDING_DIM) -> None:
        super().__init__()
        self.item_encoder = nn.Sequential(
            nn.Linear(item_dim, embed_dim * 2),
            nn.LayerNorm(embed_dim * 2),
            nn.ReLU(),
            nn.Linear(embed_dim * 2, embed_dim),
        )
        # Combines mean pooled set, max pooled set, mean pairwise interaction |h_i - h_j|, h_i * h_j, and slot conflict indicators
        in_dim = (embed_dim * 4) + 3  # +3 = unique_cat_ratio, formal_spread, slot_conflict_flag
        self.compat_head = nn.Sequential(
            nn.Linear(in_dim, 48),
            nn.LayerNorm(48),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(48, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
        )

    def encode_outfit(
        self,
        item_feats: torch.Tensor,         # (B, M, item_dim)
        slot_stats: torch.Tensor,         # (B, 3) -> [unique_cat_ratio, formal_spread_norm, duplicate_primary_flag]
        item_mask: Optional[torch.Tensor] = None,  # (B, M) 1.0 real item, 0.0 pad
    ) -> torch.Tensor:
        h = F.normalize(self.item_encoder(item_feats), p=2, dim=-1)  # (B, M, D)
        if item_mask is None:
            item_mask = torch.ones((h.size(0), h.size(1)), dtype=h.dtype, device=h.device)
        m_exp = item_mask.unsqueeze(-1)
        counts = item_mask.sum(dim=1, keepdim=True).clamp(min=1.0)
        mean_h = (h * m_exp).sum(dim=1) / counts
        masked_for_max = h.masked_fill(m_exp == 0, -1e4)
        max_h = masked_for_max.max(dim=1).values

        # Mean pairwise interaction across unordered valid pairs
        b_sz, m_len, d_dim = h.shape
        pair_prod_acc = torch.zeros((b_sz, d_dim), dtype=h.dtype, device=h.device)
        pair_diff_acc = torch.zeros((b_sz, d_dim), dtype=h.dtype, device=h.device)
        pair_denom = torch.zeros((b_sz, 1), dtype=h.dtype, device=h.device)
        for i in range(m_len):
            for j in range(i + 1, m_len):
                valid = (item_mask[:, i] * item_mask[:, j]).unsqueeze(-1)
                pair_prod_acc = pair_prod_acc + valid * (h[:, i] * h[:, j])
                pair_diff_acc = pair_diff_acc + valid * torch.abs(h[:, i] - h[:, j])
                pair_denom = pair_denom + valid
        pair_denom = pair_denom.clamp(min=1.0)
        pair_prod = pair_prod_acc / pair_denom
        pair_diff = pair_diff_acc / pair_denom

        feats = torch.cat([mean_h, max_h, pair_prod, pair_diff, slot_stats], dim=-1)
        return self.compat_head(feats).squeeze(-1)


class GraphRecommendationModel(nn.Module):
    """
    Provenance-aware LightGCN-style normalized message passing over consented
    Users <-> Garments <-> Categories/Styles graph edges in pure PyTorch.
    """

    def __init__(self, num_nodes: int, embed_dim: int = EMBEDDING_DIM, num_layers: int = 2) -> None:
        super().__init__()
        self.num_nodes = num_nodes
        self.embed_dim = embed_dim
        self.num_layers = num_layers
        self.node_embeddings = nn.Embedding(num_nodes, embed_dim)
        nn.init.xavier_uniform_(self.node_embeddings.weight)

    @staticmethod
    def build_normalized_adjacency(num_nodes: int, edges: Sequence[Tuple[int, int]]) -> torch.Tensor:
        adj = torch.eye(num_nodes, dtype=torch.float32)
        for u, v in edges:
            if 0 <= u < num_nodes and 0 <= v < num_nodes:
                adj[u, v] += 1.0
                adj[v, u] += 1.0
        deg = adj.sum(dim=1).clamp(min=1.0)
        d_inv_sqrt = torch.pow(deg, -0.5)
        return d_inv_sqrt.unsqueeze(1) * adj * d_inv_sqrt.unsqueeze(0)

    def propagate(self, norm_adj: torch.Tensor) -> torch.Tensor:
        x = self.node_embeddings.weight
        layers = [x]
        for _ in range(self.num_layers):
            x = torch.matmul(norm_adj, x)
            layers.append(x)
        out = torch.mean(torch.stack(layers, dim=0), dim=0)
        return F.normalize(out, p=2, dim=-1)


def save_neural_checkpoint(
    path: str,
    *,
    model_id: str,
    version: str,
    state_dict: Dict[str, Any],
    extra_metadata: Dict[str, Any],
) -> str:
    """Saves PyTorch state_dict + metadata cleanly and returns hex SHA-256 digest."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    payload = {
        "model_id": model_id,
        "version": version,
        "schema_version": NEURAL_REC_SCHEMA_VERSION,
        "state_dict": state_dict,
        "metadata": extra_metadata,
    }
    torch.save(payload, path)
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def verify_and_load_neural_checkpoint(
    path: str,
    *,
    expected_sha256: Optional[str] = None,
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """Verifies checkpoint file existence, optional SHA-256 digest, and safe weights load."""
    if not path or not os.path.isfile(path):
        return False, None, "Checkpoint file absent"
    try:
        raw = open(path, "rb").read()
    except OSError as exc:
        return False, None, f"Checkpoint read error: {exc}"
    actual_sha = hashlib.sha256(raw).hexdigest()
    if expected_sha256 and actual_sha != expected_sha256.lower():
        return False, None, "Checkpoint SHA-256 digest mismatch"
    try:
        import io
        # Weights + small python metadata dict saved by save_neural_checkpoint
        data = torch.load(io.BytesIO(raw), map_location="cpu", weights_only=False)
        if not isinstance(data, dict) or "state_dict" not in data:
            return False, None, "Invalid checkpoint payload structure"
        return True, data, actual_sha
    except Exception as exc:
        return False, None, f"Checkpoint deserialize failed: {type(exc).__name__}"
