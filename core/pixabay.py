"""
core/pixabay.py — Pixabay image downloader for story/ebook video backgrounds.

How it works
────────────
1. Before rendering, the runner calls download_images_for_chunks() with the
   full chunk list and cfg.
2. Keywords are extracted per chapter (ebook) or per story segment (story).
   Hindi text → English keywords via a curated translation map + stripping
   Devanagari stop words so Pixabay (which works best with English) gets
   useful queries.
3. Images are downloaded, resized to video dimensions, and cached under
   PIXABAY_CACHE_DIR.  Re-runs skip already-cached images.
4. The runner sets cfg.STORY_BG_IMAGES to the downloaded paths and switches
   cfg.STORY_BG_MODE to "image" so the existing render pipeline needs zero
   changes.

Config keys (add to your mode config)
──────────────────────────────────────
    STORY_BG_MODE            = "pixabay"
    PIXABAY_API_KEY          = "your_key_here"   # free at pixabay.com/api
    PIXABAY_IMAGES_PER_QUERY = 3     # images downloaded per chapter/segment
    PIXABAY_CACHE_DIR        = "assets/pixabay_cache"
    PIXABAY_ORIENTATION      = "horizontal"   # or "vertical" for reels
    PIXABAY_SAFE_SEARCH      = True

Get a free API key → https://pixabay.com/api/docs/  (500 req/hour free tier)
"""

import os
import re
import json
import time
import hashlib
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

from utils import get_logger

log = get_logger("core.pixabay")

# ── Pixabay API ───────────────────────────────────────────────────────────────

PIXABAY_API_URL = "https://pixabay.com/api/"


def _api_search(
    query: str,
    api_key: str,
    count: int = 5,
    orientation: str = "horizontal",
    safe_search: bool = True,
) -> list[dict]:
    """
    Call Pixabay API and return a list of image hit dicts.
    Returns [] on any error (missing key, rate limit, network).
    """
    params = urllib.parse.urlencode({
        "key":         api_key,
        "q":           query,
        "image_type":  "photo",
        "orientation": orientation,
        "safesearch":  "true" if safe_search else "false",
        "per_page":    min(count, 20),
        "min_width":   1280,
        "min_height":  720,
        "order":       "popular",
    })
    url = f"{PIXABAY_API_URL}?{params}"

    try:
        req  = urllib.request.Request(url, headers={"User-Agent": "VideoBot/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        hits = data.get("hits", [])
        log.info("Pixabay '%s' → %d results", query, len(hits))
        return hits
    except urllib.error.HTTPError as e:
        if e.code == 400:
            log.warning("Pixabay: bad request for query %r (key valid?)", query)
        elif e.code == 429:
            log.warning("Pixabay: rate limited — sleeping 30 s")
            time.sleep(30)
        else:
            log.warning("Pixabay HTTP %d for query %r", e.code, query)
    except Exception as exc:
        log.warning("Pixabay request failed (%s): %s", type(exc).__name__, exc)
    return []


def _download_image(url: str, dest: str, video_w: int, video_h: int) -> bool:
    """Download *url* to *dest*, resize to cover video dimensions."""
    try:
        from PIL import Image as PILImage
        req = urllib.request.Request(url, headers={"User-Agent": "VideoBot/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()

        import io
        img = PILImage.open(io.BytesIO(raw)).convert("RGB")

        # Resize to cover (no black bars, no distortion)
        img_ratio    = img.width / img.height
        target_ratio = video_w  / video_h
        if img_ratio > target_ratio:
            new_h = video_h
            new_w = int(img.width * video_h / img.height)
        else:
            new_w = video_w
            new_h = int(img.height * video_w / img.width)
        img = img.resize((new_w, new_h), PILImage.LANCZOS)
        # Centre-crop
        left = (new_w - video_w) // 2
        top  = (new_h - video_h) // 2
        img  = img.crop((left, top, left + video_w, top + video_h))
        img.save(dest, "JPEG", quality=92)
        return True
    except Exception as exc:
        log.warning("Image download failed (%s): %s", url[:60], exc)
        return False


# ── Keyword extraction ────────────────────────────────────────────────────────

# Common English stop words
_EN_STOPS = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with",
    "by","from","is","are","was","were","be","been","have","has","had","do",
    "does","did","will","would","could","should","may","might","this","that",
    "these","those","it","its","not","no","so","as","if","then","than","when",
    "what","who","which","how","all","each","about","into","through","during",
    "before","after","above","below","between","out","off","over","under","again",
    "more","most","other","some","such","own","same","just","because","while",
    "where","can","their","they","them","there","here","our","we","you","your",
    "his","her","him","she","he","i","my","me","us","very","also","only","up",
}

# Hindi stop words (Devanagari)
_HI_STOPS = {
    "है","हैं","था","थे","थी","की","का","के","में","को","से","यह","वह",
    "एक","और","या","लेकिन","भी","तो","ही","नहीं","जो","कि","पर","अपने",
    "हम","आप","वे","इस","उस","इन","उन","जब","तब","अब","फिर","सभी","कुछ",
    "कभी","किसी","हर","बहुत","अधिक","कम","बाद","पहले","साथ","लिए","ने",
    "हो","होता","होती","होते","करता","करती","करते","करना","होना","रहा",
    # Heading words — appear in every chapter, add no search value
    "मुख्य","सीख","अध्याय","सुझाव","करें","करो","करना","सीखें","जाओ",
}

# Hindi content words → English search terms for Pixabay
_HI_TO_EN = {
    # Finance / business
    "पैसा": "money", "पैसे": "money", "धन": "wealth", "दौलत": "wealth",
    "अमीर": "rich", "गरीब": "poor", "निवेश": "investment", "निवेशक": "investor",
    "व्यापार": "business", "व्यवसाय": "business", "उद्यमी": "entrepreneur",
    "संपत्ति": "assets", "देनदारी": "debt", "कर": "tax", "बैंक": "bank",
    "शेयर": "stocks", "रियल": "real estate", "किराया": "rent",
    "तनख्वाह": "salary", "आय": "income", "खर्च": "expense", "बचत": "savings",
    "ऋण": "loan", "उधार": "debt", "मुनाफा": "profit", "घाटा": "loss",
    "बाज़ार": "market", "अर्थव्यवस्था": "economy", "वित्त": "finance",
    # Personal growth / skills
    "सफलता": "success", "असफलता": "failure", "लक्ष्य": "goal",
    "सपना": "dream", "साहस": "courage", "ज्ञान": "knowledge",
    "शिक्षा": "education", "सीखना": "learning", "बुद्धि": "wisdom",
    "आदत": "habits", "अनुशासन": "discipline", "मेहनत": "hardwork",
    "कौशल": "skills", "काम": "work", "नौकरी": "job", "करियर": "career",
    "सुझाव": "advice", "तैयारी": "preparation", "शुरुआत": "beginning",
    "सुधार": "improvement", "बेहतर": "better", "सोच": "mindset",
    "जिम्मेदारी": "responsibility", "नेतृत्व": "leadership",
    "प्रेरणा": "motivation", "उत्साह": "enthusiasm", "संघर्ष": "struggle",
    # People
    "पिता": "father", "माता": "mother", "बच्चे": "children", "दोस्त": "friend",
    "परिवार": "family", "नेता": "leader", "गुरु": "mentor", "छात्र": "student",
    "व्यक्ति": "person", "लोग": "people", "युवा": "youth",
    # Concepts
    "स्वतंत्रता": "freedom", "डर": "fear", "लालच": "greed", "शक्ति": "power",
    "समय": "time", "भविष्य": "future", "सरकार": "government", "कानून": "law",
    "जोखिम": "risk", "अवसर": "opportunity", "रणनीति": "strategy",
    "निर्णय": "decision", "विचार": "ideas", "योजना": "planning",
    # Actions
    "खरीदना": "buying", "बेचना": "selling", "बनाना": "building",
    "सिखाना": "teaching", "पढ़ना": "reading", "लिखना": "writing",
    # Nature / environment
    "जीवन": "life", "दुनिया": "world", "समाज": "society", "देश": "country",
    "प्रकृति": "nature", "शहर": "city", "घर": "home",
    # Common in ebooks
    "अध्याय": "chapter", "किताब": "book", "कहानी": "story", "सबक": "lesson",
    "मुख्य": "key", "सीख": "lesson", "सिद्धांत": "principle",
}


def extract_keywords(text: str, lang: str = "en", max_kw: int = 3) -> str:
    """
    Extract Pixabay-friendly English search keywords from *text*.

    For Hindi/Hinglish text:
      1. Known Hindi content words → mapped to English via _HI_TO_EN.
      2. English words already in the text are kept as-is.
      3. Pure Devanagari words not in the map are dropped (Pixabay responds
         poorly to Devanagari queries).

    Returns a short English query string (2–4 words).
    """
    words = re.split(r"[\s,।,;:!?()\[\]{}\"\'/\\]+", text)
    keywords: list[str] = []
    seen: set[str] = set()

    for w in words:
        w = w.strip().rstrip(".?!,;:")
        if len(w) < 3:
            continue

        # Is it a Devanagari word?
        if any("\u0900" <= c <= "\u097F" for c in w):
            if w in _HI_STOPS:
                continue                      # skip heading/stop words
            mapped = _HI_TO_EN.get(w)
            if mapped and mapped not in seen:
                keywords.append(mapped)
                seen.add(mapped)
        else:
            # Latin word — keep if not a stop word
            lw = w.lower()
            if lw not in _EN_STOPS and lw not in seen and len(lw) > 3:
                keywords.append(lw)
                seen.add(lw)

        if len(keywords) >= max_kw:
            break

    # If nothing found, use first few Latin words from title
    if not keywords:
        for w in words:
            lw = w.strip().lower()
            if lw and all(c.isascii() for c in lw) and lw not in _EN_STOPS and len(lw) > 3:
                keywords.append(lw)
                if len(keywords) >= 2:
                    break

    return " ".join(keywords[:max_kw]) if keywords else "nature landscape"


# ── Chapter-level keyword plan ────────────────────────────────────────────────

def _build_query_plan(chunks: list[dict], lang: str, images_per_query: int) -> list[dict]:
    """
    Build a list of {query, chapter_num, count} dicts — one per unique chapter.
    Story mode (no chapter_num) gets one plan entry per ~20 narration chunks.
    """
    plan: list[dict] = []
    seen_chapters: set = set()

    # Ebook mode: one query per chapter, keywords from chapter title + first narration
    if any(c.get("chunk_type") == "chapter_card" for c in chunks):
        chapter_texts: dict[int, list[str]] = {}
        for c in chunks:
            cn = c.get("chapter_num", 0)
            if cn not in chapter_texts:
                chapter_texts[cn] = []
            t = c.get("display_text") or c.get("text", "")
            chapter_texts[cn].append(t)

        for cn, texts in sorted(chapter_texts.items()):
            combined = " ".join(texts[:4])   # title + first few lines
            query    = extract_keywords(combined, lang=lang, max_kw=3)
            if cn not in seen_chapters:
                plan.append({"query": query, "chapter_num": cn,
                             "count": images_per_query})
                seen_chapters.add(cn)
    else:
        # Story mode: bucket every 20 narration chunks into one query
        bucket_size = 20
        for i in range(0, len(chunks), bucket_size):
            bucket = chunks[i : i + bucket_size]
            combined = " ".join(c.get("text", "") for c in bucket[:5])
            query    = extract_keywords(combined, lang=lang, max_kw=3)
            plan.append({"query": query, "chapter_num": i // bucket_size,
                         "count": images_per_query})

    return plan


# ── Main entry point ──────────────────────────────────────────────────────────

def _load_cache_fallback(cache_dir: str, video_w: int, video_h: int) -> list[str]:
    """
    Return all already-resized JPEG images from cache_dir.
    Used when the API is unavailable so existing cached images are not wasted.
    Images are returned in filename order (consistent across runs).
    """
    if not os.path.isdir(cache_dir):
        return []
    paths = sorted(
        str(p) for p in Path(cache_dir).glob("*.jpg")
        if p.stat().st_size > 1024  # skip corrupt/empty stubs
    )
    log.info("Pixabay cache fallback: found %d images in %s", len(paths), cache_dir)
    return paths


def download_images_for_chunks(
    chunks: list[dict],
    cfg,
    video_w: int,
    video_h: int,
) -> list[str]:
    """
    Download Pixabay images relevant to the story/ebook content.

    Returns a list of local file paths (already resized to video dimensions),
    ordered so that images for chapter N come before chapter N+1.

    On error (bad API key, no network, etc.) returns [] so the caller can
    fall back to gradient mode gracefully.
    """
    api_key = getattr(cfg, "PIXABAY_API_KEY", "").strip()
    cache_dir = getattr(cfg, "PIXABAY_CACHE_DIR", "assets/pixabay_cache")
    os.makedirs(cache_dir, exist_ok=True)

    if not api_key or api_key in ("your_key_here", "YOUR_KEY_HERE", ""):
        log.warning(
            "PIXABAY_API_KEY not set. Get a free key at https://pixabay.com/api/docs/ "
            "and add it to your config. Trying cache fallback..."
        )
        return _load_cache_fallback(cache_dir, video_w, video_h)

    lang              = getattr(cfg, "LANGUAGE", "en")
    images_per_query  = int(getattr(cfg, "PIXABAY_IMAGES_PER_QUERY", 3))
    cache_dir         = getattr(cfg, "PIXABAY_CACHE_DIR", "assets/pixabay_cache")
    orientation       = getattr(cfg, "PIXABAY_ORIENTATION", "horizontal")
    safe_search       = bool(getattr(cfg, "PIXABAY_SAFE_SEARCH", True))

    os.makedirs(cache_dir, exist_ok=True)

    plan  = _build_query_plan(chunks, lang, images_per_query)
    paths = []

    for entry in plan:
        query = entry["query"]
        count = entry["count"]
        log.info("Pixabay query [ch%s]: %r", entry["chapter_num"], query)

        hits = _api_search(query, api_key, count=count,
                           orientation=orientation, safe_search=safe_search)

        # If no results, try a shorter/simpler query
        if not hits and " " in query:
            fallback = query.split()[0]
            log.info("Retrying with shorter query: %r", fallback)
            hits = _api_search(fallback, api_key, count=count,
                               orientation=orientation, safe_search=safe_search)

        for hit in hits[:count]:
            img_url = hit.get("largeImageURL") or hit.get("webformatURL", "")
            if not img_url:
                continue

            # Cache key: hash of (query + image_id) so same query reuses files
            img_id   = str(hit.get("id", hashlib.md5(img_url.encode()).hexdigest()[:8]))
            safe_q   = re.sub(r"[^\w]", "_", query)[:30]
            filename = f"{safe_q}_{img_id}.jpg"
            dest     = os.path.join(cache_dir, filename)

            if os.path.exists(dest):
                log.info("  Cache hit: %s", filename)
                paths.append(dest)
                continue

            log.info("  Downloading: %s", img_url[:70])
            ok = _download_image(img_url, dest, video_w, video_h)
            if ok:
                paths.append(dest)
            time.sleep(0.3)   # polite delay between downloads

    log.info("Pixabay: %d images ready in %s", len(paths), cache_dir)
    if not paths:
        log.warning("Pixabay returned no images — using existing cache as fallback")
        paths = _load_cache_fallback(cache_dir, video_w, video_h)
    return paths
