"""
Spell Corrector — Handles typos and spelling errors in user input.

Features:
- Fuzzy matching for brand names and perfume names
- Common typo corrections
- Web search fallback for unknown terms
"""
from __future__ import annotations
import re
from typing import Optional, List, Tuple
from difflib import SequenceMatcher


# Common brand name typos
BRAND_CORRECTIONS = {
    # Nike-style typos
    "nikw": "nike",
    "nkie": "nike",
    "nke": "nike",
    
    # Dior typos
    "doir": "dior",
    "dior": "dior",
    "diior": "dior",
    
    # Chanel typos
    "chanell": "chanel",
    "chanel": "chanel",
    "chanle": "chanel",
    "shannel": "chanel",
    
    # Gucci typos
    "guchi": "gucci",
    "guci": "gucci",
    "guccy": "gucci",
    
    # Versace typos
    "versace": "versace",
    "versachi": "versace",
    "versase": "versace",
    "versacce": "versace",
    
    # Armani typos
    "armani": "armani",
    "armanni": "armani",
    "armany": "armani",
    
    # YSL typos
    "ysl": "ysl",
    "yves saint laurent": "ysl",
    "yves st laurent": "ysl",
    
    # Tom Ford typos
    "tom ford": "tom ford",
    "tomford": "tom ford",
    "tom frod": "tom ford",
    
    # Creed typos
    "creed": "creed",
    "cread": "creed",
    "creid": "creed",
    
    # Prada typos
    "prada": "prada",
    "prада": "prada",
    "pradda": "prada",
    
    # Burberry typos
    "burberry": "burberry",
    "burbury": "burberry",
    "burbery": "burberry",
    "burberrry": "burberry",
    
    # Calvin Klein typos
    "calvin klein": "calvin klein",
    "calvin klien": "calvin klein",
    "calvin kline": "calvin klein",
    "ck": "calvin klein",
    
    # Hugo Boss typos
    "hugo boss": "hugo boss",
    "hugo bos": "hugo boss",
    "hugoboss": "hugo boss",
    
    # Dolce & Gabbana typos
    "dolce gabbana": "dolce gabbana",
    "dolce and gabbana": "dolce gabbana",
    "dolce & gabbana": "dolce gabbana",
    "d&g": "dolce gabbana",
    "dg": "dolce gabbana",
    
    # Givenchy typos
    "givenchy": "givenchy",
    "givency": "givenchy",
    "givenchi": "givenchy",
    
    # Hermès typos
    "hermes": "hermes",
    "hermès": "hermes",
    "herms": "hermes",
    
    # Lancôme typos
    "lancome": "lancome",
    "lancôme": "lancome",
    "lancom": "lancome",
    
    # Jo Malone typos
    "jo malone": "jo malone",
    "jomalone": "jo malone",
    "jo malon": "jo malone",
}

# Common perfume name typos
PERFUME_CORRECTIONS = {
    "sauvage": "sauvage",
    "savage": "sauvage",
    "savaje": "sauvage",
    "savauge": "sauvage",
    
    "acqua di gio": "acqua di gio",
    "aqua di gio": "acqua di gio",
    "aqua de gio": "acqua di gio",
    "acqua de gio": "acqua di gio",
    
    "bleu de chanel": "bleu de chanel",
    "blue de chanel": "bleu de chanel",
    "bleu chanel": "bleu de chanel",
    "blue chanel": "bleu de chanel",
    
    "la nuit de l'homme": "la nuit de l'homme",
    "la nuit de lhomme": "la nuit de l'homme",
    "la nuit": "la nuit de l'homme",
    
    "one million": "one million",
    "1 million": "one million",
    "onemillion": "one million",
    
    "invictus": "invictus",
    "invictis": "invictus",
    "invictuss": "invictus",
    
    "eros": "eros",
    "eross": "eros",
    "erros": "eros",
    
    "aventus": "aventus",
    "avantus": "aventus",
    "aventuss": "aventus",
}

# Common note typos
NOTE_CORRECTIONS = {
    "oud": "oud",
    "ood": "oud",
    "ude": "oud",
    "aoud": "oud",
    
    "vanilla": "vanilla",
    "vanila": "vanilla",
    "vannila": "vanilla",
    "vanilia": "vanilla",
    
    "bergamot": "bergamot",
    "bergamott": "bergamot",
    "bergamont": "bergamot",
    
    "sandalwood": "sandalwood",
    "sandlewood": "sandalwood",
    "sandelwood": "sandalwood",
    
    "patchouli": "patchouli",
    "patchouly": "patchouli",
    "patchuli": "patchouli",
    "pachouli": "patchouli",
    
    "vetiver": "vetiver",
    "vetivir": "vetiver",
    "vetyver": "vetiver",
    
    "jasmine": "jasmine",
    "jasmin": "jasmine",
    "jazmine": "jasmine",
    
    "lavender": "lavender",
    "lavendar": "lavender",
    "lavander": "lavender",
}


def similarity_score(a: str, b: str) -> float:
    """Calculate similarity between two strings (0.0-1.0)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def fuzzy_match(word: str, candidates: List[str], threshold: float = 0.75) -> Optional[str]:
    """
    Find the best fuzzy match for a word from a list of candidates.
    
    Args:
        word: Input word (possibly misspelled)
        candidates: List of correct words
        threshold: Minimum similarity score (0.0-1.0)
        
    Returns:
        Best match if similarity >= threshold, else None
    """
    if not word or not candidates:
        return None
    
    best_match = None
    best_score = 0.0
    
    for candidate in candidates:
        score = similarity_score(word, candidate)
        if score > best_score:
            best_score = score
            best_match = candidate
    
    if best_score >= threshold:
        return best_match
    
    return None


def correct_brand_name(brand: str) -> Tuple[str, bool]:
    """
    Correct brand name typos.
    
    Args:
        brand: Input brand name (possibly misspelled)
        
    Returns:
        (corrected_brand, was_corrected)
    """
    brand_lower = brand.lower().strip()
    
    # Direct lookup
    if brand_lower in BRAND_CORRECTIONS:
        return BRAND_CORRECTIONS[brand_lower], True
    
    # Fuzzy match against known brands
    known_brands = list(set(BRAND_CORRECTIONS.values()))
    match = fuzzy_match(brand_lower, known_brands, threshold=0.8)
    if match:
        return match, True
    
    return brand, False


def correct_perfume_name(perfume: str) -> Tuple[str, bool]:
    """
    Correct perfume name typos.
    
    Args:
        perfume: Input perfume name (possibly misspelled)
        
    Returns:
        (corrected_perfume, was_corrected)
    """
    perfume_lower = perfume.lower().strip()
    
    # Direct lookup
    if perfume_lower in PERFUME_CORRECTIONS:
        return PERFUME_CORRECTIONS[perfume_lower], True
    
    # Fuzzy match against known perfumes
    known_perfumes = list(set(PERFUME_CORRECTIONS.values()))
    match = fuzzy_match(perfume_lower, known_perfumes, threshold=0.8)
    if match:
        return match, True
    
    return perfume, False


def correct_note(note: str) -> Tuple[str, bool]:
    """
    Correct note typos.
    
    Args:
        note: Input note (possibly misspelled)
        
    Returns:
        (corrected_note, was_corrected)
    """
    note_lower = note.lower().strip()
    
    # Direct lookup
    if note_lower in NOTE_CORRECTIONS:
        return NOTE_CORRECTIONS[note_lower], True
    
    # Fuzzy match against known notes
    known_notes = list(set(NOTE_CORRECTIONS.values()))
    match = fuzzy_match(note_lower, known_notes, threshold=0.8)
    if match:
        return match, True
    
    return note, False


def correct_text(text: str) -> Tuple[str, List[str]]:
    """
    Correct typos in full text.
    
    Args:
        text: Input text (possibly with typos)
        
    Returns:
        (corrected_text, list_of_corrections)
    """
    corrections = []
    words = text.split()
    corrected_words = []
    
    for word in words:
        # Clean word
        clean_word = re.sub(r'[^\w\s-]', '', word)
        
        # Try brand correction
        corrected_brand, brand_corrected = correct_brand_name(clean_word)
        if brand_corrected:
            corrections.append(f"{clean_word} → {corrected_brand}")
            corrected_words.append(corrected_brand)
            continue
        
        # Try perfume correction
        corrected_perfume, perfume_corrected = correct_perfume_name(clean_word)
        if perfume_corrected:
            corrections.append(f"{clean_word} → {corrected_perfume}")
            corrected_words.append(corrected_perfume)
            continue
        
        # Try note correction
        corrected_note, note_corrected = correct_note(clean_word)
        if note_corrected:
            corrections.append(f"{clean_word} → {corrected_note}")
            corrected_words.append(corrected_note)
            continue
        
        # No correction needed
        corrected_words.append(word)
    
    corrected_text = " ".join(corrected_words)
    return corrected_text, corrections


def extract_brand_and_perfume(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract brand and perfume name from text.
    
    Args:
        text: Input text
        
    Returns:
        (brand, perfume_name)
    """
    text_lower = text.lower()
    
    # Pattern: "brand perfume" or "perfume by brand"
    # Example: "dior sauvage" or "sauvage by dior"
    
    # Try "brand perfume" pattern
    for brand in BRAND_CORRECTIONS.values():
        if brand in text_lower:
            # Extract perfume name after brand
            parts = text_lower.split(brand)
            if len(parts) > 1:
                perfume = parts[1].strip()
                # Clean perfume name
                perfume = re.sub(r'[^\w\s-]', '', perfume).strip()
                if perfume:
                    return brand, perfume
    
    # Try "perfume by brand" pattern
    by_match = re.search(r'(.+?)\s+by\s+(.+)', text_lower)
    if by_match:
        perfume = by_match.group(1).strip()
        brand = by_match.group(2).strip()
        
        # Correct brand
        corrected_brand, _ = correct_brand_name(brand)
        
        # Correct perfume
        corrected_perfume, _ = correct_perfume_name(perfume)
        
        return corrected_brand, corrected_perfume
    
    return None, None


def should_use_web_search(text: str, corrections: List[str]) -> bool:
    """
    Determine if web search should be used.
    
    Use web search when:
    - User mentions a specific brand/perfume
    - Typos were corrected (to verify)
    - Query is very specific
    
    Args:
        text: Input text
        corrections: List of corrections made
        
    Returns:
        True if web search should be used
    """
    text_lower = text.lower()
    
    # If corrections were made, use web search to verify
    if corrections:
        return True
    
    # If specific brand mentioned
    for brand in BRAND_CORRECTIONS.values():
        if brand in text_lower:
            return True
    
    # If specific perfume mentioned
    for perfume in PERFUME_CORRECTIONS.values():
        if perfume in text_lower:
            return True
    
    # If "like" or "similar to" pattern
    if any(p in text_lower for p in ["like", "similar to", "same as", "reminds me of"]):
        return True
    
    return False


def build_search_query(text: str, brand: Optional[str] = None, perfume: Optional[str] = None) -> str:
    """
    Build optimized search query for web search.
    
    Args:
        text: Original text
        brand: Extracted brand name
        perfume: Extracted perfume name
        
    Returns:
        Optimized search query
    """
    if brand and perfume:
        return f"{brand} {perfume} perfume fragrance notes review"
    elif brand:
        return f"{brand} perfume fragrance collection"
    elif perfume:
        return f"{perfume} perfume fragrance"
    else:
        # Extract key terms
        key_terms = []
        for word in text.split():
            clean_word = re.sub(r'[^\w\s-]', '', word).lower()
            if len(clean_word) > 3 and clean_word not in {"perfume", "fragrance", "scent"}:
                key_terms.append(clean_word)
        
        if key_terms:
            return f"{' '.join(key_terms[:3])} perfume fragrance"
        
        return text
