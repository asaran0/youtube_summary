"""
emotion_poc/pipeline/video.py — Stage 4: Video assembly.

Takes the merged WAV + tagged sentences and produces an MP4.
Each sentence gets its own coloured slide matching its emotion.
Background music mixed in if configured.
"""

import os
import subprocess
import shutil


# Emotion → background colour (for slideshow)
_EMOTION_COLORS = {
    "CALM":    "#1B3A4B",   # deep ocean blue
    "INTENSE": "#2D0A0A",   # deep red
    "HOPEFUL": "#1A3A1A",   # forest green
    "SAD":     "#1A1A2E",   # midnight blue
    "EXCITED": "#2D1B00",   # warm dark amber
    "NEUTRAL": "#1B2A4A",   # navy
}

_EMOTION_TEXT_COLORS = {
    "CALM":    "#7FDBCA",
    "INTENSE": "#FF6B6B",
    "HOPEFUL": "#90EE90",
    "SAD":     "#B0C4DE",
    "EXCITED": "#FFD700",
    "NEUTRAL": "#F5C842",
}


def _get_audio_duration(wav_path: str) -> float:
    """Get WAV duration in seconds using wave module."""
    import wave
    with wave.open(wav_path, "r") as wf:
        return wf.getnframes() / wf.getframerate()


def _make_slideshow(
    tagged: list[dict],
    audio_path: str,
    output_path: str,
    cfg,
    temp_dir: str,
):
    """
    Generate a simple colour-background MP4 using ffmpeg.
    Each sentence gets a coloured slide.
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found. Install: brew install ffmpeg")

    total_dur  = _get_audio_duration(audio_path)
    n          = len(tagged)
    slide_dur  = total_dur / n if n else total_dur

    w, h = (1080, 1920) if getattr(cfg, "OUTPUT_MODE", "reel") == "reel" else (1920, 1080)
    fps  = getattr(cfg, "OUTPUT_FPS", 30)

    # Build ffmpeg filter_complex for coloured slides with text
    # Each slide = a solid colour + drawtext for the sentence
    inputs  = []
    filters = []

    for i, item in enumerate(tagged):
        emotion  = item["emotion"]
        bg_color = _EMOTION_COLORS.get(emotion, "#1B2A4A").lstrip("#")
        tc       = _EMOTION_TEXT_COLORS.get(emotion, "#F5C842").lstrip("#")
        text     = item["text"].replace("'", "\\'").replace(":", "\\:")
        dur      = slide_dur

        # Use ffmpeg lavfi color source
        inputs.append(f"-f lavfi -i color=0x{bg_color}:size={w}x{h}:rate={fps}:duration={dur:.3f}")
        filters.append(
            f"[{i}:v]drawtext="
            f"fontcolor=0x{tc}:"
            f"fontsize={int(h * 0.04)}:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:"
            f"text='{text}':"
            f"line_spacing=8:"
            f"font='Arial'[v{i}]"
        )

    # Concatenate all slides
    concat_inputs = "".join(f"[v{i}]" for i in range(n))
    filters.append(f"{concat_inputs}concat=n={n}:v=1:a=0[vout]")

    filter_str = ";".join(filters)
    input_args = " ".join(inputs).split()

    # Base command: video from filter_complex + audio from wav
    cmd = (
        ["ffmpeg", "-y"]
        + input_args
        + ["-i", audio_path]
        + ["-filter_complex", filter_str]
        + ["-map", "[vout]", f"-map", f"{n}:a"]
        + ["-c:v", "libx264", "-preset", "fast", "-crf", "23"]
        + ["-c:a", "aac", "-b:a", "128k"]
        + ["-shortest"]
        + [output_path]
    )

    print(f"[video] rendering {n} slides → {output_path}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Fallback: single coloured slide with no text (ffmpeg drawtext may fail on some builds)
        print("[video] drawtext failed — falling back to plain colour slides")
        _make_slideshow_plain(tagged, audio_path, output_path, cfg)


def _make_slideshow_plain(tagged, audio_path, output_path, cfg):
    """Fallback: single background colour + audio, no text overlay."""
    w, h = (1080, 1920) if getattr(cfg, "OUTPUT_MODE", "reel") == "reel" else (1920, 1080)
    fps  = getattr(cfg, "OUTPUT_FPS", 30)

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=0x1B2A4A:size={w}x{h}:rate={fps}",
        "-i", audio_path,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest", output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def _mix_background_music(video_path: str, music_path: str, volume: float, output_path: str):
    """Mix background music into the video at given volume (0.0–1.0)."""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-stream_loop", "-1", "-i", music_path,
        "-filter_complex",
        f"[0:a]volume=1.0[va];[1:a]volume={volume}[vm];[va][vm]amix=inputs=2:duration=first[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest", output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"[video] mixed background music → {output_path}")


# ── Public entry point ────────────────────────────────────────────────────────

def assemble(tagged: list[dict], audio_path: str, cfg, temp_dir: str) -> str:
    """
    Run stage 4: assemble video from tagged sentences + audio.
    Returns path to final MP4.
    """
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)
    backend = getattr(cfg, "VIDEO_BACKEND", "slideshow").lower()

    content_type = getattr(cfg, "CONTENT_TYPE", "story")
    safe_name    = content_type.replace(" ", "_")
    video_path   = os.path.join(cfg.OUTPUT_DIR, f"{safe_name}_video.mp4")

    if backend == "none":
        print("[video] VIDEO_BACKEND=none — skipping video, audio only")
        import shutil as _sh
        final = os.path.join(cfg.OUTPUT_DIR, f"{safe_name}_audio.wav")
        _sh.copy(audio_path, final)
        return final

    if backend == "slideshow":
        raw_video = os.path.join(temp_dir, "raw_video.mp4")
        _make_slideshow(tagged, audio_path, raw_video, cfg, temp_dir)

        # Mix background music if configured
        music_path = getattr(cfg, "BACKGROUND_MUSIC_PATH", "")
        if music_path and os.path.exists(music_path):
            music_vol = getattr(cfg, "BACKGROUND_MUSIC_VOLUME", 0.12)
            _mix_background_music(raw_video, music_path, music_vol, video_path)
        else:
            import shutil as _sh
            _sh.copy(raw_video, video_path)

        print(f"[video] final video → {video_path}")
        return video_path

    raise ValueError(f"Unknown VIDEO_BACKEND: {backend!r}. Choose: slideshow | none")
