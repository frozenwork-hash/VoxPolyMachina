"""WAV I/O on the standard library `wave` module.

v1 scope: mono, 16-bit PCM. Everything else raises ValueError. No
external dependencies, no soundfile, no pydub. If you need FLAC or MP3
later, add a separate module; this one stays small.
"""
from __future__ import annotations

import array
import sys
import wave
from pathlib import Path

INT16_MAX = 32767
INT16_MIN = -32768


def write_wav(
    path: str | Path,
    samples: list[float],
    sample_rate: int,
    amplitude: float = 1.0,
) -> None:
    """Write mono 16-bit PCM WAV.

    samples are floats in [-amplitude, +amplitude]. Values outside the
    int16 range are clipped, so a misconfigured amplitude degrades
    gracefully instead of raising on the first out-of-range sample.
    """
    if sample_rate <= 0:
        raise ValueError(f"sample_rate must be positive, got {sample_rate}")
    if not 0.0 < amplitude <= 1.0:
        raise ValueError(f"amplitude must be in (0, 1], got {amplitude}")

    scale = INT16_MAX * amplitude
    ints = array.array("h")
    for s in samples:
        v = int(round(s * INT16_MAX))
        if v > INT16_MAX:
            v = INT16_MAX
        elif v < INT16_MIN:
            v = INT16_MIN
        ints.append(v)

    if sys.byteorder == "big":
        ints.byteswap()

    path = Path(path)
    if path.is_dir():
        raise ValueError(
            f"output path is a directory, need a filename: {path}"
        )
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(ints.tobytes())


def read_wav(path: str | Path) -> tuple[list[float], int]:
    """Read a mono 16-bit PCM WAV.

    Returns (samples in [-1, +1], sample_rate). Raises ValueError for
    anything that is not mono 16-bit PCM — that keeps the rest of the
    pipeline free of format checks.
    """
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"not a file: {path}")
    with wave.open(str(path), "rb") as w:
        if w.getnchannels() != 1:
            raise ValueError(
                f"only mono WAV is supported, got {w.getnchannels()} channels"
            )
        if w.getsampwidth() != 2:
            raise ValueError(
                f"only 16-bit PCM is supported, got {w.getsampwidth() * 8}-bit"
            )
        sample_rate = w.getframerate()
        raw = w.readframes(w.getnframes())

    ints = array.array("h")
    ints.frombytes(raw)
    if sys.byteorder == "big":
        ints.byteswap()

    samples = [v / INT16_MAX for v in ints]
    return samples, sample_rate


def info_wav(path: str | Path) -> dict:
    """Return basic metadata without decoding samples."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"not a file: {path}")
    with wave.open(str(path), "rb") as w:
        n_frames = w.getnframes()
        sample_rate = w.getframerate()
        return {
            "path": str(path),
            "sample_rate": sample_rate,
            "channels": w.getnchannels(),
            "sample_width": w.getsampwidth(),
            "n_frames": n_frames,
            "duration_s": n_frames / sample_rate if sample_rate else 0.0,
        }