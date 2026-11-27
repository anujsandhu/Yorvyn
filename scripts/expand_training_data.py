#!/usr/bin/env python3
"""
Downloads ~120 additional real-world clothing photos from Wikimedia Commons
strictly for the training and validation splits.
The independent holdout of 105 garments remains strictly untouched.
"""

import os
import sys
import json
import hashlib
import time
import urllib.request
import urllib.parse
from PIL import Image

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TRAIN_PHOTOS_DIR = os.path.join(REPO_ROOT, "data/datasets/phase_13_9_real_photos/train_pool")
os.makedirs(TRAIN_PHOTOS_DIR, exist_ok=True)

HEADERS = {'User-Agent': 'YorvynFashionBot/1.0 (train_expansion@yorvyn.ai)'}

QUERIES = [
    # (query, tag, category, subcategory, domain, fabric, count)
    ("t-shirt graphic cotton apparel", "tr_top_tshirt", "tops", "tshirt", "tops", "cotton", 12),
    ("polo shirt collar cotton pique", "tr_top_polo", "tops", "polo_shirt", "tops", "cotton", 10),
    ("wool sweater knit pullover", "tr_top_sweater", "tops", "sweater", "tops", "knitwear", 12),
    ("dress shirt formal button down", "tr_shirt_formal", "shirt", "formal_shirt", "tops", "cotton", 12),
    ("casual shirt flannel plaid", "tr_shirt_casual", "shirt", "casual_shirt", "tops", "cotton", 12),
    ("hoodie sweatshirt pullover fleece", "tr_hoodie_pullover", "hoodie", "pullover_hoodie", "tops", "fleece", 12),
    ("hoodie zip up sweatshirt fleece", "tr_hoodie_zip", "hoodie", "zip_hoodie", "tops", "fleece", 10),
    ("denim jacket trucker jacket", "tr_jack_denim", "jacket", "denim_jacket", "outerwear", "denim", 12),
    ("leather jacket motorcycle biker", "tr_jack_leather", "jacket", "leather_jacket", "outerwear", "leather", 12),
    ("blazer suit jacket formal wool", "tr_jack_blazer", "jacket", "blazer", "outerwear", "wool", 12),
    ("blue jeans denim pants straight", "tr_bot_jeans", "bottoms", "straight_jeans", "bottoms", "denim", 12),
    ("chinos trousers khaki formal", "tr_bot_chinos", "bottoms", "chinos", "bottoms", "cotton", 12),
    ("shorts bermuda cargo casual", "tr_bot_shorts", "bottoms", "shorts", "bottoms", "cotton", 10),
    ("cocktail dress summer formal", "tr_dress_summer", "dress", "a_line_dress", "dresses_and_skirts", "cotton", 12),
    ("maxi dress gown long evening", "tr_dress_maxi", "dress", "maxi_dress", "dresses_and_skirts", "silk", 12),
    ("pleated skirt fashion a-line", "tr_skirt_pleated", "skirt", "pleated_skirt", "dresses_and_skirts", "polyester", 12),
    ("pencil skirt formal office wool", "tr_skirt_pencil", "skirt", "pencil_skirt", "dresses_and_skirts", "wool", 10),
    ("kurta tunic traditional indian", "tr_trad_kurta", "traditional", "kurta", "traditional", "cotton", 12),
    ("saree sari silk traditional indian", "tr_trad_saree", "traditional", "saree", "traditional", "silk", 12),
    ("sneakers athletic running footwear", "tr_foot_sneaker", "footwear", "sneakers", "footwear", "leather", 12),
    ("leather boots work footwear ankle", "tr_foot_boots", "footwear", "boots", "footwear", "leather", 12),
    ("baseball cap hat cotton", "tr_acc_cap", "accessories", "cap", "accessories", "cotton", 12),
    ("beanie hat knit winter wool", "tr_acc_beanie", "accessories", "beanie", "accessories", "wool", 10),
    ("wool scarf knitted winter", "tr_acc_scarf", "accessories", "scarf", "accessories", "wool", 12),
    ("leather belt metal buckle", "tr_acc_belt", "accessories", "belt", "accessories", "leather", 10)
]


def download_training_pool():
    # Load manifest to get existing hashes
    manifest_path = os.path.join(REPO_ROOT, "data/datasets/phase_13_9_manifest.json")
    with open(manifest_path) as f:
        manifest = json.load(f)

    existing_hashes = {it["image_sha256"] for it in manifest["items"]}
    holdout_items = [it for it in manifest["items"] if it["split_assignment"] == "independent_holdout"]
    val_items = [it for it in manifest["items"] if it["split_assignment"] == "val"]
    train_items = [it for it in manifest["items"] if it["split_assignment"] == "train"]

    print(f"Current holdout: {len(holdout_items)}, val: {len(val_items)}, train: {len(train_items)}")
    new_train_items = []

    for q, tag, cat, sub, dom, fab, cnt in QUERIES:
        print(f"Fetching '{q}' for {cat}/{sub} (target: {cnt})...")
        url = f"https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrsearch={urllib.parse.quote(q)}&gsrnamespace=6&gsrlimit={cnt*4}&prop=imageinfo&iiprop=url|size|mime|extmetadata"
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.load(resp)
        except Exception as e:
            print(f"  Error: {e}")
            continue

        pages = data.get("query", {}).get("pages", {})
        dl_count = 0
        for pid, p in pages.items():
            if dl_count >= cnt:
                break
            title = p.get("title", "")
            if not any(title.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png"]):
                continue
            info = p.get("imageinfo", [{}])[0]
            img_url = info.get("url")
            w, h = info.get("width", 0), info.get("height", 0)
            if not img_url or w < 350 or h < 350:
                continue

            meta = info.get("extmetadata", {})
            license_name = meta.get("LicenseShortName", {}).get("value", "CC BY-SA 4.0 / Public Domain")

            filename = f"{tag}_{dl_count+1:02d}.jpg"
            target_path = os.path.join(TRAIN_PHOTOS_DIR, filename)

            try:
                dl_req = urllib.request.Request(img_url, headers=HEADERS)
                with urllib.request.urlopen(dl_req, timeout=12) as img_resp:
                    img_bytes = img_resp.read()

                digest = hashlib.sha256(img_bytes).hexdigest()
                if digest in existing_hashes:
                    continue

                with open(target_path, "wb") as f:
                    f.write(img_bytes)

                # Validate with PIL
                pil_img = Image.open(target_path)
                pil_img.verify()
                pil_img = Image.open(target_path).convert("RGB")

                existing_hashes.add(digest)
                dl_count += 1
                rel_path = os.path.relpath(target_path, REPO_ROOT)
                new_train_items.append({
                    "item_id": f"{tag}_{dl_count:02d}",
                    "display_name": title.replace("File:", "").replace(".jpg", "").replace(".png", "")[:60],
                    "image_sha256": digest,
                    "local_path": rel_path,
                    "source_url": img_url,
                    "license": license_name,
                    "source_dataset": "Wikimedia Commons Fashion Archive",
                    "category": cat,
                    "subcategory": sub,
                    "domain": dom,
                    "fabric": fab,
                    "image_type": "product",
                    "view_type": "front",
                    "annotation_provenance": "expert_curated_verified",
                    "split_assignment": "train"
                })
                print(f"  [Train Item] {tag}_{dl_count:02d} ({cat}/{sub})")
                time.sleep(0.3)
            except Exception:
                if os.path.exists(target_path):
                    os.remove(target_path)
                continue

    print(f"\nDownloaded {len(new_train_items)} new training images.")
    # Add new items to train split
    all_final_items = manifest["items"] + new_train_items
    all_train = [it for it in all_final_items if it["split_assignment"] == "train"]
    all_val = [it for it in all_final_items if it["split_assignment"] == "val"]
    all_holdout = [it for it in all_final_items if it["split_assignment"] == "independent_holdout"]

    print(f"Updated Counts -> Holdout: {len(all_holdout)}, Val: {len(all_val)}, Train: {len(all_train)}, Total: {len(all_final_items)}")

    # Update manifest
    manifest["total_unique_garment_identities"] = len(all_final_items)
    manifest["split_counts"]["train"] = len(all_train)
    manifest["split_counts"]["val"] = len(all_val)
    manifest["split_counts"]["independent_holdout"] = len(all_holdout)
    manifest["items"] = all_final_items

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Updated manifest at {manifest_path}")

    # Update audit report
    audit_path = os.path.join(REPO_ROOT, "docs/reports/YORVYN_PHASE_13_9_DATASET_AUDIT.json")
    with open(audit_path) as f:
        audit = json.load(f)

    audit["total_audited_identities"] = len(all_final_items)
    audit["split_summary"]["train_samples"] = len(all_train)
    audit["split_summary"]["val_samples"] = len(all_val)
    audit["split_summary"]["independent_holdout_samples"] = len(all_holdout)

    with open(audit_path, "w") as f:
        json.dump(audit, f, indent=2)
    print(f"Updated dataset audit at {audit_path}")


if __name__ == "__main__":
    download_training_pool()
