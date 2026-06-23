"""
api/config_utils.py — Safe per-job config handling.

qa_mode/config.py and story_mode/config.py are plain modules. The existing
CLI mutates module attributes directly (main.py:_apply_overrides), which is
fine for a one-shot CLI process but unsafe for a long-running API process
serving multiple jobs: overrides from job A would leak into job B.

We snapshot each config module's original attribute values once at import
time, and before every job we restore those values, then apply that job's
overrides on top. Jobs are also run one-at-a-time (see jobs.py) so this
restore/apply/run sequence is never interleaved.
"""

from __future__ import annotations

import logging
from types import ModuleType


def snapshot(cfg_module: ModuleType) -> dict:
    """Capture plain (non-callable, non-dunder) attributes of a config module."""
    return {
        k: v for k, v in vars(cfg_module).items()
        if not k.startswith("__") and not callable(v) and not isinstance(v, ModuleType)
    }


def restore(cfg_module: ModuleType, snap: dict) -> None:
    for k, v in snap.items():
        setattr(cfg_module, k, v)


def apply_overrides(cfg_module: ModuleType, overrides: dict) -> None:
    """
    Apply a dict of overrides onto a config module. Keys are matched
    case-insensitively against the module's UPPERCASE settings
    (e.g. {"language": "hi"} -> cfg.LANGUAGE = "hi").
    Unknown keys are ignored with a warning rather than raising, so a typo
    in a request body doesn't silently corrupt unrelated state.
    """
    log = logging.getLogger("api.config")
    for key, value in overrides.items():
        if value is None:
            continue
        attr = key.upper()
        if hasattr(cfg_module, attr):
            setattr(cfg_module, attr, value)
        else:
            log.warning("Ignoring unknown config override: %s", key)
