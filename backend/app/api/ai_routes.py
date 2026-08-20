"""
Utility routes: shopping links, perfume images, AI text fallback.

Image fetching — speed optimisations:
  1. In-memory LRU cache (instant, no network, survives process lifetime)
  2. Single DDG query with tight 3s timeout — no sequential retries
  3. Score all results in one pass, return best immediately
  4. Background thread so FastAPI stays non-blocking
  5. "Not found" also cached to avoid hammering DDG for missing images
"""
import re
import time
import hashlib
import concurrent.futures
from typing import Optional
from fastapi import APIRouter
from ..config import settings

router = APIRouter()

# ── In-memory cache ───────────────────────────────────────────────────
_image_cache: dict[str, dict] = {}
_CACHE_TTL   = 7200   # 2 hours
_CACHE_MAX   = 3000   # max entries before eviction

# Thread pool for non-blocking DDG calls (1 worker = serialised, avoids rate limits)
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

QUALITY_HOSTS = [
    "m.media-amazon.com",
    "images-na.ssl-images-amazon.com",
    "pinimg.com",
    "pngimg.com",
    "fragrantica.com",
    "parfumo.net",
    "notino.com",
    "sephora.com",
    "ulta.com",
    "lookfantastic.com",
]

BLOCKED_HOSTS = [
    "facebook.com", "instagram.com", "twitter.com", "x.com",
    "tiktok.com", "youtube.com", "reddit.com", "wikipedia.org",
    "ebay.com", "aliexpress.com",
]


def _cache_key(name: str, brand: str) -> str:
    return hashlib.md5(f"{brand.lower().strip()}|{name.lower().strip()}".encode()).hexdigest()


def _is_valid_url(url: str) -> bool:
    if not url or len(url) < 15 or len(url) > 600:
        return False
    if not url.startswith(("http://", "https://")):
        return False
    low = url.lower()
    if any(b in low for b in BLOCKED_HOSTS):
        return False
    has_ext  = any(low.endswith(e) for e in (".png", ".jpg", ".jpeg", ".webp"))
    has_path = any(s in low for s in ("/image", "/img", "/photo", "/product", "/media", "/perfume"))
    return has_ext or has_path


def _score(url: str) -> int:
    low = url.lower()
    s = 0
    if low.endswith(".png"):   s += 100
    elif low.endswith(".webp"): s += 70
    elif low.endswith((".jpg", ".jpeg")): s += 50
    if "fragrantica" in low:   s += 90
    if "amazon" in low and ("images" in low or "media" in low): s += 70
    for h in QUALITY_HOSTS:
        if h in low: s += 40; break
    if len(url) > 350: s -= 30
    return s


def _ddg_search(query: str, max_results: int = 12, timeout: float = 3.0) -> list[str]:
    """Single DDG image search. Runs in thread pool. Returns scored+sorted URLs."""
    try:
        import warnings
        warnings.filterwarnings("ignore")
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            from ddgs import DDGS  # type: ignore

        candidates: list[str] = []
        deadline = time.time() + timeout

        with DDGS() as ddgs:
            for r in ddgs.images(
                keywords=query,
                region="wt-wt",
                safesearch="on",
                size="Medium",
                type_image="photo",
                max_results=max_results,
            ):
                if time.time() > deadline:
                    break
                url = r.get("image", "")
                if _is_valid_url(url):
                    candidates.append(url)
                    # Early exit: found a PNG from a quality host — can't do better
                    if url.lower().endswith(".png") and any(h in url.lower() for h in QUALITY_HOSTS):
                        break

        if not candidates:
            return []
        # Deduplicate + sort by score
        seen: set[str] = set()
        unique = [u for u in candidates if not (u in seen or seen.add(u))]  # type: ignore
        return sorted(unique, key=_score, reverse=True)

    except Exception:
        return []


def _fragrantica_image_url(fragrantica_url: str) -> Optional[str]:
    """
    Extract image URL from a Fragrantica perfume page URL.
    Pattern: https://www.fragrantica.com/perfume/Brand/Name-12345.html
    Image:   https://fimgs.net/mdimg/perfume/375x500.12345.jpg
    """
    if not fragrantica_url:
        return None
    import re
    match = re.search(r'-(\d+)\.html$', fragrantica_url)
    if match:
        perfume_id = match.group(1)
        return f"https://fimgs.net/mdimg/perfume/375x500.{perfume_id}.jpg"
    return None


def _fetch_image(name: str, brand: str) -> Optional[str]:
    """
    Multi-source image fetch:
    1. Fragrantica CDN (reliable, no rate limits)
    2. DDG image search (fallback)
    """
    # Strategy 1: Try to find Fragrantica URL from the dataset
    try:
        from ..ml_model import recommender
        if recommender.data is not None:
            mask = (
                recommender.data["name"].str.lower().str.contains(name.lower()[:15], na=False) &
                recommender.data["brand"].str.lower().str.contains(brand.lower()[:10], na=False)
            )
            matches = recommender.data[mask]
            if not matches.empty and "url" in matches.columns:
                fra_url = matches.iloc[0].get("url", "")
                img_url = _fragrantica_image_url(str(fra_url))
                if img_url:
                    return img_url
    except Exception:
        pass

    # Strategy 2: DDG image search
    q1 = f'"{brand}" "{name}" perfume bottle'
    results = _ddg_search(q1, max_results=12, timeout=4.0)

    if not results:
        q2 = f"{brand} {name} perfume fragrance"
        results = _ddg_search(q2, max_results=8, timeout=3.0)

    return results[0] if results else None


def _evict_cache():
    """Remove expired entries when cache is too large."""
    if len(_image_cache) <= _CACHE_MAX:
        return
    cutoff = time.time() - _CACHE_TTL
    expired = [k for k, v in _image_cache.items() if v["ts"] < cutoff]
    for k in expired:
        del _image_cache[k]
    # If still too large, remove oldest 20%
    if len(_image_cache) > _CACHE_MAX:
        sorted_keys = sorted(_image_cache, key=lambda k: _image_cache[k]["ts"])
        for k in sorted_keys[:len(_image_cache) // 5]:
            del _image_cache[k]


# ── Routes ────────────────────────────────────────────────────────────

@router.post("/ai/shopping-links")
def get_shopping_links(perfume_name: str, brand: str, price: float = 0):
    """
    Return accurate INR pricing + shopping links.
    Uses real USD→INR conversion for eBay prices,
    or brand-tier lookup for Fragrantica/curated perfumes.
    """
    from .pricing import get_price

    price_result = get_price(perfume_name, brand, price)
    name_q = f"{brand} {perfume_name}".replace(" ", "+")

    return {
        "price_inr_min":  price_result.inr_min,
        "price_inr_max":  price_result.inr_max,
        "price_display":  price_result.inr_display,
        "price_source":   price_result.source,
        "usd_original":   price_result.usd_original,
        "fx_rate":        price_result.fx_rate,
        # Legacy fields kept for backward compat
        "original_price_inr":   f"₹{price_result.inr_max:,}",
        "discounted_price_inr": f"₹{price_result.inr_min:,}",
        "links": [
            {"platform": "Amazon",   "url": f"https://www.amazon.in/s?k={name_q}+perfume"},
            {"platform": "Flipkart", "url": f"https://www.flipkart.com/search?q={name_q}+perfume"},
            {"platform": "Nykaa",    "url": f"https://www.nykaa.com/search/result/?q={name_q}"},
            {"platform": "Myntra",   "url": f"https://www.myntra.com/{name_q.replace('+', '-')}-perfume"},
        ],
        "source": "search_api",
    }


@router.get("/ai/perfume-image")
def get_perfume_image(perfume_name: str, brand: str):
    """
    Return the best image URL for a perfume.

    Fast path  : cache hit → <1ms
    Slow path  : DDG search → 2–5s (result cached for next call)
    Miss path  : None cached → instant on repeat calls
    """
    # Sanitise
    name  = re.sub(r"[^\w\s\-&'.]", "", perfume_name.strip())[:80]
    bname = re.sub(r"[^\w\s\-&'.]", "", brand.strip())[:60]
    if not name or not bname:
        return {"image_url": None, "source": "invalid_input"}

    try:
        from ..ml_model import recommender
        if recommender.data is None:
            return {"image_url": None, "source": "loading"}
    except Exception:
        return {"image_url": None, "source": "loading"}

    key = _cache_key(name, bname)

    # ── Cache hit ──────────────────────────────────────────────────
    cached = _image_cache.get(key)
    if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
        return {"image_url": cached["url"], "source": "cache"}

    # ── Cache miss — try Fragrantica CDN first (fast, reliable) ──
    # Then fall back to DDG search in thread pool
    try:
        if recommender.data is not None:
            mask = (
                recommender.data["name"].str.lower().str.contains(name.lower()[:15], na=False) &
                recommender.data["brand"].str.lower().str.contains(bname.lower()[:10], na=False)
            )
            matches = recommender.data[mask]
            if not matches.empty and "url" in matches.columns:
                fra_url = matches.iloc[0].get("url", "")
                fra_img = _fragrantica_image_url(str(fra_url))
                if fra_img:
                    _image_cache[key] = {"url": fra_img, "ts": time.time()}
                    return {"image_url": fra_img, "source": "fragrantica"}
    except Exception:
        pass

    # ── Fall back to DDG search in thread pool (non-blocking) ────
    try:
        future = _executor.submit(_fetch_image, name, bname)
        url = future.result(timeout=6.0)   # hard cap: 6s total
    except concurrent.futures.TimeoutError:
        url = None
    except Exception:
        url = None

    # Store result (including None — prevents repeat slow calls)
    _image_cache[key] = {"url": url, "ts": time.time()}
    _evict_cache()

    if url:
        src = "png" if url.lower().endswith(".png") else "image"
        return {"image_url": url, "source": src}
    return {"image_url": None, "source": "not_found"}


@router.get("/ai/perfume-description")
def enhance_perfume_description(perfume_id: str, current_description: str = ""):
    if current_description and len(current_description.strip()) > 20:
        return {"enhanced_description": current_description, "source": "dataset"}

    prompt = (
        f"Write a 2-sentence product description for a perfume. "
        f"Info: {current_description or 'none'}. Max 80 words. Be evocative and sensory."
    )

    # ── Try Gemini via REST (avoids SDK model name issues) ────────────
    if settings.has_gemini:
        primary = settings.gemini_model.removeprefix("models/")
        model_chain = [primary]
        for fb in ["gemini-flash-latest", "gemini-2.5-flash"]:
            if fb != primary:
                model_chain.append(fb)
        for model in model_chain:
            try:
                import requests as req
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{model}:generateContent?key={settings.effective_google_key}"
                )
                resp = req.post(url, timeout=settings.ai_fallback_timeout, json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.4, "maxOutputTokens": 120},
                })
                if resp.status_code == 503:
                    continue  # try next model
                resp.raise_for_status()
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                return {"enhanced_description": text, "source": "gemini"}
            except Exception:
                continue

    # ── Try OpenAI (not configured — skip) ───────────────────────────
    # openai_api_key not in settings, skip this provider

    return {"enhanced_description": current_description or "A premium fragrance.", "source": "fallback"}
