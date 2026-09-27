"""Fixed-size header prepended to every encoded payload.

The header is part of the encoded bit stream. It is converted to base N
together with the payload, so the final string is homogeneous.

Field layout (MSB first):

    magic            16   constant 0x5650 ("VP")
    version           4   format version, currently 1
    mode              4   text mode id
    block_size        4   1, 2, or 4
    has_hash          1   whether sha256_prefix is present
    reserved          3   must be zero
    payload_bits     32   length of payload in bits, including terminator
    crc32            32   CRC32 over header (with crc32=0, hash=0) || payload
    sha256_prefix    64   optional, first 8 bytes of SHA-256

Without hash the header is 96 bits. With hash it is 160 bits.

CRC and hash are computed over the header with their own field zeroed,
concatenated with the payload. This avoids the chicken-and-egg problem
and lets verification run without mutating the Header object.
"""
from __future__ import annotations

import hashlib
import zlib
from dataclasses import dataclass, replace

MAGIC = 0x5650
VERSION = 1

MODE_IDS = {
    "codepoint21": 0,
    "utf8": 1,
    "ascii7": 2,
}
MODE_NAMES = {v: k for k, v in MODE_IDS.items()}

BASE_HEADER_BITS = 96
HASH_EXTRA_BITS = 64


@dataclass
class Header:
    mode: str
    block_size: int
    payload_bits: int
    has_hash: bool
    crc32: int = 0
    sha256_prefix: int = 0

    @property
    def size_bits(self) -> int:
        return BASE_HEADER_BITS + (HASH_EXTRA_BITS if self.has_hash else 0)

    def to_bits(self) -> str:
        parts = [
            format(MAGIC, "016b"),
            format(VERSION, "04b"),
            format(MODE_IDS[self.mode], "04b"),
            format(self.block_size, "04b"),
            format(1 if self.has_hash else 0, "01b"),
            format(0, "03b"),  # reserved
            format(self.payload_bits, "032b"),
            format(self.crc32, "032b"),
        ]
        if self.has_hash:
            parts.append(format(self.sha256_prefix, "064b"))
        return "".join(parts)


def build_header(
    mode: str,
    block_size: int,
    payload_bits_str: str,
    has_hash: bool,
) -> Header:
    """Create a header and fill in crc32 and (optionally) sha256_prefix."""
    if mode not in MODE_IDS:
        raise ValueError(f"unknown mode: {mode}")
    if block_size not in (1, 2, 4):
        raise ValueError(f"unsupported block_size: {block_size}")

    header = Header(
        mode=mode,
        block_size=block_size,
        payload_bits=len(payload_bits_str),
        has_hash=has_hash,
    )

    # CRC over header with crc=0 and hash=0, concatenated with payload.
    clean = replace(header, crc32=0, sha256_prefix=0)
    combined = clean.to_bits() + payload_bits_str
    header.crc32 = zlib.crc32(_bits_to_bytes(combined)) & 0xFFFFFFFF

    if has_hash:
        # Hash over header with crc filled in and hash still zero.
        clean = replace(header, sha256_prefix=0)
        combined = clean.to_bits() + payload_bits_str
        digest = hashlib.sha256(_bits_to_bytes(combined)).digest()
        header.sha256_prefix = int.from_bytes(digest[:8], "big")

    return header


def parse_header(bits: str) -> tuple[Header, int]:
    """Parse a header from the start of bits.

    Returns (header, consumed_bits). Raises ValueError on invalid input.
    """
    if len(bits) < BASE_HEADER_BITS:
        raise ValueError(
            f"bit stream too short for header "
            f"(need at least {BASE_HEADER_BITS} bits, got {len(bits)})"
        )

    pos = 0

    def take(n: int) -> int:
        nonlocal pos
        # Defensive: all take() calls are preceded by a length check,
        # but if a future field is added without one, this will fail
        # loudly instead of silently reading garbage.
        if pos + n > len(bits):
            raise ValueError(
                f"bit stream too short: need {pos + n} bits, got {len(bits)}"
            )
        value = int(bits[pos:pos + n], 2)
        pos += n
        return value

    magic = take(16)
    if magic != MAGIC:
        raise ValueError(
            f"bad magic: 0x{magic:04X}, expected 0x{MAGIC:04X} "
            "(wrong base or not a voxpolymachina string?)"
        )

    version = take(4)
    if version != VERSION:
        raise ValueError(f"unsupported version: {version}")

    mode_id = take(4)
    if mode_id not in MODE_NAMES:
        raise ValueError(f"unknown mode id: {mode_id}")
    mode = MODE_NAMES[mode_id]

    block_size = take(4)
    if block_size not in (1, 2, 4):
        raise ValueError(f"unsupported block_size: {block_size}")

    has_hash = take(1) == 1

    # Now that has_hash is known, check the full required size.
    required = BASE_HEADER_BITS + (HASH_EXTRA_BITS if has_hash else 0)
    if len(bits) < required:
        raise ValueError(
            f"bit stream too short for header with has_hash={has_hash} "
            f"(need {required} bits, got {len(bits)})"
        )

    reserved = take(3)
    if reserved != 0:
        raise ValueError(
            f"reserved bits must be zero, got {reserved} "
            "(stream was produced by a newer, unsupported format?)"
        )

    payload_bits = take(32)
    crc32 = take(32)
    sha256_prefix = take(64) if has_hash else 0

    header = Header(
        mode=mode,
        block_size=block_size,
        payload_bits=payload_bits,
        has_hash=has_hash,
        crc32=crc32,
        sha256_prefix=sha256_prefix,
    )
    return header, pos


def verify_header(header: Header, payload_bits_str: str) -> None:
    """Raise ValueError if crc32 or sha256_prefix does not match.

    The header is treated as immutable; all work is done on copies.
    """
    clean = replace(header, crc32=0, sha256_prefix=0)
    combined = clean.to_bits() + payload_bits_str
    expected_crc = zlib.crc32(_bits_to_bytes(combined)) & 0xFFFFFFFF
    if expected_crc != header.crc32:
        raise ValueError(
            f"CRC mismatch: got 0x{header.crc32:08X}, "
            f"expected 0x{expected_crc:08X}"
        )

    if header.has_hash:
        clean = replace(header, sha256_prefix=0)
        combined = clean.to_bits() + payload_bits_str
        digest = hashlib.sha256(_bits_to_bytes(combined)).digest()
        expected_hash = int.from_bytes(digest[:8], "big")
        if expected_hash != header.sha256_prefix:
            raise ValueError(
                f"hash mismatch: got 0x{header.sha256_prefix:016X}, "
                f"expected 0x{expected_hash:016X}"
            )


def _bits_to_bytes(bits: str) -> bytes:
    """Pack a bit string into bytes, padding with zeros on the right."""
    pad = (-len(bits)) % 8
    padded = bits + "0" * pad
    return int(padded, 2).to_bytes(len(padded) // 8, "big")