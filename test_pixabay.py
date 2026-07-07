#!/usr/bin/env python3
"""
test_pixabay.py — Run this to diagnose Pixabay issues before making a video.

Usage:
    python3 test_pixabay.py                         # uses key from config
    python3 test_pixabay.py YOUR_API_KEY_HERE       # test a specific key
    python3 test_pixabay.py --query "rich money"    # test a specific query
python3 test_pixabay.py "8DRN6mB3iaPHTQO6mlPM5d9P2lt9l8l3SKGNVqpcn1wfJ3XvmX1UR23c"
What it checks:
  1. Whether PIXABAY_API_KEY is set in ebook_mode/config.py
  2. Network connectivity to pixabay.com
  3. That a sample search returns results
  4. That an image can be downloaded and resized
  5. Shows the query plan for Rich Dad Poor Dad example
"""

import sys
import os
import logging
import argparse

# So we can run from the project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("test_pixabay")


def main():
    parser = argparse.ArgumentParser(description="Test Pixabay integration")
    parser.add_argument("api_key", nargs="?", help="Pixabay API key to test")
    parser.add_argument("--query", default="money wealth success", help="Search query to test")
    parser.add_argument("--download", action="store_true", help="Also download a test image")
    args = parser.parse_args()

    print("\n" + "═"*60)
    print("  Pixabay Integration Diagnostics")
    print("═"*60)

    # ── 1. Check config ────────────────────────────────────────────
    print("\n[1] Checking config...")
    try:
        from ebook_mode import config as cfg
        cfg_key = getattr(cfg, "PIXABAY_API_KEY", "")
        cfg_mode = getattr(cfg, "STORY_BG_MODE", "gradient")
        cfg_dir  = getattr(cfg, "PIXABAY_CACHE_DIR", "assets/pixabay_cache")
        print(f"    STORY_BG_MODE     = {cfg_mode!r}")
        print(f"    PIXABAY_API_KEY   = {'*** SET (length=' + str(len(cfg_key)) + ')' if cfg_key and cfg_key not in ('your_key_here','') else '❌ NOT SET'}")
        print(f"    PIXABAY_CACHE_DIR = {cfg_dir!r}  (exists={os.path.isdir(cfg_dir)})")
        if cfg_mode != "pixabay":
            print(f"    ⚠️  STORY_BG_MODE is {cfg_mode!r} not 'pixabay' — Pixabay won't be used!")
    except ImportError as e:
        print(f"    ⚠️  Could not import ebook_mode.config: {e}")
        cfg_key = ""

    # API key priority: CLI arg > config > env var
    api_key = (args.api_key or cfg_key or
               os.environ.get("PIXABAY_API_KEY", "")).strip()

    if not api_key or api_key in ("your_key_here", "YOUR_KEY_HERE"):
        print("\n❌  No valid API key found.")
        print("   Get a free key at https://pixabay.com/api/docs/")
        print("   Then add to ebook_mode/config.py:")
        print("     PIXABAY_API_KEY = 'your_actual_key_here'")
        sys.exit(1)

    print(f"\n    Using key: {'*'*(len(api_key)-4)}{api_key[-4:]}")

    # ── 2. Network connectivity ────────────────────────────────────
    print("\n[2] Testing network connectivity to pixabay.com...")
    import urllib.request
    try:
        req = urllib.request.Request(
            "https://pixabay.com/",
            headers={"User-Agent": "VideoBot/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            print(f"    ✅  pixabay.com reachable (HTTP {r.status})")
    except Exception as e:
        print(f"    ❌  Cannot reach pixabay.com: {e}")
        print("    → Your server may block outbound HTTP.")
        print("    → Set STORY_BG_MODE='image' and put images manually in assets/pixabay_cache/")
        sys.exit(1)

    # ── 3. API search ──────────────────────────────────────────────
    print(f"\n[3] Testing API search: {args.query!r}")
    from core.pixabay import _api_search
    hits = _api_search(args.query, api_key, count=3)
    if not hits:
        print("    ❌  Search returned 0 results. See errors above.")
        sys.exit(1)
    print(f"    ✅  Got {len(hits)} results:")
    for h in hits[:3]:
        print(f"       id={h['id']}  "
              f"size={h.get('imageWidth','?')}×{h.get('imageHeight','?')}  "
              f"tags={h.get('tags','')[:50]}")

    # ── 4. Image download ──────────────────────────────────────────
    if args.download or True:   # always test download
        print("\n[4] Testing image download and resize...")
        import tempfile
        from core.pixabay import _download_image
        from PIL import Image

        test_url = hits[0].get("largeImageURL") or hits[0].get("webformatURL","")
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
            tmp = tf.name

        ok = _download_image(test_url, tmp, 1920, 1080)
        if ok and os.path.exists(tmp):
            img = Image.open(tmp)
            size_kb = os.path.getsize(tmp) // 1024
            print(f"    ✅  Downloaded, resized to {img.size}, {size_kb}KB")
            os.unlink(tmp)
        else:
            print("    ❌  Image download failed. See errors above.")
            sys.exit(1)

    # ── 5. Query plan for sample ebook ────────────────────────────
    print("\n[5] Sample query plan (Rich Dad Poor Dad)...")
    try:
        from core.pixabay import _build_query_plan, extract_keywords
        sample_chunks = [
            {"chunk_type":"chapter_card","chapter_num":1,"text":"Rich Dad Poor Dad",
             "display_text":"Rich Dad, Poor Dad"},
            {"chunk_type":"narration","chapter_num":1,
             "text":"The rich don't work for money they make money work for them"},
            {"chunk_type":"chapter_card","chapter_num":2,"text":"The Rich Don't Work for Money",
             "display_text":"The Rich Don't Work for Money"},
        ]
        plan = _build_query_plan(sample_chunks, lang="en", images_per_query=3)
        for p in plan:
            print(f"    ch{p['chapter_num']} → {p['query']!r}  (×{p['count']} images)")
    except Exception as e:
        print(f"    ⚠️  Query plan test skipped: {e}")

    # ── Summary ────────────────────────────────────────────────────
    print("\n" + "═"*60)
    print("  ✅  All checks passed! Pixabay is ready.")
    print("═"*60)
    print("\nMake sure your config has:")
    print("  STORY_BG_MODE    = 'pixabay'")
    print(f"  PIXABAY_API_KEY  = '{api_key[:4]}...'")
    print()


if __name__ == "__main__":
    main()
