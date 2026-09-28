"""Post-processing effects on float sample lists.

Each effect is a pure function: samples in [-1, +1] go in, samples of
the same length come out. Effects are chained left to right.

Effects are applied after the preamble and payload are concatenated,
before WAV export. Some effects are destructive: they distort the
signal enough that the decoder no longer recovers the payload. Styles
that use destructive effects are marked decodable=False.
"""
from __future__ import annotations

import math

EFFECT_NAMES = (
    "soft_clip",
    "hard_clip",
    "bitcrush",
    "tremolo",
    "ring_mod",
    "chorus",
    "reverb",
    "lowpass",
)


def soft_clip(
    samples: list[float],
    sample_rate: int,
    drive: float = 3.0,
) -> list[float]:
    """tanh saturation. drive>1 pushes into clipping territory."""
    if drive <= 0:
        raise ValueError(f"drive must be positive, got {drive}")
    norm = math.tanh(drive)
    return [math.tanh(drive * s) / norm for s in samples]


def hard_clip(
    samples: list[float],
    sample_rate: int,
    drive: float = 2.0,
) -> list[float]:
    """Multiply then clip to [-1, +1]."""
    if drive <= 0:
        raise ValueError(f"drive must be positive, got {drive}")
    out = []
    for s in samples:
        v = s * drive
        if v > 1.0:
            v = 1.0
        elif v < -1.0:
            v = -1.0
        out.append(v)
    return out


def bitcrush(
    samples: list[float],
    sample_rate: int,
    bits: int = 6,
) -> list[float]:
    """Quantise to `bits` of amplitude resolution."""
    if not 2 <= bits <= 16:
        raise ValueError(f"bits must be in 2..16, got {bits}")
    levels = 1 << (bits - 1)
    return [round(s * levels) / levels for s in samples]


def tremolo(
    samples: list[float],
    sample_rate: int,
    freq_hz: float = 30.0,
    depth: float = 0.5,
) -> list[float]:
    """Sinusoidal amplitude modulation. depth in [0, 1]."""
    if freq_hz <= 0:
        raise ValueError(f"freq_hz must be positive, got {freq_hz}")
    if not 0.0 <= depth <= 1.0:
        raise ValueError(f"depth must be in [0, 1], got {depth}")
    omega = 2.0 * math.pi * freq_hz / sample_rate
    out = []
    for i, s in enumerate(samples):
        # gain oscillates between (1-depth) and 1
        gain = 1.0 - depth * (0.5 + 0.5 * math.sin(omega * i))
        out.append(s * gain)
    return out


def ring_mod(
    samples: list[float],
    sample_rate: int,
    freq_hz: float = 60.0,
    depth: float = 0.7,
) -> list[float]:
    """Multiply by a low-frequency carrier. depth=1 is true ring mod.

    Blends original and modulated: output = s * ((1-depth) + depth*carrier).
    At depth=1 the original is gone and the result is inharmonic; at
    depth<1 the original is still audible underneath.
    """
    if freq_hz <= 0:
        raise ValueError(f"freq_hz must be positive, got {freq_hz}")
    if not 0.0 <= depth <= 1.0:
        raise ValueError(f"depth must be in [0, 1], got {depth}")
    omega = 2.0 * math.pi * freq_hz / sample_rate
    out = []
    for i, s in enumerate(samples):
        carrier = math.sin(omega * i)
        out.append(s * ((1.0 - depth) + depth * carrier))
    return out


def chorus(
    samples: list[float],
    sample_rate: int,
    depth_ms: float = 6.0,
    rate_hz: float = 0.5,
    mix: float = 0.5,
) -> list[float]:
    """Delayed copy with modulating delay time. mix in [0, 1]."""
    if depth_ms <= 0:
        raise ValueError(f"depth_ms must be positive, got {depth_ms}")
    if not 0.0 <= mix <= 1.0:
        raise ValueError(f"mix must be in [0, 1], got {mix}")
    max_delay = int(sample_rate * depth_ms / 1000.0)
    if max_delay <= 0:
        return list(samples)
    omega = 2.0 * math.pi * rate_hz / sample_rate
    out = list(samples)
    for i in range(max_delay, len(samples)):
        d = int(max_delay * (0.5 + 0.5 * math.sin(omega * i)))
        if d == 0:
            continue
        out[i] += mix * samples[i - d]
    return out


def reverb(
    samples: list[float],
    sample_rate: int,
    decay_ms: float = 80.0,
    mix: float = 0.3,
) -> list[float]:
    """Simple feedback comb filter. One delay, exponential decay.

    Not a real room simulation, but enough to add a sense of space.
    A proper Schroeder reverb would use multiple delay lines; that is
    out of scope for v0.4.
    """
    if decay_ms <= 0:
        raise ValueError(f"decay_ms must be positive, got {decay_ms}")
    if not 0.0 <= mix <= 1.0:
        raise ValueError(f"mix must be in [0, 1], got {mix}")
    delay = int(sample_rate * decay_ms / 1000.0)
    if delay <= 0:
        return list(samples)
    out = list(samples)
    for i in range(delay, len(out)):
        out[i] += mix * out[i - delay]
    return out


def lowpass(
    samples: list[float],
    sample_rate: int,
    cutoff_hz: float = 1000.0,
) -> list[float]:
    """One-pole RC lowpass. Attenuates everything above cutoff."""
    if cutoff_hz <= 0:
        raise ValueError(f"cutoff_hz must be positive, got {cutoff_hz}")
    rc = 1.0 / (2.0 * math.pi * cutoff_hz)
    dt = 1.0 / sample_rate
    alpha = dt / (rc + dt)
    out = []
    prev = 0.0
    for s in samples:
        prev = prev + alpha * (s - prev)
        out.append(prev)
    return out


_EFFECT_FNS = {
    "soft_clip": soft_clip,
    "hard_clip": hard_clip,
    "bitcrush": bitcrush,
    "tremolo": tremolo,
    "ring_mod": ring_mod,
    "chorus": chorus,
    "reverb": reverb,
    "lowpass": lowpass,
}


def apply_effects(
    samples: list[float],
    sample_rate: int,
    effects: list[str],
) -> list[float]:
    """Apply effects in order. Names must be in EFFECT_NAMES."""
    if not effects:
        return list(samples)
    out = list(samples)
    for name in effects:
        if name not in _EFFECT_FNS:
            raise ValueError(
                f"unknown effect {name!r}; "
                f"expected one of {', '.join(EFFECT_NAMES)}"
            )
        out = _EFFECT_FNS[name](out, sample_rate)
    return out