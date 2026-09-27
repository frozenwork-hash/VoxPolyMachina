"""Internal sentinel and config resolution.

Lives in its own module so `__init__.py` and `audio/codec.py` can both
import it without a circular dependency.
"""
from __future__ import annotations

import copy
from typing import Any

from .config import DEFAULTS, deep_merge, load_config


class _UnsetType:
    """Sentinel type: distinguishes 'not provided' from an explicit None."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "_UNSET"


_UNSET = _UnsetType()


def _resolve_config(config: Any) -> dict:
    """Return the effective config dict for this call."""
    if config is None:
        return copy.deepcopy(DEFAULTS)
    if isinstance(config, str):
        if config == "auto":
            return load_config()
        raise TypeError(f"config string must be 'auto', got {config!r}")
    if isinstance(config, dict):
        return deep_merge(copy.deepcopy(DEFAULTS), config)
    raise TypeError(
        f"config must be None, 'auto', or a dict; got {type(config).__name__}"
    )