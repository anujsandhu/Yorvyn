# Seam and Panel Construction Model

Source engine: `backend/app/services/intelligence/pattern_construction_engine.py`.

## 1. Category Pattern Topologies

`PatternConstructionEngine` generates construction-authentic flat pieces and seam graphs tailored to each garment family:

| Family / Category | Pattern Pieces Generated | Construction Highlights |
| --- | --- | --- |
| **Jackets & Outerwear** | `front_left_body`, `front_right_body`, `placket`, `back_body`, `left_sleeve`, `right_sleeve`, `left_cuff`, `right_cuff`, `collar_stand`, `collar`, optional `chest_pocket_left`, `hem_facing` | Split center-front panels joined through `placket` (`SEWN` or `ZIPPER_ATTACHMENT`); upper collar attached to collar stand across front/back necklines; curved Bézier sleeve caps matched to armscyes with 2 cm ease. |
| **Hoodies (Pullover & Zip)** | Pullover: `front_body` (+ `kangaroo_pocket`) vs Zip: `front_left_body`, `front_right_body`; shared `back_body`, dual sleeves + ribbed cuffs, `hood_left_panel`, `hood_right_panel`, `hood_lining`, split/continuous ribbed `waistband` | Pullover vs zip topology separation; sagittal hood seam + hood inner lining (`LINING_ATTACHMENT`, `INFERRED`); drawstring channel fold line; contoured split waistband top segments matching left/right zip panels. |
| **Shirts** | `front_left_body`, `front_right_body`, `placket`, `back_body`, sleeves + cuffs, `collar_stand`, `collar`, `hem_facing` | Button placket center closure with collar stand spanning front-left, back, and front-right necklines. |
| **Tops & Sweaters** | `front_body`, `back_body`, `left_sleeve`, `right_sleeve`, `neckband`, `hem_facing` | Continuous knit panels joined to ribbed neckband (`BOUND`) and hem facing (`HEMMED`). |
| **Bottoms (Trousers / Jeans / Shorts)** | `left_front_leg`, `right_front_leg`, `left_back_leg`, `right_back_leg`, `fly_shield`, `waistband`, optional `back_pocket_left` | Bifurcated 4-leg assembly (`inseam`, `outseam`, front/back `crotch_rise` Bézier curves), multi-segment contoured waistband matching all four leg waist tops, front fly closure; rear pockets gated by back-view evidence. |
| **Dresses & Skirts** | Dress: `bodice_front` (with waist `PatternDart`), `bodice_back`, `skirt_front`, `skirt_back`, optional sleeves. Skirt: `skirt_front`, `skirt_back`, `waistband`. | Bodice waist darts explicitly parameterized (`apex`, `base_left`, `base_right`, `depth_m`, `angle_deg`); waist seam connecting bodice hem to skirt top; sleeveless vs sleeved dress branching from evidence. |
| **Traditional Wear** | Kurta: `front_body`, `back_body`, sleeves, `mandarin_collar`, `chest_slit_placket`. Lehenga: `lehenga_gore_1..4`, `waistband`. Sherwani: tailored split panels + sleeves + stand collar. | Kurta side edges terminate above lateral **chak** side slits (`side_slit_left`, `side_slit_right` kept `EdgeRole.HEMMED` rather than falsely sewn shut). |

## 2. Assembly Validation Rules (`AssemblyValidator`)

1. **2D Geometry Validity**: Every `PatternPiece2D` must pass `validate_polygon_2d()` (CCW, non-degenerate, simple, closed). Any error marks `AssemblyValidationReport.is_valid = False`.
2. **Seam Endpoint Integrity**: Both `(piece_a, edge_a)` and `(piece_b, edge_b)` must exist on non-self seams (`MISSING_SEAM_PIECE` / `MISSING_SEAM_EDGE`).
3. **Seam-Length Compatibility**: Non-applique seams compare `abs(edge_a_length_m - edge_b_length_m) - ease_allowance_m` against `length_tolerance_m`; sleeve caps scale relative to armscye perimeter to preserve ~1.5–2 cm ease.
4. **Topological Assembly DAG**: `assembly_dependencies` undergoes Kahn's algorithm cycle detection; any cycle raises `ASSEMBLY_GRAPH_CYCLE` (`is_valid = False`).
