"""
core/tts/base.py — Strategy interface every TTS backend implements.

Adding a new TTS engine in the future means: create a new file in this
folder, subclass TTSStrategy, implement synthesize(), then register it
in core/tts/factory.py. Nothing else in the codebase needs to change —
that's the point of the strategy pattern here.
"""

from abc import ABC, abstractmethod


class TTSStrategy(ABC):
    """
    One TTS backend (xtts / mms / macos / future additions).

    Each mode (story_mode, qa_mode) picks a strategy independently via
    its own config's TTS_BACKEND setting — see core/tts/factory.py.
    """

    name: str = "base"

    @abstractmethod
    def synthesize(self, texts: list[str], output_path: str, cfg) -> list[dict]:
        """
        Generate speech for an ordered list of cleaned text segments,
        write the stitched result to output_path (a WAV file), and
        return per-segment timing info.

        Parameters
        ----------
        texts : cleaned, transliterated text ready to speak (one per
                segment — silent/empty segments are filtered out before
                this is called).
        output_path : where to write the final stitched WAV.
        cfg : the active mode config (StoryConfig or QAConfig instance)
              — gives access to TTS_BACKEND, pause timings, language,
              voice settings, etc. without this module needing to know
              which mode is calling it.

        Returns
        -------
        list of dicts, one per input text, each shaped:
            {"duration": float, "phrases": [{"text": str, "start": float, "end": float}, ...]}
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
