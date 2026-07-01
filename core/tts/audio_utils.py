"""
core/tts/audio_utils.py — Shared audio helpers used by every TTS strategy.

None of this is backend-specific: resampling, loudness/EQ polishing, and
WAV concatenation are needed identically whether the audio came from
XTTS, MMS, or macOS 'say'. Keeping it here means a fix or improvement
(e.g. a better loudness filter) benefits all three strategies at once.
"""

import os
import subprocess
import wave

import numpy as np

from utils import get_logger

log = get_logger("tts.audio")


def fade_chunk_edges(audio: np.ndarray, sample_rate: int, fade_ms: float = 12.0) -> np.ndarray:
    """
    Apply a short linear fade-in/fade-out to a single audio chunk.

    Why this exists: TTS pipelines that auto-split long text into several
    model calls (e.g. Kokoro's KPipeline splitting on sentence boundaries)
    hand back a separate waveform per chunk. Each chunk starts/ends at
    whatever amplitude the model happened to produce — almost never zero,
    almost never matching the next chunk's starting amplitude. Concatenating
    them raw creates a sample-to-sample discontinuity, which is heard as a
    sharp click/pop right at the seam (i.e. right after whatever word ended
    the chunk). A few milliseconds of fade at each edge removes the jump
    without being audible as an actual fade.

    Safe to call on any chunk regardless of backend — short chunks (under
    2x fade_ms) are returned unchanged rather than risking a fade that
    eats the whole clip.
    """
    n = int(sample_rate * fade_ms / 1000)
    if n <= 0 or len(audio) <= n * 2:
        return audio
    audio = audio.astype(np.float32, copy=True) if audio.dtype != np.float32 else audio.copy()
    fade = np.linspace(0.0, 1.0, n, dtype=np.float32)
    audio[:n] *= fade
    audio[-n:] *= fade[::-1]
    return audio


def smooth_concatenate(
    chunks: list[np.ndarray],
    sample_rate: int,
    fade_ms: float = 12.0,
    gap_ms: float = 25.0,
) -> np.ndarray:
    """
    Concatenate multiple raw float waveform chunks from a TTS model into
    one continuous waveform, without the click/pop that a plain
    np.concatenate produces at each chunk boundary.

    Used whenever a single TTS strategy call returns more than one chunk
    for a single piece of text (Kokoro's internal sentence splitting is
    the main case today, but this is generic — any future backend with
    the same behavior should reuse it rather than re-solving this).

    fade_ms : per-chunk edge fade, see fade_chunk_edges().
    gap_ms  : tiny silence inserted between chunks so the fades have room
              to land on true zero rather than meeting mid-fade. 20-30ms
              is short enough to be inaudible as a "pause" but long
              enough to fully kill the seam.
    """
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    if len(chunks) == 1:
        return np.asarray(chunks[0], dtype=np.float32)

    gap = np.zeros(int(sample_rate * gap_ms / 1000), dtype=np.float32)
    parts: list[np.ndarray] = []
    for i, chunk in enumerate(chunks):
        faded = fade_chunk_edges(np.asarray(chunk, dtype=np.float32), sample_rate, fade_ms)
        parts.append(faded)
        if i < len(chunks) - 1:
            parts.append(gap)
    return np.concatenate(parts)


def resample_wav(input_wav: str, output_wav: str, target_rate: int = 44100) -> None:
    """Resample a WAV file to target_rate Hz using ffmpeg."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", input_wav,
         "-ar", str(target_rate), "-ac", "1", output_wav],
        check=True, capture_output=True,
    )


def polish_audio(input_wav: str, output_wav: str, cfg) -> None:
    """
    Apply light cleanup, compression and loudness normalization.

    cfg must provide AUDIO_POST_PROCESSING (bool) and AUDIO_FILTER
    (ffmpeg -af filter string) — both come from the active mode config.
    """
    # Core-level declick/anti-pop pass — applied unconditionally, ahead of
    # whatever the mode's own AUDIO_FILTER does. This exists as a safety
    # net for the residual clicks/pops that chunked-TTS backends can leave
    # at synthesis boundaries (see smooth_concatenate() above for the fix
    # at the source; this catches anything that still gets through, and
    # protects backends that don't go through smooth_concatenate at all).
    # adeclick targets short transient clicks; adeclip catches harder clips.
    # Cheap, voice content is unaffected — this is intentionally part of
    # core so QA mode and Story mode get it identically without either
    # mode config needing to know about it.
    declick = "adeclick=window=55:overlap=75:arorder=2:threshold=2,adeclip=window=55:overlap=75:arorder=8:threshold=10"

    if not cfg.AUDIO_POST_PROCESSING:
        cmd = ["ffmpeg", "-y", "-i", input_wav, "-af", declick, output_wav]
        subprocess.run(cmd, check=True, capture_output=True)
        return

    cmd = [
        "ffmpeg", "-y",
        "-i", input_wav,
        "-af", f"{declick},{cfg.AUDIO_FILTER}",
        "-ar", "44100",
        "-ac", "1",
        output_wav,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def normalize_and_write_wav(audio_segments: list[np.ndarray], sample_rate: int, tmp_wav_path: str) -> None:
    """
    Concatenate float32 audio segments (already including any pauses
    the caller inserted), normalize to avoid clipping, and write as a
    16-bit PCM WAV file. Used by xtts and mms strategies, whose models
    return raw float waveforms directly.
    """
    if not audio_segments:
        raise RuntimeError("No audio segments to write — TTS produced no output")

    import scipy.io.wavfile as wavfile

    combined = np.concatenate(audio_segments).astype(np.float32)
    max_val = np.max(np.abs(combined))
    if max_val > 0:
        combined = combined / max_val * 0.85

    combined_int16 = (combined * 32767).astype(np.int16)
    wavfile.write(tmp_wav_path, sample_rate, combined_int16)


def concat_wav_clips_with_pauses(
    clip_paths: list[str],
    pause_after: list[float],
    output_path: str,
    sample_rate: int,
) -> None:
    """
    Concatenate mono 16-bit WAV clips with a per-clip pause duration
    after each one. Used by the macOS strategy, which produces one WAV
    file per spoken phrase via the 'say' command.
    """
    audio_parts = []
    for path, pause_sec in zip(clip_paths, pause_after):
        with wave.open(path, "rb") as wav:
            frames = wav.readframes(wav.getnframes())
            data = np.frombuffer(frames, dtype=np.int16)
        audio_parts.append(data)
        if pause_sec > 0:
            audio_parts.append(np.zeros(int(sample_rate * pause_sec), dtype=np.int16))

    combined = np.concatenate(audio_parts) if audio_parts else np.zeros(1, dtype=np.int16)
    with wave.open(output_path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(combined.tobytes())


def get_wav_duration(filepath: str) -> float:
    """Return duration of a WAV file in seconds."""
    with wave.open(filepath, "rb") as wav:
        frames = wav.getnframes()
        rate = wav.getframerate()
        return frames / float(rate) if rate else 0.0


def add_background_music(
    voice_wav: str,
    music_path: str,
    output_wav: str,
    music_volume_db: float = -22.0,
    duck_ratio: float = 20.0,
    duck_attack_ms: int = 5,
    duck_release_ms: int = 400,
) -> None:
    """
    Mix a background music bed under a finished voice track, with the
    music automatically ducking (lowering) under speech via ffmpeg's
    sidechaincompress — this is the part that matters. Background music
    that doesn't duck just competes with the voice and makes it harder
    to listen to, not easier; ducked music sits underneath and only
    becomes noticeable in gaps/pauses.

    voice_wav        : the already-polished narration track (path).
    music_path        : background music file (mp3/wav, any length —
                         looped/trimmed to match voice_wav automatically).
    output_wav         : final mixed output path.
    music_volume_db   : base music level before ducking, relative to
                         full scale. -22dB is a safe "bed" level — audible
                         in silence, clearly secondary once ducked further
                         under speech. Raise toward -16 for a more present
                         bed, lower toward -28 for very subtle texture.
    duck_ratio        : sidechain compression ratio applied to the music
                         while voice is present. Higher = music drops more
                         aggressively under speech. 20 is a strong, clearly
                         audible duck; lower toward 4-8 for a gentler one.
    duck_attack_ms / duck_release_ms : how fast the duck kicks in/releases.
                         Fast attack (5ms) so music doesn't "leak" over the
                         first syllable of each sentence; slower release
                         (400ms) so it doesn't pump audibly between words.
    """
    voice_dur = get_wav_duration(voice_wav)

    # sidechaincompress needs two inputs: [0] = music (gets compressed),
    # [1] = voice (the sidechain trigger). amix at the end blends the
    # ducked music back in with the original voice.
    filter_complex = (
        f"[0:a]volume={music_volume_db}dB,aloop=loop=-1:size=2e9,"
        f"atrim=0:{voice_dur},asetpts=PTS-STARTPTS[music];"
        f"[music][1:a]sidechaincompress="
        f"threshold=0.02:ratio={duck_ratio}:attack={duck_attack_ms}:release={duck_release_ms}:"
        f"makeup=1[ducked];"
        f"[1:a][ducked]amix=inputs=2:duration=first:dropout_transition=0:weights=1 1[out]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", music_path,
        "-i", voice_wav,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-ar", "44100",
        "-ac", "1",
        output_wav,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
