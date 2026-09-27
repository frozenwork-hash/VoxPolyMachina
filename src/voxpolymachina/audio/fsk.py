"""MFSK: base-N symbols <-> audio samples.

A symbol is a fixed-duration tone. Symbol value v in [0, base) maps to
one of `base` frequencies evenly spaced between f_min and f_max.
Modulation is per-symbol sine with a short fade. Demodulation uses the
Goertzel algorithm on each symbol window — a single-frequency DFT bin,
much cheaper than a full FFT when only `base` frequencies matter.

The module knows nothing about WAV or text layers. It operates on
samples as list[float] in [-amplitude, +amplitude].
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ..basecodec import ALPHABET
from .tones import apply_fade, concat, sine_wave


@dataclass
class FSKParams:
    base: int
    symbol_ms: float
    sample_rate: int
    f_min: float | None = None
    f_max: float | None = None
    frequencies_hz: list[float] | None = None
    amplitude: float = 0.6
    fade_ms: float = 5.0

    def __post_init__(self) -> None:
        if not 2 <= self.base <= 36:
            raise ValueError(f"base must be in 2..36, got {self.base}")
        if self.symbol_ms <= 0:
            raise ValueError(f"symbol_ms must be positive, got {self.symbol_ms}")
        if self.sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {self.sample_rate}")
        if not 0.0 < self.amplitude <= 1.0:
            raise ValueError(f"amplitude must be in (0, 1], got {self.amplitude}")
        if self.fade_ms < 0:
            raise ValueError(f"fade_ms must be >= 0, got {self.fade_ms}")

        nyquist = self.sample_rate / 2.0

        if self.frequencies_hz is not None:
            if self.f_min is not None or self.f_max is not None:
                raise ValueError(
                    "pass either frequencies_hz or f_min/f_max, not both"
                )
            freqs = list(self.frequencies_hz)
            if len(freqs) != self.base:
                raise ValueError(
                    f"frequencies_hz has {len(freqs)} entries, "
                    f"expected exactly {self.base} (one per symbol)"
                )
            seen: set[float] = set()
            for f in freqs:
                if f <= 0:
                    raise ValueError(f"frequencies must be positive, got {f}")
                if f >= nyquist:
                    raise ValueError(
                        f"frequency {f} Hz violates Nyquist "
                        f"(sample_rate={self.sample_rate}, limit={nyquist} Hz)"
                    )
                if f in seen:
                    raise ValueError(f"duplicate frequency: {f}")
                seen.add(f)
        else:
            if self.f_min is None or self.f_max is None:
                raise ValueError(
                    "either frequencies_hz or both f_min and f_max are required"
                )
            if self.f_min <= 0:
                raise ValueError(f"f_min must be positive, got {self.f_min}")
            if self.f_max <= self.f_min:
                raise ValueError(
                    f"f_max must be > f_min, "
                    f"got f_min={self.f_min}, f_max={self.f_max}"
                )
            if self.f_max >= nyquist:
                raise ValueError(
                    f"f_max={self.f_max} Hz violates Nyquist "
                    f"(sample_rate={self.sample_rate}, limit={nyquist} Hz)"
                )

    def frequencies(self) -> list[float]:
        """Return the frequency grid, length == base."""
        if self.frequencies_hz is not None:
            return list(self.frequencies_hz)
        assert self.f_min is not None and self.f_max is not None
        step = (self.f_max - self.f_min) / (self.base - 1)
        return [self.f_min + i * step for i in range(self.base)]

    @property
    def symbol_samples(self) -> int:
        return int(round(self.sample_rate * self.symbol_ms / 1000.0))


def _digit_value(ch: str, base: int) -> int:
    idx = ALPHABET.find(ch)
    if idx < 0 or idx >= base:
        raise ValueError(f"character {ch!r} is not a valid base-{base} digit")
    return idx


def symbols_to_samples(symbols: str, params: FSKParams) -> list[float]:
    """Modulate a base-N string into audio samples."""
    freqs = params.frequencies()
    duration_s = params.symbol_ms / 1000.0
    blocks: list[list[float]] = []
    for ch in symbols:
        v = _digit_value(ch, params.base)
        block = sine_wave(
            freqs[v], duration_s, params.sample_rate, params.amplitude
        )
        block = apply_fade(block, params.sample_rate, params.fade_ms)
        blocks.append(block)
    return concat(blocks)


def _goertzel_power(
    samples: list[float], freq_hz: float, sample_rate: int
) -> float:
    """Power of `samples` at a single arbitrary frequency.

    General Goertzel form, valid for frequencies that do not line up
    with FFT bins. O(n) per call, one cos() per call.
    """
    if not samples:
        return 0.0
    omega = 2.0 * math.pi * freq_hz / sample_rate
    coeff = 2.0 * math.cos(omega)
    s_prev = 0.0
    s_prev2 = 0.0
    for x in samples:
        s = x + coeff * s_prev - s_prev2
        s_prev2 = s_prev
        s_prev = s
    return s_prev * s_prev + s_prev2 * s_prev2 - coeff * s_prev * s_prev2


def samples_to_symbols(
    samples: list[float],
    n_symbols: int,
    params: FSKParams,
) -> str:
    """Demodulate exactly n_symbols symbols from samples[0:].

    Caller is responsible for aligning samples[0] to the first symbol
    boundary (see preamble.find_preamble).
    """
    if n_symbols < 0:
        raise ValueError(f"n_symbols must be >= 0, got {n_symbols}")
    n_per = params.symbol_samples
    if n_per <= 0:
        raise ValueError(
            "symbol_samples is zero; check symbol_ms and sample_rate"
        )
    needed = n_symbols * n_per
    if len(samples) < needed:
        raise ValueError(
            f"need {needed} samples for {n_symbols} symbols, "
            f"got {len(samples)}"
        )

    freqs = params.frequencies()
    out: list[str] = []
    for i in range(n_symbols):
        block = samples[i * n_per : (i + 1) * n_per]
        best_idx = 0
        best_power = -1.0
        for j, f in enumerate(freqs):
            p = _goertzel_power(block, f, params.sample_rate)
            if p > best_power:
                best_power = p
                best_idx = j
        out.append(ALPHABET[best_idx])
    return "".join(out)