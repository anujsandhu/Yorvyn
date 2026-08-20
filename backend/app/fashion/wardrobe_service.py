"""
Yorvyn Digital Wardrobe Service
Manages user wardrobe items (Tops, Bottoms, Outerwear, Footwear, Accessories),
closet analytics, and item attribute tagging.
"""

from typing import Dict, List, Optional
import uuid
from datetime import datetime

# Sample high-curation default wardrobe items for realistic styling demonstration
DEFAULT_WARDROBE_ITEMS = [
    {
        "id": "wardrobe_1",
        "name": "Oversized Merino Wool Crewneck",
        "category": "top",
        "subcategory": "knitwear",
        "color": "cream",
        "secondary_color": "off-white",
        "material": "merino wool",
        "pattern": "solid",
        "formality": 4,  # 1-10
        "warmth": 6,     # 1-10
        "seasons": ["autumn", "winter", "spring"],
        "weather_tags": ["chilly", "mild", "cold"],
        "aesthetic": ["quiet_luxury", "minimalist_scandi", "smart_casual"],
        "brand": "COS",
        "image_url": "https://images.unsplash.com/photo-1576566588028-4147f3842f27?auto=format&fit=crop&w=600&q=80",
        "wear_count": 8,
        "favorite": True
    },
    {
        "id": "wardrobe_2",
        "name": "Relaxed Tailored Pleated Trousers",
        "category": "bottom",
        "subcategory": "trousers",
        "color": "charcoal",
        "secondary_color": "grey",
        "material": "wool blend",
        "pattern": "solid",
        "formality": 6,
        "warmth": 5,
        "seasons": ["autumn", "winter", "spring", "summer"],
        "weather_tags": ["mild", "chilly", "warm"],
        "aesthetic": ["quiet_luxury", "minimalist_scandi", "smart_casual"],
        "brand": "Arket",
        "image_url": "https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=600&q=80",
        "wear_count": 12,
        "favorite": True
    },
    {
        "id": "wardrobe_3",
        "name": "Double-Breasted Wool Overcoat",
        "category": "outerwear",
        "subcategory": "coat",
        "color": "camel",
        "secondary_color": "tan",
        "material": "virgin wool",
        "pattern": "solid",
        "formality": 7,
        "warmth": 8,
        "seasons": ["autumn", "winter"],
        "weather_tags": ["cold", "chilly", "windy"],
        "aesthetic": ["quiet_luxury", "parisian_chic", "smart_casual"],
        "brand": "Sandro",
        "image_url": "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?auto=format&fit=crop&w=600&q=80",
        "wear_count": 5,
        "favorite": True
    },
    {
        "id": "wardrobe_4",
        "name": "Minimalist White Leather Low-Tops",
        "category": "footwear",
        "subcategory": "sneakers",
        "color": "white",
        "secondary_color": "cream",
        "material": "calfskin leather",
        "pattern": "solid",
        "formality": 3,
        "warmth": 3,
        "seasons": ["spring", "summer", "autumn"],
        "weather_tags": ["mild", "warm", "clear"],
        "aesthetic": ["minimalist_scandi", "smart_casual", "quiet_luxury"],
        "brand": "Common Projects",
        "image_url": "https://images.unsplash.com/photo-1560769629-975ec94e6a86?auto=format&fit=crop&w=600&q=80",
        "wear_count": 22,
        "favorite": True
    },
    {
        "id": "wardrobe_5",
        "name": "Classic Crisp Oxford Cotton Shirt",
        "category": "top",
        "subcategory": "button-down",
        "color": "sky blue",
        "secondary_color": "white",
        "material": "oxford cotton",
        "pattern": "solid",
        "formality": 5,
        "warmth": 3,
        "seasons": ["spring", "summer", "autumn"],
        "weather_tags": ["mild", "warm"],
        "aesthetic": ["smart_casual", "quiet_luxury", "parisian_chic"],
        "brand": "Ralph Lauren",
        "image_url": "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?auto=format&fit=crop&w=600&q=80",
        "wear_count": 14,
        "favorite": False
    },
    {
        "id": "wardrobe_6",
        "name": "Japanese Selvedge Raw Denim Jeans",
        "category": "bottom",
        "subcategory": "jeans",
        "color": "navy",
        "secondary_color": "dark indigo",
        "material": "selvedge denim",
        "pattern": "solid",
        "formality": 3,
        "warmth": 5,
        "seasons": ["autumn", "winter", "spring"],
        "weather_tags": ["chilly", "mild"],
        "aesthetic": ["streetwear_tech", "smart_casual", "parisian_chic"],
        "brand": "A.P.C.",
        "image_url": "https://images.unsplash.com/photo-1542272604-780c96856484?auto=format&fit=crop&w=600&q=80",
        "wear_count": 19,
        "favorite": True
    },
    {
        "id": "wardrobe_7",
        "name": "Chunky Leather Chelsea Boots",
        "category": "footwear",
        "subcategory": "boots",
        "color": "black",
        "secondary_color": "black",
        "material": "matte leather",
        "pattern": "solid",
        "formality": 5,
        "warmth": 7,
        "seasons": ["autumn", "winter"],
        "weather_tags": ["cold", "chilly", "rainy"],
        "aesthetic": ["streetwear_tech", "minimalist_scandi", "parisian_chic"],
        "brand": "Dr. Martens",
        "image_url": "https://images.unsplash.com/photo-1638247025967-b4e38f787b76?auto=format&fit=crop&w=600&q=80",
        "wear_count": 11,
        "favorite": False
    },
    {
        "id": "wardrobe_8",
        "name": "Italian Cashmere Trench Coat",
        "category": "outerwear",
        "subcategory": "trench",
        "color": "navy",
        "secondary_color": "midnight navy",
        "material": "water-resistant gabardine",
        "pattern": "solid",
        "formality": 6,
        "warmth": 6,
        "seasons": ["spring", "autumn"],
        "weather_tags": ["rainy", "windy", "chilly"],
        "aesthetic": ["quiet_luxury", "parisian_chic", "smart_casual"],
        "brand": "Burberry",
        "image_url": "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?auto=format&fit=crop&w=600&q=80",
        "wear_count": 7,
        "favorite": True
    },
    {
        "id": "wardrobe_9",
        "name": "Heavyweight Boxy Supima Cotton Tee",
        "category": "top",
        "subcategory": "t-shirt",
        "color": "white",
        "secondary_color": "white",
        "material": "supima cotton",
        "pattern": "solid",
        "formality": 2,
        "warmth": 2,
        "seasons": ["spring", "summer", "autumn"],
        "weather_tags": ["warm", "mild"],
        "aesthetic": ["minimalist_scandi", "streetwear_tech", "quiet_luxury"],
        "brand": "Uniqlo U",
        "image_url": "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=600&q=80",
        "wear_count": 30,
        "favorite": True
    },
    {
        "id": "wardrobe_10",
        "name": "Olive Relaxed Cargo Trousers",
        "category": "bottom",
        "subcategory": "cargo",
        "color": "olive",
        "secondary_color": "khaki",
        "material": "cotton ripstop",
        "pattern": "solid",
        "formality": 2,
        "warmth": 4,
        "seasons": ["spring", "autumn", "summer"],
        "weather_tags": ["mild", "warm"],
        "aesthetic": ["streetwear_tech", "minimalist_scandi"],
        "brand": "Carhartt WIP",
        "image_url": "https://images.unsplash.com/photo-1517445312882-bc9910d016b7?auto=format&fit=crop&w=600&q=80",
        "wear_count": 9,
        "favorite": False
    },
    {
        "id": "wardrobe_11",
        "name": "Handmade Suede Penny Loafers",
        "category": "footwear",
        "subcategory": "loafers",
        "color": "brown",
        "secondary_color": "tan",
        "material": "calf suede",
        "pattern": "solid",
        "formality": 6,
        "warmth": 4,
        "seasons": ["spring", "summer", "autumn"],
        "weather_tags": ["mild", "warm", "clear"],
        "aesthetic": ["quiet_luxury", "smart_casual", "parisian_chic"],
        "brand": "Loro Piana",
        "image_url": "https://images.unsplash.com/photo-1614252369475-531eba835eb1?auto=format&fit=crop&w=600&q=80",
        "wear_count": 15,
        "favorite": True
    },
    {
        "id": "wardrobe_12",
        "name": "Minimalist Matte Black Leather Belt & Watch",
        "category": "accessory",
        "subcategory": "leather goods",
        "color": "black",
        "secondary_color": "silver",
        "material": "leather & steel",
        "pattern": "solid",
        "formality": 6,
        "warmth": 1,
        "seasons": ["spring", "summer", "autumn", "winter"],
        "weather_tags": ["all"],
        "aesthetic": ["quiet_luxury", "minimalist_scandi", "smart_casual"],
        "brand": "Cartier / Nordgreen",
        "image_url": "https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9?auto=format&fit=crop&w=600&q=80",
        "wear_count": 40,
        "favorite": True
    }
]

class WardrobeService:
    """In-memory + persistent digital wardrobe manager."""
    
    def __init__(self):
        # Key: user_id -> List[garment dict]
        self._user_wardrobes: Dict[str, List[Dict]] = {
            "default_user": list(DEFAULT_WARDROBE_ITEMS)
        }
        
    def get_wardrobe(self, user_id: str = "default_user", category: Optional[str] = None) -> List[Dict]:
        items = self._user_wardrobes.get(user_id, DEFAULT_WARDROBE_ITEMS)
        if category and category.lower() != "all":
            items = [item for item in items if item["category"].lower() == category.lower()]
        return items

    def add_item(self, user_id: str, item_data: Dict) -> Dict:
        if user_id not in self._user_wardrobes:
            self._user_wardrobes[user_id] = list(DEFAULT_WARDROBE_ITEMS)
            
        new_id = item_data.get("id") or f"garment_{uuid.uuid4().hex[:8]}"
        item = {
            "id": new_id,
            "name": item_data.get("name", "Custom Garment"),
            "category": item_data.get("category", "top").lower(),
            "subcategory": item_data.get("subcategory", "general").lower(),
            "color": item_data.get("color", "black").lower(),
            "secondary_color": item_data.get("secondary_color", ""),
            "material": item_data.get("material", "cotton"),
            "pattern": item_data.get("pattern", "solid"),
            "formality": int(item_data.get("formality", 4)),
            "warmth": int(item_data.get("warmth", 4)),
            "seasons": item_data.get("seasons", ["spring", "summer", "autumn", "winter"]),
            "weather_tags": item_data.get("weather_tags", ["mild"]),
            "aesthetic": item_data.get("aesthetic", ["smart_casual"]),
            "brand": item_data.get("brand", "Unknown"),
            "image_url": item_data.get("image_url", "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=600&q=80"),
            "wear_count": 0,
            "favorite": False,
            "created_at": datetime.utcnow().isoformat()
        }
        self._user_wardrobes[user_id].append(item)
        return item

    def delete_item(self, user_id: str, item_id: str) -> bool:
        if user_id not in self._user_wardrobes:
            return False
        initial_len = len(self._user_wardrobes[user_id])
        self._user_wardrobes[user_id] = [i for i in self._user_wardrobes[user_id] if i["id"] != item_id]
        return len(self._user_wardrobes[user_id]) < initial_len

    def toggle_favorite(self, user_id: str, item_id: str) -> Optional[Dict]:
        items = self._user_wardrobes.get(user_id, [])
        for item in items:
            if item["id"] == item_id:
                item["favorite"] = not item.get("favorite", False)
                return item
        return None

    def record_wear(self, user_id: str, item_id: str) -> Optional[Dict]:
        items = self._user_wardrobes.get(user_id, [])
        for item in items:
            if item["id"] == item_id:
                item["wear_count"] = item.get("wear_count", 0) + 1
                return item
        return None

    def get_closet_analytics(self, user_id: str = "default_user") -> Dict:
        items = self.get_wardrobe(user_id)
        if not items:
            return {"total_items": 0, "categories": {}, "colors": {}, "most_worn": []}
            
        categories_count = {}
        colors_count = {}
        for item in items:
            cat = item.get("category", "other")
            col = item.get("color", "unknown")
            categories_count[cat] = categories_count.get(cat, 0) + 1
            colors_count[col] = colors_count.get(col, 0) + 1
            
        sorted_by_wear = sorted(items, key=lambda x: x.get("wear_count", 0), reverse=True)[:4]
        
        return {
            "total_items": len(items),
            "category_breakdown": categories_count,
            "color_palette_distribution": colors_count,
            "most_worn_staples": sorted_by_wear,
            "closet_utilization_rate": round(len([i for i in items if i.get("wear_count", 0) > 0]) / len(items) * 100, 1)
        }

# Global singleton
wardrobe_service = WardrobeService()
