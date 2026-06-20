"""
core/tts/factory.py — Strategy registry and selector.

To add a new TTS backend in the future:
  1. Create core/tts/your_strategy.py, subclass TTSStrategy from base.py
  2. Implement synthesize() (and optionally check_available())
  3. Add one line to _STRATEGIES below

Nothing else changes — story_mode and qa_mode each just set
TTS_BACKEND = "your_new_name" in their own config and it works.
"""

from core.tts.base import TTSStrategy
from core.tts.xtts_strategy import XTTSStrategy
from core.tts.mms_strategy import MMSStrategy
from core.tts.macos_strategy import MacOSStrategy

_STRATEGIES: dict[str, type[TTSStrategy]] = {
    "xtts": XTTSStrategy,
    "mms": MMSStrategy,
    "macos": MacOSStrategy,
}


def get_strategy(backend_name: str) -> TTSStrategy:
    """
    Look up and instantiate the TTS strategy for the given backend name
    (cfg.TTS_BACKEND — independently configurable per mode).
    """
    strategy_cls = _STRATEGIES.get(backend_name)
    if strategy_cls is None:
        valid = ", ".join(sorted(_STRATEGIES))
        raise ValueError(
            f"Unknown TTS_BACKEND '{backend_name}'. Choose one of: {valid}"
        )
    return strategy_cls()


def available_backends() -> list[str]:
    """List all registered backend names — used for CLI --tts-backend choices."""
    return sorted(_STRATEGIES)
