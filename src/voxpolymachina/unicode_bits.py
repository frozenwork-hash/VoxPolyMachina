"""Text <-> bit stream conversions.

Modes:
    codepoint21: every Unicode code point is stored as exactly 21 bits.
        Universal, fixed-size, works for any language and emoji.
        End of payload is marked with TERMINATOR (0x110000), which is
        not a valid Unicode code point and must be the last code point.

    utf8: reserved for a later release.
    ascii7: reserved for a later release.

Surrogate code points (U+D800..U+DFFF) are rejected on both encode and
decode. They are not valid Unicode scalar values and cannot be round-
tripped safely. Support may return in a future format version with an
explicit header flag.
"""
from __future__ import annotations

import unicodedata

BITS_PER_CODEPOINT = 21
MAX_CODEPOINT = 0x10FFFF
SURROGATE_START = 0xD800
SURROGATE_END = 0xDFFF
TERMINATOR = 0x110000  # one past the highest valid code point


def _normalize(text: str, mode: str | None) -> str:
    return unicodedata.normalize(mode, text) if mode else text


def _is_surrogate(cp: int) -> bool:
    return SURROGATE_START <= cp <= SURROGATE_END


def text_to_bits(
    text: str,
    mode: str = "codepoint21",
    block_size: int = 1,
    normalization: str | None = None,
) -> str:
    """Convert text to a bit string.

    The result includes the terminator and, in codepoint21 mode, is always
    a multiple of BITS_PER_CODEPOINT.

    block_size is validated and recorded in the header, but in v1 it does
    not change the bit layout. Blocks of 2 or 4 code points are simply
    concatenated; the decoder uses block_size to reproduce the user's
    choice for future versions or for audio timing.
    """
    if block_size not in (1, 2, 4):
        raise ValueError(f"unsupported block_size: {block_size}")

    text = _normalize(text, normalization)

    if mode == "codepoint21":
        return _codepoint21_to_bits(text)
    if mode == "utf8":
        raise NotImplementedError("utf8 mode is planned for a later release")
    if mode == "ascii7":
        raise NotImplementedError("ascii7 mode is planned for a later release")
    raise ValueError(f"unknown mode: {mode}")


def bits_to_text(bits: str, mode: str = "codepoint21") -> str:
    if mode == "codepoint21":
        return _codepoint21_from_bits(bits)
    if mode == "utf8":
        raise NotImplementedError("utf8 mode is planned for a later release")
    if mode == "ascii7":
        raise NotImplementedError("ascii7 mode is planned for a later release")
    raise ValueError(f"unknown mode: {mode}")


def _codepoint21_to_bits(text: str) -> str:
    parts = []
    for ch in text:
        cp = ord(ch)
        if cp > MAX_CODEPOINT:
            raise ValueError(f"invalid code point: U+{cp:04X}")
        if _is_surrogate(cp):
            raise ValueError(
                f"surrogate code point U+{cp:04X} is not allowed "
                "(not a valid Unicode scalar value)"
            )
        parts.append(format(cp, "021b"))
    parts.append(format(TERMINATOR, "021b"))
    return "".join(parts)


def _codepoint21_from_bits(bits: str) -> str:
    if len(bits) % BITS_PER_CODEPOINT != 0:
        raise ValueError(
            f"bit length {len(bits)} is not a multiple of {BITS_PER_CODEPOINT}"
        )

    chars: list[str] = []
    saw_terminator = False

    for i in range(0, len(bits), BITS_PER_CODEPOINT):
        cp = int(bits[i:i + BITS_PER_CODEPOINT], 2)

        if cp == TERMINATOR:
            if saw_terminator:
                raise ValueError("multiple terminators in payload")
            saw_terminator = True
            continue

        if saw_terminator:
            raise ValueError(
                f"data after terminator: 0x{cp:X} "
                "(malformed or tampered payload)"
            )

        if cp > MAX_CODEPOINT:
            raise ValueError(f"invalid code point in stream: 0x{cp:X}")
        if _is_surrogate(cp):
            raise ValueError(
                f"surrogate code point U+{cp:04X} in stream; "
                "not a valid Unicode scalar value"
            )
        chars.append(chr(cp))

    if not saw_terminator:
        raise ValueError("terminator not found in payload")

    return "".join(chars)