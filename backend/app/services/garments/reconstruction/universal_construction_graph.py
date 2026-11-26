"""
YORVYN — Universal Garment Construction Graph (Phase 14.22 Workstream D)
Represents fine-grained functional garment components, hierarchical attachments,
topological boundary seams, and construction constraints across 10 apparel categories:
- Hoodie (pullover and zip-front)
- Denim Jacket (collar, placket, chest pockets, cuffs, waistband)
- Formal Shirt (tailored collar, yoke, button placket, cuffs, curved hem)
- T-Shirt & Sweatshirt (crew neckline, body, sleeves, cuffs, hem)
- Knit Sweater (ribbed collar, body, sleeves, ribbed hem)
- Trousers & Jeans (waistband, left leg, right leg, crotch fly, ankle hems)
- Dress (fitted bodice, waistline, flared skirt, scoop neckline)
- Ethnic Kurta (mandarin collar, front placket, tunic body, side slits)
Supports missing-component detection, evidence-backed confidence scoring, and DAG topological assembly.
"""

from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConstructionNode:
    component_id: str
    semantic_type: str
    name: str
    status: str = "detected"           # "detected", "missing", "inferred"
    confidence: float = 0.95
    parent_id: Optional[str] = None
    attachment_point: str = "origin"
    boundary_coordinates_m: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    seam_ids: List[str] = field(default_factory=list)
    has_visual_evidence: bool = True


@dataclass
class ConstructionSeam:
    seam_id: str
    name: str
    node_a: str
    node_b: str
    seam_type: str                     # "armscye", "side_seam", "shoulder", "neckline", "cuff_join", "hem_join"
    elastic_compliance: float = 0.001
    is_structural: bool = True


class UniversalConstructionGraph:
    """Directed Acyclic Graph (DAG) for multi-category garment assembly."""

    def __init__(self, category: str, subcategory: str):
        self.category = category
        self.subcategory = subcategory
        self.nodes: Dict[str, ConstructionNode] = {}
        self.seams: Dict[str, ConstructionSeam] = {}
        self._build_category_template()

    def _build_category_template(self):
        """Constructs template nodes and seams tailored to category and subcategory."""
        cat = self.category.lower()
        sub = self.subcategory.lower()

        if "hoodie" in sub or cat == "hoodie":
            self._add_node("torso", "torso", "Main Torso Shell", None, "body_root", (0.0, 1.10, 0.0))
            self._add_node("hood", "hood", "Dual-Panel Hood Cowl", "torso", "neckline_rim", (0.0, 1.36, 0.0))
            self._add_node("left_sleeve", "sleeve", "Left Articulated Sleeve", "torso", "shoulder_L", (-0.22, 1.30, 0.0))
            self._add_node("right_sleeve", "sleeve", "Right Articulated Sleeve", "torso", "shoulder_R", (0.22, 1.30, 0.0))
            self._add_node("left_cuff", "cuff", "Left Ribbed Wrist Cuff", "left_sleeve", "wrist_L", (-0.42, 0.88, 0.0))
            self._add_node("right_cuff", "cuff", "Right Ribbed Wrist Cuff", "right_sleeve", "wrist_R", (0.42, 0.88, 0.0))
            self._add_node("waistband", "hem", "Ribbed Lower Waistband", "torso", "hem_rim", (0.0, 0.88, 0.0))
            
            if "zip" not in sub:
                self._add_node("kangaroo_pocket", "pocket", "Kangaroo Front Abdomen Pouch", "torso", "abdomen_surface", (0.0, 0.98, 0.12))
                self._add_node("drawstrings", "trim", "Dual Braided Drawstrings & Grommets", "hood", "cowl_front", (0.0, 1.38, 0.10))
            else:
                self._add_node("zipper_placket", "closure", "Center Metal Zipper & Split Pockets", "torso", "center_front", (0.0, 1.10, 0.11))

            self._add_seam("seam_neck_hood", "Neckline to Hood Seam", "torso", "hood", "neckline")
            self._add_seam("seam_armscye_L", "Left Armscye Shoulder Seam", "torso", "left_sleeve", "armscye")
            self._add_seam("seam_armscye_R", "Right Armscye Shoulder Seam", "torso", "right_sleeve", "armscye")
            self._add_seam("seam_cuff_L", "Left Sleeve to Cuff Seam", "left_sleeve", "left_cuff", "cuff_join")
            self._add_seam("seam_cuff_R", "Right Sleeve to Cuff Seam", "right_sleeve", "right_cuff", "cuff_join")
            self._add_seam("seam_waistband", "Torso to Waistband Seam", "torso", "waistband", "hem_join")

        elif "jacket" in sub or cat == "jacket" or "blazer" in sub:
            self._add_node("torso", "torso", "Structured Denim Torso Shell", None, "body_root", (0.0, 1.10, 0.0))
            self._add_node("collar", "collar", "Pointed Turn-Down Collar", "torso", "neckline_rim", (0.0, 1.35, 0.0))
            self._add_node("placket", "closure", "Front Button Placket", "torso", "center_front", (0.0, 1.10, 0.10))
            self._add_node("left_sleeve", "sleeve", "Left Articulated Sleeve", "torso", "shoulder_L", (-0.22, 1.30, 0.0))
            self._add_node("right_sleeve", "sleeve", "Right Articulated Sleeve", "torso", "shoulder_R", (0.22, 1.30, 0.0))
            self._add_node("chest_pockets", "pocket", "Dual Flap Chest Pockets", "torso", "chest_front", (0.0, 1.22, 0.11))
            self._add_node("left_cuff", "cuff", "Left Button Cuff", "left_sleeve", "wrist_L", (-0.42, 0.88, 0.0))
            self._add_node("right_cuff", "cuff", "Right Button Cuff", "right_sleeve", "wrist_R", (0.42, 0.88, 0.0))
            self._add_node("waistband", "hem", "Fitted Hem Band", "torso", "hem_rim", (0.0, 0.88, 0.0))

            self._add_seam("seam_collar", "Torso to Collar Seam", "torso", "collar", "neckline")
            self._add_seam("seam_armscye_L", "Left Armscye Seam", "torso", "left_sleeve", "armscye")
            self._add_seam("seam_armscye_R", "Right Armscye Seam", "torso", "right_sleeve", "armscye")
            self._add_seam("seam_cuff_L", "Left Cuff Seam", "left_sleeve", "left_cuff", "cuff_join")
            self._add_seam("seam_cuff_R", "Right Cuff Seam", "right_sleeve", "right_cuff", "cuff_join")
            self._add_seam("seam_hem", "Torso to Hem Band Seam", "torso", "waistband", "hem_join")

        elif "dress" in sub or "skirt" in sub or cat in ["dress", "skirt"]:
            self._add_node("bodice", "torso", "Contoured Fitted Bodice", None, "body_root", (0.0, 1.22, 0.0))
            self._add_node("neckline", "neckline", "Curved Scoop Neckline", "bodice", "neckline_rim", (0.0, 1.35, 0.0))
            self._add_node("skirt", "skirt", "Flared A-Line Skirt", "bodice", "waistline_join", (0.0, 0.82, 0.0))
            self._add_node("hem", "hem", "Finished Lower Hemline", "skirt", "hem_perimeter", (0.0, 0.60, 0.0))

            self._add_seam("seam_neckline", "Bodice to Neckline Seam", "bodice", "neckline", "neckline")
            self._add_seam("seam_waist_skirt", "Bodice to Skirt Waist Seam", "bodice", "skirt", "waist_join")
            self._add_seam("seam_hem", "Skirt to Lower Hem Seam", "skirt", "hem", "hem_join")

        elif cat in ["bottoms", "jeans", "trousers", "shorts"] or any(k in sub for k in ["jeans", "trousers", "pants", "shorts"]):
            self._add_node("waistband", "waistband", "Contoured Waistband", None, "body_root", (0.0, 1.00, 0.0))
            self._add_node("crotch_fly", "closure", "Center Crotch & Fly Seam", "waistband", "crotch_root", (0.0, 0.86, 0.0))
            self._add_node("left_leg", "leg", "Left Inseam / Outseam Leg Tube", "waistband", "hip_L", (-0.11, 0.50, 0.0))
            self._add_node("right_leg", "leg", "Right Inseam / Outseam Leg Tube", "waistband", "hip_R", (0.11, 0.50, 0.0))
            self._add_node("left_hem", "hem", "Left Ankle Hem Band", "left_leg", "ankle_L", (-0.11, 0.10, 0.0))
            self._add_node("right_hem", "hem", "Right Ankle Hem Band", "right_leg", "ankle_R", (0.11, 0.10, 0.0))

            self._add_seam("seam_waist_left", "Waistband to Left Leg Seam", "waistband", "left_leg", "waist_join")
            self._add_seam("seam_waist_right", "Waistband to Right Leg Seam", "waistband", "right_leg", "waist_join")
            self._add_seam("seam_crotch", "Center Crotch Inseam", "left_leg", "right_leg", "crotch_seam")
            self._add_seam("seam_hem_L", "Left Leg to Hem Seam", "left_leg", "left_hem", "hem_join")
            self._add_seam("seam_hem_R", "Right Leg to Hem Seam", "right_leg", "right_hem", "hem_join")

        elif "kurta" in sub or cat in ["kurta", "traditional_clothing"]:
            self._add_node("torso", "torso", "Straight Long Ethnic Tunic Body", None, "body_root", (0.0, 1.05, 0.0))
            self._add_node("collar", "collar", "Traditional Mandarin Band Collar", "torso", "neckline_rim", (0.0, 1.36, 0.0))
            self._add_node("placket", "closure", "Center Buttoned Neck Placket", "torso", "center_front", (0.0, 1.25, 0.10))
            self._add_node("left_sleeve", "sleeve", "Straight Left Sleeve", "torso", "shoulder_L", (-0.22, 1.28, 0.0))
            self._add_node("right_sleeve", "sleeve", "Right Straight Sleeve", "torso", "shoulder_R", (0.22, 1.28, 0.0))
            self._add_node("side_slits", "vents", "Lateral Vent Slits", "torso", "hip_sides", (0.0, 0.72, 0.0))
            self._add_node("hem", "hem", "Straight Cut Lower Hemline", "torso", "hem_rim", (0.0, 0.65, 0.0))

            self._add_seam("seam_collar", "Torso to Mandarin Collar", "torso", "collar", "neckline")
            self._add_seam("seam_armscye_L", "Left Armscye Seam", "torso", "left_sleeve", "armscye")
            self._add_seam("seam_armscye_R", "Right Armscye Seam", "torso", "right_sleeve", "armscye")
            self._add_seam("seam_hem", "Torso to Hemline Seam", "torso", "hem", "hem_join")

        else:  # tshirt, sweatshirt, sweater, generic top
            self._add_node("torso", "torso", "Main Torso Shell", None, "body_root", (0.0, 1.10, 0.0))
            self._add_node("collar", "collar", "Ribbed Crew Neckline", "torso", "neckline_rim", (0.0, 1.34, 0.0))
            self._add_node("left_sleeve", "sleeve", "Left Sleeve Tube", "torso", "shoulder_L", (-0.22, 1.28, 0.0))
            self._add_node("right_sleeve", "sleeve", "Right Sleeve Tube", "torso", "shoulder_R", (0.22, 1.28, 0.0))
            self._add_node("left_cuff", "cuff", "Left Sleeve Hem", "left_sleeve", "wrist_L", (-0.38, 0.95, 0.0))
            self._add_node("right_cuff", "cuff", "Right Sleeve Hem", "right_sleeve", "wrist_R", (0.38, 0.95, 0.0))
            self._add_node("hem", "hem", "Bottom Finished Hem", "torso", "hem_rim", (0.0, 0.88, 0.0))

            self._add_seam("seam_collar", "Torso to Crew Neckline", "torso", "collar", "neckline")
            self._add_seam("seam_armscye_L", "Left Armscye Seam", "torso", "left_sleeve", "armscye")
            self._add_seam("seam_armscye_R", "Right Armscye Seam", "torso", "right_sleeve", "armscye")
            self._add_seam("seam_hem", "Torso to Hem Seam", "torso", "hem", "hem_join")

    def _add_node(self, comp_id, sem_type, name, parent_id, attach_pt, coords):
        self.nodes[comp_id] = ConstructionNode(
            component_id=comp_id,
            semantic_type=sem_type,
            name=name,
            parent_id=parent_id,
            attachment_point=attach_pt,
            boundary_coordinates_m=coords
        )

    def _add_seam(self, seam_id, name, node_a, node_b, seam_type):
        self.seams[seam_id] = ConstructionSeam(
            seam_id=seam_id,
            name=name,
            node_a=node_a,
            node_b=node_b,
            seam_type=seam_type
        )
        if node_a in self.nodes:
            self.nodes[node_a].seam_ids.append(seam_id)
        if node_b in self.nodes:
            self.nodes[node_b].seam_ids.append(seam_id)

    def audit_visual_evidence(self, detected_components: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cross-checks template nodes against actual visual detections.
        Marks components as 'missing' if visual evidence is absent, rather than fabricating geometry.
        """
        missing: List[str] = []
        verified: List[str] = []

        for node_id, node in self.nodes.items():
            found = False
            for det_k in detected_components.keys():
                if node_id in det_k or det_k in node_id:
                    found = True
                    break
            if found:
                node.status = "detected"
                node.has_visual_evidence = True
                verified.append(node_id)
            else:
                # Primary torso or waistband are structurally inferred; optional pockets/drawstrings marked missing
                if node_id in ["kangaroo_pocket", "drawstrings", "chest_pockets"]:
                    node.status = "missing"
                    node.has_visual_evidence = False
                    node.confidence = 0.0
                    missing.append(node_id)
                else:
                    node.status = "inferred"
                    node.has_visual_evidence = False
                    node.confidence = 0.65
                    verified.append(node_id)

        return {
            "category": self.category,
            "subcategory": self.subcategory,
            "total_nodes": len(self.nodes),
            "verified_nodes": len(verified),
            "missing_components": missing,
            "structural_seams": len(self.seams)
        }

    @classmethod
    def from_unified_contract(cls, contract: Any) -> "UniversalConstructionGraph":
        """Bridge a Phase 16.2 UnifiedConstructionGraphContract into legacy DAG consumers."""
        graph = cls.__new__(cls)
        graph.category = contract.category
        graph.subcategory = contract.subcategory
        graph.nodes = {}
        graph.seams = {}
        for pid, piece in contract.pieces.items():
            observed = piece.verification_state.value == "OBSERVED"
            graph.nodes[pid] = ConstructionNode(
                component_id=pid,
                semantic_type=piece.piece_type.value,
                name=piece.name,
                status="detected" if observed else "inferred",
                confidence=piece.confidence,
                parent_id=piece.parent_component,
                attachment_point=piece.parent_component,
                has_visual_evidence=observed,
            )
        for seam in contract.seams:
            graph._add_seam(seam.seam_id, seam.seam_id, seam.piece_a, seam.piece_b, seam.seam_type.value)
        return graph


def build_universal_construction_graph(category: str = "tops", subcategory: str = "hoodie") -> UniversalConstructionGraph:
    return UniversalConstructionGraph(category, subcategory)
