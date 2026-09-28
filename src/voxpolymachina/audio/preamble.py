"""Preamble: a trill for synchronisation and coarse calibration.

A trill is an alternating sequence of two tones, f_a and f_b, repeated
`repeats` times, followed by a short silence gap. The decoder slides a
two-frequency Goertzel detector over the incoming samples and looks for
a run where f_a and f_b alternate with the expected symbol period, and
where the samples right after the run are silent. The silence check
breaks the ambiguity caused by the trill's period-2 structure: a shift
by an even number of symbols matches the trill but not the silence.

The sample index right after the silence gap is the start of the
payload.

v1 scope: only "trill" and "none" modes. "custom" and "both" are
reserved for later; the config keys exist but are not implemented.
"""
from __future__ import annotations

from dataclasses import dataclass

from .fsk import FSKParams, _goertzel_power
from .tones import apply_fade, concat, generate_wave, silence


@dataclass
class PreambleParams:
    f_a: float
    f_b: float
    symbol_ms: float
    repeats: int
    sample_rate: int
    amplitude: float = 0.6
    fade_ms: float = 5.0
    silence_ms: float = 100.0
    waveform: str = "sine"

    def __post_init__(self) -> None:
        if self.f_a <= 0 or self.f_b <= 0:
            raise ValueError("preamble frequencies must be positive")
        if self.f_a == self.f_b:
            raise ValueError("preamble f_a and f_b must differ")
        if self.repeats < 1:
            raise ValueError(f"repeats must be >= 1, got {self.repeats}")
        if self.symbol_ms <= 0:
            raise ValueError(f"symbol_ms must be positive, got {self.symbol_ms}")
        if self.silence_ms < 0:
            raise ValueError(f"silence_ms must be >= 0, got {self.silence_ms}")
        if self.sample_rate <= 0:
            raise ValueError(
                f"sample_rate must be positive, got {self.sample_rate}"
            )
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
    def silence_samples(self) -> int:
        return int(round(self.sample_rate * self.silence_ms / 1000.0))

    @property
    def total_samples(self) -> int:
        return 2 * self.repeats * self.symbol_samples + self.silence_samples


def build_trill(params: PreambleParams) -> list[float]:
    """Return the preamble block: trill (a-b-a-b-...) then silence."""
    duration_s = params.symbol_ms / 1000.0
    blocks: list[list[float]] = []
    for _ in range(params.repeats):
        for f in (params.f_a, params.f_b):
            block = generate_wave(
                f,
                duration_s,
                params.sample_rate,
                params.waveform,
                params.amplitude,
            )
            block = apply_fade(block, params.sample_rate, params.fade_ms)
            blocks.append(block)
    if params.silence_ms > 0:
        blocks.append(
            silence(params.silence_ms / 1000.0, params.sample_rate)
        )
    return concat(blocks)


def _window_score(
    samples: list[float],
    start: int,
    params: PreambleParams,
    expected: list[str],
) -> float:
    """Normalised score in [-N, +N], N = len(expected).

    Each trill window contributes (p_expected - p_other) / (p_expected
    + p_other), in [-1, +1]. Then a silence check adds a large negative
    penalty if the gap after the trill is not silent. The penalty is
    what breaks the trill's period-2 ambiguity.
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

    silence_samples = params.silence_samples
    if silence_samples > 0:
        s_lo = start + len(expected) * n_per
        s_hi = s_lo + silence_samples
        if s_hi > len(samples):
            return float("-inf")
        s_block = samples[s_lo:s_hi]
        peak = max(abs(x) for x in s_block)
        # After peak normalisation, a real trill is around 0.6 in
        # amplitude; silence in a real recording is < 0.05. Penalise
        # loudly if the gap is not actually silent.
        if peak > 0.1:
            score -= 2.0 * len(expected)

    return score


def find_preamble(
    samples: list[float],
    params: PreambleParams,
) -> int | None:
    """Return the sample index right after the preamble, or None.

    Strategy: coarse scan on a step of symbol_samples // 4, refine the
    best candidate within one step, then require the score to exceed
    half of the maximum possible. The silence gap in the preamble makes
    the argmax unambiguous, so no walk-left is needed.
    """
    n_per = params.symbol_samples
    if n_per <= 0:
        return None
    total = params.total_samples
    if len(samples) < total:
        return None

    expected = [
        "a" if i % 2 == 0 else "b" for i in range(2 * params.repeats)
    ]
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
        if s > best_score + 1e-3:
            best_score = s
            best_start = r

    n_expected = len(expected)
    if best_score < 0.5 * n_expected:
        return None

    # Return just after the silence gap. The payload starts there.
    return best_start + total


def find_preamble_debug(
    samples: list[float],
    params: PreambleParams,
) -> dict:
    """Same scan as find_preamble but returns diagnostics.

    Used to see why detection failed on a real recording.
    """
    n_per = params.symbol_samples
    total = params.total_samples
    expected = [
        "a" if i % 2 == 0 else "b" for i in range(2 * params.repeats)
    ]

    out: dict = {
        "n_samples": len(samples),
        "n_per": n_per,
        "total_preamble": total,
        "peak": max(abs(s) for s in samples) if samples else 0.0,
        "rms": (
            (sum(s * s for s in samples) / len(samples)) ** 0.5
            if samples
            else 0.0
        ),
        "threshold": 0.5 * len(expected),
    }

    if n_per <= 0 or len(samples) < total:
        out["verdict"] = "not enough samples"
        return out

    last_start = len(samples) - total
    step = max(1, n_per // 4)

    candidates: list[tuple[int, float]] = []
    for start in range(0, last_start + 1, step):
        s = _window_score(samples, start, params, expected)
        candidates.append((start, s))

    if not candidates:
        out["verdict"] = "no candidates"
        return out

    candidates.sort(key=lambda x: x[1], reverse=True)
    out["top5"] = [
        {
            "start": st,
            "score": round(sc, 3),
            "sec": round(st / params.sample_rate, 3),
        }
        for st, sc in candidates[:5]
    ]
    best_start, best_score = candidates[0]
    out["best_score"] = round(best_score, 3)
    out["best_start"] = best_start
    out["best_sec"] = round(best_start / params.sample_rate, 3)
    out["verdict"] = (
        "would pass"
        if best_score >= out["threshold"]
        else "below threshold"
    )
    return out


def preamble_params_from_fsk(
    fsk: FSKParams,
    repeats: int,
    mode: str = "trill",
) -> PreambleParams | None:
    """Build preamble params consistent with an FSKParams setup."""
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
            waveform=fsk.waveform,
        )
    raise ValueError(
        f"preamble mode {mode!r} is not implemented in v1 "
        "(only 'trill' and 'none')"
    )