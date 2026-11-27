"""
YORVYN — Construction-Aware Garment Topology & Seam Relationship Graph (Phase 14.20 Workstream B)
Explicitly models garment construction as a directed assembly graph of 2D sewing panels,
3D boundary curves, structural seams, and physical attachment relationships:
- GarmentComponent: Front/Rear body panels, side panels, sleeves, sleeve caps, armscyes,
  hood panels, sagittal seams, cuffs, hem band, pockets, drawstrings, zippers.
- SeamRelationship: Explicit stitch topology (stitched, zippered, elastic, applique, fold).
- 2D Pattern-to-3D Draping Mapping: Links flat tailoring panel geometry to 3D surface shells.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any, Set
from enum import Enum
import numpy as np


class ComponentType(str, Enum):
    BODY_PANEL = "body_panel"
    SLEEVE = "sleeve"
    SLEEVE_CAP = "sleeve_cap"
    ARMSCYE = "armscye"
    HOOD_PANEL = "hood_panel"
    HOOD_LINING = "hood_lining"
    CUFF = "cuff"
    HEM_BAND = "hem_band"
    POCKET = "pocket"
    COLLAR = "collar"
    SEAM = "seam"
    HARDWARE = "hardware"


class SeamType(str, Enum):
    STITCHED = "stitched"               # Standard needle stitch joining two panels
    ELASTIC_CINCH = "elastic_cinch"     # Ribbed elastic tension seam (cuffs, hem)
    ZIPPERED = "zippered"               # Interlocking metal/plastic tooth closure
    SURFACE_APPLIQUE = "surface_applique" # Patch applied onto base panel (pockets)
    FOLD_LINE = "fold_line"             # Continuous fabric fold with crease normal
    RIVETED = "riveted"                 # Grommets, eyelets, metal studs


@dataclass
class SeamRelationship:
    """Explicit tailoring seam connecting two garment components."""
    seam_id: str
    component_a: str
    component_b: str
    seam_type: SeamType
    allowance_mm: float = 10.0          # Standard 1cm tailoring seam allowance
    stitch_density_spi: float = 10.0    # 10 stitches per inch
    is_watertight: bool = True          # Manifold seam without boundary gaps
    length_m: float = 0.0
    confidence: float = 0.95
    notes: str = ""


@dataclass
class ConstructionPanel2D:
    """2D flat-pattern panel representation for tailoring correspondence."""
    panel_id: str
    width_m: float
    height_m: float
    boundary_polygon_2d: List[Tuple[float, float]]  # (u, v) normalized pattern coords
    grainline_angle_deg: float = 0.0                # Warp thread orientation
    area_m2: float = 0.0


@dataclass
class GarmentConstructionNode:
    """Detailed record for a physical garment construction component."""
    component_id: str
    component_type: ComponentType
    name: str
    parent_id: Optional[str] = None
    adjacent_components: List[str] = field(default_factory=list)
    boundary_curves: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def node_id(self) -> str:
        return self.component_id
    seam_relationships: List[str] = field(default_factory=list)
    material_assignment: str = "main_shell"
    confidence: float = 0.95
    image_evidence: Dict[str, Any] = field(default_factory=dict)
    vertex_range: Tuple[int, int] = (0, 0)
    triangle_range: Tuple[int, int] = (0, 0)
    dimensions_m: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    pattern_2d: Optional[ConstructionPanel2D] = None


class GarmentConstructionGraph:
    """
    Manages complete garment construction architecture, seam connectivity,
    and hierarchical topological assembly.
    """

    def __init__(self, garment_type: str = "hoodie"):
        self.garment_type = garment_type
        self.nodes: Dict[str, GarmentConstructionNode] = {}
        self.seams: Dict[str, SeamRelationship] = {}
        self.assembly_order: List[str] = []

    def add_component(self, node: GarmentConstructionNode):
        self.nodes[node.component_id] = node

    def add_seam(self, seam: SeamRelationship):
        self.seams[seam.seam_id] = seam
        if seam.component_a in self.nodes:
            if seam.seam_id not in self.nodes[seam.component_a].seam_relationships:
                self.nodes[seam.component_a].seam_relationships.append(seam.seam_id)
            if seam.component_b not in self.nodes[seam.component_a].adjacent_components:
                self.nodes[seam.component_a].adjacent_components.append(seam.component_b)
        if seam.component_b in self.nodes:
            if seam.seam_id not in self.nodes[seam.component_b].seam_relationships:
                self.nodes[seam.component_b].seam_relationships.append(seam.seam_id)
            if seam.component_a not in self.nodes[seam.component_b].adjacent_components:
                self.nodes[seam.component_b].adjacent_components.append(seam.component_a)

    def get_topological_assembly_order(self) -> List[str]:
        """
        Returns physically valid sewing assembly sequence:
        1. Main body panels joined at shoulder and side seams
        2. Armscyes prepared and sleeves attached
        3. Cuffs and hem band attached with elastic cinch
        4. Neckline collar seam prepared and hood panels attached
        5. Sagittal seam closed and hood lining inserted
        6. Kangaroo pocket patch appliqued onto front torso
        7. Hardware (eyelets, drawstrings, zippers) installed
        """
        priority = {
            ComponentType.BODY_PANEL: 1,
            ComponentType.SEAM: 2,
            ComponentType.ARMSCYE: 3,
            ComponentType.SLEEVE_CAP: 4,
            ComponentType.SLEEVE: 5,
            ComponentType.CUFF: 6,
            ComponentType.HEM_BAND: 7,
            ComponentType.COLLAR: 8,
            ComponentType.HOOD_PANEL: 9,
            ComponentType.HOOD_LINING: 10,
            ComponentType.POCKET: 11,
            ComponentType.HARDWARE: 12
        }
        sorted_nodes = sorted(
            self.nodes.values(),
            key=lambda n: (priority.get(n.component_type, 99), n.component_id)
        )
        self.assembly_order = [n.component_id for n in sorted_nodes]
        return self.assembly_order

    def topological_assembly_sequence(self) -> List[str]:
        """Alias for get_topological_assembly_order."""
        return self.get_topological_assembly_order()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "garment_type": self.garment_type,
            "total_components": len(self.nodes),
            "total_seams": len(self.seams),
            "assembly_sequence": self.get_topological_assembly_order(),
            "components": {
                k: {
                    "type": v.component_type.value,
                    "name": v.name,
                    "material": v.material_assignment,
                    "confidence": v.confidence,
                    "adjacent": v.adjacent_components,
                    "seams": v.seam_relationships,
                    "dimensions_m": [round(float(x), 4) for x in v.dimensions_m]
                }
                for k, v in self.nodes.items()
            },
            "seams": {
                k: {
                    "component_a": v.component_a,
                    "component_b": v.component_b,
                    "type": v.seam_type.value,
                    "allowance_mm": v.allowance_mm,
                    "is_watertight": v.is_watertight
                }
                for k, v in self.seams.items()
            }
        }


def build_canonical_hoodie_construction_graph(
    has_zipper: bool = False,
    has_pocket: bool = True,
    has_drawstrings: bool = True,
    hood_posture: str = "draped"
) -> GarmentConstructionGraph:
    """Constructs a complete tailoring construction graph for a structured hoodie."""
    graph = GarmentConstructionGraph(garment_type="zip_hoodie" if has_zipper else "pullover_hoodie")

    # 1. Body Panels
    graph.add_component(GarmentConstructionNode(
        component_id="front_body_panel",
        component_type=ComponentType.BODY_PANEL,
        name="Front Torso Panel",
        material_assignment="main_fleece",
        confidence=0.96
    ))
    graph.add_component(GarmentConstructionNode(
        component_id="rear_body_panel",
        component_type=ComponentType.BODY_PANEL,
        name="Rear Torso Panel",
        material_assignment="main_fleece",
        confidence=0.90
    ))

    # 2. Shoulder & Side Seams
    graph.add_seam(SeamRelationship("seam_shoulder_left", "front_body_panel", "rear_body_panel", SeamType.STITCHED, length_m=0.14))
    graph.add_seam(SeamRelationship("seam_shoulder_right", "front_body_panel", "rear_body_panel", SeamType.STITCHED, length_m=0.14))
    graph.add_seam(SeamRelationship("seam_side_left", "front_body_panel", "rear_body_panel", SeamType.STITCHED, length_m=0.42))
    graph.add_seam(SeamRelationship("seam_side_right", "front_body_panel", "rear_body_panel", SeamType.STITCHED, length_m=0.42))

    # 3. Armscyes & Sleeves
    graph.add_component(GarmentConstructionNode(
        component_id="left_armscye",
        component_type=ComponentType.ARMSCYE,
        name="Left Armscye Hole",
        parent_id="front_body_panel"
    ))
    graph.add_component(GarmentConstructionNode(
        component_id="right_armscye",
        component_type=ComponentType.ARMSCYE,
        name="Right Armscye Hole",
        parent_id="front_body_panel"
    ))
    graph.add_component(GarmentConstructionNode(
        component_id="left_sleeve",
        component_type=ComponentType.SLEEVE,
        name="Left Tubular Sleeve",
        material_assignment="main_fleece"
    ))
    graph.add_component(GarmentConstructionNode(
        component_id="right_sleeve",
        component_type=ComponentType.SLEEVE,
        name="Right Tubular Sleeve",
        material_assignment="main_fleece"
    ))
    graph.add_seam(SeamRelationship("seam_left_armscye_sleeve", "left_armscye", "left_sleeve", SeamType.STITCHED, length_m=0.46))
    graph.add_seam(SeamRelationship("seam_right_armscye_sleeve", "right_armscye", "right_sleeve", SeamType.STITCHED, length_m=0.46))

    # 4. Cuffs & Waistband
    graph.add_component(GarmentConstructionNode(
        component_id="left_cuff",
        component_type=ComponentType.CUFF,
        name="Left Elastic Ribbed Cuff",
        parent_id="left_sleeve",
        material_assignment="ribbed_cotton"
    ))
    graph.add_component(GarmentConstructionNode(
        component_id="right_cuff",
        component_type=ComponentType.CUFF,
        name="Right Elastic Ribbed Cuff",
        parent_id="right_sleeve",
        material_assignment="ribbed_cotton"
    ))
    graph.add_seam(SeamRelationship("seam_cuff_left", "left_sleeve", "left_cuff", SeamType.ELASTIC_CINCH, length_m=0.22))
    graph.add_seam(SeamRelationship("seam_cuff_right", "right_sleeve", "right_cuff", SeamType.ELASTIC_CINCH, length_m=0.22))

    graph.add_component(GarmentConstructionNode(
        component_id="hem_band",
        component_type=ComponentType.HEM_BAND,
        name="Ribbed Waistband Hem",
        parent_id="front_body_panel",
        material_assignment="ribbed_cotton"
    ))
    graph.add_seam(SeamRelationship("seam_torso_hem_band", "front_body_panel", "hem_band", SeamType.ELASTIC_CINCH, length_m=0.84))

    # 5. Hood Panels & Sagittal Seam
    graph.add_component(GarmentConstructionNode(
        component_id="hood_left_panel",
        component_type=ComponentType.HOOD_PANEL,
        name="Hood Left Lateral Panel",
        material_assignment="main_fleece"
    ))
    graph.add_component(GarmentConstructionNode(
        component_id="hood_right_panel",
        component_type=ComponentType.HOOD_PANEL,
        name="Hood Right Lateral Panel",
        material_assignment="main_fleece"
    ))
    graph.add_component(GarmentConstructionNode(
        component_id="hood_lining",
        component_type=ComponentType.HOOD_LINING,
        name="Hood Inner Fleece Lining",
        material_assignment="brushed_fleece"
    ))
    graph.add_seam(SeamRelationship("seam_hood_sagittal_center", "hood_left_panel", "hood_right_panel", SeamType.STITCHED, length_m=0.38))
    graph.add_seam(SeamRelationship("seam_neckline_collar", "front_body_panel", "hood_left_panel", SeamType.STITCHED, length_m=0.48))
    graph.add_seam(SeamRelationship("seam_hood_lining_attachment", "hood_left_panel", "hood_lining", SeamType.STITCHED, length_m=0.62))

    # 6. Pocket
    if has_pocket:
        pocket_id = "split_pockets" if has_zipper else "kangaroo_pocket"
        graph.add_component(GarmentConstructionNode(
            component_id=pocket_id,
            component_type=ComponentType.POCKET,
            name="Split Pockets (Zipped)" if has_zipper else "3D Kangaroo Pouch Pocket",
            parent_id="front_body_panel",
            material_assignment="main_fleece"
        ))
        graph.add_seam(SeamRelationship("seam_pocket_applique", "front_body_panel", pocket_id, SeamType.SURFACE_APPLIQUE, length_m=0.52))

    # 7. Hardware (Drawstrings, Eyelets, Zipper)
    if has_zipper:
        graph.add_component(GarmentConstructionNode(
            component_id="front_zipper",
            component_type=ComponentType.HARDWARE,
            name="Metal Separating Front Zipper",
            parent_id="front_body_panel",
            material_assignment="metallic_hardware"
        ))
        graph.add_seam(SeamRelationship("seam_front_zipper_track", "front_body_panel", "front_zipper", SeamType.ZIPPERED, length_m=0.58))
    elif has_drawstrings:
        graph.add_component(GarmentConstructionNode(
            component_id="drawstrings_and_eyelets",
            component_type=ComponentType.HARDWARE,
            name="Grommet Eyelets & Hanging Cords",
            parent_id="hood_left_panel",
            material_assignment="cotton_cord_and_metal_aglet"
        ))
        graph.add_seam(SeamRelationship("seam_eyelet_rivet", "hood_left_panel", "drawstrings_and_eyelets", SeamType.RIVETED))

    # Compute topological assembly order
    graph.get_topological_assembly_order()
    return graph
