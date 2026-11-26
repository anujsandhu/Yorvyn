"""
YORVYN — 3D Garment Reconstruction Engine Registry
Dispatches category/subcategory pairs to specialized reconstruction engines.
Zero generic cylinder fallbacks — guarantees dedicated anatomical pattern construction
for tops, formal shirts, hoodies, jackets, bottoms, dresses, traditional wear, footwear, and accessories.
"""

from typing import Dict, List, Optional, Any
import logging

from .base_reconstruction_engine import IGarmentReconstructionEngine
from .tops_engine import TopsReconstructionEngine
from .shirt_engine import ShirtReconstructionEngine
from .hoodie_engine import HoodieReconstructionEngine
from .jacket_engine import JacketReconstructionEngine
from .bottoms_engine import BottomsReconstructionEngine
from .dress_engine import DressReconstructionEngine
from .traditional_engine import TraditionalWearReconstructionEngine
from .footwear_engine import FootwearReconstructionEngine
from .accessories_engine import AccessoriesReconstructionEngine
from .neural.neural_reconstruction_engine import NeuralGarmentReconstructionEngine

logger = logging.getLogger(__name__)


class ReconstructionEngineRegistry:
    """Registry managing category-specific 3D garment reconstruction engines."""

    def __init__(self):
        self._engines: Dict[str, IGarmentReconstructionEngine] = {}
        self._register_default_engines()

    def register(self, engine: IGarmentReconstructionEngine) -> None:
        self._engines[engine.engine_id] = engine

    def _register_default_engines(self) -> None:
        self.tops_engine = TopsReconstructionEngine()
        self.shirt_engine = ShirtReconstructionEngine()
        self.hoodie_engine = HoodieReconstructionEngine()
        self.jacket_engine = JacketReconstructionEngine()
        self.bottoms_engine = BottomsReconstructionEngine()
        self.dress_engine = DressReconstructionEngine()
        self.traditional_engine = TraditionalWearReconstructionEngine()
        self.footwear_engine = FootwearReconstructionEngine()
        self.accessories_engine = AccessoriesReconstructionEngine()
        self.neural_engine = NeuralGarmentReconstructionEngine()

        self.register(self.tops_engine)
        self.register(self.shirt_engine)
        self.register(self.hoodie_engine)
        self.register(self.jacket_engine)
        self.register(self.bottoms_engine)
        self.register(self.dress_engine)
        self.register(self.traditional_engine)
        self.register(self.footwear_engine)
        self.register(self.accessories_engine)
        self.register(self.neural_engine)

    def get_neural_engine(self) -> NeuralGarmentReconstructionEngine:
        return self.neural_engine

    def get_engine(self, category: str, subcategory: str, prefer_neural: bool = False) -> IGarmentReconstructionEngine:
        if prefer_neural:
            return self.neural_engine
        cat = category.lower().strip()
        subcat = subcategory.lower().strip()

        # 1. Footwear
        if cat in ["footwear", "shoes", "sneakers"] or subcat in ["sneakers", "running_shoes", "boots", "shoes", "formal_shoes", "sandals"]:
            return self.footwear_engine

        # 2. Traditional & Cultural Wear
        if cat in ["traditional", "ethnic_wear", "cultural_wear"] or subcat in ["kurta", "sherwani", "saree", "lehenga", "salwar_suit"]:
            return self.traditional_engine

        # 3. Bottoms
        if cat in ["bottom", "bottoms", "pants", "trousers", "jeans", "shorts"] or subcat in ["jeans", "straight_fit_jeans", "slim_fit_jeans", "wide_leg_jeans", "trousers", "chinos", "joggers", "cargo_pants", "shorts", "formal_pants"]:
            return self.bottoms_engine

        # 4. Dresses & Skirts
        if cat in ["dress", "skirt", "dresses", "skirts", "dresses_and_skirts"] or subcat in ["dress", "casual_dress", "formal_dress", "gown", "maxi_dress", "mini_dress", "skirt", "a_line_skirt", "pleated_skirt"]:
            return self.dress_engine

        # 5. Accessories & Headwear
        if cat in ["accessories", "hats", "caps"] or subcat in ["caps", "hats", "scarves", "beanies", "baseball_cap"]:
            return self.accessories_engine

        # 6. Outerwear & Jackets
        if cat in ["outerwear", "jackets", "coats", "blazers"] or subcat in ["jacket", "denim_jacket", "leather_jacket", "bomber_jacket", "blazer", "formal_coat", "trench_coat", "parka", "windbreaker"]:
            return self.jacket_engine

        # 7. Hoodies & Hooded Tops
        if subcat in ["hoodie", "zip_hoodie", "pullover_hoodie", "hooded_sweatshirt"]:
            return self.hoodie_engine

        # 8. Formal & Casual Shirts
        if subcat in ["formal_shirt", "casual_shirt", "oversized_shirt", "oxford_shirt", "shirt", "button_down", "polo_shirt"]:
            return self.shirt_engine

        # 9. Tops Fallback (T-shirts, sweaters, etc.)
        return self.tops_engine

    def validate_construction_handoff(self, handoff: Any) -> Dict[str, Any]:
        """Verify Phase 16.2 ConstructionToGeometryHandoff compatibility with registered engines."""
        engine = self.get_engine(handoff.category, handoff.subcategory)
        val = handoff.validation_report
        return {
            "garment_id": handoff.garment_id,
            "target_engine_id": engine.engine_id,
            "handoff_engine_id": handoff.target_engine_id,
            "engine_match": engine.engine_id == handoff.target_engine_id,
            "compatible": bool(handoff.engine_compatible and val.is_valid and engine.engine_id == handoff.target_engine_id),
            "evidence_supported_count": len(handoff.evidence_supported_features),
            "inferred_count": len(handoff.inferred_features),
            "missing_or_ambiguous_count": len(handoff.missing_or_ambiguous_features),
            "invalid_count": len(handoff.invalid_features),
            "pieces_count": len(handoff.construction_graph.pieces),
            "seams_count": len(handoff.construction_graph.seams),
        }

    def list_engines(self) -> List[Dict[str, Any]]:
        return [
            {
                "engine_id": eng.engine_id,
                "supported_categories": eng.supported_categories,
                "supported_subcategories": eng.supported_subcategories
            }
            for eng in self._engines.values()
        ]


reconstruction_registry = ReconstructionEngineRegistry()
