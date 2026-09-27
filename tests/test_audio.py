"""Round-trip and behaviour tests for the audio layer.

These tests are slower than the text-layer ones: each case synthesises
a WAV, scans it with Goertzel, and decodes. Keep the parameter grid
small; move heavy sweeps to a separate slow-marked file if needed.
"""
from __future__ import annotations

import pytest

from voxpolymachina.audio import audio_decode, audio_encode, audio_info
from voxpolymachina.audio.fsk import FSKParams
from voxpolymachina.audio.preamble import PreambleParams


# --- Round-trip ---


@pytest.mark.parametrize("audio_base", [2, 4, 8, 16])
@pytest.mark.parametrize(
    "text",
    [
        "",
        "A",
        "Hello, world",
        "Привет 🌍",
        "a\tb\nc",
    ],
)
def test_audio_roundtrip(tmp_path, audio_base: int, text: str) -> None:
    path = tmp_path / "out.wav"
    audio_encode(text, path, audio_base=audio_base, config=None)
    assert audio_decode(path, audio_base=audio_base, config=None) == text


def test_audio_roundtrip_base36(tmp_path) -> None:
    """Base 36 is a stress case for the frequency grid, test separately."""
    path = tmp_path / "out.wav"
    text = "Привет 🌍"
    audio_encode(text, path, audio_base=36, config=None)
    assert audio_decode(path, audio_base=36, config=None) == text


def test_audio_roundtrip_no_preamble(tmp_path) -> None:
    path = tmp_path / "out.wav"
    text = "no preamble"
    audio_encode(
        text, path, audio_base=4, preamble_mode="none", config=None
    )
    assert audio_decode(path, audio_base=4, config={
        "audio": {"preamble_mode": "none"},
    }) == text


def test_audio_roundtrip_custom_symbol_ms(tmp_path) -> None:
    path = tmp_path / "out.wav"
    text = "custom timing"
    audio_encode(text, path, audio_base=4, symbol_ms=25.0, config=None)
    assert audio_decode(path, audio_base=4, config={
        "audio": {"symbol_ms": 25.0},
    }) == text


def test_audio_roundtrip_custom_sample_rate(tmp_path) -> None:
    path = tmp_path / "out.wav"
    text = "48k"
    audio_encode(text, path, audio_base=4, sample_rate=48000, config=None)
    assert audio_decode(path, audio_base=4, config={
        "audio": {"sample_rate": 48000},
    }) == text


# --- Errors ---


def test_missing_preamble_raises(tmp_path) -> None:
    """Decoding with trill mode on a file encoded without one."""
    path = tmp_path / "out.wav"
    audio_encode("x", path, audio_base=4, preamble_mode="none", config=None)
    with pytest.raises(ValueError, match="preamble not found"):
        audio_decode(path, audio_base=4, config=None)


def test_wrong_audio_base_fails_or_mismatches(tmp_path) -> None:
    """Wrong base must not silently return garbage text."""
    path = tmp_path / "out.wav"
    audio_encode("hello", path, audio_base=4, config=None)
    with pytest.raises(Exception):
        # Base 8 decoder still finds the trill (same frequencies),
        # but the payload is misinterpreted.
        audio_decode(path, audio_base=8, config=None)


# --- FSKParams validation ---


def test_fskparams_rejects_nyquist_violation() -> None:
    with pytest.raises(ValueError, match="Nyquist"):
        FSKParams(
            base=4, f_min=500, f_max=25000, symbol_ms=50, sample_rate=44100
        )


def test_fskparams_rejects_bad_base() -> None:
    with pytest.raises(ValueError, match="base"):
        FSKParams(base=1, f_min=500, f_max=5000, symbol_ms=50, sample_rate=44100)


def test_fskparams_rejects_bad_amplitude() -> None:
    with pytest.raises(ValueError, match="amplitude"):
        FSKParams(
            base=4, f_min=500, f_max=5000, symbol_ms=50,
            sample_rate=44100, amplitude=1.5,
        )


def test_fskparams_frequency_grid() -> None:
    p = FSKParams(
        base=4, f_min=500, f_max=7500, symbol_ms=50, sample_rate=44100
    )
    freqs = p.frequencies()
    assert len(freqs) == 4
    assert freqs[0] == 500
    assert freqs[-1] == 7500


def test_preambleparams_rejects_same_frequencies() -> None:
    with pytest.raises(ValueError, match="must differ"):
        PreambleParams(
            f_a=1000, f_b=1000, symbol_ms=50, repeats=6, sample_rate=44100
        )


# --- audio_info ---


def test_audio_info_returns_expected_fields(tmp_path) -> None:
    path = tmp_path / "out.wav"
    audio_encode("info", path, audio_base=4, config=None)
    info = audio_info(path, config=None)
    assert info["sample_rate"] == 44100
    assert info["channels"] == 1
    assert info["sample_width"] == 2
    assert info["preamble_mode"] == "trill"
    assert isinstance(info["preamble_offset"], int)
    assert info["preamble_offset"] > 0
    assert info["duration_s"] > 0