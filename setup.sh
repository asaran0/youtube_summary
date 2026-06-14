#!/bin/bash
# setup.sh — One-time setup for Hindi YouTube Video Summarizer
# Run once before using the project:   bash setup.sh

set -e   # exit on any error

echo ""
echo "══════════════════════════════════════════════════════"
echo "   Hindi YouTube Video Summarizer — Setup"
echo "══════════════════════════════════════════════════════"
echo ""

# ── 1. Check macOS / Homebrew ────────────────────────────────
if ! command -v brew &>/dev/null; then
    echo "❌  Homebrew not found."
    echo "    Install it from https://brew.sh and re-run setup.sh"
    exit 1
fi
echo "✅  Homebrew found"

# ── 2. Install ffmpeg ────────────────────────────────────────
if ! command -v ffmpeg &>/dev/null; then
    echo "📦  Installing ffmpeg …"
    brew install ffmpeg
else
    echo "✅  ffmpeg already installed"
fi

# ── 3. Upgrade pip ───────────────────────────────────────────
echo ""
echo "📦  Upgrading pip …"
# python3 -m pip install --upgrade pip --break-system-packages

# ── 4. Install Python packages ───────────────────────────────
echo ""
echo "📦  Installing Python dependencies …"
pip install -r requirements.txt

# ── 5. Download Hindi font ───────────────────────────────────
echo ""
echo "📦  Downloading Noto Sans Devanagari font (Hindi) …"
mkdir -p assets

FONT_URL="https://fonts.gstatic.com/s/notosansdevanagari/v26/TuGoUUFzXI5FBtUq5a8bjKYTZjtgoo_U62T5BDE.ttf"
FONT_PATH="assets/NotoSansDevanagari-Regular.ttf"

if [ -f "$FONT_PATH" ]; then
    echo "✅  Font already downloaded"
else
    if curl -L --silent --output "$FONT_PATH" "$FONT_URL"; then
        # Verify the download is a real font file (> 10 KB)
        SIZE=$(wc -c < "$FONT_PATH")
        if [ "$SIZE" -gt 10000 ]; then
            echo "✅  Font downloaded → $FONT_PATH"
        else
            rm -f "$FONT_PATH"
            echo "⚠️   Font download may have failed (file too small)."
            echo "     Try manually: copy any Devanagari .ttf to assets/"
        fi
    else
        echo "⚠️   Could not download font. You can continue but banners/subtitles"
        echo "     may fall back to a system font."
    fi
fi

# ── 6. Create output / temp directories ─────────────────────
mkdir -p output temp
echo "✅  output/ and temp/ directories ready"

# ── 7. Quick smoke test ──────────────────────────────────────
echo ""
echo "🔍  Running quick import test …"
python -c "
import yt_dlp, whisper, moviepy, PIL, numpy, torch
print('  yt-dlp  ✓')
print('  whisper ✓')
print('  moviepy ✓')
print('  Pillow  ✓')
print('  numpy   ✓')
print('  torch   ✓  (device:', 'mps' if torch.backends.mps.is_available() else 'cpu', ')')
print()
print('All imports OK ✅')
"

echo ""
echo "══════════════════════════════════════════════════════"
echo "   Setup complete! 🎉"
echo ""
echo "   Run the summarizer:"
echo "   python main.py <youtube_url>"
echo ""
echo "   Example:"
echo "   python main.py https://youtu.be/YOUR_VIDEO_ID"
echo "══════════════════════════════════════════════════════"
echo ""
