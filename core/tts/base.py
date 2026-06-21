"""
core/tts/base.py — Strategy interface every TTS backend implements.

Adding a new TTS engine in the future means: create a new file in this
folder, subclass TTSStrategy, implement synthesize_segments(), then
register it in core/tts/factory.py. Nothing else in the codebase needs
to change — that's the point of the strategy pattern here.
"""

from abc import ABC, abstractmethod


class TTSStrategy(ABC):
    """
    One TTS backend (xtts / mms / macos / future additions).

    Each mode (story_mode, qa_mode) picks a strategy independently via
    its own config's TTS_BACKEND setting — see core/tts/factory.py.

    IMPORTANT: a strategy's only job is turning text into raw audio
    samples. It must NOT insert its own pauses between segments, write
    a stitched output file, or make any timing decisions — all of that
    is owned by core/tts/pipeline.py's single timeline-building pass,
    specifically so audio content and subtitle/slideshow timestamps
    can never be computed by two different pieces of code and drift
    apart from each other.
    """

    name: str = "base"

    @abstractmethod
    def synthesize_segments(self, texts: list[str], cfg) -> list[dict]:
        """
        Generate speech for an ordered list of cleaned text segments.
        Does NOT write any file and does NOT insert pauses between
        segments — that is pipeline.py's job.

        Parameters
        ----------
        texts : cleaned, transliterated text ready to speak (one per
                segment — silent/empty segments are filtered out before
                this is called).
        cfg : the active mode config (StoryConfig or QAConfig instance)
              — gives access to TTS_BACKEND, language, voice settings,
              etc. without this module needing to know which mode is
              calling it.

        Returns
        -------
        list of dicts, one per input text (same order, same length),
        each shaped:
            {
                "samples": np.ndarray (int16, mono),
                "sample_rate": int,
                "phrases": [{"text": str, "start": float, "end": float}, ...]
            }
        If a segment fails to synthesize, return 2 seconds of silence
        for it rather than skipping it — the list length must always
        match len(texts), or downstream timing will misalign.
        """
        raise NotImplementedError

    def check_available(self, cfg) -> None:
        """
        Optional fail-fast dependency/config check. Raise RuntimeError
        with a clear message if this strategy can't run (missing
        package, missing voice sample, etc). Called once at startup,
        before the heavy pipeline runs, so failures surface immediately
        instead of after summarization/TTS has already started.

        Default: no extra checks.
        """
        return None
