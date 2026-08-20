"""
Pricing engine — accurate INR prices for perfumes.

Strategy:
1. If the dataset has a real USD price (eBay data) → convert to INR using
   a live exchange rate fetched from a free public API (cached 6 hours).
2. If no dataset price → look up the brand in a curated tier table that
   maps well-known brands to realistic Indian market price ranges.
3. Always return a structured PriceResult with source transparency.

Exchange rate source: exchangerate-api.com (free, no key needed for USD→INR)
Fallback rate: 84 INR/USD (updated periodically in code)
"""
import time
import threading
from typing import Optional

# ── Exchange rate cache ───────────────────────────────────────────────
_fx_lock   = threading.Lock()
_fx_cache: dict = {"rate": 84.0, "ts": 0.0}   # fallback 84 INR/USD
_FX_TTL    = 21600   # 6 hours

def _fetch_usd_inr() -> float:
    """Fetch live USD→INR rate. Returns cached fallback on any error."""
    try:
        import urllib.request, json
        # Free endpoint — no API key required
        url = "https://open.er-api.com/v6/latest/USD"
        with urllib.request.urlopen(url, timeout=4) as resp:
            data = json.loads(resp.read())
        rate = float(data["rates"]["INR"])
        if 70 <= rate <= 110:   # sanity check
            return rate
    except Exception:
        pass
    return _fx_cache["rate"]   # return last known good rate

def get_usd_to_inr() -> float:
    """Return USD→INR rate, refreshing every 6 hours."""
    with _fx_lock:
        if time.time() - _fx_cache["ts"] > _FX_TTL:
            rate = _fetch_usd_inr()
            _fx_cache["rate"] = rate
            _fx_cache["ts"]   = time.time()
        return _fx_cache["rate"]


# ── Brand tier table ──────────────────────────────────────────────────
# (min_inr, max_inr) for 100ml / standard bottle
# Based on actual Indian market prices (Nykaa, Amazon.in, Sephora India)
BRAND_TIERS: dict[str, tuple[int, int]] = {
    # Ultra-luxury (₹15,000–₹80,000+)
    "creed":              (25000, 80000),
    "tom ford":           (15000, 55000),
    "maison margiela":    (12000, 45000),
    "xerjoff":            (20000, 70000),
    "amouage":            (18000, 60000),
    "roja parfums":       (25000, 90000),
    "frederic malle":     (18000, 55000),
    "byredo":             (14000, 40000),
    "diptyque":           (10000, 30000),
    "jo malone":          (8000,  25000),
    "maison francis kurkdjian": (15000, 50000),
    "mfk":                (15000, 50000),
    "parfums de marly":   (14000, 45000),
    "initio":             (16000, 50000),
    "nishane":            (12000, 40000),
    "orto parisi":        (10000, 35000),
    "serge lutens":       (8000,  28000),
    "penhaligon":         (8000,  25000),
    "clive christian":    (30000, 120000),
    "bond no. 9":         (15000, 60000),
    "bond no 9":          (15000, 60000),

    # Premium designer (₹5,000–₹20,000)
    "chanel":             (8000,  22000),
    "dior":               (6000,  18000),
    "christian dior":     (6000,  18000),
    "yves saint laurent": (5000,  15000),
    "ysl":                (5000,  15000),
    "givenchy":           (5000,  14000),
    "guerlain":           (6000,  20000),
    "hermes":             (8000,  25000),
    "hermès":             (8000,  25000),
    "lancome":            (5000,  14000),
    "lancôme":            (5000,  14000),
    "cartier":            (6000,  18000),
    "bvlgari":            (5000,  15000),
    "bulgari":            (5000,  15000),
    "versace":            (4000,  12000),
    "prada":              (6000,  18000),
    "valentino":          (5000,  15000),
    "burberry":           (4000,  12000),
    "gucci":              (5000,  15000),
    "dolce & gabbana":    (4000,  12000),
    "dolce and gabbana":  (4000,  12000),
    "d&g":                (4000,  12000),
    "armani":             (4000,  12000),
    "giorgio armani":     (4000,  12000),
    "emporio armani":     (3500,  10000),
    "hugo boss":          (3000,  9000),
    "boss":               (3000,  9000),
    "mont blanc":         (3000,  9000),
    "montblanc":          (3000,  9000),
    "calvin klein":       (2500,  8000),
    "ck":                 (2500,  8000),
    "ralph lauren":       (3000,  9000),
    "polo ralph lauren":  (3000,  9000),
    "michael kors":       (3500,  10000),
    "coach":              (3500,  10000),
    "marc jacobs":        (3500,  10000),
    "jimmy choo":         (4000,  12000),
    "alexander mcqueen":  (5000,  15000),
    "viktor & rolf":      (5000,  15000),
    "viktor and rolf":    (5000,  15000),
    "jean paul gaultier": (4000,  12000),
    "thierry mugler":     (4000,  12000),
    "mugler":             (4000,  12000),
    "issey miyake":       (4000,  12000),
    "kenzo":              (3500,  10000),
    "lacoste":            (3000,  9000),
    "davidoff":           (2500,  8000),
    "dunhill":            (3000,  9000),
    "azzaro":             (3000,  9000),
    "nina ricci":         (3500,  10000),
    "lanvin":             (3500,  10000),
    "loewe":              (7000,  20000),
    "chloe":              (5000,  15000),
    "chloé":              (5000,  15000),
    "stella mccartney":   (5000,  15000),
    "narciso rodriguez":  (5000,  15000),
    "carolina herrera":   (4000,  12000),
    "oscar de la renta":  (4000,  12000),
    "roberto cavalli":    (3500,  10000),
    "trussardi":          (3000,  9000),
    "salvatore ferragamo":(4000,  12000),
    "ferragamo":          (4000,  12000),
    "cerruti":            (3000,  9000),
    "escada":             (3500,  10000),
    "joop":               (2500,  8000),
    "mexx":               (2000,  6000),
    "s.t. dupont":        (4000,  12000),
    "st dupont":          (4000,  12000),
    "chopard":            (4000,  12000),
    "boucheron":          (5000,  15000),
    "van cleef":          (8000,  25000),
    "bulgari":            (5000,  15000),
    "tiffany":            (5000,  15000),
    "tiffany & co":       (5000,  15000),

    # Mid-range (₹1,500–₹6,000)
    "elizabeth arden":    (1500,  5000),
    "revlon":             (800,   3000),
    "avon":               (500,   2500),
    "coty":               (800,   3000),
    "adidas":             (800,   2500),
    "nike":               (1000,  3000),
    "puma":               (800,   2500),
    "playboy":            (800,   2500),
    "davidoff":           (2500,  8000),
    "nautica":            (2000,  6000),
    "kenneth cole":       (2500,  7000),
    "tommy hilfiger":     (2500,  8000),
    "tommy":              (2500,  8000),
    "dkny":               (3000,  9000),
    "donna karan":        (3000,  9000),
    "anne klein":         (2000,  6000),
    "liz claiborne":      (1500,  5000),
    "paris hilton":       (1500,  5000),
    "britney spears":     (1200,  4000),
    "beyonce":            (1200,  4000),
    "jennifer lopez":     (1500,  5000),
    "jlo":                (1500,  5000),
    "ed hardy":           (2000,  6000),
    "diesel":             (2500,  8000),
    "guess":              (2000,  6000),
    "esprit":             (1500,  5000),
    "fcuk":               (2000,  6000),
    "french connection":  (2000,  6000),
    "bench":              (1000,  3500),
    "axe":                (300,   1000),
    "lynx":               (300,   1000),
    "old spice":          (300,   1200),
    "brut":               (300,   1000),
    "fogg":               (200,   800),
    "engage":             (200,   800),
    "denver":             (300,   1200),
    "wildstone":          (200,   800),
    "park avenue":        (300,   1200),
    "set wet":            (150,   600),

    # Niche / indie (₹3,000–₹25,000)
    "le labo":            (10000, 35000),
    "aesop":              (8000,  25000),
    "escentric molecules":(5000,  18000),
    "molecule":           (5000,  18000),
    "juliette has a gun": (6000,  20000),
    "etat libre d'orange":(6000,  20000),
    "sweet tea apothecary":(3000, 10000),
    "d.s. & durga":       (8000,  25000),
    "ds & durga":         (8000,  25000),
    "commodity":          (5000,  15000),
    "phlur":              (5000,  15000),
    "dedcool":            (4000,  12000),
    "snif":               (4000,  12000),
    "imaginary authors":  (6000,  18000),
    "zoologist":          (6000,  20000),
    "henry rose":         (5000,  15000),
    "skylar":             (3000,  10000),
    "maison tahite":      (5000,  15000),
    "vilhelm parfumerie": (8000,  25000),
    "memo paris":         (10000, 35000),
    "atelier cologne":    (8000,  25000),
    "l'artisan parfumeur":(8000,  25000),
    "l artisan parfumeur":(8000,  25000),
    "annick goutal":      (7000,  22000),
    "goutal paris":       (7000,  22000),
    "miller harris":      (6000,  20000),
    "ormonde jayne":      (8000,  25000),
    "clive christian":    (30000, 120000),
    "henry jacques":      (20000, 80000),

    # Arabic / Oud houses (₹2,000–₹30,000)
    "lattafa":            (1500,  6000),
    "rasasi":             (2000,  8000),
    "ajmal":              (1500,  8000),
    "al haramain":        (2000,  10000),
    "swiss arabian":      (2000,  10000),
    "armaf":              (1500,  6000),
    "fragrance world":    (1500,  6000),
    "oud elite":          (3000,  15000),
    "nabeel":             (2000,  8000),
    "ard al zaafaran":    (1500,  6000),
    "maison alhambra":    (1500,  6000),
    "zimaya":             (2000,  8000),
    "afnan":              (1500,  6000),
    "fa paris":           (2000,  8000),
    "hamidi":             (1500,  6000),
    "surrati":            (2000,  8000),
    "oud mood":           (2000,  8000),
    "arabiyat":           (1500,  6000),
    "khalis":             (1500,  6000),
    "rihanah":            (1500,  6000),
    "emper":              (1000,  4000),
    "pendora":            (1500,  6000),
    "paris corner":       (1500,  6000),
    "oud elite":          (3000,  15000),
    "oud mood":           (2000,  8000),
    "oud":                (2000,  10000),
}

# Default tiers when brand not found
_DEFAULT_TIERS = {
    "luxury":   (8000,  25000),
    "premium":  (3000,  10000),
    "standard": (1200,  5000),
    "budget":   (400,   2000),
}

def _brand_tier(brand: str) -> tuple[int, int]:
    """Return (min_inr, max_inr) for a brand."""
    key = brand.lower().strip()
    # Exact match
    if key in BRAND_TIERS:
        return BRAND_TIERS[key]
    # Partial match (e.g. "Dior" matches "christian dior")
    for b, rng in BRAND_TIERS.items():
        if key in b or b in key:
            return rng
    return _DEFAULT_TIERS["standard"]


# ── Public API ────────────────────────────────────────────────────────

class PriceResult:
    __slots__ = ("inr_min", "inr_max", "inr_display", "source", "usd_original", "fx_rate")

    def __init__(
        self,
        inr_min: int,
        inr_max: int,
        source: str,
        usd_original: float = 0.0,
        fx_rate: float = 0.0,
    ):
        self.inr_min      = inr_min
        self.inr_max      = inr_max
        self.source       = source
        self.usd_original = usd_original
        self.fx_rate      = fx_rate
        # Display string
        if inr_min == inr_max:
            self.inr_display = f"₹{inr_min:,}"
        else:
            self.inr_display = f"₹{inr_min:,} – ₹{inr_max:,}"

    def to_dict(self) -> dict:
        return {
            "inr_min":      self.inr_min,
            "inr_max":      self.inr_max,
            "inr_display":  self.inr_display,
            "source":       self.source,
            "usd_original": self.usd_original,
            "fx_rate":      round(self.fx_rate, 2),
        }


def get_price(name: str, brand: str, dataset_price_usd: float = 0.0) -> PriceResult:
    """
    Return the best available INR price for a perfume.

    Priority:
    1. Real USD price from dataset (eBay) → convert with live FX rate
    2. Brand tier lookup → realistic Indian market range
    """
    if dataset_price_usd and dataset_price_usd > 0:
        fx = get_usd_to_inr()
        inr = int(round(dataset_price_usd * fx))
        # Add ~15% import duty + GST typical for India
        inr_with_tax = int(inr * 1.18)
        return PriceResult(
            inr_min=inr_with_tax,
            inr_max=inr_with_tax,
            source="dataset_usd",
            usd_original=dataset_price_usd,
            fx_rate=fx,
        )

    # Brand tier
    lo, hi = _brand_tier(brand)
    return PriceResult(
        inr_min=lo,
        inr_max=hi,
        source="brand_tier",
    )
