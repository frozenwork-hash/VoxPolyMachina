"""Signal primitives: waveform generation, silence, fades, concatenation.

Pure math on float sample lists in [-1, +1]. No knowledge of WAV, base,
or MFSK — those live in higher layers.
"""
from __future__ import annotations

import math
from collections.abc import Iterable

WAVEFORMS = ("sine", "square", "sawtooth", "triangle")


def _sine(phase: float) -> float:
    return math.sin(phase)


def _square(phase: float) -> float:
    return 1.0 if math.sin(phase) >= 0.0 else -1.0


def _sawtooth(phase: float) -> float:
    t = (phase / (2.0 * math.pi)) % 1.0
    return 2.0 * t - 1.0


def _triangle(phase: float) -> float:
    t = (phase / (2.0 * math.pi)) % 1.0
    return 4.0 * abs(t - 0.5) - 1.0


_WAVEFORM_FNS = {
    "sine": _sine,
    "square": _square,
    "sawtooth": _sawtooth,
    "triangle": _triangle,
}


def generate_wave(
    freq_hz: float,
    duration_s: float,
    sample_rate: int,
    waveform: str = "sine",
    amplitude: float = 0.6,
) -> list[float]:
    """One channel of samples in [-amplitude, +amplitude].

    Phase starts at 0 for every waveform so concatenating blocks of the
    same frequency produces a continuous signal. Square, sawtooth and
    triangle are harmonically rich; use them only for small bases, see
    the warning in fsk.FSKParams.
    """
    if waveform not in _WAVEFORM_FNS:
        raise ValueError(
            f"unknown waveform {waveform!r}; "
            f"expected one of {', '.join(WAVEFORMS)}"
        )
    n = int(round(duration_s * sample_rate))
    if n <= 0:
        return []
    omega = 2.0 * math.pi * freq_hz / sample_rate
    fn = _WAVEFORM_FNS[waveform]
    return [amplitude * fn(omega * i) for i in range(n)]


def sine_wave(
    freq_hz: float,
    duration_s: float,
    sample_rate: int,
    amplitude: float = 0.6,
) -> list[float]:
    """Backwards-compatible sine generator."""
    return generate_wave(freq_hz, duration_s, sample_rate, "sine", amplitude)


def silence(duration_s: float, sample_rate: int) -> list[float]:
    """Return a block of zeros."""
    n = int(round(duration_s * sample_rate))
    return [0.0] * max(n, 0)


def apply_fade(
    samples: list[float],
    sample_rate: int,
    fade_ms: float,
) -> list[float]:
    """Linear fade-in/out at both ends. Returns a new list."""
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