"""voxpolymachina: bidirectional codec for text <-> base N <-> audio.

Public API:

    encode(text, base=..., mode=..., ...) -> str
    decode(code, base=...) -> str
    load_config()

Parameters left unset (sentinel _UNSET) are taken from the resolved
configuration. How the configuration is resolved depends on the
``config`` argument:

    config=None    use built-in defaults only; no file I/O
    config="auto"  read global and local config files
    config={...}   merge the given dict over built-in defaults

Audio layer lives in voxpolymachina.audio:

    audio_encode(text, path=..., style=...) -> None
    audio_decode(path, ..., style=...) -> str
"""
from __future__ import annotations

import copy
from typing import Any

from .basecodec import CHUNK_BITS, base_to_bits, bits_to_base
from .config import DEFAULTS, deep_merge, load_config
from .header import build_header, parse_header, verify_header
from .unicode_bits import bits_to_text, text_to_bits

from ._sentinel import _UNSET, _UnsetType, _resolve_config

__version__ = "0.5.1"
__all__ = ["encode", "decode", "load_config", "__version__"]


def encode(
    text: str,
    base: int | _UnsetType = _UNSET,
    mode: str | _UnsetType = _UNSET,
    block_size: int | _UnsetType = _UNSET,
    normalization: str | None | _UnsetType = _UNSET,
    has_hash: bool = False,
    config: Any = None,
) -> str:
    """Encode text into a base-N string.

    Unset keyword arguments are filled from the resolved configuration.
    """
    cfg = _resolve_config(config)

    if isinstance(base, _UnsetType):
        base = cfg["base"]["default_base"]
    if isinstance(mode, _UnsetType):
        mode = cfg["text"]["mode"]
    if isinstance(block_size, _UnsetType):
        block_size = cfg["text"]["block_size"]
    if isinstance(normalization, _UnsetType):
        normalization = cfg["text"]["normalization"]

    payload = text_to_bits(
        text,
        mode=mode,
        block_size=block_size,
        normalization=normalization,
    )
    header = build_header(
        mode=mode,
        block_size=block_size,
        payload_bits_str=payload,
        has_hash=has_hash,
    )
    combined = header.to_bits() + payload
    return bits_to_base(combined, base)


def decode(
    code: str,
    base: int | _UnsetType = _UNSET,
    config: Any = None,
) -> str:
    """Decode a base-N string produced by encode().

    The base must be supplied by the caller (or taken from config). It is
    not stored in the header, because the header itself has to be decoded
    before we could read it, which would be circular.
    """
    cfg = _resolve_config(config)
    if isinstance(base, _UnsetType):
        base = cfg["base"]["default_base"]

    combined = base_to_bits(code, base)

    header, consumed = parse_header(combined)
    payload_end = consumed + header.payload_bits
    if payload_end > len(combined):
        raise ValueError("payload_bits exceeds available data")
    if len(combined) - payload_end >= CHUNK_BITS:
        raise ValueError("trailing data after payload (malformed or tampered string)")

    payload = combined[consumed:payload_end]
    verify_header(header, payload)
    return bits_to_text(payload, mode=header.mode)