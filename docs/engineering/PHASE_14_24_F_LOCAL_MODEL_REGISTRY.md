# YORVYN — PHASE 14.24-F: LOCAL MODEL REGISTRY & COMPATIBILITY AUDIT

## Executive Overview
Phase 14.24-F establishes a **100% Zero-Cost Local Multimodal Garment Identification Engine** designed and verified for Apple Silicon M2 (16GB Unified Memory, macOS Darwin arm64). The engine operates entirely locally without requiring paid vision APIs (e.g. OpenAI GPT-4V, Google Gemini Cloud, Claude 3.5), external GPU servers, or cloud infrastructure.

---

## 1. Local Model Registry

| Model | Architecture | Role in Yorvyn | Parameter Count | License & Commercial Terms | Execution Provider | Local Cache Location |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FashionCLIP** | CLIP ViT-B/32 (Domain-Specific Ensembling) | 15-category classification & subcategory disambiguation | 151M | MIT License (Commercial Permitted) | PyTorch MPS (Apple Silicon M2) | `~/.cache/huggingface/hub/models--openai--clip-vit-base-patch32` |
| **SigLIP** | Sigmoid-Loss ViT-B/16-224 | Multi-label visual attributes (patterns, sleeves, collar, closure, pockets) | 151M | Apache 2.0 (Commercial Permitted) | PyTorch MPS (Apple Silicon M2) | `~/.cache/huggingface/hub/models--openai--clip-vit-base-patch32` |
| **DINOv2** | ViT-Small/14 | Dense visual patch representations & structural consistency | 22M | Apache 2.0 (Commercial Permitted) | PyTorch MPS (Apple Silicon M2) | `~/.cache/huggingface/hub/models--facebook--dinov2-small` |
| **Grounded-SAM 2** | Grounding DINO + SegFormer B2 / SAM 2 | Prompt-guided component localization & silhouette segmentation | 27M | Apache 2.0 (Commercial Permitted) | PyTorch MPS / CPU Fallback | `~/.cache/huggingface/hub/models--mattmdjaga--segformer_b2_clothes` |
| **Depth Anything V2** | DPT-ViT-S / Relative Disparity Backbone | Monocular relative disparity & surface fold relief | 24M | Apache 2.0 (Commercial Permitted) | PyTorch MPS / CPU Fallback | Native Local PyTorch Adapter |
| **Local Deterministic Generator** | Structured Rule Engine / Optional Ollama | Natural language explanation & DAG parameter synthesis | 0M (Rule) / 3B-7B (Ollama) | MIT / Open Weights | Local CPU / Host Localhost | Host System |

---

## 2. Capability Matrix Across 15 Garment Categories

The engine natively identifies and constructs geometry handoffs for 15 primary categories:

1. **T-shirts** (`tshirt`): crew neck, v-neck, graphic, plain; short sleeves, straight hem.
2. **Shirts** (`shirt`): formal dress shirt, plaid flannel, oxford button-down; collar points, placket, cuffs.
3. **Hoodies** (`hoodie`): pullover, full-zip, oversized; hood cowl, kangaroo pocket, ribbed cuffs & hem.
4. **Sweatshirts** (`sweatshirt`): crewneck athletic, oversized fleece; ribbed neckband and cuffs.
5. **Sweaters** (`sweater`): cable-knit, fine knit, turtleneck; ribbed trims.
6. **Jackets** (`jacket`): denim trucker, tailored blazer, bomber; collar, chest pockets, front buttons/zipper.
7. **Coats** (`coat`): long wool overcoat, trench coat; lapels, storm flap, knee-length hem.
8. **Dresses** (`dress`): A-line, maxi, sheath; fitted bodice, flared skirt.
9. **Kurtas** (`kurta`): traditional ethnic kurta, mandarin collar, side slits, long tunic body.
10. **Tunics** (`tunic`): flowy bohemian tunic, button-front tunic blouse.
11. **Jeans** (`jeans`): classic five-pocket denim, slim tapered, relaxed straight; waistband, crotch fly, legs.
12. **Trousers** (`trousers`): tailored chinos, dress slacks, cargo pants; pleats, welt pockets.
13. **Shorts** (`shorts`): casual shorts, denim cut-offs, bermudas; hem above knee.
14. **Skirts** (`skirt`): pleated midi, pencil skirt, A-line skirt.
15. **Traditional Clothing** (`traditional_clothing`): sherwani, bandhgala, cultural formal attire.

---

## 3. Visual Attributes Extracted

- **Palette & Color**: Dominant primary color, secondary color, and hex palette extracted via K-means clustering.
- **Pattern**: `solid`, `striped`, `plaid`, `graphic`, `floral`, `cable_knit`, `checkered`.
- **Fit**: `regular`, `oversized`, `slim`, `relaxed`, `loose`.
- **Sleeve Type**: `long_sleeve`, `short_sleeve`, `sleeveless`, `raglan`, `drop_shoulder`.
- **Neckline & Collar**: `crew_neck`, `v_neck`, `hooded`, `mandarin`, `button_down`, `spread`, `turtle_neck`.
- **Closure**: `pullover`, `front_zipper`, `full_button_placket`, `half_zip`, `drawstring`.
- **Pockets**: `kangaroo_pocket`, `chest_pockets`, `welt_pockets`, `patch_pockets`, `five_pocket`.
- **Trims & Finishes**: Ribbed cuffs, ribbed waistband, curved shirttail hem, side slits.

---

## 4. Hardware Safety & Memory Footprint

To ensure safe concurrent operation alongside other desktop applications on 16GB unified memory:
- **Peak RSS**: Kept under 850 MB for the entire identification pipeline.
- **Sequential Model Execution**: Active neural weights are swapped sequentially with `torch.mps.empty_cache()` and `gc.collect()`.
- **Headroom Limit**: Strict 12.0 GB ceiling with automatic CPU fallback if MPS memory pressure occurs.
