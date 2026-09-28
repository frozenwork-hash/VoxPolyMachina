"""Configuration management for voxpolymachina.

The configuration is stored as JSON. It is auto-generated on first use
and can be overridden by a local file or an explicit path.

Precedence (lowest to highest):
    1. Built-in defaults
    2. Global config file (auto-created)
    3. Local config file in the current directory
    4. Explicit config path passed by the caller
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "version": 1,
    "text": {
        "mode": "codepoint21",
        "block_size": 1,
        "normalization": None,
    },
    "base": {
        "default_base": 2,
    },
    "audio": {
        "sample_rate": 44100,
        "symbol_ms": 50,
        "fade_ms": 5,
        "waveform": "sine",
        "amplitude": 0.6,
        "f_min": 500,
        "f_max": 5000,
        "frequencies": None,
        "auto_range": True,
        "preamble_mode": "trill",
        "custom_preamble": None,
        "base": 4,
        "preamble_repeats": 6,
        "effects": [],
    },
}


def _global_config_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "voxpolymachina" / "config.json"


def _local_config_path() -> Path:
    return Path.cwd() / "voxpolymachina.json"


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict.

    Neither input is mutated. Leaf values from override are deep-copied
    so that later changes to the caller's dict do not affect the result.
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def ensure_global_config() -> Path:
    """Create the global config with defaults if it does not exist."""
    path = _global_config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(DEFAULTS, indent=2), encoding="utf-8")
    return path


def load_config(explicit: str | Path | None = None) -> dict:
    cfg = copy.deepcopy(DEFAULTS)

    global_path = ensure_global_config()
    if global_path.exists():
        cfg = deep_merge(cfg, json.loads(global_path.read_text(encoding="utf-8")))

    local_path = _local_config_path()
    if local_path.exists():
        cfg = deep_merge(cfg, json.loads(local_path.read_text(encoding="utf-8")))

    if explicit is not None:
        cfg = deep_merge(cfg, json.loads(Path(explicit).read_text(encoding="utf-8")))

    return cfg