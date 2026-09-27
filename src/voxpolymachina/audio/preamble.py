"""Preamble: a trill for synchronisation and coarse calibration.

A trill is an alternating sequence of two tones, f_a and f_b, repeated
`repeats` times. The decoder slides a two-frequency Goertzel detector
over the incoming samples and looks for a run where f_a and f_b
alternate with the expected symbol period. The sample index right after
the last tone is the start of the payload.

v1 scope: only "trill" and "none" modes. "custom" and "both" are
reserved for later; the config keys exist but are not implemented.
"""
from __future__ import annotations

from dataclasses import dataclass

from .fsk import FSKParams, _goertzel_power
from .tones import apply_fade, concat, sine_wave


@dataclass
class PreambleParams:
    f_a: float
    f_b: float
    symbol_ms: float
    repeats: int
    sample_rate: int
    amplitude: float = 0.6
    fade_ms: float = 5.0

    def __post_init__(self) -> None:
        if self.f_a <= 0 or self.f_b <= 0:
            raise ValueError("preamble frequencies must be positive")
        if self.f_a == self.f_b:
            raise ValueError("preamble f_a and f_b must differ")
        if self.repeats < 1:
            raise ValueError(f"repeats must be >= 1, got {self.repeats}")
        if self.symbol_ms <= 0:
            raise ValueError(f"symbol_ms must be positive, got {self.symbol_ms}")
        nyquist = self.sample_rate / 2.0
        for f in (self.f_a, self.f_b):
            if f >= nyquist:
                raise ValueError(
                    f"preamble frequency {f} Hz violates Nyquist "
                    f"(limit {nyquist} Hz)"
                )

    @property
    def symbol_samples(self) -> int:
        return int(round(self.sample_rate * self.symbol_ms / 1000.0))

    @property
    def total_samples(self) -> int:
        return 2 * self.repeats * self.symbol_samples


def build_trill(params: PreambleParams) -> list[float]:
    """Return the preamble sample block: a-b-a-b-... , `repeats` pairs."""
    duration_s = params.symbol_ms / 1000.0
    blocks: list[list[float]] = []
    for _ in range(params.repeats):
        for f in (params.f_a, params.f_b):
            block = sine_wave(f, duration_s, params.sample_rate, params.amplitude)
            block = apply_fade(block, params.sample_rate, params.fade_ms)
            blocks.append(block)
    return concat(blocks)


def _window_score(
    samples: list[float],
    start: int,
    params: PreambleParams,
    expected: list[str],
) -> float:
    """Normalised score in [-N, +N], where N = len(expected).

    Each window contributes (p_expected - p_other) / (p_expected + p_other),
    which lies in [-1, +1]. Amplitude-independent, so a fixed threshold
    is meaningful across signal levels. Silence contributes 0.

    A perfect trill scores close to +N. A random payload scores a few at
    most — it matches some windows by chance but pays for the others.
    """
    n_per = params.symbol_samples
    score = 0.0
    for i, want in enumerate(expected):
        lo = start + i * n_per
        hi = lo + n_per
        if hi > len(samples):
            return float("-inf")
        block = samples[lo:hi]
        pa = _goertzel_power(block, params.f_a, params.sample_rate)
        pb = _goertzel_power(block, params.f_b, params.sample_rate)
        denom = pa + pb
        if denom <= 1e-12:
            continue
        if want == "a":
            score += (pa - pb) / denom
        else:
            score += (pb - pa) / denom
    return score


def find_preamble(
    samples: list[float],
    params: PreambleParams,
) -> int | None:
    """Return the sample index right after the preamble, or None.

    The score function is nearly flat within ±n_per/4 of the true start:
    inside a single tone, Goertzel power is phase-invariant, so sliding
    the window by a few hundred samples changes nothing. The argmax
    within that plateau is essentially arbitrary. We deliberately bias
    left by n_per/8, well inside the plateau, so the decoder sees a
    window whose majority is still the first payload symbol.
    """
    n_per = params.symbol_samples
    if n_per <= 0:
        return None
    total = params.total_samples
    if len(samples) < total:
        return None

    expected = ["a" if i % 2 == 0 else "b" for i in range(2 * params.repeats)]
    last_start = len(samples) - total
    step = max(1, n_per // 4)

    best_start = 0
    best_score = float("-inf")
    for start in range(0, last_start + 1, step):
        s = _window_score(samples, start, params, expected)
        if s > best_score:
            best_score = s
            best_start = start

    lo = max(0, best_start - step)
    hi = min(last_start, best_start + step)
    for r in range(lo, hi + 1):
        s = _window_score(samples, r, params, expected)
        if s > best_score:
            best_score = s
            best_start = r

    n_expected = len(expected)
    if best_score < 0.75 * n_expected:
        return None

    safety = n_per // 8
    idx = best_start + total - safety
    if idx < 0:
        idx = 0
    return idx


def preamble_params_from_fsk(
    fsk: FSKParams,
    repeats: int,
    mode: str = "trill",
) -> PreambleParams | None:
    """Build preamble params consistent with an FSKParams setup.

    Returns None when mode == "none". Raises ValueError for modes that
    are declared in the config but not implemented in v1.
    """
    if mode == "none":
        return None
    if mode == "trill":
        freqs = fsk.frequencies()
        return PreambleParams(
            f_a=freqs[0],
            f_b=freqs[-1],
            symbol_ms=fsk.symbol_ms,
            repeats=repeats,
            sample_rate=fsk.sample_rate,
            amplitude=fsk.amplitude,
            fade_ms=fsk.fade_ms,
        )
    raise ValueError(
        f"preamble mode {mode!r} is not implemented in v1 "
        "(only 'trill' and 'none')"
    )