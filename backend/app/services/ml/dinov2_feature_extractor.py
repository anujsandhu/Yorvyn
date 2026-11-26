"""
YORVYN — DINOv2 Visual Feature Extraction Adapter (Phase 14.22 Workstream A3)
Extracts robust, self-supervised semantic and structural visual embeddings from garment photographs.
Supports:
- Global image representation (CLS token embedding, 384-dim)
- Dense patch-level feature maps for local component and texture analysis
- Cross-view visual consistency and feature distance measurement
- Optimized inference on Apple Silicon M2 MPS (with CPU fallback)
"""

import time
import logging
import os
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
import numpy as np
from PIL import Image

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class Dinov2FeatureExtractor:
    """Extracts dense and global visual features using DINOv2 vision transformer architecture."""

    def __init__(self, model_name: str = "facebook/dinov2-small", device: Optional[str] = None):
        self.model_name = model_name
        if device is None:
            if torch.backends.mps.is_available():
                self.device = torch.device("mps")
            else:
                self.device = torch.device("cpu")
        else:
            self.device = torch.device(device)

        self._model = None
        self._processor = None
        self.execution_backend = "uninitialized"
        self.pretrained_weights_loaded = False
        self.successful_inferences = 0
        self.embedding_dim = 384
        self.patch_size = 14
        self.input_size = 224
        logger.info(f"Initialized Dinov2FeatureExtractor on {self.device}")

    @property
    def cached_weights_available(self) -> bool:
        """Report whether the local Hugging Face cache appears to contain model weights."""
        hf_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
        repo_dir = hf_home / "hub" / ("models--" + self.model_name.replace("/", "--"))
        snapshots = repo_dir / "snapshots"
        if not snapshots.is_dir():
            return False
        for snapshot in snapshots.iterdir():
            if snapshot.is_dir() and (snapshot / "config.json").is_file() and any(
                (snapshot / weight_name).is_file()
                for weight_name in ("model.safetensors", "pytorch_model.bin", "model.safetensors.index.json")
            ):
                return True
        return False

    def _ensure_model(self):
        """Loads cached DINOv2 weights without network access or marks an untrained fallback."""
        if self._model is not None:
            return

        try:
            from transformers import AutoImageProcessor, AutoModel
            self._processor = AutoImageProcessor.from_pretrained(self.model_name, local_files_only=True)
            self._model = AutoModel.from_pretrained(self.model_name, local_files_only=True).to(self.device)
            self._model.eval()
            self.execution_backend = "cached_pretrained_dinov2"
            self.pretrained_weights_loaded = True
            logger.info(f"Successfully loaded {self.model_name} onto {self.device}")
        except Exception as e:
            logger.warning(f"Cached DINOv2 unavailable ({e}); using explicitly untrained shape-only fallback.")
            self._model = self._create_native_backbone().to(self.device)
            self._model.eval()
            self.execution_backend = "untrained_random_vit_shape_fallback"

    def _create_native_backbone(self) -> nn.Module:
        """Lightweight native PyTorch ViT architecture matching DINOv2-Small 384-dim dimensions."""
        class LightweightViTBackbone(nn.Module):
            def __init__(self, embed_dim=384, patch_size=14, in_channels=3):
                super().__init__()
                self.patch_embed = nn.Conv2d(in_channels, embed_dim, kernel_size=patch_size, stride=patch_size)
                self.cls_token = nn.Parameter(torch.zeros(1, 1, embed_dim))
                self.norm = nn.LayerNorm(embed_dim)
                self.proj = nn.Sequential(
                    nn.Linear(embed_dim, embed_dim),
                    nn.GELU(),
                    nn.Linear(embed_dim, embed_dim)
                )

            def forward(self, x):
                b = x.shape[0]
                patches = self.patch_embed(x)  # (b, embed_dim, h', w')
                h_p, w_p = patches.shape[2], patches.shape[3]
                patches = patches.flatten(2).transpose(1, 2)  # (b, n_patches, embed_dim)
                cls_tokens = self.cls_token.expand(b, -1, -1)
                tokens = torch.cat((cls_tokens, patches), dim=1)
                normed = self.norm(tokens)
                features = self.proj(normed)
                return {
                    "last_hidden_state": features,
                    "pooler_output": features[:, 0],
                    "patch_features": features[:, 1:].reshape(b, h_p, w_p, -1)
                }

        return LightweightViTBackbone(embed_dim=self.embedding_dim, patch_size=self.patch_size)

    def extract_features(self, image: Image.Image) -> Dict[str, Any]:
        """
        Extracts global CLS embedding and dense patch feature maps from image.
        Returns dictionary with cls_embedding, patch_features, latency_ms, device.
        """
        t0 = time.perf_counter()
        self._ensure_model()

        img_rgb = image.convert("RGB").resize((self.input_size, self.input_size), Image.Resampling.BILINEAR)
        img_np = np.array(img_rgb).astype(np.float32) / 255.0
        # Normalize with ImageNet mean/std
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        norm_np = (img_np - mean) / std
        tensor_in = torch.from_numpy(norm_np).permute(2, 0, 1).unsqueeze(0).to(self.device)

        with torch.no_grad():
            outputs = self._model(tensor_in)
            if isinstance(outputs, dict):
                cls_emb = outputs["pooler_output"].cpu().numpy()[0]
                patch_feats = outputs.get("patch_features")
                if patch_feats is not None:
                    patch_np = patch_feats.cpu().numpy()[0]
                else:
                    patch_np = outputs["last_hidden_state"][:, 1:].cpu().numpy()[0]
            else:
                last_hidden = outputs.last_hidden_state
                cls_emb = last_hidden[:, 0].cpu().numpy()[0]
                patch_np = last_hidden[:, 1:].cpu().numpy()[0]

        if self.pretrained_weights_loaded:
            self.successful_inferences += 1

        # L2 normalize CLS embedding
        norm = np.linalg.norm(cls_emb)
        if norm > 1e-6:
            cls_emb = cls_emb / norm

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "model": self.model_name if self.pretrained_weights_loaded else self.execution_backend,
            "device": str(self.device),
            "execution_backend": self.execution_backend,
            "pretrained_weights_loaded": self.pretrained_weights_loaded,
            "semantic_valid": self.pretrained_weights_loaded,
            "embedding_dim": int(cls_emb.shape[0]),
            "cls_embedding": cls_emb,
            "patch_feature_shape": list(patch_np.shape),
            "latency_ms": latency_ms
        }

    def compute_similarity(self, emb_a: np.ndarray, emb_b: np.ndarray) -> float:
        """Computes cosine similarity between two feature embeddings in [-1.0, 1.0]."""
        dot = float(np.dot(emb_a, emb_b))
        norm_a = float(np.linalg.norm(emb_a))
        norm_b = float(np.linalg.norm(emb_b))
        if norm_a < 1e-6 or norm_b < 1e-6:
            return 0.0
        return max(-1.0, min(1.0, dot / (norm_a * norm_b)))


dinov2_extractor = Dinov2FeatureExtractor()
