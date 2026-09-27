"""Signal primitives: sine generation, silence, fades, concatenation.

Pure math on float sample lists in [-1, +1]. No knowledge of WAV, base,
or MFSK — those live in higher layers.
"""
from __future__ import annotations

import math
from collections.abc import Iterable


def sine_wave(
    freq_hz: float,
    duration_s: float,
    sample_rate: int,
    amplitude: float = 0.6,
) -> list[float]:
    """Return one channel of samples in [-amplitude, +amplitude].

    Phase starts at 0, so concatenating blocks of the same frequency
    produces a continuous wave.
    """
    n = int(round(duration_s * sample_rate))
    if n <= 0:
        return []
    omega = 2.0 * math.pi * freq_hz / sample_rate
    return [amplitude * math.sin(omega * i) for i in range(n)]


def silence(duration_s: float, sample_rate: int) -> list[float]:
    """Return a block of zeros."""
    n = int(round(duration_s * sample_rate))
    return [0.0] * max(n, 0)


def apply_fade(
    samples: list[float],
    sample_rate: int,
    fade_ms: float,
) -> list[float]:
    """Linear fade-in/out at both ends. Returns a new list.

    The fade length is clipped to half the block so short blocks are
    still faded without overlap.
    """
    if fade_ms <= 0 or not samples:
        return list(samples)

    n_fade = int(round(sample_rate * fade_ms / 1000.0))
    n = len(samples)
    n_fade = min(n_fade, n // 2)

    if n_fade <= 0:
        return list(samples)

    out = list(samples)
    for i in range(n_fade):
        g = i / n_fade
        out[i] *= g
        out[n - 1 - i] *= g
    return out


def concat(blocks: Iterable[list[float]]) -> list[float]:
    """Concatenate sample blocks into one stream."""
    out: list[float] = []
    for b in blocks:
        out.extend(b)
    return out