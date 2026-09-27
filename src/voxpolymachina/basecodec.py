"""Bit stream <-> base N string conversions.

The bit stream (header + payload) is split into fixed-size chunks of
CHUNK_BITS bits. Each chunk is treated as a big-endian integer and
converted to base N. All chunks use the same digit width W, where W is
the smallest integer such that base^W >= 2^CHUNK_BITS.

If the total bit length is not a multiple of CHUNK_BITS, the last chunk
is zero-padded on the right. The decoder relies on the header to know
exactly how many payload bits to keep.

Digit width examples for CHUNK_BITS = 32:
    base  2 -> 32 digits
    base  3 -> 21 digits
    base  5 -> 14 digits
    base 10 -> 10 digits
    base 16 ->  8 digits
    base 36 ->  7 digits
"""
from __future__ import annotations

CHUNK_BITS = 32

# Fixed 36-character alphabet: 0-9 then A-Z.
# For base N only the first N characters are used.
ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _digits_for_base(base: int) -> str:
    if not 2 <= base <= 36:
        raise ValueError(f"base must be in 2..36, got {base}")
    return ALPHABET[:base]


def _width_for(base: int) -> int:
    """Smallest W such that base^W >= 2^CHUNK_BITS."""
    limit = 1 << CHUNK_BITS
    w = 1
    while base ** w < limit:
        w += 1
    return w


def _int_to_base(value: int, base: int, width: int, digits: str) -> str:
    if value == 0:
        return digits[0] * width
    out = []
    v = value
    while v:
        v, rem = divmod(v, base)
        out.append(digits[rem])
    s = "".join(reversed(out))
    if len(s) > width:
        raise ValueError(
            f"value {value} does not fit in {width} digits of base {base}"
        )
    return s.rjust(width, digits[0])


def _base_to_int(s: str, base: int, digits: str) -> int:
    value = 0
    for ch in s:
        idx = digits.find(ch)
        if idx < 0:
            raise ValueError(f"character {ch!r} is not valid in base {base}")
        value = value * base + idx
    return value


def bits_to_base(bits: str, base: int) -> str:
    """Encode a bit string as a string in the given base."""
    digits = _digits_for_base(base)
    width = _width_for(base)

    pad = (-len(bits)) % CHUNK_BITS
    padded = bits + "0" * pad

    out = []
    for i in range(0, len(padded), CHUNK_BITS):
        chunk = int(padded[i:i + CHUNK_BITS], 2)
        out.append(_int_to_base(chunk, base, width, digits))
    return "".join(out)


def base_to_bits(s: str, base: int) -> str:
    """Decode a base-N string into a bit string.

    The returned bit string has a length that is a multiple of CHUNK_BITS.
    Trailing padding is left in place; the caller should slice it away
    using payload_bits from the header.
    """
    digits = _digits_for_base(base)
    width = _width_for(base)

    if len(s) % width != 0:
        raise ValueError(
            f"string length {len(s)} is not a multiple of {width} "
            f"(digit width for base {base})"
        )

    out = []
    for i in range(0, len(s), width):
        value = _base_to_int(s[i:i + width], base, digits)
        if value >= (1 << CHUNK_BITS):
            raise ValueError(
                f"chunk value {value} does not fit in {CHUNK_BITS} bits"
            )
        out.append(format(value, f"0{CHUNK_BITS}b"))
    return "".join(out)