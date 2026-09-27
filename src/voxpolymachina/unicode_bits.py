"""Text <-> bit stream conversions.

Modes:
    codepoint21: every Unicode code point is stored as exactly 21 bits.
        Universal, fixed-size, works for any language and emoji.
        End of payload is marked with TERMINATOR (0x110000), which is
        not a valid Unicode code point and must be the last code point.

    utf8: text is encoded as UTF-8 bytes, 8 bits per byte. No
        terminator; the payload length comes from the header. Compact
        for Latin text (8 bits/char), reasonable for Cyrillic (16), not
        great for CJK (24). Cannot represent surrogates — str.encode()
        rejects them, which is exactly the behaviour we want.

    ascii7: text is encoded as 7 bits per ASCII code point. Only
        U+0000..U+007F are allowed. Compact for pure ASCII, and the
        only mode that beats codepoint21 by more than 2x. No terminator;
        same length story as utf8.

Surrogate code points (U+D800..U+DFFF) are rejected in every mode.
They are not valid Unicode scalar values and cannot be round-tripped
safely.
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

    The result length is determined by the mode and the input; the
    decoder recovers it from the header, so no terminator is added for
    utf8 or ascii7. codepoint21 still appends TERMINATOR for backward
    compatibility with format version 1.
    """
    if block_size not in (1, 2, 4):
        raise ValueError(f"unsupported block_size: {block_size}")

    text = _normalize(text, normalization)

    if mode == "codepoint21":
        return _codepoint21_to_bits(text)
    if mode == "utf8":
        return _utf8_to_bits(text)
    if mode == "ascii7":
        return _ascii7_to_bits(text)
    raise ValueError(f"unknown mode: {mode}")


def bits_to_text(bits: str, mode: str = "codepoint21") -> str:
    if mode == "codepoint21":
        return _codepoint21_from_bits(bits)
    if mode == "utf8":
        return _utf8_from_bits(bits)
    if mode == "ascii7":
        return _ascii7_from_bits(bits)
    raise ValueError(f"unknown mode: {mode}")


# --- codepoint21 ---


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


# --- utf8 ---


def _utf8_to_bits(text: str) -> str:
    try:
        data = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        # Happens on surrogates and any code point above U+10FFFF.
        raise ValueError(f"cannot encode text as UTF-8: {exc}") from exc
    return "".join(format(b, "08b") for b in data)


def _utf8_from_bits(bits: str) -> str:
    if len(bits) % 8 != 0:
        raise ValueError(
            f"utf8 bit length {len(bits)} is not a multiple of 8"
        )
    data = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"invalid UTF-8 in payload: {exc}") from exc


# --- ascii7 ---


def _ascii7_to_bits(text: str) -> str:
    parts = []
    for ch in text:
        cp = ord(ch)
        if cp > 0x7F:
            raise ValueError(
                f"ascii7 mode supports only U+0000..U+007F, "
                f"got U+{cp:04X} ({ch!r})"
            )
        parts.append(format(cp, "07b"))
    return "".join(parts)


def _ascii7_from_bits(bits: str) -> str:
    if len(bits) % 7 != 0:
        raise ValueError(
            f"ascii7 bit length {len(bits)} is not a multiple of 7"
        )
    chars = []
    for i in range(0, len(bits), 7):
        cp = int(bits[i:i + 7], 2)
        if cp > 0x7F:
            # 7 bits always fit in 0..127, but this guards against a
            # future change to the bit width without touching the code.
            raise ValueError(f"invalid ascii7 code point: 0x{cp:X}")
        chars.append(chr(cp))
    return "".join(chars)